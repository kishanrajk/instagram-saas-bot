import os
from dotenv import load_dotenv

from pathlib import Path

# Try loading from project root first, then app/ folder
root_env = Path(__file__).resolve().parent.parent / '.env'
app_env = Path(__file__).resolve().parent / '.env'

if root_env.exists():
    load_dotenv(dotenv_path=root_env)
    env_path = root_env
else:
    load_dotenv(dotenv_path=app_env)
    env_path = app_env

# SaaS / OAuth Credentials (Loaded from DB per user, but these are for the App itself)
APP_ID = os.getenv("APP_ID", "")
APP_SECRET = os.getenv("APP_SECRET", "")
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost:8082/auth/callback")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "my_secure_verify_token")
GRAPH_API_VERSION = os.getenv("GRAPH_API_VERSION", "v25.0")

# Debugging
print(f"DEBUG: Loaded APP_ID: {APP_ID[:5]}... Success: {bool(APP_ID)}")
print(f"DEBUG: Loaded REDIRECT_URI: {REDIRECT_URI}")
print(f"DEBUG: Using env file: {env_path}")

# Bot settings
_keywords_str = os.getenv("KEYWORDS", "price,details,info,cost")
KEYWORDS = [k.strip().lower() for k in _keywords_str.split(",")]

DM_TEMPLATE = os.getenv(
    "DM_TEMPLATE", 
    "Hey! Thanks for your interest 😊 Check this out: https://yourlink.com"
)

# Database
ROOT_DIR = Path(__file__).resolve().parent.parent
DB_NAME = str(ROOT_DIR / "leads_v3.db")
