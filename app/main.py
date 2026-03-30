import asyncio
import hmac
import hashlib
from fastapi import FastAPI, Request, HTTPException, Response
import requests
from config import VERIFY_TOKEN, APP_ID, APP_SECRET, REDIRECT_URI, GRAPH_API_VERSION
from messaging import process_comment_for_dm
from database import init_db, upsert_user

import logging

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("instagram_saas")

app = FastAPI()

# Make sure database handles the table at start
@app.on_event("startup")
def startup_db_client():
    init_db()
    logger.info(f"SaaS Startup: APP_ID={APP_ID}")

@app.get("/")
async def root():
    return {"message": "Instagram Sales Bot SaaS is running. Visit /login to connect your account."}

@app.get("/login")
async def login():
    """Redirect user to Meta Login with Full Permissions"""
    if not APP_ID or not REDIRECT_URI:
        return {"error": "APP_ID or REDIRECT_URI not configured in .env"}
        
    scope = "instagram_basic,instagram_manage_comments,instagram_manage_messages,pages_show_list,pages_read_engagement,pages_messaging,pages_manage_metadata,business_management"
    auth_url = (
        f"https://www.facebook.com/{GRAPH_API_VERSION}/dialog/oauth?"
        f"client_id={APP_ID}&redirect_uri={REDIRECT_URI}&scope={scope}"
    )
    return Response(status_code=302, headers={"Location": auth_url})

@app.get("/auth/callback")
async def auth_callback(code: str = None, error: str = None):
    """Handle Meta OAuth Redirect and Exchange for Long-Lived Tokens"""
    if error: return {"error": error}
    if not code: return {"error": "No code provided"}
    
    try:
        # 1. Exchange code for Short-Lived User Token
        token_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/oauth/access_token"
        params = {"client_id": APP_ID, "client_secret": APP_SECRET, "redirect_uri": REDIRECT_URI, "code": code}
        resp = requests.get(token_url, params=params).json()
        short_token = resp.get("access_token")

        # 2. Exchange for Long-Lived User Token (60 days)
        ll_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/oauth/access_token"
        ll_params = {
            "grant_type": "fb_exchange_token",
            "client_id": APP_ID,
            "client_secret": APP_SECRET,
            "fb_exchange_token": short_token
        }
        ll_user_data = requests.get(ll_url, params=ll_params).json()
        long_lived_user_token = ll_user_data.get("access_token")

        # 3. Get Pages and Long-Lived Page Tokens
        pages_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/me/accounts?access_token={long_lived_user_token}"
        pages_data = requests.get(pages_url).json().get("data", [])
        
        connected_ig_accounts = []
        for page in pages_data:
            page_id, page_name, page_token = page.get("id"), page.get("name"), page.get("access_token") 
            
            # 4. Find linked IG account
            ig_check_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{page_id}?fields=instagram_business_account&access_token={page_token}"
            ig_data = requests.get(ig_check_url).json()
            ig_account = ig_data.get("instagram_business_account")
            
            if ig_account:
                ig_id = ig_account.get("id")
                ig_info = requests.get(f"https://graph.facebook.com/{GRAPH_API_VERSION}/{ig_id}?fields=username&access_token={page_token}").json()
                ig_username = ig_info.get("username", "unknown")
                
                # 5. Subscribe App to Webhooks (Proper list format)
                sub_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{page_id}/subscribed_apps"
                # Meta expects a comma-separated string for subscribed_fields in the POST body usually
                # but let's send it in a way that is robust.
                sub_params = {
                    "access_token": page_token,
                    "subscribed_fields": "comments,messages,messaging_postbacks"
                }
                sub_resp = requests.post(sub_url, data=sub_params).json()
                logger.info(f"Subscription result for {page_name}: {sub_resp}")
                
                upsert_user(instagram_id=ig_id, instagram_username=ig_username, access_token=page_token)
                connected_ig_accounts.append(f"@{ig_username}")
        
        return {"status": "success", "accounts": connected_ig_accounts}
        
    except Exception as e:
        logger.error(f"Auth error: {e}")
        return {"error": str(e)}

@app.get("/webhook")
async def verify_webhook(request: Request):
    """Webhook Verification per Meta documentation"""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return Response(content=challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verification failed")

async def background_webhook_processor(data: dict):
    """Process webhook data in the background to avoid blocking Meta's 5s timeout"""
    try:
        entries = data.get("entry", [])
        for entry in entries:
            ig_owner_id = entry.get("id")
            for change in entry.get("changes", []):
                val = change.get("value", {})
                if change.get("field") in ["comments", "mentions"]:
                    process_comment_for_dm(
                        instagram_owner_id=ig_owner_id,
                        commenter_id=val.get("from", {}).get("id"),
                        username=val.get("from", {}).get("username", "unknown"),
                        comment_text=val.get("text", "")
                    )
    except Exception as e:
        logger.error(f"Background Processor Error: {e}")

@app.post("/webhook")
async def handle_webhook(request: Request):
    """Receive IG Webhook Events with Signature Security & Background Processing"""
    # 1. Verify Signature
    if APP_SECRET:
        signature = request.headers.get("X-Hub-Signature-256")
        if not signature:
            raise HTTPException(status_code=401, detail="No signature provided")
        
        body = await request.body()
        expected_sig = "sha256=" + hmac.new(APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
        
        if not hmac.compare_digest(signature, expected_sig):
            logger.warning("Invalid Webhook Signature!")
            raise HTTPException(status_code=401, detail="Signature mismatch")

    # 2. Parse and delegate to background task
    try:
        data = await request.json()
        logger.info(f"Webhook Validated. Scheduling background task...")
        asyncio.create_task(background_webhook_processor(data))
    except Exception as e:
        logger.error(f"Webhook parsing failed: {e}")

    # 3. Return 200 OK immediately
    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8082, reload=True)
