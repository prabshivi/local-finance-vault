import os
import re
import socket
import hmac
import hashlib

# Keep references to the original network functions
_original_socket_connect = socket.socket.connect
_original_getaddrinfo = socket.getaddrinfo
_original_gethostbyname = socket.gethostbyname

def enforce_network_isolation():
    """
    Enforces local-only zero-trust data protection by intercepting out-of-band network calls.
    Allows traffic to localhost/127.0.0.1 for local Streamlit rendering but blocks all others.
    """
    def custom_connect(self, address):
        host = address[0]
        # Allow loopback interface for Streamlit local hosting
        if host in ('127.0.0.1', 'localhost', '::1') or host.startswith('127.'):
            return _original_socket_connect(self, address)
        raise RuntimeError(
            f"Outbound Network Blocked: Outbound connection to {address} was intercepted "
            f"under Canadian PIPEDA & OSFI B-13 zero-trust controls."
        )

    def custom_getaddrinfo(host, *args, **kwargs):
        if host in ('127.0.0.1', 'localhost', '::1') or (host and host.startswith('127.')):
            return _original_getaddrinfo(host, *args, **kwargs)
        raise RuntimeError(f"DNS Resolution Blocked: Resolution for {host} was intercepted.")

    def custom_gethostbyname(host):
        if host in ('127.0.0.1', 'localhost', '::1') or (host and host.startswith('127.')):
            return _original_gethostbyname(host)
        raise RuntimeError(f"DNS Resolution Blocked: Resolution for {host} was intercepted.")

    socket.socket.connect = custom_connect
    socket.getaddrinfo = custom_getaddrinfo
    socket.gethostbyname = custom_gethostbyname


def derive_vault_key(passphrase: str, salt: bytes, force_pbkdf2: bool = False) -> bytes:
    """
    Derives a 256-bit AES database key using Argon2id or fallback PBKDF2-HMAC-SHA512.
    Minimum 250,000 PBKDF2 iterations or Argon2id with m=64MB, t=3, p=4.
    """
    if len(salt) != 32:
        raise ValueError("Salt must be exactly 32 bytes.")
    
    if not force_pbkdf2:
        try:
            from argon2.low_level import hash_secret_raw, Type
            # Argon2id profile (m=64MB, t=3, p=4) for OSFI B-13 compliance
            return hash_secret_raw(
                secret=passphrase.encode('utf-8'),
                salt=salt,
                time_cost=3,
                memory_cost=65536,
                parallelism=4,
                hash_len=32,
                type=Type.ID
            )
        except ImportError:
            # Fall back to PBKDF2-HMAC-SHA512
            pass

    return hashlib.pbkdf2_hmac(
        "sha512",
        passphrase.encode("utf-8"),
        salt,
        250000,
        dklen=32
    )


def get_or_create_salt(salt_path: str) -> bytes:
    """
    Loads a local salt from the specified path, or generates a new 32-byte cryptographically
    secure random salt (os.urandom) and saves it with restricted POSIX permissions (0600).
    """
    if os.path.exists(salt_path):
        try:
            with open(salt_path, 'rb') as f:
                salt = f.read()
                if len(salt) == 32:
                    return salt
        except Exception:
            pass

    salt = os.urandom(32)
    # Write salt file with secure POSIX permissions (0600)
    flags = os.O_CREAT | os.O_WRONLY | os.O_TRUNC
    mode = 0o600
    fd = os.open(salt_path, flags, mode)
    with os.fdopen(fd, 'wb') as f:
        f.write(salt)
    return salt


def mask_pii(text: str) -> str:
    """
    Scrubs PII (SINs, credit card numbers, Canadian transit, bank account numbers) from text.
    Replaces them with masked references.
    """
    if not text:
        return ""

    # SIN: e.g. 123-456-789 or 123456789
    sin_formatted = re.compile(r'\b(\d{3})-(\d{3})-(\d{3})\b')
    text = sin_formatted.sub(r'***-***-\3', text)
    sin_raw = re.compile(r'\b\d{9}\b')
    text = sin_raw.sub(lambda m: '*****' + m.group(0)[5:], text)

    # PAN (Credit Card): 16-digits or standard spacing
    pan_pattern = re.compile(r'\b(\d{4})[- ]?(\d{4})[- ]?(\d{4})[- ]?(\d{4})\b')
    text = pan_pattern.sub(r'****-****-****-\4', text)

    # Canadian Transit/Routing Numbers: 5 digits + 3 digits (e.g. 12345-678)
    transit_pattern = re.compile(r'\b\d{5}-\d{3}\b')
    text = transit_pattern.sub(r'*****-***', text)

    # Bank Account Numbers: 7-12 digits bounded securely to avoid years, transaction amounts, etc.
    # Excludes values with decimal dots or preceding commas.
    bank_pattern = re.compile(r'(?<![\.,\d])\b\d{7,12}\b(?![\.,\d])')
    text = bank_pattern.sub(lambda m: '****' + m.group(0)[-4:], text)

    return text


def sanitize_text(text: str) -> str:
    """
    Strips control characters, HTML tags, script injection keywords, and SQL comments.
    Neutralizes CSV formula injection (DDE attacks) by prepending a single quote to strings
    starting with =, +, -, or @.
    """
    if not text:
        return ""

    # Remove non-ascii and unsafe control characters, preserve tabs, space, newlines
    text = "".join(ch for ch in text if ch == '\n' or ch == '\r' or ch == '\t' or (32 <= ord(ch) < 127) or (ord(ch) >= 160))

    # Strip HTML tags
    text = re.sub(r'<[^>]*>', '', text)

    # Remove script indicators
    text = re.sub(r'(?i)javascript\s*:', '', text)

    # Strip SQL comments to prevent raw query manipulation (comments block execution paths)
    text = text.replace("--", "")
    text = re.sub(r'/\*.*?\*/', '', text)

    # Prevent CSV DDE formula injections
    if text.startswith(('=', '+', '-', '@')):
        text = "'" + text

    return text.strip()


def secure_delete_file(file_path: str):
    """
    Safely destroys temporary disk files by zero-filling them before deletion.
    """
    if os.path.exists(file_path):
        try:
            size = os.path.getsize(file_path)
            with open(file_path, 'r+b') as f:
                f.write(b'\x00' * size)
                f.flush()
                os.fsync(f.fileno())
            os.remove(file_path)
        except Exception:
            # Fallback to standard delete if overwriting fails
            try:
                os.remove(file_path)
            except Exception:
                pass

import base64
from cryptography.fernet import Fernet

def encrypt_master_key(master_key: bytes, user_passphrase: str, salt: bytes) -> str:
    """
    Encrypts the master database key using the derived user key with Fernet.
    """
    derived_key = derive_vault_key(user_passphrase, salt)
    fernet_key = base64.urlsafe_b64encode(derived_key)
    f = Fernet(fernet_key)
    return f.encrypt(master_key).decode('utf-8')

def decrypt_master_key(encrypted_master_key_str: str, user_passphrase: str, salt: bytes) -> bytes:
    """
    Decrypts the master database key using the derived user key.
    """
    derived_key = derive_vault_key(user_passphrase, salt)
    fernet_key = base64.urlsafe_b64encode(derived_key)
    f = Fernet(fernet_key)
    return f.decrypt(encrypted_master_key_str.encode('utf-8'))

def hash_password(password: str, salt: bytes = None) -> tuple[str, str]:
    """
    Hashes a password with pbkdf2_hmac_sha256 or argon2.
    """
    if salt is None:
        salt = os.urandom(16)
    try:
        from argon2 import PasswordHasher
        ph = PasswordHasher()
        h = ph.hash(password)
        return h, ""
    except ImportError:
        h = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
        return h.hex(), salt.hex()

def verify_password(password: str, stored_hash: str, salt_hex: str) -> bool:
    """
    Verifies a password against its stored hash.
    """
    try:
        from argon2 import PasswordHasher
        from argon2.exceptions import VerifyMismatchError
        ph = PasswordHasher()
        try:
            ph.verify(stored_hash, password)
            return True
        except VerifyMismatchError:
            return False
        except Exception:
            pass
    except ImportError:
        pass
        
    salt = bytes.fromhex(salt_hex) if salt_hex else b""
    h = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return h.hex() == stored_hash
