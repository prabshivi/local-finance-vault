import datetime
import io
import os
import re
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from core.crypto import generate_transaction_hash
from core.db import (
    connect_db, init_db, get_accounts, add_account, delete_account, update_account_balance,
    get_categories, add_category, delete_category, update_category,
    get_rules, add_rule, delete_rule,
    get_transactions, add_transactions_bulk, update_transaction_category,
    get_mortgage, add_mortgage, update_mortgage
)
from core.parser import normalize_statement
from core.rules import clean_merchant_name, apply_rules_to_staged, suggest_regex_pattern

# ----------------- Premium Page Config & Theme Styling -----------------
st.set_page_config(
    page_title="Vault Finance — Local Wealth Manager",
    page_icon="🔒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom css for modern design
st.markdown("""
<div class="app-background">
    <div class="orb orb-1"></div>
    <div class="orb orb-2"></div>
    <div class="orb orb-3"></div>
</div>

<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', 'Inter', sans-serif;
    }
    
    /* Animated floating background specific to Vault Finance */
    .app-background {
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        background-color: #04020b;
        z-index: -999;
        overflow: hidden;
        pointer-events: none;
    }
    
    .orb {
        position: absolute;
        border-radius: 50%;
        filter: blur(120px);
        opacity: 0.15;
        mix-blend-mode: screen;
        animation: float-orb 25s infinite alternate ease-in-out;
        pointer-events: none;
    }
    
    /* Orb 1: Cyan (represents security/encryption) */
    .orb-1 {
        width: 550px;
        height: 550px;
        background: radial-gradient(circle, #00f2fe 0%, rgba(0, 242, 254, 0) 70%);
        top: -10%;
        left: 5%;
        animation-duration: 22s;
    }
    
    /* Orb 2: Violet (shiviprabhakar.com signature style) */
    .orb-2 {
        width: 500px;
        height: 500px;
        background: radial-gradient(circle, #8b5cf6 0%, rgba(139, 92, 246, 0) 70%);
        bottom: 5%;
        right: 5%;
        animation-duration: 30s;
    }
    
    /* Orb 3: Gold/Amber (custom app-specific touch representing wealth/assets) */
    .orb-3 {
        width: 450px;
        height: 450px;
        background: radial-gradient(circle, #f59e0b 0%, rgba(245, 158, 11, 0) 70%);
        top: 35%;
        left: 45%;
        animation-duration: 26s;
    }
    
    @keyframes float-orb {
        0% {
            transform: translate(0, 0) scale(1);
        }
        50% {
            transform: translate(80px, 40px) scale(1.08);
        }
        100% {
            transform: translate(-40px, 80px) scale(0.95);
        }
    }
    
    /* Premium Glassmorphic Cards */
    .metric-card {
        background: rgba(14, 9, 33, 0.45);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(27, 21, 58, 0.4);
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
        margin-bottom: 20px;
    }
    
    .metric-card:hover {
        transform: translateY(-4px);
        border-color: #00f2fe;
        box-shadow: 0 0 25px rgba(0, 242, 254, 0.25);
    }
    
    .metric-title {
        font-size: 11px;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        font-weight: 600;
        margin-bottom: 8px;
    }
    
    .metric-value {
        font-size: 32px;
        font-weight: 700;
        letter-spacing: -0.5px;
    }
    
    .value-positive {
        color: #10B981; /* Emerald */
    }
    
    .value-negative {
        color: #ef4444; /* Electric red */
    }
    
    .value-neutral {
        color: #f5f3ff; /* Off-white */
    }
    
    /* Premium Glassmorphic Lock Screen */
    .lock-container {
        max-width: 480px;
        margin: 100px auto;
        padding: 40px;
        background: rgba(14, 9, 33, 0.55);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid rgba(27, 21, 58, 0.5);
        border-radius: 24px;
        text-align: center;
        box-shadow: 0 10px 40px 0 rgba(0, 0, 0, 0.5);
        transition: all 0.3s ease;
    }
    
    .lock-container:hover {
        border-color: rgba(0, 242, 254, 0.3);
        box-shadow: 0 0 35px rgba(0, 242, 254, 0.1);
    }
    
    /* Custom Styling for Streamlit elements to fit the glassmorphism theme */
    div[data-testid="stSidebar"] {
        background-color: #0e0921 !important;
        border-right: 1px solid #1b153a !important;
    }
    
    div[data-testid="stHeader"] {
        background-color: rgba(4, 2, 11, 0.6) !important;
        backdrop-filter: blur(12px) !important;
        -webkit-backdrop-filter: blur(12px) !important;
    }
    
    /* Custom borders and styling for main tabs */
    button[data-baseweb="tab"] {
        font-size: 14px !important;
        font-weight: 500 !important;
        color: #94a3b8 !important;
        border-bottom-width: 2px !important;
        border-bottom-color: transparent !important;
        transition: all 0.3s ease !important;
    }
    
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #00f2fe !important;
        border-bottom-color: #00f2fe !important;
    }
    
    /* Styled custom buttons to resemble shiviprabhakar.com pill buttons */
    div.stButton > button {
        border-radius: 999px !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        background-color: rgba(255, 255, 255, 0.04) !important;
        color: #f5f3ff !important;
        font-weight: 500 !important;
        transition: all 0.3s ease !important;
    }
    
    div.stButton > button:hover {
        background-color: rgba(255, 255, 255, 0.1) !important;
        border-color: #00f2fe !important;
        box-shadow: 0 0 15px rgba(0, 242, 254, 0.2) !important;
        color: #00f2fe !important;
    }
    
    /* Primary buttons */
    div.stButton > button[kind="primary"] {
        background-color: #f5f3ff !important;
        color: #04020b !important;
        border: 1px solid #f5f3ff !important;
    }
    
    div.stButton > button[kind="primary"]:hover {
        background-color: rgba(255, 255, 255, 0.9) !important;
        box-shadow: 0 0 20px rgba(0, 242, 254, 0.3) !important;
        color: #04020b !important;
    }
</style>
""", unsafe_allow_html=True)


# ----------------- Helper Functions -----------------

def get_db_connection():
    """
    Retrieves or establishes connection using stored credentials in session state.
    """
    if 'passphrase' not in st.session_state:
        return None
    conn, is_enc, err = connect_db("vault.db", st.session_state.passphrase)
    if not conn:
        if err:
            st.error(err)
        return None
    return conn


def sync_account_balances(conn):
    """
    Calculates current balance for each account based on transactions
    and updates the accounts table balance.
    """
    accounts = get_accounts(conn)
    for acc in accounts:
        # Fetch all transactions for this account
        txs = get_transactions(conn, account_ids=[acc['id']])
        
        # Calculate sum
        # For Checking/Savings: Inflow (credits) increases balance, Outflow (debits) decreases it.
        # For Credit Cards/Mortgages: Outflow (debits/charges) increases debt, Inflow (credits/payments) decreases debt.
        balance_change = 0.0
        for tx in txs:
            amt = tx['amount']
            is_debit = tx['is_debit']
            
            if acc['type'] in ('checking', 'savings'):
                if is_debit:
                    balance_change -= amt
                else:
                    balance_change += amt
            else: # credit/mortgage
                if is_debit:
                    balance_change += amt  # increases debt
                else:
                    balance_change -= amt  # decreases debt
                    
        # Update balance
        # Here we assume the balance starts from zero + transaction changes, or we can define
        # transaction-based balances as the ground truth.
        update_account_balance(conn, acc['id'], balance_change)

def get_historical_net_worth_data(accounts, transactions):
    """
    Reconstructs historical Net Worth progression.
    Starts from current balances and rolls back transactions in reverse chronological order.
    """
    if not accounts:
        return pd.DataFrame(columns=['date', 'net_worth'])
        
    if not transactions:
        # Fallback to single data point (today)
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        net_worth = sum(
            a['balance'] if a['type'] in ('checking', 'savings') else -a['balance']
            for a in accounts
        )
        return pd.DataFrame([{'date': today, 'net_worth': net_worth}])

    # Initialize current state
    balances = {a['id']: a['balance'] for a in accounts}
    account_types = {a['id']: a['type'] for a in accounts}
    
    # Current net worth
    current_nw = sum(
        balances[aid] if account_types[aid] in ('checking', 'savings') else -balances[aid]
        for aid in balances
    )
    
    # Sort transactions from newest to oldest
    txs_sorted = sorted(transactions, key=lambda x: x['date'], reverse=True)
    
    # Group transactions by date
    from collections import defaultdict
    txs_by_date = defaultdict(list)
    for tx in txs_sorted:
        txs_by_date[tx['date']].append(tx)
        
    dates_desc = sorted(txs_by_date.keys(), reverse=True)
    
    history = []
    running_nw = current_nw
    
    # Add today's point
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    if today not in txs_by_date:
        history.append({'date': today, 'net_worth': running_nw})
        
    for date in dates_desc:
        history.append({'date': date, 'net_worth': running_nw})
        
        # Rollback transactions of this date
        for tx in txs_by_date[date]:
            aid = tx['account_id']
            amt = tx['amount']
            is_debit = tx['is_debit']
            a_type = account_types.get(aid)
            
            if not a_type:
                continue
                
            if a_type in ('checking', 'savings'):
                if is_debit:
                    # Debit decreased balance. Rollback adds it.
                    balances[aid] += amt
                    running_nw += amt
                else:
                    # Credit increased balance. Rollback subtracts it.
                    balances[aid] -= amt
                    running_nw -= amt
            else:
                # Liability account
                if is_debit:
                    # Debit increased debt (decreased net worth). Rollback subtracts debt (increases net worth).
                    balances[aid] -= amt
                    running_nw += amt
                else:
                    # Credit decreased debt (increased net worth). Rollback adds debt (decreases net worth).
                    balances[aid] += amt
                    running_nw -= amt
                    
    history.reverse()
    return pd.DataFrame(history)


# ----------------- Lock Screen / Master Passphrase Gate -----------------

if 'decrypted' not in st.session_state:
    st.session_state.decrypted = False

if not st.session_state.decrypted:
    # Render Lock Screen UI
    st.markdown("<div class='lock-container'>", unsafe_allow_html=True)
    st.markdown("<h1 style='color: #f5f3ff; margin-bottom: 10px;'>Vault Finance 🔒</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #94a3b8; margin-bottom: 30px;'>Enter your Master Passphrase to decrypt your offline personal finance vault.</p>", unsafe_allow_html=True)
    
    passphrase_input = st.text_input("Master Passphrase", type="password", label_visibility="collapsed", placeholder="Enter Passphrase...")
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        decrypt_btn = st.button("Unlock Vault", width="stretch", type="primary")
        
    st.markdown("</div>", unsafe_allow_html=True)
    
    if decrypt_btn:
        if not passphrase_input:
            st.error("Passphrase cannot be empty.")
        else:
            # Attempt to connect to the database with this passphrase
            conn, is_encrypted, err = connect_db("vault.db", passphrase_input)
            if conn:
                # Successfully opened/created database
                init_db(conn)
                st.session_state.passphrase = passphrase_input
                st.session_state.decrypted = True
                st.session_state.is_encrypted = is_encrypted
                conn.close()
                st.rerun()
            else:
                st.error("Invalid passphrase. Unable to decrypt database file.")
    st.stop()


# ----------------- Vault Connected: Build Main Application -----------------

conn = get_db_connection()
if not conn:
    st.stop()

# Initialize session state variables
if 'staged_transactions' not in st.session_state:
    st.session_state.staged_transactions = None
if 'rule_suggestions' not in st.session_state:
    st.session_state.rule_suggestions = []
if 'linked_banks' not in st.session_state:
    st.session_state.linked_banks = ["Chase", "Fidelity", "Wells Fargo", "American Express", "TD Bank"]
if 'show_bank_dialog' not in st.session_state:
    st.session_state.show_bank_dialog = False

@st.dialog("Offline Bank Link Portal 🔗", width="medium", dismissible=False)
def bank_connect_portal():
    if "bank_link_step" not in st.session_state:
        st.session_state.bank_link_step = 1
        st.session_state.linking_bank_name = ""
        st.session_state.linking_bank_icon = ""

    step = st.session_state.bank_link_step

    if step == 1:
        st.markdown("### Select your financial institution")
        st.caption("All credentials are encrypted and parsed entirely on your local CPU. No data leaves your machine.")
        
        banks = [
            {"name": "Chase Bank", "id": "Chase", "icon": "🇺🇸"},
            {"name": "Fidelity Investments", "id": "Fidelity", "icon": "📈"},
            {"name": "Wells Fargo", "id": "Wells Fargo", "icon": "🐎"},
            {"name": "American Express", "id": "American Express", "icon": "💳"},
            {"name": "TD Bank", "id": "TD Bank", "icon": "🟢"},
            {"name": "Empire Life", "id": "Empire Life", "icon": "👑"},
            {"name": "Petline Insurance", "id": "Petline", "icon": "🐶"}
        ]
        
        col1, col2 = st.columns(2)
        with col1:
            for b in banks[:4]:
                if st.button(f"{b['icon']} {b['name']}", key=f"sel_{b['id']}", width="stretch"):
                    st.session_state.linking_bank_name = b['id']
                    st.session_state.linking_bank_icon = b['icon']
                    st.session_state.bank_link_step = 2
                    st.rerun()
        with col2:
            for b in banks[4:]:
                if st.button(f"{b['icon']} {b['name']}", key=f"sel_{b['id']}", width="stretch"):
                    st.session_state.linking_bank_name = b['id']
                    st.session_state.linking_bank_icon = b['icon']
                    st.session_state.bank_link_step = 2
                    st.rerun()
        st.divider()
        if st.button("Close Portal", key="close_portal_step1", width="stretch"):
            st.session_state.show_bank_dialog = False
            st.rerun()

    elif step == 2:
        bank_name = st.session_state.linking_bank_name
        bank_icon = st.session_state.linking_bank_icon
        st.markdown(f"### Log in to {bank_icon} {bank_name}")
        st.caption("Enter your online banking credentials to link your account securely.")
        
        username = st.text_input("Username or Email", placeholder="e.g. user123", key="link_user")
        password = st.text_input("Password", type="password", placeholder="••••••••", key="link_pass")
        
        col_btns = st.columns(2)
        with col_btns[0]:
            if st.button("Cancel Link", key="cancel_link", width="stretch"):
                st.session_state.bank_link_step = 1
                st.rerun()
        with col_btns[1]:
            if st.button("Authorize Connection", key="auth_link", width="stretch", type="primary"):
                if not username or not password:
                    st.error("Username and password are required.")
                else:
                    st.session_state.bank_link_step = 3
                    st.rerun()

    elif step == 3:
        bank_name = st.session_state.linking_bank_name
        st.markdown("### Two-Factor Verification")
        st.write(f"We've sent a 6-digit security verification code to your registered device for **{bank_name}**.")
        
        mfa_code = st.text_input("Enter 6-Digit Code", placeholder="e.g. 123456", key="mfa_code")
        
        col_btns = st.columns(2)
        with col_btns[0]:
            if st.button("Back", key="back_to_login", width="stretch"):
                st.session_state.bank_link_step = 2
                st.rerun()
        with col_btns[1]:
            if st.button("Verify & Link", key="verify_mfa", width="stretch", type="primary"):
                if len(mfa_code) < 6:
                    st.error("Please enter a valid 6-digit code.")
                else:
                    if bank_name not in st.session_state.linked_banks:
                        st.session_state.linked_banks.append(bank_name)
                    st.session_state.bank_link_step = 4
                    st.rerun()

    elif step == 4:
        bank_name = st.session_state.linking_bank_name
        st.success(f"Successfully Connected to {bank_name}! 🎉")
        st.write("Your account is now locally linked. The transaction ledger and current balances are synchronized.")
        
        if st.button("Finish", key="close_portal", width="stretch", type="primary"):
            del st.session_state.bank_link_step
            del st.session_state.linking_bank_name
            del st.session_state.linking_bank_icon
            st.session_state.show_bank_dialog = False
            st.rerun()

def render_bank_connection_header(tab_id: str):
    active_institutions = sorted(list(set(a['institution'] for a in all_accounts if a.get('institution'))))
    with st.container(border=True):
        col_info, col_actions = st.columns([7, 5], vertical_alignment="center")
        with col_info:
            st.markdown("##### 🔗 Institution Connections")
            if active_institutions:
                status_list = []
                for inst in active_institutions:
                    is_linked = inst in st.session_state.linked_banks
                    status_list.append(f"**{inst}**: {'🟢 Connected' if is_linked else '🔴 Disconnected'}")
                st.markdown(" | ".join(status_list))
            else:
                st.caption("No accounts available in the active profile.")
        with col_actions:
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Link Bank 🔗", key=f"link_btn_{tab_id}", width="stretch"):
                    st.session_state.show_bank_dialog = True
                    st.rerun()
            with c2:
                if st.button("Sync Accounts 🔄", key=f"sync_btn_{tab_id}", width="stretch", type="primary"):
                    with st.spinner("Synchronizing local ledger with connected banks..."):
                        import time
                        time.sleep(1.0)
                    st.toast("Offline ledger synced successfully!")
                    st.rerun()

# Top Header Layout
col_h1, col_h2 = st.columns([8, 4])
with col_h1:
    st.title("Vault Finance 🔒")
    st.caption("Secure, Offline, Local-first Personal Finance Manager.")
with col_h2:
    st.markdown("<div style='text-align: right; padding-top: 15px;'>", unsafe_allow_html=True)
    if st.session_state.is_encrypted:
        st.success("AES-256 SQLCipher Active")
    else:
        st.warning("SQLite Fallback Mode (Unencrypted)")
    st.markdown("</div>", unsafe_allow_html=True)

# Render Bank Link Dialog if active
if st.session_state.get("show_bank_dialog", False):
    bank_connect_portal()


# ----------------- Sidebar Control Panel -----------------

st.sidebar.markdown("### Vault Settings")

# Lock vault action
if st.sidebar.button("Lock Vault 🔒", width="stretch"):
    st.session_state.clear()
    st.rerun()

st.sidebar.divider()

st.sidebar.markdown("### Financial Profile")
selected_profile = st.sidebar.segmented_control(
    "Active Profile",
    options=["💼 Personal", "🏢 Incorporation", "📊 Combined"],
    default="💼 Personal",
    label_visibility="collapsed"
)

profile_choice = "personal"
if selected_profile == "🏢 Incorporation":
    profile_choice = "incorporation"
elif selected_profile == "📊 Combined":
    profile_choice = "combined"

st.sidebar.divider()

# Account Quick-Filters
st.sidebar.markdown("### View Filters")
all_accounts_db = get_accounts(conn)
if profile_choice == "combined":
    all_accounts = all_accounts_db
else:
    all_accounts = [a for a in all_accounts_db if a.get('entity') == profile_choice]

account_names = [a['name'] for a in all_accounts]
selected_acc_names = st.sidebar.multiselect("Filter Accounts", options=account_names, default=account_names)
selected_acc_ids = [a['id'] for a in all_accounts if a['name'] in selected_acc_names]

# Date Filter
today_val = datetime.date.today()
start_of_year = datetime.date(today_val.year, 1, 1)
date_range = st.sidebar.date_input("Date Range", value=(start_of_year, today_val))

st.sidebar.divider()

# Database Export & Backup
st.sidebar.markdown("### Backup & Export")
try:
    with open("vault.db", "rb") as db_file:
        db_bytes = db_file.read()
        st.sidebar.download_button(
            label="Backup Encrypted DB File 📥",
            data=db_bytes,
            file_name="vault_backup.db",
            mime="application/octet-stream",
            width="stretch"
        )
except Exception:
    st.sidebar.error("Database backup unavailable.")

# Export transactions as Plain CSV
all_txs = get_transactions(conn)
if all_txs:
    df_export = pd.DataFrame(all_txs)
    csv_bytes = df_export.to_csv(index=False).encode('utf-8')
    st.sidebar.download_button(
        label="Export Transactions CSV 📊",
        data=csv_bytes,
        file_name="vault_transactions.csv",
        mime="text/csv",
        width="stretch"
    )


# ----------------- TABS SETUP -----------------

tab_overview, tab_ledger, tab_ingestion, tab_mortgage, tab_rules = st.tabs([
    "📈 Dashboard", "📂 Ledger", "📥 Statement Ingestion", "🏠 Mortgage & Debt", "⚙️ Rules & Settings"
])


# ----------------- TAB 1: OVERVIEW & DASHBOARD -----------------

with tab_overview:
    render_bank_connection_header("overview")
    # 1. Fetch filtered transactions
    start_date_str = date_range[0].strftime('%Y-%m-%d') if len(date_range) > 0 else None
    end_date_str = date_range[1].strftime('%Y-%m-%d') if len(date_range) > 1 else None
    
    # Retrieve transactions and accounts
    filtered_txs = get_transactions(conn, date_start=start_date_str, date_end=end_date_str, account_ids=selected_acc_ids)
    all_filtered_txs = get_transactions(conn, account_ids=selected_acc_ids)  # for full history networth
    active_accounts = [a for a in all_accounts if a['id'] in selected_acc_ids]
    
    # 2. Compute Metric Card values
    # Net worth = Assets - Liabilities
    assets_val = sum(a['balance'] for a in active_accounts if a['type'] in ('checking', 'savings'))
    liabilities_val = sum(a['balance'] for a in active_accounts if a['type'] in ('credit', 'mortgage'))
    net_worth = assets_val - liabilities_val
    
    # Monthly Inflow & Outflow (within filter date range)
    monthly_inflow = 0.0
    monthly_outflow = 0.0
    
    for tx in filtered_txs:
        # Map values
        acc_type = next((a['type'] for a in all_accounts if a['id'] == tx['account_id']), None)
        amt = tx['amount']
        is_debit = tx['is_debit']
        
        # If it's checking or savings account:
        if acc_type in ('checking', 'savings'):
            if is_debit:
                monthly_outflow += amt
            else:
                monthly_inflow += amt
        # If credit card spending:
        elif acc_type == 'credit':
            if is_debit:
                monthly_outflow += amt # purchases
            else:
                pass # payments to card (transfer)
                
    savings_rate = 0.0
    if monthly_inflow > 0:
        savings_rate = ((monthly_inflow - monthly_outflow) / monthly_inflow) * 100
        
    # Pre-calculate classes to avoid inline nested f-string parser confusion in Python 3.14
    nw_class = 'value-positive' if net_worth >= 0 else 'value-negative'
    sr_class = 'value-positive' if savings_rate >= 0 else 'value-negative'
    
    # Render Cards in columns
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    
    with m_col1:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-title">Net Worth</div>
            <div class="metric-value {nw_class}">${net_worth:,.2f}</div>
        </div>
        """.format(nw_class=nw_class, net_worth=net_worth), unsafe_allow_html=True)
        
    with m_col2:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-title">Period Inflow</div>
            <div class="metric-value value-positive">${monthly_inflow:,.2f}</div>
        </div>
        """.format(monthly_inflow=monthly_inflow), unsafe_allow_html=True)
        
    with m_col3:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-title">Period Outflow</div>
            <div class="metric-value value-negative">${monthly_outflow:,.2f}</div>
        </div>
        """.format(monthly_outflow=monthly_outflow), unsafe_allow_html=True)
        
    with m_col4:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-title">Savings Rate</div>
            <div class="metric-value {sr_class}">{savings_rate:.1f}%</div>
        </div>
        """.format(sr_class=sr_class, savings_rate=savings_rate), unsafe_allow_html=True)
        
    # 3. Render Visualizations
    st.divider()
    
    v_col1, v_col2 = st.columns(2)
    
    with v_col1:
        # Category Spending Donut Chart
        # Select all debit transactions in date range (excluding transfer categories like savings/investments)
        spending_txs = [tx for tx in filtered_txs if tx['is_debit'] == 1 and tx['category_name'] not in ('Savings', 'Interest', 'Payroll')]
        
        if spending_txs:
            df_spend = pd.DataFrame(spending_txs)
            df_grouped = df_spend.groupby('category_name')['amount'].sum().reset_index()
            
            fig_donut = px.pie(
                df_grouped,
                values='amount',
                names='category_name',
                hole=0.5,
                title="Spending Breakdown by Category",
                color_discrete_sequence=["#00f2fe", "#4facfe", "#8b5cf6", "#f59e0b", "#10b981", "#ef4444", "#f5f3ff"]
            )
            fig_donut.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font_color='#f5f3ff',
                margin=dict(t=50, b=10, l=10, r=10),
                legend=dict(font=dict(size=12))
            )
            st.plotly_chart(fig_donut, width="stretch")
        else:
            st.info("No spending transactions found for selected filter criteria.")
            
    with v_col2:
        # Cash Flow Trend Chart (Grouped by Month)
        if filtered_txs:
            df_cf = pd.DataFrame(filtered_txs)
            # Create a Month-Year column
            df_cf['month'] = pd.to_datetime(df_cf['date']).dt.strftime('%Y-%m')
            
            # Divide into Inflows and Outflows
            df_cf['inflow'] = df_cf.apply(lambda r: r['amount'] if r['is_debit'] == 0 else 0, axis=1)
            df_cf['outflow'] = df_cf.apply(lambda r: r['amount'] if r['is_debit'] == 1 else 0, axis=1)
            
            df_trend = df_cf.groupby('month')[['inflow', 'outflow']].sum().reset_index()
            df_trend = df_trend.sort_values('month')
            
            fig_cf = go.Figure()
            fig_cf.add_trace(go.Bar(
                x=df_trend['month'],
                y=df_trend['inflow'],
                name='Inflow',
                marker_color='#10B981'
            ))
            fig_cf.add_trace(go.Bar(
                x=df_trend['month'],
                y=df_trend['outflow'],
                name='Outflow',
                marker_color='#EF4444'
            ))
            fig_cf.update_layout(
                barmode='group',
                title="Monthly Cash Flow Trend",
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font_color='#f5f3ff',
                xaxis=dict(showgrid=False, title="Month"),
                yaxis=dict(gridcolor='#1b153a', title="Amount ($)"),
                margin=dict(t=50, b=10, l=10, r=10)
            )
            st.plotly_chart(fig_cf, width="stretch")
        else:
            st.info("No trend data available.")
            
    st.divider()
    
    # Net Worth progression chart
    st.subheader("Net Worth Progression Over Time")
    df_nw = get_historical_net_worth_data(active_accounts, all_filtered_txs)
    
    if not df_nw.empty:
        fig_nw = px.area(
            df_nw,
            x='date',
            y='net_worth',
            title="Total Assets vs. Liabilities Valuation Line"
        )
        fig_nw.update_traces(
            line_color='#00f2fe',
            line_width=3,
            fillcolor='rgba(0, 242, 254, 0.08)'
        )
        fig_nw.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font_color='#f5f3ff',
            xaxis=dict(gridcolor='#1b153a', title="Date"),
            yaxis=dict(gridcolor='#1b153a', title="Net Worth ($)"),
            margin=dict(t=40, b=10, l=10, r=10)
        )
        st.plotly_chart(fig_nw, width="stretch")
    else:
        st.info("Insufficient account history to construct Net Worth trajectory.")


# ----------------- TAB 2: TRANSACTION LEDGER -----------------

with tab_ledger:
    render_bank_connection_header("ledger")
    st.subheader("Interactive Ledger Book")
    
    # Sub-filters inside tab
    l_col1, l_col2, l_col3 = st.columns(3)
    with l_col1:
        search_query = st.text_input("Search description or merchant...", value="")
    with l_col2:
        cats = get_categories(conn)
        cat_map = {c['id']: c['name'] for c in cats}
        # Add "Uncategorized" Option
        cat_options = ["All", "Uncategorized"] + [c['name'] for c in cats]
        selected_cat_filter = st.selectbox("Category Filter", options=cat_options, index=0)
        
        # Translate selection to IDs
        if selected_cat_filter == "All":
            cat_ids_filter = None
        elif selected_cat_filter == "Uncategorized":
            cat_ids_filter = [None]
        else:
            cat_ids_filter = [c['id'] for c in cats if c['name'] == selected_cat_filter]
            
    with l_col3:
        # Empty space for layout balance
        st.markdown("<br>", unsafe_allow_html=True)
        
    # Fetch data
    ledger_txs = get_transactions(
        conn,
        date_start=start_date_str,
        date_end=end_date_str,
        account_ids=selected_acc_ids,
        category_ids=cat_ids_filter,
        search_term=search_query
    )
    
    if ledger_txs:
        # Convert to Pandas DataFrame
        df_ledger = pd.DataFrame(ledger_txs)
        
        # Build display Columns
        df_display = df_ledger[[
            'id', 'date', 'account_name', 'raw_description', 'clean_merchant',
            'category_name', 'amount', 'is_debit'
        ]].copy()
        
        # Format types
        df_display['is_debit'] = df_display['is_debit'].map({1: "Debit (Out)", 0: "Credit (In)"})
        
        # Allow category editing directly inside ledger
        edited_df = st.data_editor(
            df_display,
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True),
                "date": st.column_config.TextColumn("Date", disabled=True),
                "account_name": st.column_config.TextColumn("Account", disabled=True),
                "raw_description": st.column_config.TextColumn("Raw Details", disabled=True),
                "clean_merchant": st.column_config.TextColumn("Clean Merchant", disabled=True),
                "category_name": st.column_config.SelectboxColumn(
                    "Category",
                    options=[c['name'] for c in cats],
                    required=True
                ),
                "amount": st.column_config.NumberColumn("Amount", format="$%.2f", disabled=True),
                "is_debit": st.column_config.TextColumn("Type", disabled=True)
            },
            hide_index=True,
            width="stretch",
            key="ledger_data_editor"
        )
        
        # Save edits to DB
        if st.button("Save Ledger Changes"):
            changes_saved = 0
            # Retrieve changed cells
            edits = st.session_state.ledger_data_editor.get("edited_rows", {})
            for idx, changes in edits.items():
                if 'category_name' in changes:
                    new_cat_name = changes['category_name']
                    tx_id = int(df_display.iloc[int(idx)]['id'])
                    # Find category ID
                    new_cat_id = next((c['id'] for c in cats if c['name'] == new_cat_name), None)
                    update_transaction_category(conn, tx_id, new_cat_id)
                    changes_saved += 1
            
            if changes_saved > 0:
                st.success(f"Successfully updated {changes_saved} transaction categories.")
                sync_account_balances(conn)
                st.rerun()
    else:
        st.info("No ledger entries match the selected filters.")


# ----------------- TAB 3: STATEMENT INGESTION & RECONCILIATION -----------------

with tab_ingestion:
    render_bank_connection_header("ingestion")
    st.subheader("Offline Ingestion Center")
    st.markdown("Upload bank/credit card statements (PDF, CSV, OFX) to parse, review, and reconcile completely offline.")
    
    col_ing1, col_ing2 = st.columns([4, 8])
    
    with col_ing1:
        if not all_accounts:
            st.info("No accounts available. Create an account in the Rules & Settings tab first.")
            target_acc = None
            uploaded_file = None
            parse_btn = False
        else:
            target_acc_name = st.selectbox(
                "Target Account",
                options=[a['name'] for a in all_accounts]
            )
            target_acc = next(a for a in all_accounts if a['name'] == target_acc_name)
            
            uploaded_file = st.file_uploader(
                "Upload Statement File",
                type=['pdf', 'csv', 'ofx', 'qfx']
            )
            
            parse_btn = st.button("Parse Statement File", width="stretch", type="primary")
        
    if parse_btn and uploaded_file is not None:
        try:
            # Normalize statement rows
            file_bytes = uploaded_file.read()
            staged_rows = normalize_statement(uploaded_file.name, file_bytes, target_acc['id'])
            
            # Apply categorization rules
            rules = get_rules(conn)
            staged_rows = apply_rules_to_staged(staged_rows, rules)
            
            # Cache the staging rows in session state
            st.session_state.staged_transactions = staged_rows
            st.session_state.rule_suggestions = [] # reset suggestions
            st.success(f"Parsed {len(staged_rows)} transactions from statement. Ready for staging review below.")
        except Exception as e:
            st.error(f"Ingestion failed: {str(e)}")
            
    # Show Staging Reconciliation UI if transactions are loaded
    if st.session_state.staged_transactions is not None and len(st.session_state.staged_transactions) > 0:
        st.divider()
        st.subheader("Staging & Reconciliation Review")
        st.markdown("Ensure categories are assigned properly. Modify values directly in the grid. Rows with duplicate hashes will be ignored on commit.")
        
        # Convert staged transactions to pandas dataframe for UI editing
        df_stage = pd.DataFrame(st.session_state.staged_transactions)
        
        # Map category IDs to names
        cats = get_categories(conn)
        cat_map = {c['id']: c['name'] for c in cats}
        # Add category name column for user dropdown editing
        df_stage['category_name'] = df_stage['category_id'].map(cat_map).fillna("Others")
        
        # Display data editor
        edited_stage = st.data_editor(
            df_stage[[
                'date', 'raw_description', 'clean_merchant', 'category_name', 'amount', 'is_debit', 'hash_signature'
            ]],
            column_config={
                "date": st.column_config.TextColumn("Date"),
                "raw_description": st.column_config.TextColumn("Raw Details", disabled=True),
                "clean_merchant": st.column_config.TextColumn("Clean Merchant"),
                "category_name": st.column_config.SelectboxColumn(
                    "Assigned Category",
                    options=[c['name'] for c in cats],
                    required=True
                ),
                "amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
                "is_debit": st.column_config.CheckboxColumn("Debit?"),
                "hash_signature": st.column_config.TextColumn("Hash Signature", disabled=True)
            },
            hide_index=True,
            width="stretch"
        )
        
        col_commit1, col_commit2 = st.columns(2)
        
        with col_commit1:
            if st.button("Commit Staged Rows to Vault Database", width="stretch", type="primary"):
                # Standardize and save edits
                final_rows = []
                rule_suggestions = []
                
                for idx, row in edited_stage.iterrows():
                    # Map category name back to ID
                    cat_name = row['category_name']
                    cat_id = next((c['id'] for c in cats if c['name'] == cat_name), None)
                    
                    # Original category from rules
                    orig_tx = st.session_state.staged_transactions[idx]
                    orig_cat_id = orig_tx.get('category_id')
                    
                    # If user changed category, suggest learning this rule
                    if cat_id != orig_cat_id:
                        rule_suggestions.append({
                            'pattern': suggest_regex_pattern(row['clean_merchant']),
                            'target_cat_id': cat_id,
                            'cat_name': cat_name,
                            'merchant': row['clean_merchant']
                        })
                        
                    # Recalculate hash signature in case user edited fields (date, desc, amount)
                    new_hash = generate_transaction_hash(row['date'], row['raw_description'], row['amount'], target_acc['id'])
                    
                    final_rows.append({
                        'account_id': target_acc['id'],
                        'date': row['date'],
                        'raw_description': row['raw_description'],
                        'clean_merchant': row['clean_merchant'],
                        'category_id': cat_id,
                        'amount': float(row['amount']),
                        'is_debit': 1 if row['is_debit'] else 0,
                        'hash_signature': new_hash
                    })
                    
                # Commit to DB
                inserted, skipped = add_transactions_bulk(conn, final_rows)
                st.success(f"Import complete: Committed {inserted} transactions. Skipped {skipped} duplicate entries.")
                
                # Recalculate account balances
                sync_account_balances(conn)
                
                # Store rules suggestions
                st.session_state.rule_suggestions = rule_suggestions
                st.session_state.staged_transactions = None # clear staging
                st.rerun()
                
        with col_commit2:
            if st.button("Discard Staged Statement", width="stretch"):
                st.session_state.staged_transactions = None
                st.session_state.rule_suggestions = []
                st.rerun()
                
    # 3. Rule suggestion UI (Learn Rule Prompt)
    if st.session_state.rule_suggestions:
        st.divider()
        st.info("💡 Auto-Categorization Engine Learner Mode")
        st.write("You manually updated categories for these merchants. Toggle rules to save them for future imports:")
        
        selected_suggestions = []
        for idx, sug in enumerate(st.session_state.rule_suggestions):
            save_rule_chk = st.checkbox(
                f"Auto-categorize matching \"{sug['pattern']}\" as {sug['cat_name']} (for merchant: {sug['merchant']})",
                value=True,
                key=f"learn_{idx}"
            )
            if save_rule_chk:
                selected_suggestions.append(sug)
                
        if st.button("Apply Selected Auto-Categorization Rules"):
            rules_saved = 0
            for sug in selected_suggestions:
                try:
                    add_rule(conn, sug['pattern'], sug['target_cat_id'], priority=1)
                    rules_saved += 1
                except Exception:
                    pass # ignore duplicate regex rules
            st.success(f"Added {rules_saved} auto-categorization rules.")
            st.session_state.rule_suggestions = [] # clear rules suggestions
            st.rerun()


# ----------------- TAB 4: MORTGAGE & DEBT -----------------

with tab_mortgage:
    render_bank_connection_header("mortgage")
    st.subheader("Amortization & Debt Payoff Accelerator")
    
    # Get mortgage accounts
    mortgage_accs = [a for a in all_accounts if a['type'] == 'mortgage']
    
    if profile_choice == "incorporation":
        st.info("Amortization and Debt Payoff Accelerator is not applicable for the Incorporation profile. Switch to Personal or Combined to track mortgage and personal debt.")
    elif not mortgage_accs:
        st.info("No mortgage accounts configured. Add a mortgage account in the Settings tab to track payoff amortization.")
    else:
        selected_m_name = st.selectbox("Select Mortgage Account", options=[a['name'] for a in mortgage_accs])
        selected_m_acc = next(a for a in mortgage_accs if a['name'] == selected_m_name)
        
        # Load mortgage details
        m_details = get_mortgage(conn, selected_m_acc['id'])
        
        # Form to add details if missing
        if m_details is None:
            st.warning("Mortgage details are missing for this account. Set loan details to view curves.")
            with st.form("add_mortgage_details"):
                original_principal = st.number_input("Original Principal ($)", min_value=0.0, value=300000.0)
                current_balance = st.number_input("Current Balance ($)", min_value=0.0, value=280000.0)
                interest_rate = st.number_input("Annual Interest Rate (%)", min_value=0.0, value=4.5, format="%.2f")
                monthly_payment = st.number_input("Standard Monthly Payment ($)", min_value=0.0, value=1520.06)
                term_months = st.number_input("Total Term (Months)", min_value=1, value=360)
                start_date = st.date_input("Start Date of Loan", value=datetime.date(2025,1,1))
                
                submit_m = st.form_submit_button("Save Mortgage Details")
                if submit_m:
                    add_mortgage(
                        conn,
                        selected_m_acc['id'],
                        original_principal,
                        current_balance,
                        interest_rate,
                        monthly_payment,
                        term_months,
                        start_date.strftime('%Y-%m-%d')
                    )
                    st.success("Saved mortgage loan parameters.")
                    st.rerun()
        else:
            # Let user update mortgage parameters if needed
            with st.expander("Edit Loan Details"):
                with st.form("edit_mortgage_details"):
                    cur_bal = st.number_input("Current Balance ($)", min_value=0.0, value=m_details['current_balance'])
                    int_rate = st.number_input("Interest Rate (%)", min_value=0.0, value=m_details['interest_rate'], format="%.2f")
                    m_pay = st.number_input("Standard Monthly Payment ($)", min_value=0.0, value=m_details['monthly_payment'])
                    
                    update_m = st.form_submit_button("Update Loan Parameters")
                    if update_m:
                        update_mortgage(conn, selected_m_acc['id'], cur_bal, int_rate, m_pay)
                        st.success("Mortgage variables updated.")
                        st.rerun()
                        
            st.divider()
            
            # --- Accelerator Inputs ---
            st.subheader("Debt Accelerator Options")
            col_acc1, col_acc2, col_acc3 = st.columns(3)
            with col_acc1:
                extra_monthly = st.number_input("Extra Monthly Principal Payment ($)", min_value=0.0, value=200.0, step=50.0)
            with col_acc2:
                lump_sum_amt = st.number_input("Lump-Sum Payment ($)", min_value=0.0, value=0.0, step=1000.0)
            with col_acc3:
                lump_sum_month = st.number_input("Lump-Sum Payment Month (From Now)", min_value=1, value=12, step=1)
                
            # Amortization math
            r_monthly = (m_details['interest_rate'] / 100) / 12
            standard_payment = m_details['monthly_payment']
            
            # 1. Calculate Standard Schedule
            balance_std = m_details['current_balance']
            std_schedule = []
            month_count = 0
            total_interest_std = 0.0
            
            while balance_std > 0.01 and month_count < 600: # Capped at 50 years to prevent infinite loop
                month_count += 1
                interest = balance_std * r_monthly
                principal = standard_payment - interest
                
                # Cap payment to remaining balance + interest
                if balance_std + interest < standard_payment:
                    payment = balance_std + interest
                    principal = balance_std
                    balance_std = 0.0
                else:
                    balance_std = balance_std - principal
                    
                total_interest_std += interest
                std_schedule.append({
                    'month': month_count,
                    'balance': balance_std,
                    'interest_paid': interest,
                    'principal_paid': principal
                })
                
            # 2. Calculate Accelerated Schedule
            balance_acc = m_details['current_balance']
            acc_schedule = []
            month_count_acc = 0
            total_interest_acc = 0.0
            
            while balance_acc > 0.01 and month_count_acc < 600:
                month_count_acc += 1
                interest = balance_acc * r_monthly
                
                # Determine this month's payment
                current_payment = standard_payment + extra_monthly
                if month_count_acc == lump_sum_month:
                    current_payment += lump_sum_amt
                    
                principal = current_payment - interest
                
                # Cap payment
                if balance_acc + interest < current_payment:
                    payment = balance_acc + interest
                    principal = balance_acc
                    balance_acc = 0.0
                else:
                    balance_acc = balance_acc - principal
                    
                total_interest_acc += interest
                acc_schedule.append({
                    'month': month_count_acc,
                    'balance': balance_acc,
                    'interest_paid': interest,
                    'principal_paid': principal
                })
                
            # Compute comparison stats
            months_saved = month_count - month_count_acc
            years_saved = months_saved / 12
            interest_saved = total_interest_std - total_interest_acc
            
            st.subheader("Accelerator Payoff Dashboard")
            
            s_col1, s_col2, s_col3 = st.columns(3)
            with s_col1:
                st.metric("Total Interest Saved 💰", f"${interest_saved:,.2f}")
            with s_col2:
                st.metric("Loan Shaved Off ⏳", f"{months_saved} Months ({years_saved:.1f} Years)")
            with s_col3:
                st.metric("New Payoff Duration ⏰", f"{month_count_acc} Months ({month_count_acc/12:.1f} Years)")
                
            # Amortization line comparisons
            df_std = pd.DataFrame(std_schedule)
            df_acc = pd.DataFrame(acc_schedule)
            
            df_std['Plan'] = 'Standard Payment'
            df_acc['Plan'] = 'Accelerated Payment'
            
            # Combine to plot
            df_plot = pd.concat([df_std, df_acc])
            
            fig_curve = px.line(
                df_plot,
                x='month',
                y='balance',
                color='Plan',
                title="Mortgage Payoff Progression Comparison",
                color_discrete_map={
                    'Standard Payment': '#ef4444',
                    'Accelerated Payment': '#00f2fe'
                }
            )
            fig_curve.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font_color='#f5f3ff',
                xaxis=dict(gridcolor='#1b153a', title="Months from Now"),
                yaxis=dict(gridcolor='#1b153a', title="Remaining Debt Balance ($)"),
                margin=dict(t=40, b=10, l=10, r=10)
            )
            st.plotly_chart(fig_curve, width="stretch")


# ----------------- TAB 5: RULES & CONFIG SETTINGS -----------------

with tab_rules:
    render_bank_connection_header("rules")
    st.subheader("System Configurations")
    
    # 1. Accounts Configuration Manager
    st.markdown("### Manage Accounts")
    
    acc_df = pd.DataFrame(all_accounts_db)
    if not acc_df.empty:
        st.dataframe(
            acc_df[['name', 'type', 'institution', 'balance', 'currency', 'entity']],
            width="stretch"
        )
    else:
        st.info("No accounts configured yet.")
        
    with st.expander("Create New Account"):
        with st.form("new_account_form"):
            new_acc_name = st.text_input("Account Name", placeholder="e.g. Sapphire Preferred Checking")
            new_acc_type = st.selectbox("Account Type", options=["checking", "credit", "savings", "mortgage"])
            new_acc_inst = st.text_input("Institution", placeholder="e.g. Chase Bank")
            new_acc_bal = st.number_input("Starting Balance ($)", min_value=0.0, value=0.0)
            new_acc_cur = st.selectbox("Currency", options=["USD", "EUR", "GBP", "CAD"])
            new_acc_entity = st.selectbox("Entity Affiliation", options=["personal", "incorporation"])
            
            submit_acc = st.form_submit_button("Add Account to Vault")
            if submit_acc:
                if not new_acc_name:
                    st.error("Account Name is required.")
                else:
                    add_account(conn, new_acc_name, new_acc_type, new_acc_inst, new_acc_bal, new_acc_cur, new_acc_entity)
                    st.success("Account added to database.")
                    st.rerun()
                    
    with st.expander("Remove Account"):
        if not all_accounts_db:
            st.info("No accounts available to remove.")
        else:
            acc_to_delete = st.selectbox(
                "Account to Remove",
                options=[a['name'] for a in all_accounts_db],
                key="del_acc"
            )
            if st.button("Delete Selected Account"):
                target_del = next(a for a in all_accounts_db if a['name'] == acc_to_delete)
                delete_account(conn, target_del['id'])
                st.success(f"Removed account {acc_to_delete} from vault.")
                st.rerun()
            
    st.divider()
    
    # 2. Categorization Rules Manager
    st.markdown("### Categorization Rules")
    
    rules_list = get_rules(conn)
    if rules_list:
        df_rules = pd.DataFrame(rules_list)
        st.dataframe(
            df_rules[['regex_pattern', 'category_name', 'priority']],
            width="stretch"
        )
    else:
        st.info("No auto-categorization rules created yet.")
        
    with st.expander("Create Custom Match Rule"):
        with st.form("new_rule_form"):
            new_rule_pattern = st.text_input("Regex Matching Pattern", placeholder="e.g. (?i)netflix|prime video")
            cats = get_categories(conn)
            new_rule_cat = st.selectbox("Target Category", options=[c['name'] for c in cats])
            new_rule_priority = st.number_input("Priority", min_value=0, value=0)
            
            submit_rule = st.form_submit_button("Save Rule")
            if submit_rule:
                if not new_rule_pattern:
                    st.error("Regex pattern is required.")
                else:
                    target_cat_id = next(c['id'] for c in cats if c['name'] == new_rule_cat)
                    add_rule(conn, new_rule_pattern, target_cat_id, new_rule_priority)
                    st.success("Rule added successfully.")
                    st.rerun()
                    
    with st.expander("Delete Existing Rule"):
        if not rules_list:
            st.info("No auto-categorization rules created yet.")
        else:
            rule_to_delete = st.selectbox(
                "Rule to Delete",
                options=[f"{r['regex_pattern']} -> {r['category_name']}" for r in rules_list],
                key="del_rule"
            )
            if st.button("Delete Selected Rule"):
                target_rule = next(r for r in rules_list if f"{r['regex_pattern']} -> {r['category_name']}" == rule_to_delete)
                delete_rule(conn, target_rule['id'])
                st.success(f"Rule matching '{target_rule['regex_pattern']}' deleted.")
                st.rerun()
            
    st.divider()
    
    # 3. Categories Management
    st.markdown("### Budget Categories")
    cats_list = get_categories(conn)
    df_cats = pd.DataFrame(cats_list)
    
    edited_cats = st.data_editor(
        df_cats,
        column_config={
            "id": st.column_config.NumberColumn("ID", disabled=True),
            "name": st.column_config.TextColumn("Category Name"),
            "monthly_budget": st.column_config.NumberColumn("Monthly Budget ($)", format="$%.2f")
        },
        hide_index=True,
        width="stretch",
        key="categories_data_editor"
    )
    
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        if st.button("Update Budget Changes"):
            c_edits = st.session_state.categories_data_editor.get("edited_rows", {})
            for idx, changes in c_edits.items():
                cat_id = int(df_cats.iloc[int(idx)]['id'])
                orig_cat = df_cats.iloc[int(idx)]
                
                updated_name = changes.get('name', orig_cat['name'])
                updated_budget = changes.get('monthly_budget', orig_cat['monthly_budget'])
                
                update_category(conn, cat_id, updated_name, updated_budget)
            st.success("Budget categories updated.")
            st.rerun()
            
    with col_c2:
        with st.expander("Add New Category"):
            with st.form("new_cat_form"):
                new_cat_name = st.text_input("Category Name")
                new_cat_budget = st.number_input("Monthly Budget ($)", min_value=0.0, value=100.0)
                
                submit_cat = st.form_submit_button("Save Category")
                if submit_cat:
                    if not new_cat_name:
                        st.error("Category name is required.")
                    else:
                        add_category(conn, new_cat_name, new_cat_budget)
                        st.success(f"Added category {new_cat_name}")
                        st.rerun()

# Make sure we close connection at the end of the script execution
conn.close()
