import streamlit as st
import pandas as pd
from database import get_connection, init_db, get_leads_for_user

# Ensure table exists
init_db()

st.set_page_config(page_title="Instagram Sales SaaS Dashboard", layout="wide")

# Sidebar - Connected Accounts
st.sidebar.title("🚀 Instagram SaaS")
st.sidebar.markdown("Manage multiple Instagram accounts and automate your sales.")

# Fetch all connected users
conn = get_connection()
users_df = pd.read_sql("SELECT instagram_id, instagram_username FROM users", conn)
conn.close()

if users_df.empty:
    st.sidebar.info("No accounts connected yet.")
else:
    st.sidebar.header("Connected Accounts")
    # Store a mapping of Username -> ID for the selectbox
    user_mapping = dict(zip(users_df['instagram_username'], users_df['instagram_id']))
    
    selected_username = st.sidebar.selectbox(
        "Select Account to View",
        list(user_mapping.keys())
    )
    selected_user = user_mapping[selected_username]
    st.sidebar.success(f"Viewing leads for: @{selected_username}")

st.sidebar.markdown("---")
if st.sidebar.button("➕ Connect New Account"):
    st.sidebar.markdown(f'<a href="http://localhost:8080/login" target="_self">Click here to Authorize</a>', unsafe_allow_html=True)

# Main Title
st.title("📱 Auto-DM Lead Manager")

if users_df.empty:
    st.warning("Welcome! You haven't connected any Instagram accounts yet.")
    st.markdown("""
    To get started:
    1. Click **'Connect New Account'** in the sidebar.
    2. Authorize your Instagram through Meta.
    3. Once connected, your leads will start appearing here automatically.
    """)
else:
    # Fetch leads for selected user
    columns, rows = get_leads_for_user(selected_user)
    df = pd.DataFrame(rows, columns=columns)

    if df.empty:
        st.info(f"No leads captured for account {selected_user} yet. Wait for comments to trigger the webhook.")
    else:
        # Key Metrics
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Leads", len(df))
        col2.metric("DMs Sent", df['dm_sent'].sum())
        col3.metric("Success Rate", f"{(df['dm_sent'].sum() / len(df) * 100):.1f}%")

        # Display Table
        st.subheader("Recent Leads")
        # Ensure column names match the new schema
        # leads table: instagram_owner_id, commenter_id, commenter_username, comment_text, dm_sent, timestamp
        st.dataframe(
            df[['commenter_username', 'comment_text', 'dm_sent', 'timestamp']],
            use_container_width=True,
            hide_index=True
        )

        # Export CSV
        st.download_button(
            label="Download Leads as CSV",
            data=df.to_csv(index=False).encode('utf-8'),
            file_name=f'leads_{selected_user}.csv',
            mime='text/csv'
        )
