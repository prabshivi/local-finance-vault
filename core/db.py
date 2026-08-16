import os
import sqlite3

# Try importing SQLCipher library wrappers.
# Fallback to standard sqlite3 if SQLCipher is not installed or compiled.
sqlcipher = None
SQLCIPHER_TYPE = None

try:
    from pysqlcipher3 import dbapi2 as sqlcipher
    SQLCIPHER_TYPE = "pysqlcipher3"
except ImportError:
    try:
        import sqlcipher3 as sqlcipher
        SQLCIPHER_TYPE = "sqlcipher3"
    except ImportError:
        pass

def connect_db(db_path: str, passphrase: str = ""):
    """
    Connect to the SQLite database.
    If SQLCipher is available, decrypt the database using the passphrase.
    Otherwise, fall back to standard sqlite3 (unencrypted).
    
    Returns:
        (conn, is_encrypted, error_message)
    """
    is_encrypted = (sqlcipher is not None)
    
    if is_encrypted and passphrase:
        try:
            # Connect using the SQLCipher wrapper
            conn = sqlcipher.connect(db_path)
            # Escape single quotes in the passphrase for the PRAGMA key statement
            escaped_key = passphrase.replace("'", "''")
            conn.execute(f"PRAGMA key = '{escaped_key}'")
            # Verify key correctness by reading from sqlite_master
            conn.execute("SELECT count(*) FROM sqlite_master;")
            # Enable foreign keys
            conn.execute("PRAGMA foreign_keys = ON;")
            return conn, True, None
        except Exception as e:
            return None, True, f"Failed to decrypt database: {str(e)}"
    else:
        # Fallback to standard sqlite3
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA foreign_keys = ON;")
            warn_msg = None if not passphrase else "Running in UNENCRYPTED fallback mode. SQLCipher libraries not found."
            return conn, False, warn_msg
        except Exception as e:
            return None, False, f"Failed to connect to database: {str(e)}"

def init_db(conn):
    """
    Creates tables and pre-populates default categories if they do not exist.
    """
    cursor = conn.cursor()
    
    # 1. Categories Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            monthly_budget REAL DEFAULT 0.0
        )
    ''')
    
    # 2. Accounts Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('checking', 'credit', 'mortgage', 'savings')),
            institution TEXT,
            balance REAL DEFAULT 0.0,
            currency TEXT DEFAULT 'USD'
        )
    ''')
    
    # 3. Transactions Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            raw_description TEXT,
            clean_merchant TEXT,
            category_id INTEGER,
            amount REAL NOT NULL,
            is_debit INTEGER NOT NULL CHECK(is_debit IN (0, 1)),
            hash_signature TEXT UNIQUE NOT NULL,
            FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE CASCADE,
            FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE SET NULL
        )
    ''''')
    
    # 4. Rules Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            regex_pattern TEXT UNIQUE NOT NULL,
            target_category_id INTEGER NOT NULL,
            priority INTEGER DEFAULT 0,
            FOREIGN KEY(target_category_id) REFERENCES categories(id) ON DELETE CASCADE
        )
    ''')
    
    # 5. Mortgages Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mortgages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER UNIQUE NOT NULL,
            original_principal REAL NOT NULL,
            current_balance REAL NOT NULL,
            interest_rate REAL NOT NULL,
            monthly_payment REAL NOT NULL,
            term_months INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE CASCADE
        )
    ''')
    
    # Pre-populate default categories
    default_categories = [
        ("Groceries", 500.0),
        ("Utilities", 250.0),
        ("Housing", 1500.0),
        ("Entertainment", 150.0),
        ("Dining Out", 200.0),
        ("Transport", 150.0),
        ("Insurance", 150.0),
        ("Savings", 500.0),
        ("Payroll", 0.0),
        ("Interest", 0.0),
        ("Others", 100.0)
    ]
    for name, budget in default_categories:
        cursor.execute('''
            INSERT OR IGNORE INTO categories (name, monthly_budget)
            VALUES (?, ?)
        ''', (name, budget))
        
    conn.commit()

# --- Accounts CRUD ---

def add_account(conn, name: str, type_: str, institution: str, balance: float, currency: str = "USD") -> int:
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO accounts (name, type, institution, balance, currency)
        VALUES (?, ?, ?, ?, ?)
    ''', (name, type_, institution, balance, currency))
    conn.commit()
    return cursor.lastrowid

def get_accounts(conn) -> list:
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, type, institution, balance, currency FROM accounts')
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]

def update_account_balance(conn, account_id: int, balance: float):
    cursor = conn.cursor()
    cursor.execute('UPDATE accounts SET balance = ? WHERE id = ?', (balance, account_id))
    conn.commit()

def delete_account(conn, account_id: int):
    cursor = conn.cursor()
    cursor.execute('DELETE FROM accounts WHERE id = ?', (account_id,))
    conn.commit()

# --- Categories CRUD ---

def get_categories(conn) -> list:
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, monthly_budget FROM categories')
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]

def add_category(conn, name: str, monthly_budget: float) -> int:
    cursor = conn.cursor()
    cursor.execute('INSERT INTO categories (name, monthly_budget) VALUES (?, ?)', (name, monthly_budget))
    conn.commit()
    return cursor.lastrowid

def update_category(conn, category_id: int, name: str, monthly_budget: float):
    cursor = conn.cursor()
    cursor.execute('UPDATE categories SET name = ?, monthly_budget = ? WHERE id = ?', (name, monthly_budget, category_id))
    conn.commit()

def delete_category(conn, category_id: int):
    cursor = conn.cursor()
    cursor.execute('DELETE FROM categories WHERE id = ?', (category_id,))
    conn.commit()

# --- Rules CRUD ---

def get_rules(conn) -> list:
    cursor = conn.cursor()
    cursor.execute('''
        SELECT r.id, r.regex_pattern, r.target_category_id, r.priority, c.name as category_name
        FROM rules r
        JOIN categories c ON r.target_category_id = c.id
        ORDER BY r.priority DESC, r.id ASC
    ''')
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]

def add_rule(conn, regex_pattern: str, target_category_id: int, priority: int = 0) -> int:
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO rules (regex_pattern, target_category_id, priority)
        VALUES (?, ?, ?)
    ''', (regex_pattern, target_category_id, priority))
    conn.commit()
    return cursor.lastrowid

def delete_rule(conn, rule_id: int):
    cursor = conn.cursor()
    cursor.execute('DELETE FROM rules WHERE id = ?', (rule_id,))
    conn.commit()

# --- Transactions CRUD ---

def add_transaction(conn, account_id: int, date: str, raw_description: str, clean_merchant: str, category_id: int, amount: float, is_debit: int, hash_signature: str) -> int:
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO transactions (account_id, date, raw_description, clean_merchant, category_id, amount, is_debit, hash_signature)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (account_id, date, raw_description, clean_merchant, category_id, amount, is_debit, hash_signature))
    conn.commit()
    return cursor.lastrowid

def add_transactions_bulk(conn, transactions: list) -> tuple:
    """
    Inserts multiple transactions in a single transaction block.
    Skips rows with duplicate hash signatures.
    Returns (inserted_count, skipped_count).
    """
    inserted = 0
    skipped = 0
    cursor = conn.cursor()
    
    # We will do this inside a try-except to rollback on major errors
    for tx in transactions:
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO transactions 
                (account_id, date, raw_description, clean_merchant, category_id, amount, is_debit, hash_signature)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                tx['account_id'], tx['date'], tx['raw_description'], tx['clean_merchant'],
                tx.get('category_id'), tx['amount'], tx['is_debit'], tx['hash_signature']
            ))
            if cursor.rowcount > 0:
                inserted += 1
            else:
                skipped += 1
        except Exception:
            skipped += 1
            
    conn.commit()
    return inserted, skipped

def get_transactions(conn, date_start: str = None, date_end: str = None, account_ids: list = None, category_ids: list = None, search_term: str = None) -> list:
    cursor = conn.cursor()
    query = '''
        SELECT t.id, t.account_id, t.date, t.raw_description, t.clean_merchant, 
               t.category_id, t.amount, t.is_debit, t.hash_signature,
               a.name as account_name, c.name as category_name
        FROM transactions t
        JOIN accounts a ON t.account_id = a.id
        LEFT JOIN categories c ON t.category_id = c.id
        WHERE 1=1
    '''
    params = []
    
    if date_start:
        query += " AND t.date >= ?"
        params.append(date_start)
    if date_end:
        query += " AND t.date <= ?"
        params.append(date_end)
    if account_ids:
        query += f" AND t.account_id IN ({','.join(['?'] * len(account_ids))})"
        params.extend(account_ids)
    if category_ids:
        # Support searching for uncategorized specifically (None or id matches)
        has_none = None in category_ids or "None" in category_ids
        valid_ids = [cid for cid in category_ids if cid not in (None, "None")]
        if valid_ids:
            placeholders = ','.join(['?'] * len(valid_ids))
            if has_none:
                query += f" AND (t.category_id IN ({placeholders}) OR t.category_id IS NULL)"
            else:
                query += f" AND t.category_id IN ({placeholders})"
            params.extend(valid_ids)
        elif has_none:
            query += " AND t.category_id IS NULL"
    if search_term:
        query += " AND (t.raw_description LIKE ? OR t.clean_merchant LIKE ?)"
        params.append(f"%{search_term}%")
        params.append(f"%{search_term}%")
        
    query += " ORDER BY t.date DESC, t.id DESC"
    cursor.execute(query, params)
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]

def update_transaction_category(conn, transaction_id: int, category_id: int):
    cursor = conn.cursor()
    cursor.execute('UPDATE transactions SET category_id = ? WHERE id = ?', (category_id, transaction_id))
    conn.commit()

# --- Mortgages CRUD ---

def get_mortgage(conn, account_id: int) -> dict:
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, account_id, original_principal, current_balance, interest_rate, 
               monthly_payment, term_months, start_date 
        FROM mortgages 
        WHERE account_id = ?
    ''', (account_id,))
    row = cursor.fetchone()
    if row:
        columns = [col[0] for col in cursor.description]
        return dict(zip(columns, row))
    return None

def add_mortgage(conn, account_id: int, original_principal: float, current_balance: float, interest_rate: float, monthly_payment: float, term_months: int, start_date: str) -> int:
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO mortgages (account_id, original_principal, current_balance, interest_rate, monthly_payment, term_months, start_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (account_id, original_principal, current_balance, interest_rate, monthly_payment, term_months, start_date))
    conn.commit()
    return cursor.lastrowid

def update_mortgage(conn, account_id: int, current_balance: float, interest_rate: float, monthly_payment: float):
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE mortgages 
        SET current_balance = ?, interest_rate = ?, monthly_payment = ? 
        WHERE account_id = ?
    ''', (current_balance, interest_rate, monthly_payment, account_id))
    conn.commit()
