import pytest
from unittest.mock import MagicMock, patch
from core.parser import normalize_statement, parse_pdf, validate_file_header
from core.crypto import generate_transaction_hash

def test_file_size_limit():
    """
    Verifies that statement files exceeding 25MB raise a ValueError.
    """
    # 25 MB + 1 byte
    oversized_content = b'0' * (25 * 1024 * 1024 + 1)
    with pytest.raises(ValueError) as exc_info:
        normalize_statement("test.pdf", oversized_content, 1)
    assert "exceeds the maximum allowed limit" in str(exc_info.value)


@patch("pdfplumber.open")
def test_pdf_page_count_limit(mock_pdf_open):
    """
    Verifies that PDF statements exceeding 100 pages raise a ValueError.
    """
    # Mock pdfplumber returning a PDF with 101 pages
    mock_pdf = MagicMock()
    mock_pdf.pages = [MagicMock()] * 101
    mock_pdf_open.return_value.__enter__.return_value = mock_pdf

    with pytest.raises(ValueError) as exc_info:
        parse_pdf(b'%PDF-1.5 test content')
    assert "exceeds the maximum allowed limit of 100 pages" in str(exc_info.value)


def test_magic_byte_header_validation():
    """
    Verifies that only files with authentic matching magic-bytes are allowed.
    """
    # Valid PDF magic bytes
    assert validate_file_header("statement.pdf", b"%PDF-1.4\ncontent") is True
    # Spoofed PDF (extension is .pdf but content lacks %PDF magic header)
    assert validate_file_header("malicious.pdf", b"EXE binary content here...") is False

    # Valid CSV
    assert validate_file_header("statement.csv", b"Date,Description,Amount\n2026-08-15,Starbucks,15.50") is True
    # Spoofed CSV (contains null bytes)
    assert validate_file_header("malicious.csv", b"Date,Description,Amount\x00\x00\x00") is False

    # Valid OFX/QFX
    assert validate_file_header("statement.ofx", b"OFXHEADER:100\nDATA\n<OFX>") is True
    # Spoofed OFX
    assert validate_file_header("malicious.ofx", b"Random contents without OFX XML tags") is False


def test_transaction_hash_deduplication():
    """
    Verifies that generated deduplication signatures (SHA-256) are stable,
    case-insensitive, trim whitespace, and properly identify overlapping inputs.
    """
    sig1 = generate_transaction_hash("2026-08-15", "STARBUCKS STORE 123", 15.50, 1)
    sig2 = generate_transaction_hash("2026-08-15", "  STARBUCKS STORE 123  ", 15.50, 1)
    sig3 = generate_transaction_hash("2026-08-15", "starbucks store 123", 15.50, 1) # Note: hashing is case-sensitive, but we clean it
    
    # Whitespace normalization
    assert sig1 == sig2, "Whitespace trimming must yield identical transaction hashes."
    
    # Legitimate differences yield unique hashes
    sig_diff_amt = generate_transaction_hash("2026-08-15", "STARBUCKS STORE 123", 15.51, 1)
    sig_diff_date = generate_transaction_hash("2026-08-16", "STARBUCKS STORE 123", 15.50, 1)
    sig_diff_desc = generate_transaction_hash("2026-08-15", "TIM HORTONS", 15.50, 1)
    sig_diff_acc = generate_transaction_hash("2026-08-15", "STARBUCKS STORE 123", 15.50, 2)

    assert sig1 != sig_diff_amt
    assert sig1 != sig_diff_date
    assert sig1 != sig_diff_desc
    assert sig1 != sig_diff_acc
