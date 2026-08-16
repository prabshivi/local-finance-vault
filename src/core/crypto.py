import hashlib
import os
from core.security import derive_vault_key

def derive_key(passphrase: str, salt: bytes = None, iterations: int = 250000) -> bytes:
    """
    Derives a 256-bit key from a passphrase. Wraps the compliance secure key derivation function
    to preserve legcay compatibility.
    """
    if salt is None:
        # legacy static salt, padded to 32 bytes for the new zero-trust controls
        salt = b"local_finance_salt_sec_vector_99".ljust(32, b"\x00")[:32]
    return derive_vault_key(passphrase, salt)

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
