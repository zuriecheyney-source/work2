#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块

管理所有环境变量和配置项
"""

import os
from pathlib import Path
from typing import Optional, List
from dotenv import load_dotenv
from pydantic import Field, AliasChoices, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

# 获取项目根目录 (backend/config.py -> backend -> project_root)
PROJECT_ROOT = Path(__file__).parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

# 强制加载 .env 并在冲突时覆盖操作系统的环境变量
if ENV_FILE.exists():
    load_dotenv(ENV_FILE, override=True)
else:
    # 兼容部署环境，可能直接使用环境变量
    load_dotenv(override=True)


class Settings(BaseSettings):
    """应用配置"""
    
    # 核心 API 配置
    deepseek_api_key: str = Field(default="", alias=AliasChoices("DEEPSEEK_API_KEY", "DEEPSEEK_KEY"))
    deepseek_base_url: str = Field(default="https://api.deepseek.com/v1", alias=AliasChoices("DEEPSEEK_BASE_URL", "DEEPSEEK_URL"))
    deepseek_model: str = Field(default="deepseek-chat", alias=AliasChoices("DEEPSEEK_MODEL"))
    
    openai_api_key: str = Field(default="", alias=AliasChoices("OPENAI_API_KEY", "OPENAI_KEY"))
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias=AliasChoices("OPENAI_BASE_URL", "OPENAI_URL"))
    openai_model: str = Field(default="gpt-4o-mini", alias=AliasChoices("OPENAI_MODEL"))

    # ===== 微调模型配置 =====
    use_local_model: bool = False
    local_model_path: str = "/models/medical-triage-lora"
    
    # ===== Langfuse 配置 =====
    langfuse_enabled: bool = False
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"
    
    # ===== 数据库配置 =====
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "medical_agent"
    postgres_user: str = "agent"
    postgres_password: str = "agent123"
    database_url_env: Optional[str] = Field(default=None, alias=AliasChoices("DATABASE_URL", "POSTGRES_URL"))
    
    # ===== Redis 配置 =====
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    
    # ===== 服务配置 =====
    backend_host: str = "0.0.0.0"
    backend_port: int = Field(default=8000, alias=AliasChoices("PORT", "BACKEND_PORT"))
    frontend_port: int = 8501
    
    @computed_field
    @property
    def llm_api_key(self) -> str:
        """根据优先级获取 API Key"""
        # 优先级: DEEPSEEK_API_KEY -> OPENAI_API_KEY
        key = self.deepseek_api_key or os.getenv("DEEPSEEK_API_KEY") 
        if not key or key.startswith("sk-your"):
            key = self.openai_api_key or os.getenv("OPENAI_API_KEY")
        return key or ""
        
    @computed_field
    @property
    def llm_base_url(self) -> str:
        """确定 Base URL，除非明确指定，否则默认使用 DeepSeek"""
        # 如果设置了 DEEPSEEK_BASE_URL，那肯定是用它
        if self.deepseek_base_url != "https://api.deepseek.com/v1":
            return self.deepseek_base_url
        if os.getenv("DEEPSEEK_BASE_URL"):
            return os.getenv("DEEPSEEK_BASE_URL")
            
        # 如果只有 OpenAI Key 且自定义了 Base URL，则使用 OpenAI
        if not self.deepseek_api_key and self.openai_api_key:
            if self.openai_base_url != "https://api.openai.com/v1":
                return self.openai_base_url
            if os.getenv("OPENAI_BASE_URL"):
                return os.getenv("OPENAI_BASE_URL")
        
        # 默认回归官方 DeepSeek
        return "https://api.deepseek.com/v1"
        
    @computed_field
    @property
    def llm_model(self) -> str:
        """确定模型"""
        return self.deepseek_model if self.deepseek_api_key else self.openai_model

    @property
    def database_url(self) -> str:
        """PostgreSQL 连接 URL"""
        if self.database_url_env:
            return self.database_url_env
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
    
    @property
    def redis_url(self) -> str:
        """Redis 连接 URL"""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}"
        return f"redis://{self.redis_host}:{self.redis_port}"
    
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE) if ENV_FILE.exists() else None,
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix=""
    )


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    s = Settings()
    
    # 启动时诊断日志
    print(f"\n[CONFIG] 加载配置文件: {ENV_FILE if ENV_FILE.exists() else '未找到'}")
    print(f"[CONFIG] 当前模型: {s.llm_model}")
    print(f"[CONFIG] Base URL: {s.llm_base_url}")
    
    # 获取真正的密钥（考虑计算属性）
    final_key = s.llm_api_key
    if final_key and len(final_key) > 5:
        masked_key = f"{final_key[:6]}...{final_key[-4:]}"
    else:
        masked_key = "❌ 未配置"
        
    print(f"[CONFIG] 最终 API Key: {masked_key}")
    print(f"[CONFIG] Langfuse: {'启用' if s.langfuse_enabled else '禁用'}\n")
    
    # 额外诊断环境
    if not final_key:
        print("⚠️ 警告: 无法在环境变量中找到 DEEPSEEK_API_KEY 或 OPENAI_API_KEY。")
        print(f"DEBUG: deepseek_api_key={bool(s.deepseek_api_key)}, openai_api_key={bool(s.openai_api_key)}")
    
    return s


# 导出配置实例
settings = get_settings()
