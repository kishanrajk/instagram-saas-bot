import requests
import time
from database import log_lead, has_been_contacted_recently, get_user_settings
from config import GRAPH_API_VERSION

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def send_instagram_dm(instagram_owner_id: str, recipient_id: str, message_text: str, access_token: str) -> bool:
    """Send a direct message via the Instagram Graph API using the correct /ig-id/messages endpoint"""
    if not access_token:
        logger.error("No access token provided. Cannot send DM.")
        return False
        
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{instagram_owner_id}/messages"
    
    headers = {"Content-Type": "application/json"}
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text},
        "access_token": access_token
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        logger.info(f"Successfully sent DM from {instagram_owner_id} to {recipient_id}")
        return True
    except Exception as e:
        logger.error(f"DM Send Failure: {e}")
        return False

def process_comment_for_dm(instagram_owner_id: str, commenter_id: str, username: str, comment_text: str, test_mode: bool = False) -> bool:
    """Production logic for processing leads with keywords and rate limits"""
    
    settings = get_user_settings(instagram_owner_id)
    
    # Check if this is a synthetic Meta test hit
    is_meta_test = (commenter_id == "232323232")
    
    if not settings:
        if is_meta_test:
            logger.info("Meta Dashboard Test detected. Logging lead for verification.")
            log_lead(instagram_owner_id, commenter_id, username, comment_text, dm_sent=False)
            return True
        logger.warning(f"No settings for IG owner {instagram_owner_id}. Ignoring.")
        return False
        
    keywords = settings['keywords']
    
    # 1. Keyword Check
    has_keyword = any(k.strip().lower() in comment_text.lower() for k in keywords)
    if not has_keyword and not is_meta_test:
        logger.info(f"No keywords in '{comment_text}' from @{username}. Skipping.")
        return False
        
    # 2. Rate Limit (24h cooldown)
    if not is_meta_test and has_been_contacted_recently(instagram_owner_id, commenter_id, hours=24):
        logger.info(f"Rate limit hit for @{username}. Skipping.")
        return False
        
    # 3. Send DM (Skip if test mode or meta test)
    sent = False
    if not test_mode and not is_meta_test:
        sent = send_instagram_dm(
            instagram_owner_id=instagram_owner_id,
            recipient_id=commenter_id,
            message_text=settings['response_message'],
            access_token=settings['access_token']
        )
    
    # 4. Log lead
    log_lead(instagram_owner_id, commenter_id, username, comment_text, dm_sent=sent)
    return sent
