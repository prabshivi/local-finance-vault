import os
import sqlite3
import pytest
import socket
from core.security import mask_pii, sanitize_text, enforce_network_isolation, get_or_create_salt, derive_vault_key
from core.db import connect_db, init_db, add_account, get_accounts

def test_sqlcipher_encryption_at_rest(tmp_path):
    """
    Verifies that the database is encrypted at rest and standard sqlite3 cannot read it
    without the correct derived key.
    """
    db_file = os.path.join(tmp_path, "test_compliance.db")
    passphrase = "compliance_test_passphrase_123"
    
    # 1. Establish connection and write test data
    conn, is_encrypted, err = connect_db(db_file, passphrase)
    assert conn is not None, f"Failed to connect: {err}"
    if not is_encrypted:
        assert "UNENCRYPTED" in err
        pytest.skip("SQLCipher libraries not found. Skipping encryption tests.")
    assert err is None
    
    init_db(conn)
    acc_id = add_account(conn, "Checking", "checking", "TD Bank", 5000.0)
    assert acc_id is not None
    conn.close()
    
    # 2. Attempt to read database file using raw sqlite3 without SQLCipher derived key
    # (SQLCipher encrypts the database structure at rest, so reading table information throws DatabaseError)
    conn_raw = sqlite3.connect(db_file)
    try:
        cursor = conn_raw.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        # If it returns results or doesn't fail, then the file was not encrypted!
        results = cursor.fetchall()
        assert False, "Security Vulnerability: Database was read without decryption!"
    except sqlite3.DatabaseError:
        # Expected behavior: file is encrypted and unreadable by standard SQLite
        pass
    finally:
        conn_raw.close()

    # 3. Attempt connection with incorrect passphrase
    conn_wrong, is_enc_wrong, err_wrong = connect_db(db_file, "incorrect_passphrase")
    assert conn_wrong is None, "Security Violation: Database opened with an incorrect passphrase."
    assert "Failed to decrypt database" in err_wrong


def test_pii_sanitization():
    """
    Verifies that Sensitive PII is masked (SINs, credit card numbers, Canadian transit, bank account numbers).
    """
    # SIN formatted and raw
    assert mask_pii("My SIN is 123-456-789") == "My SIN is ***-***-789"
    assert mask_pii("SIN raw is 123456789") == "SIN raw is *****6789"
    
    # Credit Card
    assert mask_pii("CARD NUMBER 1234 5678 1234 5678") == "CARD NUMBER ****-****-****-5678"
    assert mask_pii("CARD NUMBER 1234-5678-1234-5678") == "CARD NUMBER ****-****-****-5678"
    
    # Canadian routing/transit: 5 digits + 3 digits (e.g. 12345-004)
    assert mask_pii("Transit is 12345-004") == "Transit is *****-***"

    # Bank Account numbers (7 to 12 digits)
    # Note: 10 digits is used here to avoid collision with 9-digit raw SIN masking
    assert mask_pii("Account number 1234567890") == "Account number ****7890"
    assert mask_pii("Account 987654321012") == "Account ****1012"
    
    # Ensure float amounts / dates are NOT masked
    assert mask_pii("Amount is $12345.67") == "Amount is $12345.67"
    assert mask_pii("Date is 2026-08-15") == "Date is 2026-08-15"


def test_network_isolation():
    """
    Verifies that out-of-band network calls (DNS, TCP connection) are strictly blocked.
    """
    # Enforce network hook
    enforce_network_isolation()
    
    # 1. Attempt TCP socket connection to external site
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    with pytest.raises(RuntimeError) as exc_info:
        s.connect(("8.8.8.8", 53))
    assert "Outbound Network Blocked" in str(exc_info.value)
    
    # 2. Attempt DNS resolution lookup
    with pytest.raises(RuntimeError) as exc_info:
        socket.getaddrinfo("google.com", 80)
    assert "DNS Resolution Blocked" in str(exc_info.value)

    with pytest.raises(RuntimeError) as exc_info:
        socket.gethostbyname("yahoo.com")
    assert "DNS Resolution Blocked" in str(exc_info.value)

    # 3. Verify localhost is allowed
    # Note: We won't actually perform a full connect since no local server might be listening on testing port,
    # but we can verify the socket connection doesn't raise the custom RuntimeError (fails with normal socket ref/error if not listening).
    try:
        s_local = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s_local.settimeout(0.1)
        s_local.connect(("127.0.0.1", 9999))
    except RuntimeError:
        pytest.fail("Localhost connection was incorrectly blocked.")
    except Exception:
        # Normal socket error (ConnectionRefused/timeout) is fine, as long as it isn't RuntimeError
        pass


def test_tamper_and_injection():
    """
    Verifies sanitization removes script artifacts and SQL comment sequences, and blocks CSV DDE injection.
    """
    # Script tag & javascript protocol injection
    assert sanitize_text("<script>alert(1)</script>") == "alert(1)"
    assert sanitize_text("javascript:alert(1)") == "alert(1)"
    
    # SQL comment attacks
    assert sanitize_text("SELECT * FROM accounts -- comment") == "SELECT * FROM accounts  comment"
    assert sanitize_text("SELECT * FROM /* comment */ accounts") == "SELECT * FROM  accounts"

    # CSV DDE Formula Injection: prepends single quote if starting with =, +, -, @
    assert sanitize_text("=SUM(A1:A5)") == "'=SUM(A1:A5)"
    assert sanitize_text("+12345") == "'+12345"
    assert sanitize_text("-999.00") == "'-999.00"
    assert sanitize_text("@SUM") == "'@SUM"
    
    # Standard string remains untouched
    assert sanitize_text("SAFEWAY STORE 102") == "SAFEWAY STORE 102"
