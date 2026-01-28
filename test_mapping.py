import os
import sys

# Set env vars BEFORE importing anything that might call load_dotenv
os.environ['DEEPSEEK_API_KEY'] = '' # Clear to test fallback
os.environ['OPENAI_API_KEY'] = 'sk-from-openai-env'
os.environ['OPENAI_BASE_URL'] = 'https://api.openai.proxy'
os.environ['OPENAI_MODEL'] = 'gpt-4o-test'

from backend.config import Settings

# Create new settings instance
s = Settings()

print(f"llm_api_key: {s.llm_api_key}")
print(f"llm_base_url: {s.llm_base_url}")
print(f"llm_model: {s.llm_model}")

if s.llm_api_key == 'sk-from-openai-env':
    print("SUCCESS: Successfully mapped OPENAI_API_KEY to llm_api_key")
else:
    print("FAILURE: Failed to map OPENAI_API_KEY")

# Test precedence
os.environ['DEEPSEEK_API_KEY'] = 'sk-deepseek-priority'
s2 = Settings()
print(f"Precedence check (DEEPSEEK_API_KEY set): {s2.llm_api_key}")
if s2.llm_api_key == 'sk-deepseek-priority':
    print("SUCCESS: DEEPSEEK_API_KEY has precedence")
else:
    print("FAILURE: Precedence check failed")
