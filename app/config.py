import os
from dotenv import load_dotenv

from pathlib import Path

# Explicitly load .env from the root directory
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Meta / IG API
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN", "")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "my_secure_verify_token")
IG_USER_ID = os.getenv("IG_USER_ID", "")
GRAPH_API_VERSION = os.getenv("GRAPH_API_VERSION", "v19.0")

# SaaS / OAuth Credentials
APP_ID = os.getenv("APP_ID", "")
APP_SECRET = os.getenv("APP_SECRET", "")
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost:8082/auth/callback")

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
