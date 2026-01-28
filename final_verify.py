import os
import sys
from pathlib import Path

# Move to backend to simulate most common startup scenario
os.chdir(Path(__file__).parent / "backend")
sys.path.append(str(Path(__file__).parent))

from backend.config import settings

print("\n--- [FINAL VERIFICATION] ---")
print(f"Working Directory: {os.getcwd()}")
print(f"Settings loaded? {settings is not None}")
print(f"LLM Base URL: {settings.llm_base_url}")
print(f"LLM Model: {settings.llm_model}")
print(f"API Key (masked): {settings.llm_api_key[:6]}...")

if "deepseek" in settings.llm_base_url.lower():
    print("SUCCESS: Target is DeepSeek as expected.")
else:
    print("WARNING: Target is NOT DeepSeek. Check aliases.")

if settings.llm_api_key and not settings.llm_api_key.startswith("sk-your"):
    print("SUCCESS: Valid key looks configured.")
else:
    print("FAILURE: No valid key found or placeholder used.")
