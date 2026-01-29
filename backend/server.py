#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FastAPI 后端服务

提供医疗分诊 API 接口:
- POST /start - 启动分诊任务
- GET /status/{task_id} - 查询任务状态
- POST /human-approval - 人工审批
- GET /health - 健康检查

使用 BackgroundTasks 执行 Agent 工作流
"""

import uuid
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.config import settings
from backend.schemas import (
    StartTaskRequest, 
    StartTaskResponse,
    HumanApprovalRequest,
    UpdateTaskNameRequest,
    PatientProfileUpdateRequest,
    TaskResponse,
    TaskStatus,
    HealthResponse,
    TriageResult,
    AgentStep
)
from backend.storage import storage
from backend.memory import patient_memory
from backend.graph import create_medical_triage_app, MedicalTriageState, get_llm
from backend.agents import AgentFactory, AgentResponse
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from backend.observability import trace_task

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from langchain_core.messages import HumanMessage


# ===== 全局变量 =====

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

# LangGraph 应用和检查点 (全局)
pool = None
checkpointer = None
app_graph = None


# ===== 生命周期 =====

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global app_graph, pool, checkpointer
    
    # 启动时初始化
    print("=" * 50)
    print("医疗分诊 API 服务启动")
    print(f"时间: {datetime.now().isoformat()}")
    print(f"模型: {settings.llm_model}")
    print(f"数据库: {settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}")
    print("=" * 50)
    
    # 1. 初始化数据库及 Checkpointer
    # 策略：如果有外部传入的 DATABASE_URL (如 Railway)，则尝试连接；
    # 否则默认使用内存模式，避免在云端因连接 localhost 而导致 502。
    if settings.database_url_env:
        try:
            print(f"检测到数据库配置，尝试连接: {settings.database_url.split('@')[-1]}")
            connection_kwargs = {
                "autocommit": True,
                "prepare_threshold": 0,
            }
            pool = AsyncConnectionPool(
                conninfo=settings.database_url,
                max_size=20,
                kwargs=connection_kwargs,
                open=False
            )
            
            # 尝试短暂连接以验证
            await asyncio.wait_for(pool.open(), timeout=2.0)
            
            checkpointer = AsyncPostgresSaver(pool)
            await asyncio.wait_for(checkpointer.setup(), timeout=3.0)
            print("✅ 数据库 Checkpointer 初始化成功")
        except Exception as e:
            print(f"⚠️ 数据库连接失败, 切换到内存模式: {e}")
            if pool:
                await pool.close()
                pool = None
            checkpointer = MemorySaver()
    else:
        print("ℹ️ 未检测到云端数据库配置，默认启用内存模式")
        checkpointer = MemorySaver()
        print("✅ 内存 Checkpointer 初始化成功")
    
    # 2. 创建 LangGraph 应用
    app_graph = create_medical_triage_app(checkpointer=checkpointer)
    
    yield
    
    # 关闭时清理
    if pool:
        await pool.close()
    print("服务关闭")


# ===== FastAPI 应用 =====

app = FastAPI(
    title="医疗分诊智能体 API",
    description="基于 LangGraph 的多智能体医疗分诊系统",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 请求日志中间件
@app.middleware("http")
async def add_process_time_header(request, call_next):
    print(f"[{datetime.now().isoformat()}] 🛸 收到请求: {request.method} {request.url.path}")
    response = await call_next(request)
    return response


# ===== 后台任务 =====

async def run_triage_task(task_id: str, patient_input: str, patient_id: str = "default_user", patient_info: Optional[Dict] = None, require_approval: bool = True, chat_history: Optional[List[Dict]] = None):
    """
    后台执行分诊任务
    
    Args:
        task_id: 任务ID
        patient_input: 患者描述
        patient_id: 患者ID
        patient_info: 患者信息
        require_approval: 是否需要审核
    """
    try:
        # 更新状态为处理中
        await storage.update_task(task_id, {"status": TaskStatus.COORDINATOR})
        
        # 初始状态
        initial_state = {
            "patient_id": patient_id,
            "patient_input": patient_input,
            "patient_info": patient_info,
            "task_shards": [],
            "shard_results": {},
            "task_plan": [],
            "priority": "",
            "intent": "",
            "require_approval": require_approval,
            "triage_result": None,
            "analysis_report": None,
            "messages": [
                HumanMessage(content=msg["content"]) if msg["role"] == "user" else SystemMessage(content=msg["content"]) if msg["role"] == "system" else AIMessage(content=msg["content"])
                for msg in (chat_history or [])
            ] + [HumanMessage(content=patient_input)],
            "steps": [],
            "current_agent": "coordinator",
            "human_approved": None,
            "reviewer_comment": None,
            "error": None,
            "initial_symptoms": None # 初始锚点将由 coordinator_node 首次运行时锁定
        }
        
        config = {"configurable": {"thread_id": task_id}}
        
        # 运行工作流直到 interrupt
        current_agent = "coordinator"
        
        async for event in app_graph.astream(initial_state, config, stream_mode="updates"):
            # 更新状态
            for node_name, node_output in event.items():
                if isinstance(node_output, dict):
                    current_agent = node_output.get("current_agent", current_agent)
                    
                    # 映射到状态枚举
                    status_map = {
                        "coordinator": TaskStatus.COORDINATOR,
                        "expert_parallel": TaskStatus.EXPERT,
                        "analyst": TaskStatus.ANALYST,
                        "human_reviewer": TaskStatus.WAITING_APPROVAL,
                        "completed": TaskStatus.COMPLETED
                    }
                    
                    status = status_map.get(current_agent, TaskStatus.PENDING)
                    
                    # 记录累计步骤 (防止 expert 并行时互相覆盖)
                    task = await storage.get_task(task_id)
                    existing_steps = task.get("steps", []) if task else []
                    new_steps = node_output.get("steps", [])
                    total_steps = existing_steps + new_steps
                    
                    await storage.update_task(task_id, {
                        "status": status,
                        "current_agent": current_agent,
                        "task_plan": node_output.get("task_plan"),
                        "triage_result": node_output.get("triage_result"),
                        "analysis_report": node_output.get("analysis_report"),
                        "intent": node_output.get("intent"),
                        "steps": total_steps
                    })
        
        # 获取最终状态
        final_state = await app_graph.aget_state(config)
        state_values = final_state.values
        
        # 最终保存并同步意图
        await storage.update_task(task_id, {
            "status": TaskStatus.COMPLETED if state_values.get("current_agent") == "completed" else TaskStatus.WAITING_APPROVAL,
            "triage_result": state_values.get("triage_result"),
            "analysis_report": state_values.get("analysis_report"),
            "intent": state_values.get("intent"),
            "steps": state_values.get("steps", [])
        })
        
        # 如果已完成，更新患者长期记忆
        if state_values.get("current_agent") == "completed" or state_values.get("triage_result"):
            patient_memory.update_profile(
                patient_id=patient_id,
                triage_result=state_values.get("triage_result", {}),
                patient_info=patient_info
            )
        
    except Exception as e:
        # 记录详细错误堆栈
        import traceback
        error_detail = traceback.format_exc()
        print(f"❌ 任务 {task_id} 执行失败:\n{error_detail}")
        
        await storage.update_task(task_id, {
            "status": TaskStatus.FAILED,
            "error": str(e) # 虽然界面只显示摘要，但后台日志有全量堆栈
        })
        traceback.print_exc()


# ===== API 端点 =====

@app.get("/", tags=["系统"])
async def root():
    """根路径，用于 Railway 默认健康检查"""
    return {"message": "医疗分诊 API 正在运行", "status": "healthy"}


@app.get("/health", response_model=HealthResponse, tags=["系统"])
async def health_check():
    """健康检查"""
    print(f"[{datetime.now().isoformat()}] 收到诊断请求")
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.now()
    )


@app.post("/start", response_model=StartTaskResponse, tags=["分诊任务"])
async def start_task(
    request: StartTaskRequest,
    background_tasks: BackgroundTasks
):
    """
    提交患者主诉，系统将自动预读意图。
    - 闲聊意图：直接同步返回回复内容。
    - 分诊意图：异步启动后端工作流并返回任务ID。
    """
    # 1. 极速意图预检 (同步调用 LLM)
    llm = get_llm(temperature=0.7)
    
    # 0. 确定任务 ID (复用现有会话或生成新的)
    task_id = request.task_id or str(uuid.uuid4())
    
    # 获取追踪处理器
    from backend.observability import create_trace_handler
    handler = create_trace_handler(
        session_id=task_id[:12],
        metadata={"mode": "sync_router", "input": request.patient_description}
    )
    
    # 格式化对话历史 (大幅增加窗口，取最近 20 条，解决长对话遗忘)
    history_lines = []
    if request.chat_history:
        for msg in request.chat_history[-20:]:
            role = "用户" if msg["role"] == "user" else "小星球"
            history_lines.append(f"{role}: {msg['content']}")
    history_str = "\n".join(history_lines)
    
    router_prompt = AgentFactory.get_router_prompt(
        patient_input=request.patient_description,
        chat_history=history_str
    )
    
    try:
        router_res = await llm.ainvoke([
            SystemMessage(content="你是一个意图识别专家。"),
            HumanMessage(content=router_prompt)
        ], config={"callbacks": [handler] if handler else []})
        router_data = AgentResponse.parse_router_response(router_res.content)
        intent = router_data.get("intent", "general_chat")
        
        # --- 模式 A: 直接对话模式 ---
        if intent == "general_chat":
            # 即使是闲聊，也要保存到存储中，以便展现历史记录
            task_name = request.patient_description[:15] + "..."
            
            # 由于是闲聊，直接标记为已完成
            # 注意：这里我们使用 update_task 如果是复用，或者 save_task 如果是新建
            existing_task = await storage.get_task(task_id)
            new_messages = request.chat_history + [
                {"role": "user", "content": request.patient_description},
                {"role": "assistant", "content": router_data.get("reply", "你好呀~"), "intent": "general_chat"}
            ]
            
            task_data = {
                "task_id": task_id,
                "status": TaskStatus.COMPLETED,
                "patient_input": f"💬 {task_name}" if not existing_task else existing_task.get("patient_input"),
                "patient_description": request.patient_description,
                "patient_id": request.patient_id,
                "intent": "general_chat",
                "messages": new_messages,
                "updated_at": datetime.now().isoformat()
            }
            
            if existing_task:
                await storage.update_task(task_id, task_data)
            else:
                task_data["created_at"] = datetime.now().isoformat()
                await storage.save_task(task_id, task_data)
            
            return StartTaskResponse(
                task_id=task_id,
                message="对话完成",
                intent="general_chat",
                reply=router_data.get("reply", "你好呀~")
            )
            
    except Exception as e:
        # 如果路由失败，降级到分诊流程
        print(f"路由预检失败: {e}")
        intent = "medical_triage"

    # --- 智能标题生成 (异步后台或快速内联) ---
    # 我们在这里生成一个简短标题，代替冗长的初始主诉
    task_name = request.patient_description[:15] + "..."
    try:
        title_prompt = f"请为以下患者症状描述生成一个极简标题（不超过6个字）：\n{request.patient_description}"
        title_res = await llm.ainvoke([
            SystemMessage(content="你是一个专业的医疗文案助手，擅长总结简短、精准的标题。"),
            HumanMessage(content=title_prompt)
        ])
        task_name = title_res.content.strip().strip('"').replace("标题：", "").replace("标题:", "")
        if len(task_name) > 10:
            task_name = task_name[:9] + "..."
    except Exception as e:
        print(f"生成标题失败: {e}")

    # 保存任务初始状态
    await storage.save_task(task_id, {
        "task_id": task_id,
        "status": TaskStatus.PENDING,
        "patient_input": task_name, # 使用生成的短标题作为显示名称
        "patient_description": request.patient_description, # 保留完整原始主诉
        "original_description": request.patient_description, 
        "patient_id": request.patient_id, 
        "patient_info": request.patient_info,
        "intent": "medical_triage",
        "require_approval": request.require_approval,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "steps": [],
        "triage_result": None,
        "analysis_report": None,
        "human_approved": None,
        "reviewer_comment": None,
        "error": None
    })
    
    # 添加后台任务 (注意：后台任务依然需要使用原始的 patient_description)
    background_tasks.add_task(
        run_triage_task,
        task_id=task_id,
        patient_input=request.patient_description, # 使用原始描述
        patient_id=request.patient_id,
        patient_info=request.patient_info,
        require_approval=request.require_approval,
        chat_history=request.chat_history # 传入历史记录
    )
    
    return StartTaskResponse(
        task_id=task_id,
        message="寻医问诊流程已开启，智慧引擎正在分析中...",
        intent="medical_triage"
    )


@app.get("/status/{task_id}", response_model=TaskResponse, tags=["分诊任务"])
async def get_task_status(task_id: str):
    """
    查询任务状态
    
    返回任务的当前状态、执行步骤、分诊结果等信息。
    """
    task = await storage.get_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
    
    # 转换步骤格式
    steps = []
    for step in task.get("steps", []):
        steps.append(AgentStep(
            agent_name=step.get("agent_name", ""),
            action=step.get("action", ""),
            output=step.get("output"),
            timestamp=datetime.fromisoformat(step.get("timestamp", datetime.now().isoformat())),
            duration_ms=step.get("duration_ms")
        ))
    
    # 转换分诊结果格式
    triage_result = None
    if task.get("triage_result"):
        tr = task["triage_result"]
        triage_result = TriageResult(
            diagnosis_suggestion=tr.get("diagnosis_suggestion", ""),
            department=tr.get("department", []),
            urgency=tr.get("urgency", ""),
            advice=tr.get("advice", "")
        )
    
    return TaskResponse(
        task_id=task["task_id"],
        status=TaskStatus(task.get("status", "pending")),
        created_at=datetime.fromisoformat(task.get("created_at", datetime.now().isoformat())),
        updated_at=datetime.fromisoformat(task.get("updated_at", datetime.now().isoformat())),
        patient_description=task.get("patient_description", ""),
        task_plan=task.get("task_plan"),
        steps=steps,
        triage_result=triage_result,
        analysis_report=task.get("analysis_report"),
        intent=task.get("intent"),
        human_approved=task.get("human_approved"),
        reviewer_comment=task.get("reviewer_comment"),
        error=task.get("error")
    )


@app.post("/human-approval", response_model=TaskResponse, tags=["分诊任务"])
async def submit_human_approval(
    request: HumanApprovalRequest,
    background_tasks: BackgroundTasks
):
    """
    提交人工审批
    
    对等待审批的分诊结果进行确认或拒绝。
    """
    task = await storage.get_task(request.task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail=f"任务不存在: {request.task_id}")
    
    if task.get("status") != TaskStatus.WAITING_APPROVAL:
        raise HTTPException(
            status_code=400, 
            detail=f"任务状态不正确，当前状态: {task.get('status')}"
        )
    
    # 更新审批状态
    await storage.update_task(request.task_id, {
        "human_approved": request.approved,
        "reviewer_comment": request.reviewer_comment,
        "status": TaskStatus.APPROVED if request.approved else TaskStatus.REJECTED
    })
    
    # 恢复工作流
    try:
        config = {"configurable": {"thread_id": request.task_id}}
        
        approval_response = {
            "approved": request.approved,
            "comment": request.reviewer_comment or ""
        }
        
        # 使用 Command 恢复
        resume_command = Command(resume=approval_response)
        
        async for event in app_graph.astream(resume_command, config, stream_mode="updates"):
            for node_name, node_output in event.items():
                if isinstance(node_output, dict):
                    await storage.update_task(request.task_id, {
                        "status": TaskStatus.COMPLETED,
                        "steps": node_output.get("steps", [])
                    })
        
        # 更新最终状态
        await storage.update_task(request.task_id, {
            "status": TaskStatus.COMPLETED
        })
        
    except Exception as e:
        await storage.update_task(request.task_id, {
            "error": str(e)
        })
    
    # 返回更新后的任务
    return await get_task_status(request.task_id)


@app.delete("/tasks/{task_id}", tags=["分诊任务"])
async def delete_task(task_id: str):
    """
    删除任务及其所有历史记录
    """
    task = await storage.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
    
    # 1. 从存储中删除 (Redis/内存)
    await storage.delete_task(task_id)
    
    # 2. 如果配置了 Postgres 检查点，原则上也可以清理这里的内容
    # 但由于 AsyncPostgresSaver 接口限制，删除通常需要直接操作 SQL
    # 这里保持简单，主要依赖存储层的删除
    
    return {"message": "任务已成功删除", "task_id": task_id}


@app.patch("/tasks/{task_id}/name", tags=["分诊任务"])
async def update_task_name(request: UpdateTaskNameRequest):
    """
    更新任务名称 (重命名)
    """
    task = await storage.get_task(request.task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务不存在: {request.task_id}")
    
    await storage.update_task(request.task_id, {"patient_input": request.name})
    return {"message": "名称更新成功", "task_id": request.task_id, "new_name": request.name}


@app.get("/patient/tasks/{patient_id}", tags=["患者"])
async def list_patient_tasks(patient_id: str, limit: int = Query(default=20, le=100)):
    """获取患者的历史对话列表摘要"""
    tasks = await storage.list_tasks_by_patient(patient_id, limit=limit)
    return {"tasks": tasks, "count": len(tasks)}


@app.get("/tasks/{task_id}/messages", tags=["患者"])
async def get_task_messages(task_id: str):
    """从持久化状态中恢复完整聊天记录"""
    config = {"configurable": {"thread_id": task_id}}
    state = await app_graph.aget_state(config)
    
    if not state or not state.values:
        # 如果 LangGraph 状态不存在，回退到 storage 中的基本信息
        task = await storage.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="会话不存在")
        return {"messages": task.get("messages", [])}
        
    # 提取并格式化消息 (包含元数据以便前端恢复 UI)
    raw_messages = state.values.get("messages", [])
    formatted_messages = []
    
    # 尝试从 state 中获取其它任务元数据
    intent = state.values.get("intent", "medical_triage")
    steps = state.values.get("steps", [])
    
    for i, msg in enumerate(raw_messages):
        role = "user" if isinstance(msg, HumanMessage) else "assistant"
        m_data = {
            "role": role,
            "content": msg.content
        }
        
        # 为 assistant 的最后一条回复附带任务元数据 (以此还原分诊卡片)
        if role == "assistant" and i == len(raw_messages) - 1:
            m_data["intent"] = intent
            m_data["steps"] = steps
            # 如果是非 general_chat，尝试补全 task_data 以便显示审批卡片
            if intent != "general_chat":
                m_data["task_data"] = {
                    "task_id": task_id,
                    "status": task.get("status") if 'task' in locals() else state.values.get("status", "completed"),
                    "triage_result": state.values.get("triage_result", {})
                }
        
        formatted_messages.append(m_data)
        
    return {"messages": formatted_messages}


@app.get("/patient/profile/{patient_id}", tags=["患者"])
async def get_patient_profile(patient_id: str):
    """获取患者长期档案"""
    profile = patient_memory.get_profile(patient_id)
    return profile


@app.post("/patient/profile", tags=["患者"])
async def update_patient_profile(request: PatientProfileUpdateRequest):
    """更新患者长期档案"""
    # 模拟 triage_result 为空，因为这只是手动更新档案
    patient_memory.update_profile(
        request.patient_id, 
        triage_result={}, 
        patient_info=request.model_dump()
    )
    return {"message": "档案更新成功", "patient_id": request.patient_id}


@app.get("/patient/search", tags=["患者"])
async def search_patient_profiles(query: str = Query(..., min_length=1, description="搜索关键词(姓名/电话/ID)")):
    """搜索患者档案"""
    results = patient_memory.search_profiles(query)
    return {"results": results, "query": query}


# ===== 启动入口 =====

if __name__ == "__main__":
    import uvicorn
    import os
    
    # 强制从环境变量读取端口，确保与 Railway 绑定一致
    port = int(os.getenv("PORT", 8080))
    host = "0.0.0.0"
    
    print(f"🚀 启动生产级服务器: {host}:{port}")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        proxy_headers=True,
        forwarded_allow_ips="*",
        access_log=True,
        reload=False
    )
