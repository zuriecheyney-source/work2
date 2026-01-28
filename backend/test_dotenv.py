import os
from dotenv import load_dotenv
load_dotenv()
print(f"ENV DEEPSEEK_API_KEY: {os.environ.get('DEEPSEEK_API_KEY')}")
