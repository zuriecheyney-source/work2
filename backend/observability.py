#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Langfuse 可观测性集成

集成 Langfuse 追踪 LangGraph 执行路径
记录 Token 消耗、延迟、Agent 调用链
"""

import os
from typing import Optional
from functools import lru_cache

from backend.config import settings


# ===== Langfuse Handler =====

_langfuse_handler = None


def get_langfuse_handler():
    """
    获取 Langfuse 回调处理器
    
    Returns:
        CallbackHandler 或 None
    """
    global _langfuse_handler
    
    if not settings.langfuse_enabled:
        return None
    
    if _langfuse_handler is not None:
        return _langfuse_handler
    
    try:
        from langfuse.callback import CallbackHandler
        
        _langfuse_handler = CallbackHandler(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
            # 可选配置
            session_id=None,  # 会在每次请求时动态设置
            release=os.getenv("APP_VERSION", "1.0.0"),
            debug=False
        )
        
        print("[OK] Langfuse 已初始化")
        return _langfuse_handler
        
    except ImportError:
        print("[WARN] langfuse 未安装，跳过可观测性集成")
        return None
    except Exception as e:
        print(f"[WARN] Langfuse 初始化失败: {e}")
        return None


def create_trace_handler(
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    metadata: Optional[dict] = None
):
    """
    创建带有自定义元数据的追踪处理器
    
    Args:
        session_id: 会话ID
        user_id: 用户ID
        metadata: 额外元数据
    """
    if not settings.langfuse_enabled:
        return None
    
    try:
        from langfuse.callback import CallbackHandler
        
        handler = CallbackHandler(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
            session_id=session_id,
            user_id=user_id,
            metadata=metadata or {},
            release=os.getenv("APP_VERSION", "1.0.0")
        )
        
        return handler
        
    except Exception as e:
        print(f"[WARN] 创建追踪处理器失败: {e}")
        return None


class LangfuseTracer:
    """
    Langfuse 追踪器
    
    提供手动追踪 API，用于追踪非 LLM 操作
    """
    
    def __init__(self):
        self.langfuse = None
        self._init_langfuse()
    
    def _init_langfuse(self):
        """初始化 Langfuse 客户端"""
        if not settings.langfuse_enabled:
            return
        
        try:
            from langfuse import Langfuse
            
            self.langfuse = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host
            )
        except Exception as e:
            print(f"[WARN] Langfuse 客户端初始化失败: {e}")
    
    def trace(
        self,
        name: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[dict] = None
    ):
        """
        创建追踪
        
        Args:
            name: 追踪名称
            session_id: 会话ID
            user_id: 用户ID
            metadata: 元数据
        """
        if not self.langfuse:
            return None
        
        try:
            return self.langfuse.trace(
                name=name,
                session_id=session_id,
                user_id=user_id,
                metadata=metadata or {}
            )
        except Exception as e:
            print(f"[WARN] 创建追踪失败: {e}")
            return None
    
    def span(
        self,
        trace,
        name: str,
        input: Optional[dict] = None,
        output: Optional[dict] = None,
        metadata: Optional[dict] = None
    ):
        """
        在追踪中创建 Span
        
        Args:
            trace: 追踪对象
            name: Span 名称
            input: 输入数据
            output: 输出数据
            metadata: 元数据
        """
        if not trace:
            return None
        
        try:
            return trace.span(
                name=name,
                input=input,
                output=output,
                metadata=metadata or {}
            )
        except Exception as e:
            print(f"[WARN] 创建 Span 失败: {e}")
            return None
    
    def score(
        self,
        trace,
        name: str,
        value: float,
        comment: Optional[str] = None
    ):
        """
        为追踪添加评分
        
        Args:
            trace: 追踪对象
            name: 评分名称
            value: 评分值 (0-1)
            comment: 评论
        """
        if not trace:
            return
        
        try:
            trace.score(
                name=name,
                value=value,
                comment=comment
            )
        except Exception as e:
            print(f"[WARN] 添加评分失败: {e}")
    
    def flush(self):
        """刷新待发送的追踪数据"""
        if self.langfuse:
            try:
                self.langfuse.flush()
            except Exception:
                pass


# 全局追踪器实例
tracer = LangfuseTracer()


# ===== 追踪装饰器 =====

def trace_agent(agent_name: str):
    """
    Agent 追踪装饰器
    
    用法:
        @trace_agent("Coordinator")
        async def coordinator_node(state):
            ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            handler = get_langfuse_handler()
            
            if handler:
                # 设置 trace 名称
                handler.trace_name = f"Agent: {agent_name}"
            
            result = await func(*args, **kwargs)
            
            return result
        return wrapper
    return decorator


def trace_task(task_id: str, patient_input: str):
    """
    创建任务级别的追踪
    
    Args:
        task_id: 任务ID
        patient_input: 患者描述
    """
    return create_trace_handler(
        session_id=task_id,
        metadata={
            "task_id": task_id,
            "patient_input_length": len(patient_input),
            "task_type": "medical_triage"
        }
    )
