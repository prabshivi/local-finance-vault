import os
import sqlite3
import datetime
from core.crypto import derive_key, generate_transaction_hash
from core.db import connect_db, init_db, add_account, get_accounts, add_transaction, get_transactions
from core.parser import parse_date, parse_amount, parse_ofx_custom
from core.rules import clean_merchant_name, suggest_regex_pattern

def test_crypto():
    print("Running cryptographic tests...")
    # Derive key test
    key1 = derive_key("my_passphrase")
    key2 = derive_key("my_passphrase")
    key3 = derive_key("other_passphrase")
    assert key1 == key2, "Derived keys from the same passphrase must be identical."
    assert key1 != key3, "Derived keys from different passphrases must differ."
    
    # Hash signature deduplication test
    sig1 = generate_transaction_hash("2026-08-15", "STARBUCKS STORE 123", 15.50, 1)
    sig2 = generate_transaction_hash("2026-08-15", " STARBUCKS STORE 123 ", 15.50, 1)
    sig3 = generate_transaction_hash("2026-08-15", "STARBUCKS STORE 123", 15.51, 1)
    assert sig1 == sig2, "Whitespace trimming should yield identical hashes."
    assert sig1 != sig3, "Different transaction amounts should yield different hashes."
    print("✅ Cryptographic tests passed.")

def test_db_encryption():
    print("Running database encryption tests...")
    db_path = "test_vault.db"
    passphrase = "test_passphrase_99"
    
    # Cleanup any existing test DB
    if os.path.exists(db_path):
        os.remove(db_path)
        
    # Connect and init schema
    conn, is_encrypted, err = connect_db(db_path, passphrase)
    assert conn is not None, f"Failed to connect to test db: {err}"
    print(f"Connection active. SQLCipher active? {is_encrypted}")
    
    init_db(conn)
    
    # Add account
    acc_id = add_account(conn, "Checking", "checking", "Chase", 1000.00)
    assert acc_id is not None, "Failed to insert account."
    
    # Add transaction
    tx_id = add_transaction(
        conn,
        account_id=acc_id,
        date="2026-08-15",
        raw_description="STARBUCKS #1234",
        clean_merchant="STARBUCKS",
        category_id=1,
        amount=15.50,
        is_debit=1,
        hash_signature="test_sig_unique_1"
    )
    assert tx_id is not None, "Failed to insert transaction."
    
    # Verify transaction retrieval
    txs = get_transactions(conn)
    assert len(txs) == 1, "Expected 1 transaction."
    assert txs[0]['raw_description'] == "STARBUCKS #1234", "Transaction contents mismatched."
    
    conn.close()
    
    # Test file reading without key (using standard sqlite3)
    if is_encrypted:
        print("SQLCipher was detected. Verifying file security...")
        # A standard SQLite connection (without PRAGMA key) should fail to read tables
        conn_std = sqlite3.connect(db_path)
        try:
            cursor = conn_std.cursor()
            cursor.execute("SELECT count(*) FROM sqlite_master;")
            # If standard sqlite3 can read the file, it means it was not encrypted!
            assert False, "Security Vulnerability: Encrypted database could be read without passphrase!"
        except sqlite3.DatabaseError:
            print("✅ Verified: Database is encrypted at rest. Standard SQLite cannot read it.")
        finally:
            conn_std.close()
            
        # Test connecting with wrong key
        conn_wrong, is_enc_wrong, err_wrong = connect_db(db_path, "wrong_passphrase")
        assert conn_wrong is None, "Wrong passphrase should not allow database connection."
        print("✅ Verified: Connecting with wrong passphrase fails.")
    else:
        print("⚠️ SQLCipher was not detected. Standard SQLite fallback tests completed.")
        
    # Clean up test database
    if os.path.exists(db_path):
        os.remove(db_path)
        
    print("✅ Database tests completed successfully.")

def test_parser():
    print("Running parser tests...")
    # Parse date tests
    assert parse_date("2026-08-15") == "2026-08-15"
    assert parse_date("08/15/2026") == "2026-08-15"
    assert parse_date("Aug 15") == f"{datetime.datetime.now().year}-08-15"
    assert parse_date("August 15") == f"{datetime.datetime.now().year}-08-15"
    
    # Parse amount tests
    assert parse_amount("$1,250.55") == 1250.55
    assert parse_amount("($100.00)") == -100.00
    assert parse_amount(" -45.00 ") == -45.00
    
    # Custom OFX parsing tests
    mock_ofx = """
    <OFX>
      <BANKMSGSRSV1>
        <STMTTRN>
          <TRNTYPE>DEBIT</TRNTYPE>
          <DTPOSTED>20260815120000</DTPOSTED>
          <TRNAMT>-15.50</TRNAMT>
          <FITID>tx_ref_12345</FITID>
          <NAME>STARBUCKS #123</NAME>
        </STMTTRN>
      </BANKMSGSRSV1>
    </OFX>
    """
    txs = parse_ofx_custom(mock_ofx)
    assert len(txs) == 1, "Expected 1 parsed OFX transaction."
    assert txs[0]['date'] == "2026-08-15"
    assert txs[0]['amount'] == 15.50
    assert txs[0]['is_debit'] == 1
    assert "STARBUCKS" in txs[0]['raw_description']
    
    print("✅ Parser tests passed.")

def test_rules():
    print("Running rules tests...")
    # Clean merchant name tests
    assert clean_merchant_name("STARBUCKS COFFEE STORE #12345 CA 94103") == "STARBUCKS COFFEE"
    assert clean_merchant_name("WWW.NETFLIX.COM ON 08/15 CA") == "NETFLIX"
    assert clean_merchant_name("SAFEWAY STORE 994") == "SAFEWAY"
    
    # Suggest regex tests
    pattern = suggest_regex_pattern("STARBUCKS #1234")
    assert pattern == "(?i)STARBUCKS"
    
    print("✅ Rules tests passed.")

def main():
    print("=== Vault Finance Verification Engine ===")
    test_crypto()
    test_db_encryption()
    test_parser()
    test_rules()
    print("=== All Tests Passed Successfully ===")

if __name__ == "__main__":
    main()
