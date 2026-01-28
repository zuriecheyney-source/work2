import os
from backend.config import settings
from dotenv import load_dotenv

# 强制重新载入 .env
load_dotenv(override=True)

print("=== 🧪 环境深度诊断 (Deep Environment Audit) ===")
print(f"1. .env 绝对路径: {os.path.abspath('.env')}")

print("\n--- [A] 操作系统/Shell 环境变量 (OS/Shell Level) ---")
print(f"OS_DEEPSEEK_API_KEY: {os.environ.get('DEEPSEEK_API_KEY', 'NOT_SET')[:10]}...")
print(f"OS_DEEPSEEK_BASE_URL: {os.environ.get('DEEPSEEK_BASE_URL', 'NOT_SET')}")

print("\n--- [B] Pydantic 解析后的配置 (Pydantic settings Level) ---")
print(f"SETTINGS_BASE_URL: {settings.deepseek_base_url}")
print(f"SETTINGS_MODEL:    {settings.deepseek_model}")

print("\n--- [C] 结论与诊断 (Verdict) ---")
if os.environ.get('DEEPSEEK_BASE_URL') == settings.deepseek_base_url:
    print("📋 OS 环境变量与系统配置一致。")
    if "api.deepseek.com" in settings.deepseek_base_url:
        print("✅ 状态：配置已正确指向官方 DeepSeek。")
    else:
        print("❌ 状态：系统仍在抓取此地址，并不是官方地址！")
else:
    print("⚠️ 警告：环境变量与配置不对应，可能存在缓存。")

print("\n💡 建议：如果 A 部分还是旧地址，请务必【完全重启】你的 VS Code 或命令行窗口。")
print("Windows 的环境变量更新后，已经打开的窗口是看不见的。")
