#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LangGraph 多智能体工作流

使用 LangGraph 1.x 构建医疗分诊多智能体系统

架构:
    Coordinator → Domain Expert → Analyst → Human Reviewer → END
                                              ↓
                                          (interrupt)

关键特性:
1. 使用 StateGraph 管理状态
2. 使用 Command 进行状态更新和路由
3. 支持 HITL (Human-in-the-Loop) 中断机制
"""

import json
import re
from typing import Dict, Any, Optional, TypedDict, Literal, Annotated
from datetime import datetime
import operator

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command, Send

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from backend.config import settings
from backend.agents import AgentFactory, AgentResponse
from backend.graph_db import medical_kg
from backend.memory import patient_memory
from backend.observability import get_langfuse_handler


# ===== State 定义 =====

class TaskShard(TypedDict):
    """任务分片"""
    shard_id: str
    task_type: str
    content: str
    status: str
    output: Optional[Dict[str, Any]]


class MedicalTriageState(TypedDict):
    """
    多智能体工作流状态 - Map-Reduce + Memory 版本
    """
    # 输入与身份
    patient_id: str
    patient_input: str
    patient_info: Optional[Dict[str, Any]]
    memory_context: str
    intent: str
    initial_symptoms: Optional[str] # 核心主诉锚点，锁定后不再通过滑动窗口丢失
    
    # Map-Reduce 核心结构
    task_shards: list[TaskShard]
    shard_results: Annotated[dict[str, Any], operator.ior]  # 使用 ior 合并并行结果
    
    # 任务规划
    task_plan: list
    priority: str
    
    # Agent 输出
    triage_result: Optional[Dict[str, Any]]
    analysis_report: Optional[str]
    
    # 消息历史 (使用 add_messages reducer)
    messages: Annotated[list, add_messages]
    
    # 执行步骤记录
    steps: Annotated[list, operator.add]
    
    # 图谱背景知识 (Map-Reduce 过程中的临时共享知识)
    graph_context: Annotated[str, operator.add]
    
    # 控制
    current_agent: str
    require_approval: bool
    human_approved: Optional[bool]
    reviewer_comment: Optional[str]
    
    # 错误
    error: Optional[str]


# ===== LLM 配置 =====

def get_llm(temperature: float = 0.1) -> ChatOpenAI:
    """获取 LLM 实例"""
    print(f"[LLM] 初始化: {settings.llm_model} | Base: {settings.llm_base_url}")
    return ChatOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        temperature=temperature,
        max_tokens=1000,
    )


# ===== Agent 节点函数 =====

def coordinator_node(state: MedicalTriageState):
    """
    Coordinator Agent 节点 (Map + Memory + Intelligent Route)
    """
    # 1. 加载患者长期记忆
    patient_id = state.get("patient_id", "default_user")
    memory_context = patient_memory.get_context_for_agent(patient_id)
    
    # --- 锁定初始主诉 (Context Anchoring) ---
    initial_symptoms = state.get("initial_symptoms")
    if not initial_symptoms:
        initial_symptoms = state["patient_input"]
    
    start_time = datetime.now()
    
    # 2. 调用 LLM 进行并行拆解与路由规划
    # 这里我们扩展 Prompt，让 Coordinator 具备路由意识
    prompt = AgentFactory.get_coordinator_prompt(
        patient_input=state["patient_input"],
        patient_info=state.get("patient_info")
    )
    # 在 2.0 版中，我们显式加入“初始主诉”作为北极星
    prompt = f"【核心关注点（始终不变）】: {initial_symptoms}\n\n{prompt}"
    # 在 Prompt 中注入记忆
    prompt = f"{memory_context}\n\n当前任务：\n{prompt}"
    
    llm = get_llm()
    response = llm.invoke([
        SystemMessage(content="你是温暖、博学的“小星球”，正在帮你的好朋友初步梳理健康问题。请保持自然、真诚的对话语气。"),
        HumanMessage(content=prompt)
    ])
    
    parsed = AgentResponse.parse_coordinator_response(response.content)
    intent = parsed.get("intent", "medical_triage")
    shards = parsed.get("shards", [])
    analysis = parsed.get("analysis", "")
    
    # 记录步骤
    step = {
        "agent_name": "Coordinator (Router)",
        "action": f"意图识别: {intent}",
        "output": analysis[:100] + "...",
        "timestamp": datetime.now().isoformat(),
        "duration_ms": int((datetime.now() - start_time).total_seconds() * 1000)
    }
    
    # --- 智能路由分支 ---
    
    # 分支 A: 一般性对话 (Chat)
    if intent == "general_chat":
        return Command(
            update={
                "intent": intent,
                "analysis_report": analysis,
                "triage_result": {
                    "diagnosis_suggestion": "一般性对话",
                    "department": ["日常咨询"],
                    "urgency": "无建议",
                    "advice": analysis
                },
                "current_agent": "completed",
                "steps": [step],
                "messages": [AIMessage(content=f"[Assistant] {analysis}")]
            },
            goto=END
        )
    
    # 分支 B: 医疗分诊 (Triage)
    if not shards:
        # 兜底：如果没有分片成功，创建一个默认分片
        shards = [{"shard_id": "core", "task_type": "core", "content": "全面分析"}]
        
    expert_calls = [
        Send("expert_node", {
            "patient_id": patient_id,
            "patient_input": state["patient_input"],
            "patient_info": state.get("patient_info"),
            "memory_context": memory_context,
            "initial_symptoms": initial_symptoms,
            "shard": shard
        })
        for shard in shards
    ]
    
    return Command(
        update={
            "patient_id": patient_id,
            "memory_context": memory_context,
            "intent": intent,
            "initial_symptoms": initial_symptoms, # 持久化锚点
            "task_shards": shards,
            "current_agent": "routing",
            "steps": [step],
            "messages": [AIMessage(content=f"[Coordinator] 识别到医疗分诊意图，已拆解 {len(shards)} 个分析分片")]
        },
        goto=expert_calls
    )


def expert_node(shard_state: dict) -> dict:
    """
    Expert Agent 节点 (Parallel Processing + KG-Augmented)
    
    职责: 处理单个任务分片，并利用知识图谱进行事实校验
    """
    start_time = datetime.now()
    shard = shard_state["shard"]
    
    # --- 动态知识匹配 ---
    # 改为从全局症状库中动态提取用户提到的症状
    found_symptoms = medical_kg.extract_symptoms(shard_state["patient_input"])
    graph_context = medical_kg.get_context_for_symptoms(found_symptoms)
    
    # 构建 Prompt
    prompt = AgentFactory.get_expert_prompt(
        patient_input=shard_state["patient_input"],
        shard_content=shard["content"],
        patient_info=shard_state.get("patient_info"),
        graph_context=graph_context
    )
    # 注入记忆与锚点，确保专家不因长对话丢失焦点
    initial_anchor = shard_state.get("initial_symptoms", shard_state["patient_input"])
    prompt = f"【核心北极星（初始主诉）】: {initial_anchor}\n\n{prompt}"
    
    if shard_state.get("memory_context"):
        prompt = f"【患者长期背景】: {shard_state['memory_context']}\n\n{prompt}"
    
    # 调用 LLM
    llm = get_llm()
    response = llm.invoke([
        SystemMessage(content="你是一名专业的医疗专家。请基于知识图谱事實进行深度剖析。"),
        HumanMessage(content=prompt)
    ])
    
    # 解析响应
    expert_output = AgentResponse.parse_expert_response(response.content)
    
    # 计算执行时间
    duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
    
    # 记录步骤
    step = {
        "agent_name": f"Expert ({shard['shard_id']})",
        "action": f"专项分析: {shard['shard_id']}",
        "output": expert_output.get("opinion", "")[:100] + "...",
        "timestamp": datetime.now().isoformat(),
        "duration_ms": duration_ms
    }
    
    # 返回分片结果，由 operator.ior 自动合并到主状态的 shard_results 中
    return {
        "shard_results": {shard["shard_id"]: expert_output},
        "steps": [step],
        # 将本次匹配到的知识图谱背景记录下来，供最后 Analyst 参考
        "graph_context": graph_context 
    }


def analyst_node(state: MedicalTriageState):
    """
    Analyst Agent 节点 (Reduce)
    
    职责: 聚合并行结果，输出最终报告
    """
    start_time = datetime.now()
    
    # 聚合专家意见时，同时参考最原始输入、长期记忆和锁定锚点
    initial_anchor = state.get("initial_symptoms", state["patient_input"])
    prompt = AgentFactory.get_analyst_prompt(
        patient_input=state["patient_input"],
        shard_results=state["shard_results"],
        memory_context=state.get("memory_context", "")
    )
    prompt = f"【核心锚点记忆】: {initial_anchor}\n\n{prompt}"
    
    # 增强 Prompt：注入知识背景和长期记忆
    graph_info = state.get("graph_context", "无特定匹配知识")
    memory_info = state.get("memory_context", "尚无长期记忆记录")
    prompt = f"【患者长期记忆回顾】\n{memory_info}\n\n【知识图谱辅助参考】\n{graph_info}\n\n{prompt}"
    
    # 调用 LLM
    llm = get_llm()
    response = llm.invoke([
        SystemMessage(content="你是温暖、博学的“小星球”。你的任务是总结专家建议并以老朋友的身份温暖地回复用户。"),
        HumanMessage(content=prompt)
    ])
    
    # 解析响应
    triage_result = AgentResponse.parse_analyst_response(response.content)
    
    # --- 健壮性增强：确保所有字段都是 Pydantic 期待的类型 ---
    # 有时模型会把 advice 输出成一个 dict (嵌套结构)，我们需要将其转为字符串
    def ensure_str(val):
        if val is None: return ""
        if isinstance(val, str): return val
        try:
            return json.dumps(val, ensure_ascii=False, indent=2)
        except:
            return str(val)

    triage_result["diagnosis_suggestion"] = ensure_str(triage_result.get("diagnosis_suggestion", ""))
    triage_result["urgency"] = ensure_str(triage_result.get("urgency", ""))
    triage_result["advice"] = ensure_str(triage_result.get("advice", ""))
    
    # 确保 department 是列表
    if not isinstance(triage_result.get("department"), list):
        triage_result["department"] = [ensure_str(triage_result.get("department", "内科"))]
    
    # 生成报告文本
    analysis_report = triage_result["advice"]
    
    # 计算执行时间
    duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
    
    # --- 长期记忆增强：记录纪要 ---
    patient_id = state.get("patient_id", "default_user")
    depts = triage_result.get('department')
    if not isinstance(depts, list): depts = [str(depts)] if depts else ["内科"]
    event_summary = f"识别到症状: {initial_anchor}。分析结论: {triage_result.get('diagnosis_suggestion')}。建议去 {', '.join(depts)}。"
    patient_memory.add_to_chronicle(patient_id, event_summary)

    # 记录步骤
    step = {
        "agent_name": "Analyst (Reducer)",
        "action": "结果聚合与报告生成 (Reduce)",
        "output": "聚合完成",
        "timestamp": datetime.now().isoformat(),
        "duration_ms": duration_ms
    }
    
    # --- 流程分支 ---
    next_node = "human_reviewer" if state.get("require_approval", True) else END
    
    return Command(
        update={
            "triage_result": triage_result,
            "analysis_report": analysis_report,
            "current_agent": "completed" if next_node == END else "human_reviewer",
            "steps": [step],
            "messages": [AIMessage(content=f"[Analyst] 并行结果已汇总完毕{' (已自动发布)' if next_node == END else ' (等待审批)'}")]
        },
        goto=next_node
    )


def human_reviewer_node(state: MedicalTriageState) -> Command[Literal["__end__"]]:
    """
    Human Reviewer 节点
    
    职责: 等待人工审批
    使用 interrupt 暂停工作流，等待人工确认
    """
    # 记录步骤
    step = {
        "agent_name": "Human Reviewer",
        "action": "等待人工审批",
        "output": "分诊结果待审核",
        "timestamp": datetime.now().isoformat(),
        "duration_ms": 0
    }
    
    # 检查是否已有审批结果
    if state.get("human_approved") is not None:
        # 已审批，直接结束
        approval_status = "已批准" if state["human_approved"] else "已拒绝"
        step["output"] = f"审批结果: {approval_status}"
        
        return Command(
            update={
                "current_agent": "completed",
                "steps": state.get("steps", []) + [step],
                "messages": [AIMessage(content=f"[Human Reviewer] {approval_status}")]
            },
            goto=END
        )
    
    # 需要人工审批 - 使用 interrupt 暂停
    # 构建审批请求信息
    triage_result = state.get("triage_result", {})
    approval_request = {
        "type": "approval_required",
        "message": "请审核以下分诊结果",
        "triage_result": triage_result,
        "urgency": triage_result.get("urgency", "未知"),
        "departments": triage_result.get("department", []),
        "timestamp": datetime.now().isoformat()
    }
    
    # 使用 interrupt 暂停工作流
    # 当恢复时，会从这里继续执行
    approval_response = interrupt(approval_request)
    
    # 处理审批结果
    approved = approval_response.get("approved", False)
    comment = approval_response.get("comment", "")
    
    step["output"] = f"审批结果: {'已批准' if approved else '已拒绝'}"
    if comment:
        step["output"] += f" - {comment}"
    
    return Command(
        update={
            "human_approved": approved,
            "reviewer_comment": comment,
            "current_agent": "completed",
            "steps": [step], # operator.add 会自动处理 state.get("steps") + [step]
            "messages": [AIMessage(content=f"[Human Reviewer] {'已批准' if approved else '已拒绝'}")]
        },
        goto=END
    )


# ===== 构建工作流图 =====

def build_medical_triage_graph() -> StateGraph:
    """
    构建医疗分诊工作流图 (Map-Reduce 架构)
    
    流程:
        START ➡️ Coordinator (Map) ➡️ Expert Nodes (Parallel) ➡️ Analyst (Reduce) ➡️ Human Reviewer ➡️ END
    """
    workflow = StateGraph(MedicalTriageState)
    
    # 添加节点
    workflow.add_node("coordinator", coordinator_node)
    workflow.add_node("expert_node", expert_node)
    workflow.add_node("analyst", analyst_node)
    workflow.add_node("human_reviewer", human_reviewer_node)
    
    # 添加边与路由
    workflow.add_edge(START, "coordinator")
    
    # 注意: coordinator_node 使用 Send 动态生成 expert_node 实例，
    # 汇合点 (Gather) 需要显式连接到 analyst
    workflow.add_edge("expert_node", "analyst")
    
    workflow.add_edge("analyst", "human_reviewer")
    workflow.add_edge("human_reviewer", END)
    
    return workflow


def create_medical_triage_app(checkpointer=None):
    """
    创建可运行的应用实例
    
    Args:
        checkpointer: 检查点存储器，用于状态持久化
    """
    workflow = build_medical_triage_graph()
    
    if checkpointer is None:
        checkpointer = MemorySaver()
    
    return workflow.compile(checkpointer=checkpointer)


# ===== 便捷函数 =====

async def run_triage(
    patient_input: str,
    patient_info: Optional[Dict] = None,
    thread_id: str = "default"
) -> Dict[str, Any]:
    """
    运行分诊工作流（直到需要人工审批）
    
    Args:
        patient_input: 患者症状描述
        patient_info: 患者基本信息
        thread_id: 线程ID，用于状态恢复
    
    Returns:
        当前状态
    """
    app = create_medical_triage_app()
    
    initial_state = {
        "patient_input": patient_input,
        "patient_info": patient_info,
        "task_shards": [],
        "shard_results": {},
        "task_plan": [],
        "priority": "",
        "intent": "",
        "triage_result": None,
        "analysis_report": None,
        "messages": [HumanMessage(content=patient_input)],
        "steps": [],
        "current_agent": "coordinator",
        "require_approval": True,
        "human_approved": None,
        "reviewer_comment": None,
        "error": None
    }
    
    config = {"configurable": {"thread_id": thread_id}}
    
    # 运行直到 interrupt
    result = None
    async for event in app.astream(initial_state, config, stream_mode="updates"):
        result = event
    
    # 获取最终状态
    final_state = await app.aget_state(config)
    
    return final_state.values


async def resume_with_approval(
    thread_id: str,
    approved: bool,
    comment: Optional[str] = None
) -> Dict[str, Any]:
    """
    恢复工作流并提供审批结果
    
    Args:
        thread_id: 线程ID
        approved: 是否批准
        comment: 审核意见
    """
    app = create_medical_triage_app()
    config = {"configurable": {"thread_id": thread_id}}
    
    # 使用 Command 恢复
    approval_response = {
        "approved": approved,
        "comment": comment or ""
    }
    
    # 恢复执行
    resume_command = Command(resume=approval_response)
    
    result = None
    async for event in app.astream(resume_command, config, stream_mode="updates"):
        result = event
    
    final_state = await app.aget_state(config)
    return final_state.values


# ===== 测试入口 =====

if __name__ == "__main__":
    import asyncio
    
    async def test_workflow():
        print("=" * 60)
        print("医疗分诊多智能体工作流测试")
        print("=" * 60)
        
        # 测试输入
        patient_input = "我最近一周经常头晕，早上起来特别严重，有时候还恶心，量血压偏高大概150/95。"
        
        print(f"\n患者描述: {patient_input}")
        print("\n开始执行工作流...")
        
        try:
            result = await run_triage(
                patient_input=patient_input,
                patient_info={"age": "55岁", "gender": "男性", "history": "无"},
                thread_id="test_001"
            )
            
            print("\n执行步骤:")
            for i, step in enumerate(result.get("steps", []), 1):
                print(f"  {i}. [{step['agent_name']}] {step['action']}")
            
            print("\n分诊结果:")
            triage = result.get("triage_result", {})
            print(f"  诊断建议: {triage.get('diagnosis_suggestion', 'N/A')}")
            print(f"  推荐科室: {triage.get('department', [])}")
            print(f"  紧急程度: {triage.get('urgency', 'N/A')}")
            
            print("\n当前状态:", result.get("current_agent"))
            
            if result.get("current_agent") == "human_reviewer":
                print("\n等待人工审批...")
                
                # 模拟人工审批
                final_result = await resume_with_approval(
                    thread_id="test_001",
                    approved=True,
                    comment="审核通过，建议尽快就医"
                )
                
                print(f"\n审批结果: {'已批准' if final_result.get('human_approved') else '已拒绝'}")
                print(f"审核意见: {final_result.get('reviewer_comment', '')}")
            
        except Exception as e:
            print(f"\n错误: {e}")
            import traceback
            traceback.print_exc()
    
    asyncio.run(test_workflow())
