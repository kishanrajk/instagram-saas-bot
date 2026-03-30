import requests
import time
from database import log_lead, has_been_contacted_recently, get_user_settings
from config import GRAPH_API_VERSION

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def send_instagram_dm(recipient_id: str, message_text: str, access_token: str) -> bool:
    """Send a direct message via the Instagram Graph API using a specific user token"""
    if not access_token:
        logger.error("No access token provided. Cannot send DM.")
        return False
        
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/me/messages"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        logger.info(f"Successfully sent DM to {recipient_id}")
        return True
    except requests.exceptions.HTTPError as err:
        logger.error(f"HTTP Error failed to send DM: {err.response.text}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending DM: {e}")
        return False

def process_comment_for_dm(instagram_owner_id: str, commenter_id: str, username: str, comment_text: str) -> bool:
    """Check user's specific settings and send DM - TEST VERSION (Captures EVERYTHING)"""
    
    # Fetch settings for THIS Instagram account owner
    settings = get_user_settings(instagram_owner_id)
    
    # FOR TESTING: We will capture the lead even if settings are missing (e.g. Meta Test Data)
    if not settings:
        logger.info(f"TEST DATA DETECTED for IG owner {instagram_owner_id}. Capturing lead anyway.")
        # Log in Database with fake 'sent=False' since we have no token
        log_lead(instagram_owner_id=instagram_owner_id, commenter_id=commenter_id, commenter_username=username, comment_text=comment_text, dm_sent=False)
        return True
        
    access_token = settings['access_token']
    keywords = settings['keywords']
    response_message = settings['response_message']
    
    # BYPASS KEYWORDS FOR TESTING
    has_keyword = True # any(k.strip().lower() in comment_text.lower() for k in keywords)
    
    if not has_keyword:
        logger.info(f"Skipping DM for {username}: No keywords found in '{comment_text}'.")
        return False
        
    # Send Message (Only if real data)
    sent = False
    if commenter_id != "232323232": # Don't DM the Meta test ID
        sent = send_instagram_dm(recipient_id=commenter_id, message_text=response_message, access_token=access_token)
    
    # Log in Database
    log_lead(instagram_owner_id=instagram_owner_id, commenter_id=commenter_id, commenter_username=username, comment_text=comment_text, dm_sent=sent)
    return sent
