import os
from pathlib import Path
from dotenv import load_dotenv

# Current CWD
print(f"Current CWD: {os.getcwd()}")

# Attempt to find .env
p = Path(".env")
print(f".env exists in CWD? {p.exists()}")

parent_p = Path("..") / ".env"
print(f".env exists in ..? {parent_p.exists()}")

# Load it
load_dotenv(parent_p)
print(f"DEEPSEEK_API_KEY after manual load: {os.environ.get('DEEPSEEK_API_KEY')[:10]}...")
