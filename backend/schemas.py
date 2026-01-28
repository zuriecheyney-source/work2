#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pydantic 数据模型定义

定义 API 请求/响应的数据结构
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


# ===== 任务状态枚举 =====

class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"              # 待处理
    COORDINATOR = "coordinator"      # Coordinator 处理中
    EXPERT = "expert"               # Domain Expert 处理中
    ANALYST = "analyst"             # Analyst 处理中
    WAITING_APPROVAL = "waiting_approval"  # 等待人工审批
    APPROVED = "approved"           # 已批准
    REJECTED = "rejected"           # 已拒绝
    COMPLETED = "completed"         # 已完成
    FAILED = "failed"               # 失败


class UrgencyLevel(str, Enum):
    """紧急程度"""
    IMMEDIATE = "立即就医/拨打120"
    URGENT = "建议24小时内就医"
    SOON = "建议3天内就医"
    ROUTINE = "择期就医"
    OBSERVATION = "可先观察"


# ===== 请求模型 =====

class StartTaskRequest(BaseModel):
    """启动任务请求"""
    patient_id: str = Field(
        default="default_user",
        description="唯一患者ID，用于记忆追踪",
        examples=["user_12345"]
    )
    patient_description: str = Field(
        ..., 
        min_length=1,
        max_length=2000,
        description="患者症状描述",
        examples=["我最近一周经常头晕，早上起来特别严重，有高血压病史"]
    )
    patient_info: Optional[Dict[str, Any]] = Field(
        default=None,
        description="患者基本信息（年龄、性别、病史等）"
    )
    require_approval: bool = Field(
        default=True,
        description="是否开启人工审核模式 (建议开启以确保准确性)"
    )
    chat_history: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="对话历史 (用于保持上下文连贯性)"
    )
    task_id: Optional[str] = Field(
        default=None,
        description="现有任务 ID (如果是在同一个会话中继续对话)"
    )


class HumanApprovalRequest(BaseModel):
    """人工审批请求"""
    task_id: str = Field(..., description="任务ID")
    approved: bool = Field(..., description="是否批准")
    reviewer_comment: Optional[str] = Field(
        default=None,
        max_length=500,
        description="审核意见"
    )


class UpdateTaskNameRequest(BaseModel):
    """更新任务名称请求"""
    task_id: str = Field(..., description="任务ID")
    name: str = Field(..., min_length=1, max_length=50, description="新名称")


class PatientProfileUpdateRequest(BaseModel):
    """患者画像更新请求"""
    patient_id: str = Field(..., description="患者ID")
    name: Optional[str] = Field(default=None, description="姓名")
    phone: Optional[str] = Field(default=None, description="电话")
    age: Optional[str] = Field(default=None, description="年龄")
    gender: Optional[str] = Field(default=None, description="性别")
    history: Optional[str] = Field(default=None, description="既往病史")
    allergies: Optional[str] = Field(default=None, description="过敏史")
    smoking: Optional[str] = Field(default=None, description="吸烟史")
    alcohol: Optional[str] = Field(default=None, description="饮酒史")
    medications: Optional[str] = Field(default=None, description="当前用药")


# ===== 响应模型 =====

class TriageResult(BaseModel):
    """分诊结果"""
    diagnosis_suggestion: str = Field(..., description="初步诊断建议")
    department: List[str] = Field(..., description="推荐就诊科室")
    urgency: str = Field(..., description="紧急程度")
    advice: str = Field(..., description="就医建议")


class AgentStep(BaseModel):
    """Agent 执行步骤"""
    agent_name: str = Field(..., description="Agent 名称")
    action: str = Field(..., description="执行动作")
    output: Optional[str] = Field(default=None, description="输出内容")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")
    duration_ms: Optional[int] = Field(default=None, description="执行时长(毫秒)")


class TaskResponse(BaseModel):
    """任务响应"""
    task_id: str = Field(..., description="任务ID")
    status: TaskStatus = Field(..., description="任务状态")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    # 输入
    patient_description: str = Field(..., description="患者症状描述")
    intent: Optional[str] = Field(default=None, description="任务意图 (chat/triage)")
    
    # 中间结果
    task_plan: Optional[List[str]] = Field(default=None, description="任务规划")
    steps: List[AgentStep] = Field(default_factory=list, description="执行步骤")
    
    # 最终结果
    triage_result: Optional[TriageResult] = Field(default=None, description="分诊结果")
    analysis_report: Optional[str] = Field(default=None, description="分析报告")
    
    # 审批信息
    require_approval: Optional[bool] = Field(default=True, description="是否开启了人工审核")
    human_approved: Optional[bool] = Field(default=None, description="人工审批结果")
    reviewer_comment: Optional[str] = Field(default=None, description="审核意见")
    
    # 错误信息
    error: Optional[str] = Field(default=None, description="错误信息")


class StartTaskResponse(BaseModel):
    """启动任务响应"""
    task_id: Optional[str] = Field(default=None, description="任务ID (如果是 chat 则可能为空)")
    message: str = Field(..., description="提示信息内容")
    intent: str = Field(default="medical_triage", description="识别到的意图")
    reply: Optional[str] = Field(default=None, description="直接回复内容 (针对 chat)")


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = Field(default="healthy", description="服务状态")
    version: str = Field(default="1.0.0", description="版本号")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")


# ===== LangGraph State =====

class TaskShard(BaseModel):
    """任务分片"""
    shard_id: str = Field(..., description="分片ID")
    task_type: str = Field(..., description="任务类型")
    content: str = Field(..., description="子任务内容")
    status: str = Field(default="pending", description="状态")
    output: Optional[Dict[str, Any]] = Field(default=None, description="处理输出")


class MedicalTriageState(BaseModel):
    """
    LangGraph 状态定义 - Map-Reduce + Memory 版本
    """
    # 输入与身份
    patient_id: str = Field(default="default_user", description="患者ID")
    patient_input: str = Field(..., description="患者主诉")
    patient_info: Optional[Dict[str, Any]] = Field(default=None, description="患者信息")
    memory_context: Optional[str] = Field(default="", description="患者历史记忆背景")
    intent: str = Field(default="medical_triage", description="任务意图")
    
    # Map-Reduce 核心结构
    task_shards: List[TaskShard] = Field(default_factory=list, description="任务分片列表 (Map)")
    shard_results: Dict[str, Any] = Field(default_factory=dict, description="各分片执行结果 (Reduce)")
    
    # 任务规划 (总控)
    task_plan: List[str] = Field(default_factory=list, description="任务规划步骤")
    
    # 汇总输出
    triage_result: Optional[Dict[str, Any]] = Field(default=None, description="最终汇总的分诊结果")
    analysis_report: Optional[str] = Field(default=None, description="最终分析报告")
    
    # 执行历史
    messages: List[Dict[str, Any]] = Field(default_factory=list, description="消息历史")
    steps: List[Dict[str, Any]] = Field(default_factory=list, description="执行步骤")
    
    # 控制
    current_agent: str = Field(default="coordinator", description="当前 Agent")
    require_approval: bool = Field(default=True, description="是否需要人工审核")
    human_approved: Optional[bool] = Field(default=None, description="人工审批结果")
    reviewer_comment: Optional[str] = Field(default=None, description="审核意见")
    
    # 错误
    error: Optional[str] = Field(default=None, description="错误信息")
    
    class Config:
        arbitrary_types_allowed = True
