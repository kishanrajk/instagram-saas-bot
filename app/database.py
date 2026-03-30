import sqlite3
from datetime import datetime
from config import DB_NAME

def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    # Users table (SaaS customers)
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            instagram_id TEXT UNIQUE,
            instagram_username TEXT,
            access_token TEXT,
            keywords TEXT DEFAULT 'price,details,info,cost',
            response_message TEXT DEFAULT 'Hey! Check this out: https://yourlink.com',
            last_login DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Leads table (People who commented)
    c.execute('''
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            instagram_owner_id TEXT,
            commenter_id TEXT,
            commenter_username TEXT,
            comment_text TEXT,
            dm_sent BOOLEAN DEFAULT 0,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (instagram_owner_id) REFERENCES users(instagram_id)
        )
    ''')
    conn.commit()
    conn.close()

def upsert_user(instagram_id: str, access_token: str, instagram_username: str = "unknown"):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO users (instagram_id, instagram_username, access_token, last_login)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(instagram_id) DO UPDATE SET
        instagram_username = excluded.instagram_username,
        access_token = excluded.access_token,
        last_login = excluded.last_login
    ''', (instagram_id, instagram_username, access_token, datetime.utcnow()))
    conn.commit()
    conn.close()

def get_user_settings(instagram_id: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT access_token, keywords, response_message FROM users WHERE instagram_id = ?', (instagram_id,))
    res = c.fetchone()
    conn.close()
    if res:
        return {"access_token": res[0], "keywords": res[1].split(','), "response_message": res[2]}
    return None

def log_lead(instagram_owner_id: str, commenter_id: str, commenter_username: str, comment_text: str, dm_sent: bool = False):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        INSERT OR IGNORE INTO leads (instagram_owner_id, commenter_id, commenter_username, comment_text, dm_sent, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (instagram_owner_id, commenter_id, commenter_username, comment_text, dm_sent, datetime.utcnow()))
    conn.commit()
    conn.close()

def has_been_contacted_recently(instagram_owner_id: str, commenter_id: str, hours: int = 24) -> bool:
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        SELECT count(*) FROM leads 
        WHERE instagram_owner_id = ? AND commenter_id = ? AND timestamp >= datetime('now', ?)
    ''', (instagram_owner_id, commenter_id, f'-{hours} hours'))
    count = c.fetchone()[0]
    conn.close()
    return count > 0

def get_leads_for_user(instagram_owner_id: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM leads WHERE instagram_owner_id = ? ORDER BY timestamp DESC', (instagram_owner_id,))
    rows = c.fetchall()
    columns = [desc[0] for desc in c.description]
    conn.close()
    return columns, rows
