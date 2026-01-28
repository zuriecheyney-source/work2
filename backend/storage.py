#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务存储模块

支持 Redis 或内存存储
用于任务状态持久化
"""

import json
from typing import Dict, Any, Optional
from datetime import datetime
from abc import ABC, abstractmethod
import asyncio

from backend.config import settings


class TaskStorage(ABC):
    """任务存储抽象基类"""
    
    @abstractmethod
    async def save_task(self, task_id: str, data: Dict[str, Any]):
        """保存任务"""
        pass
    
    @abstractmethod
    async def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务"""
        pass
    
    @abstractmethod
    async def update_task(self, task_id: str, updates: Dict[str, Any]):
        """更新任务"""
        pass
    
    @abstractmethod
    async def delete_task(self, task_id: str):
        """删除任务"""
        pass
    
    @abstractmethod
    async def list_tasks(self, limit: int = 100) -> list:
        """列出所有任务"""
        pass
    
    @abstractmethod
    async def list_tasks_by_patient(self, patient_id: str, limit: int = 100) -> list:
        """根据患者 ID 列出任务"""
        pass


class MemoryStorage(TaskStorage):
    """内存存储"""
    
    def __init__(self):
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
    
    async def save_task(self, task_id: str, data: Dict[str, Any]):
        async with self._lock:
            self._tasks[task_id] = {
                **data,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
    
    async def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        return self._tasks.get(task_id)
    
    async def update_task(self, task_id: str, updates: Dict[str, Any]):
        async with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].update(updates)
                self._tasks[task_id]["updated_at"] = datetime.now().isoformat()
    
    async def delete_task(self, task_id: str):
        async with self._lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
    
    async def list_tasks(self, limit: int = 100) -> list:
        tasks = list(self._tasks.values())
        # 按更新时间排序
        tasks.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return tasks[:limit]

    async def list_tasks_by_patient(self, patient_id: str, limit: int = 100) -> list:
        tasks = [t for t in self._tasks.values() if t.get("patient_id") == patient_id]
        tasks.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return tasks[:limit]


class RedisStorage(TaskStorage):
    """Redis 存储"""
    
    def __init__(self):
        self._redis = None
        self._prefix = "medical_triage:"
    
    async def _get_client(self):
        """获取 Redis 客户端"""
        if self._redis is None:
            try:
                import redis.asyncio as redis
                self._redis = redis.from_url(
                    settings.redis_url,
                    encoding="utf-8",
                    decode_responses=True
                )
            except ImportError:
                raise RuntimeError("redis 包未安装，请运行: pip install redis")
        return self._redis
    
    def _key(self, task_id: str) -> str:
        """生成 Redis key"""
        return f"{self._prefix}{task_id}"
    
    async def save_task(self, task_id: str, data: Dict[str, Any]):
        client = await self._get_client()
        data_with_meta = {
            **data,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        await client.set(
            self._key(task_id),
            json.dumps(data_with_meta, ensure_ascii=False, default=str),
            ex=86400 * 7  # 7天过期
        )
        # 添加到任务列表
        await client.zadd(
            f"{self._prefix}list",
            {task_id: datetime.now().timestamp()}
        )
        # 添加到患者任务索引
        patient_id = data.get("patient_id", "default_user")
        await client.zadd(
            f"{self._prefix}patient:{patient_id}:tasks",
            {task_id: datetime.now().timestamp()}
        )
    
    async def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        client = await self._get_client()
        data = await client.get(self._key(task_id))
        if data:
            return json.loads(data)
        return None
    
    async def update_task(self, task_id: str, updates: Dict[str, Any]):
        client = await self._get_client()
        existing = await self.get_task(task_id)
        if existing:
            existing.update(updates)
            existing["updated_at"] = datetime.now().isoformat()
            await client.set(
                self._key(task_id),
                json.dumps(existing, ensure_ascii=False, default=str),
                ex=86400 * 7
            )
    
    async def delete_task(self, task_id: str):
        client = await self._get_client()
        task = await self.get_task(task_id)
        if task:
            patient_id = task.get("patient_id", "default_user")
            await client.delete(self._key(task_id))
            await client.zrem(f"{self._prefix}list", task_id)
            await client.zrem(f"{self._prefix}patient:{patient_id}:tasks", task_id)
    
    async def list_tasks(self, limit: int = 100) -> list:
        client = await self._get_client()
        task_ids = await client.zrevrange(f"{self._prefix}list", 0, limit - 1)
        tasks = []
        for task_id in task_ids:
            task = await self.get_task(task_id)
            if task:
                tasks.append(task)
        return tasks

    async def list_tasks_by_patient(self, patient_id: str, limit: int = 100) -> list:
        client = await self._get_client()
        task_ids = await client.zrevrange(f"{self._prefix}patient:{patient_id}:tasks", 0, limit - 1)
        tasks = []
        for task_id in task_ids:
            task = await self.get_task(task_id)
            if task:
                tasks.append(task)
        return tasks


def get_storage() -> TaskStorage:
    """
    获取存储实例
    
    根据配置选择 Redis 或内存存储
    """
    # 简化版：优先使用内存存储
    # 生产环境建议使用 Redis
    try:
        if settings.redis_host and settings.redis_host != "localhost":
            return RedisStorage()
    except Exception:
        pass
    
    return MemoryStorage()


# 全局存储实例
storage = get_storage()
