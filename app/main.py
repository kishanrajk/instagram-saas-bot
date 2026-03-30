from fastapi import FastAPI, Request, HTTPException, Response
import requests
from config import VERIFY_TOKEN, APP_ID, APP_SECRET, REDIRECT_URI, GRAPH_API_VERSION
from messaging import process_comment_for_dm
from database import init_db, upsert_user

app = FastAPI()

# Make sure database handles the table at start
@app.on_event("startup")
def startup_db_client():
    init_db()
    print(f"MAIN DEBUG: APP_ID={APP_ID}")
    print(f"MAIN DEBUG: REDIRECT_URI={REDIRECT_URI}")

@app.get("/")
async def root():
    return {"message": "Instagram Sales Bot SaaS is running. Visit /login to connect your account."}

@app.get("/login")
async def login():
    """Redirect user to Meta Login with Full Permissions"""
    if not APP_ID or not REDIRECT_URI:
        return {"error": "APP_ID or REDIRECT_URI not configured in .env"}
        
    # Standard Meta Login URL with necessary permissions
    scope = "instagram_basic,instagram_manage_comments,instagram_manage_messages,pages_show_list,pages_read_engagement,pages_messaging,pages_manage_metadata,business_management"
    auth_url = (
        f"https://www.facebook.com/{GRAPH_API_VERSION}/dialog/oauth?"
        f"client_id={APP_ID}&redirect_uri={REDIRECT_URI}&scope={scope}"
    )
    return Response(status_code=302, headers={"Location": auth_url})

@app.get("/auth/callback")
async def auth_callback(code: str = None, error: str = None):
    """Handle Meta OAuth Redirect"""
    if error:
        return {"error": error}
    if not code:
        return {"error": "No code provided"}
    
    try:
        # Step 0: Exchange code for Token
        token_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/oauth/access_token"
        params = {
            "client_id": APP_ID,
            "client_secret": APP_SECRET,
            "redirect_uri": REDIRECT_URI,
            "code": code
        }
        resp = requests.get(token_url, params=params)
        resp.raise_for_status()
        token_data = resp.json()
        access_token = token_data.get("access_token")

        # Step 1: Optional Debugging (Protected from crashes)
        scopes = []
        try:
            perm_url = f"https://graph.facebook.com/debug_token?input_token={access_token}&access_token={APP_ID}|{APP_SECRET}"
            perm_resp = requests.get(perm_url)
            if perm_resp.status_code == 200:
                scopes = perm_resp.json().get('data', {}).get('scopes', [])
        except:
            pass
        
        # Step 2: Get the user's Facebook Pages
        pages_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/me/accounts?access_token={access_token}"
        pages_resp = requests.get(pages_url)
        pages_resp.raise_for_status()
        raw_pages_resp = pages_resp.json()
        pages_data = raw_pages_resp.get("data", [])
        
        if not pages_data:
            return {
                "error": "No Facebook Pages found. Make sure you selected them in the login popup.",
                "DEBUG_SCOPES": scopes,
                "API_RESPONSE": raw_pages_resp
            }

        # Step 3: Find IG accounts linked to those pages
        connected_ig_accounts = []
        for page in pages_data:
            page_id = page.get("id")
            page_name = page.get("name")
            page_token = page.get("access_token") 
            
            ig_check_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{page_id}?fields=instagram_business_account&access_token={page_token}"
            ig_resp = requests.get(ig_check_url)
            if ig_resp.status_code == 200:
                ig_data = ig_resp.json()
                ig_account = ig_data.get("instagram_business_account")
                if ig_account:
                    ig_id = ig_account.get("id")
                    ig_info_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{ig_id}?fields=username&access_token={page_token}"
                    ig_info = requests.get(ig_info_url).json()
                    ig_username = ig_info.get("username", "unknown")
                    
                    # Step 4: SUBSCRIBE the App to Webhooks for this Page (CRITICAL for SaaS)
                    sub_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{page_id}/subscribed_apps"
                    sub_params = {
                        "access_token": page_token,
                        "subscribed_fields": "comments,messages,messaging_postbacks"
                    }
                    sub_resp = requests.post(sub_url, data=sub_params).json()
                    print(f"DEBUG: Webhook Subscription for {page_name}: {sub_resp}")
                    
                    upsert_user(instagram_id=ig_id, instagram_username=ig_username, access_token=page_token)
                    connected_ig_accounts.append(f"@{ig_username} (via {page_name})")
        
        if not connected_ig_accounts:
            page_names = [p.get('name') for p in pages_data]
            return {"error": f"Found {len(pages_data)} Pages ({', '.join(page_names)}), but none have a linked Instagram Business account."}
            
        return {"message": f"Successfully connected! Accounts found: {', '.join(connected_ig_accounts)}. You can now view them in your dashboard."}
        
    except Exception as e:
        return {"error": f"Connection Failed: {str(e)}"}

@app.get("/webhook")
async def verify_webhook(request: Request):
    """Webhook Verification per Meta documentation"""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    
    if mode and token:
        if mode == "subscribe" and token == VERIFY_TOKEN:
            print(f"Webhook Verified with challenge: {challenge}")
            return Response(content=challenge, media_type="text/plain")
        else:
            raise HTTPException(status_code=403, detail="Verification tokens do not match")
    return {"message": "Invalid request"}

import logging

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("instagram_saas")

@app.post("/webhook")
async def handle_webhook(request: Request):
    """Receive IG Webhook Events for ANY user - LOGGING VERSION"""
    try:
        data = await request.json()
        logger.info(f"RECEIVED WEBHOOK (RAW): {data}")
    except Exception as e:
        logger.error(f"WEBHOOK ERROR PARSING JSON: {e}")
        return {"status": "error", "message": "Invalid JSON"}
        
    entries = data.get("entry", [])
    if not entries:
        logger.info("Webhook received but no entries found.")
    
    for entry in entries:
        instagram_owner_id = entry.get("id")
        logger.info(f"Processing Entry for Owner: {instagram_owner_id}")
        
        changes = entry.get("changes", [])
        for change in changes:
            field = change.get("field")
            value = change.get("value", {})
            logger.info(f"Found Field '{field}' with Value: {value}")
            
            if field in ["comments", "mentions"]:
                comment_text = value.get("text", "")
                commenter_id = value.get("from", {}).get("id")
                username = value.get("from", {}).get("username", "unknown")
                
                logger.info(f"Comment Text: '{comment_text}' from @{username}")
                
                process_comment_for_dm(
                    instagram_owner_id=instagram_owner_id,
                    commenter_id=commenter_id,
                    username=username,
                    comment_text=comment_text
                )
    
    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8082, reload=True)
