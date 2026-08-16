import os
import sqlite3
import datetime
from core.crypto import derive_key, generate_transaction_hash
from core.db import (
    connect_db, init_db, add_account, get_accounts, add_transaction,
    get_categories, add_rule, get_rules, add_mortgage, get_transactions,
    update_account_balance
)

def sync_account_balances(conn):
    """
    Calculates current balance for each account based on transactions
    and updates the accounts table balance.
    """
    accounts = get_accounts(conn)
    for acc in accounts:
        txs = get_transactions(conn, account_ids=[acc['id']])
        
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
                    
        update_account_balance(conn, acc['id'], balance_change)

def seed():
    db_path = "vault.db"
    
    # 1. Clean up existing database
    if os.path.exists(db_path):
        os.remove(db_path)
        print("Removed existing vault.db")

    # 2. Connect and initialize tables
    # Using 'demo123' as our passphrase
    conn, is_encrypted, err = connect_db(db_path, "demo123")
    if not conn:
        print(f"Error connecting to database: {err}")
        return
    
    init_db(conn)
    print("Database schema initialized.")

    # Get default categories and map by name
    categories = {c['name']: c['id'] for c in get_categories(conn)}
    
    # 3. Add Personal accounts
    chase_checking = add_account(conn, "Chase Checking", "checking", "Chase", 0.0, entity="personal")
    fidelity_savings = add_account(conn, "Fidelity Savings", "savings", "Fidelity", 0.0, entity="personal")
    amex_gold = add_account(conn, "Amex Gold Card", "credit", "American Express", 0.0, entity="personal")
    home_mortgage_acc = add_account(conn, "Home Mortgage", "mortgage", "Wells Fargo", 0.0, entity="personal")
    auto_loan = add_account(conn, "Ford Auto Loan", "credit", "Ford Motor Credit", 0.0, entity="personal")
    
    # Add Incorporation accounts
    td_business = add_account(conn, "TD Business Checking", "checking", "TD Bank", 0.0, entity="incorporation")
    visa_business = add_account(conn, "Visa Business Card", "credit", "Chase Business", 0.0, entity="incorporation")
    
    print("Accounts created for both Personal and Incorporation profiles.")

    # 4. Add mortgage details
    add_mortgage(
        conn,
        account_id=home_mortgage_acc,
        original_principal=380000.0,
        current_balance=350000.0,
        interest_rate=6.25,
        monthly_payment=2350.0,
        term_months=360,
        start_date="2024-01-01"
    )
    print("Mortgage details added.")

    # 5. Add rules
    add_rule(conn, "(?i)starbucks", categories["Dining Out"], priority=1)
    add_rule(conn, "(?i)netflix", categories["Entertainment"], priority=1)
    add_rule(conn, "(?i)safeway", categories["Groceries"], priority=1)
    add_rule(conn, "(?i)empire life", categories["Payroll"], priority=1)
    add_rule(conn, "(?i)petline", categories["Payroll"], priority=1)
    add_rule(conn, "(?i)electric", categories["Utilities"], priority=1)
    add_rule(conn, "(?i)water", categories["Utilities"], priority=1)
    add_rule(conn, "(?i)insurance", categories["Insurance"], priority=1)
    add_rule(conn, "(?i)auto loan", categories["Transport"], priority=1)
    add_rule(conn, "(?i)aws", categories["Others"], priority=1)
    add_rule(conn, "(?i)github", categories["Others"], priority=1)
    add_rule(conn, "(?i)zoom", categories["Others"], priority=1)
    print("Rules added.")

    # Helper function to insert transactions
    def insert_tx(account_id, date, raw_desc, clean_m, cat_name, amount, is_debit):
        cat_id = categories.get(cat_name)
        sig = generate_transaction_hash(date, raw_desc, amount, account_id)
        add_transaction(
            conn,
            account_id=account_id,
            date=date,
            raw_description=raw_desc,
            clean_merchant=clean_m,
            category_id=cat_id,
            amount=amount,
            is_debit=is_debit,
            hash_signature=sig
        )

    # 6. Generate historical transactions
    # We will generate data from May 1, 2026 to August 15, 2026
    start_date = datetime.date(2026, 5, 1)
    end_date = datetime.date(2026, 8, 15)

    # Initial deposits on May 1
    insert_tx(chase_checking, "2026-05-01", "Opening Deposit Transfer", "Chase", "Savings", 10000.0, 0)
    insert_tx(fidelity_savings, "2026-05-01", "Opening Balance Deposit", "Fidelity", "Savings", 35000.0, 0)
    insert_tx(td_business, "2026-05-01", "Business Capital Injection", "TD Bank", "Savings", 15000.0, 0)

    curr = start_date
    while curr <= end_date:
        date_str = curr.strftime("%Y-%m-%d")
        
        # ----------------- PERSONAL TRANSACTIONS -----------------
        # Monthly Payroll from Empire Life on the 1st
        if curr.day == 1:
            insert_tx(chase_checking, date_str, "EMPIRE LIFE INSURANCE DIRECT DEP", "Empire Life", "Payroll", 5500.0, 0)
            
        # Monthly Mortgage Payment on the 5th
        if curr.day == 5:
            insert_tx(chase_checking, date_str, "WELLS FARGO MORTGAGE PAYMENT", "Wells Fargo Mortgage", "Housing", 2350.0, 1)
            insert_tx(home_mortgage_acc, date_str, "MORTGAGE PAYMENT RECEIVED", "Wells Fargo Mortgage", "Housing", 1200.0, 0) # approx principal
            
        # Monthly Auto Loan Payment on the 10th
        if curr.day == 10:
            insert_tx(chase_checking, date_str, "FORD MOTOR CREDIT AUTO LOAN PYMT", "Ford Credit", "Transport", 450.0, 1)
            insert_tx(auto_loan, date_str, "AUTO LOAN PAYMENT RECEIVED", "Ford Credit", "Transport", 450.0, 0)

        # Monthly Utility Bills on the 12th
        if curr.day == 12:
            insert_tx(chase_checking, date_str, "PGE ELECTRIC AND GAS BILL", "PGE Electric", "Utilities", 145.20, 1)
            insert_tx(chase_checking, date_str, "CITY WATER SEWER BILL", "City Water", "Utilities", 68.50, 1)
            
        # Monthly Netflix Subscription on the 18th
        if curr.day == 18:
            insert_tx(amex_gold, date_str, "NETFLIX ONLINE SUBSCRIPTION GBR", "Netflix", "Entertainment", 15.49, 1)

        # Monthly Personal Insurance Premium on the 20th
        if curr.day == 20:
            insert_tx(chase_checking, date_str, "GEICO AUTO INSURANCE PREM", "Geico Insurance", "Insurance", 110.0, 1)

        # Weekly Groceries (every Saturday)
        if curr.weekday() == 5: # Saturday
            insert_tx(chase_checking, date_str, "SAFEWAY STORE #1493 CA", "Safeway", "Groceries", 142.80, 1)

        # Dining out & Coffee details
        if curr.weekday() in (4, 6): # Friday or Sunday
            insert_tx(amex_gold, date_str, "LOCAL SUSHI BAR AND GRILL", "Sushi Bar", "Dining Out", 84.50, 1)
            
        if curr.day % 4 == 0: # Every 4 days
            insert_tx(amex_gold, date_str, "STARBUCKS STORE #1034 CA", "Starbucks", "Dining Out", 7.85, 1)

        # ----------------- INCORPORATION TRANSACTIONS -----------------
        # Contract Income from Petline on the 10th of each month
        if curr.day == 10:
            insert_tx(td_business, date_str, "PETLINE INS CORP CONTRACT INVS", "Petline", "Payroll", 9200.0, 0)
            
        # AWS cloud bill on the 3rd of each month
        if curr.day == 3:
            insert_tx(visa_business, date_str, "AWS BILLING CLOUD HOSTING SERVICES", "AWS", "Others", 185.0, 1)
            
        # GitHub subscription on the 15th
        if curr.day == 15:
            insert_tx(visa_business, date_str, "GITHUB INC DEV ENVIRONMENT SUITE", "GitHub", "Others", 24.0, 1)
            
        # Zoom meeting subscription on the 22nd
        if curr.day == 22:
            insert_tx(visa_business, date_str, "ZOOM VIDEO COMMUNICATION SERVICES", "Zoom", "Others", 14.99, 1)
            
        curr += datetime.timedelta(days=1)

    print("Transactions generated for both profiles.")

    # 7. Sync account balances
    sync_account_balances(conn)
    print("Balances synchronized.")
    
    conn.close()
    print("Seeding finished successfully! Database is ready.")

if __name__ == "__main__":
    seed()
