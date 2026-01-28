from backend.config import settings
import os

print(f"CWD: {os.getcwd()}")
print(f"llm_api_key: {settings.llm_api_key}")
print(f"llm_base_url: {settings.llm_base_url}")
print(f"llm_model: {settings.llm_model}")
