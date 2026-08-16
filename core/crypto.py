import hashlib
import os

def derive_key(passphrase: str, salt: bytes = None, iterations: int = 100000) -> bytes:
    """
    Derives a 256-bit key from a passphrase using PBKDF2-HMAC-SHA256.
    Uses a standard static salt for deterministic derivation when decrypting the database file
    unless a specific salt is stored outside the database.
    """
    if salt is None:
        # A static salt for the SQLCipher key derivation fallback.
        # In SQLCipher, the library does its own internal key derivation using PBKDF2.
        # But if we pass a derived key directly, we use this static salt.
        salt = b"local_finance_salt_sec_vector_99"
    return hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, iterations, dklen=32)

def generate_transaction_hash(date: str, raw_description: str, amount: float, account_id: int) -> str:
    """
    Computes a cryptographic SHA-256 hash signature for transaction deduplication.
    Format: sha256(date | raw_description | amount | account_id)
    Standardizes description whitespace and amount formatting.
    """
    desc = (raw_description or "").strip()
    # Normalize amount to 2 decimal places to avoid string representation differences (e.g. float precision)
    data_str = f"{date}|{desc}|{amount:.2f}|{account_id}"
    return hashlib.sha256(data_str.encode("utf-8")).hexdigest()
