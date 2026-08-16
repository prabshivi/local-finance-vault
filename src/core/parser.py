import csv
import datetime
import io
import re
from core.crypto import generate_transaction_hash
from core.security import mask_pii, sanitize_text

# Compliance limits under OSFI B-13 DoS guidelines
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB
MAX_PAGE_COUNT = 100

def validate_file_header(file_name: str, file_bytes: bytes) -> bool:
    """
    Validates file magic-bytes/headers against MIME spoofing.
    - PDF: Starts with %PDF
    - CSV: Decodable text with no NULL bytes
    - OFX/QFX: Contains OFX header tags in the first 500 bytes
    """
    file_lower = file_name.lower()
    if file_lower.endswith('.pdf'):
        return file_bytes.startswith(b'%PDF')
    elif file_lower.endswith('.csv'):
        try:
            content = file_bytes.decode('utf-8', errors='strict')
            return '\x00' not in content
        except UnicodeDecodeError:
            return False
    elif file_lower.endswith(('.ofx', '.qfx')):
        try:
            header = file_bytes[:500].decode('utf-8', errors='ignore')
            return any(tag in header for tag in ('OFXHEADER', '<OFX', '<?xml'))
        except Exception:
            return False
    return False

# Try importing pdfplumber and ofxparse (we also have a fallback custom OFX parser)
pdfplumber_available = False
try:
    import pdfplumber
    pdfplumber_available = True
except ImportError:
    pass

ofxparse_available = False
try:
    from ofxparse import OfxParser
    ofxparse_available = True
except ImportError:
    pass

def parse_date(date_str: str) -> str:
    """
    Tries to parse various date formats and return YYYY-MM-DD string.
    If parsing fails, returns None.
    """
    if not date_str:
        return None
    
    cleaned = date_str.strip()
    
    # Common formats
    formats = [
        '%Y-%m-%d', '%m/%d/%Y', '%m/%d/%y', '%d/%m/%Y', '%d/%m/%y',
        '%b %d, %Y', '%b %d %Y', '%d-%b-%Y', '%d %b %Y', '%d %B %Y',
        '%Y/%m/%d'
    ]
    
    for fmt in formats:
        try:
            return datetime.datetime.strptime(cleaned, fmt).strftime('%Y-%m-%d')
        except ValueError:
            pass
            
    # Try parsing shorthand format "MM/DD" or "MM-DD" and assume current year
    match = re.match(r'^(\d{1,2})[-/](\d{1,2})$', cleaned)
    if match:
        month, day = int(match.group(1)), int(match.group(2))
        year = datetime.datetime.now().year
        return f"{year}-{month:02d}-{day:02d}"
        
    # Try shorthand text format "Aug 15" or "August 15"
    match = re.match(r'^([A-Za-z]{3,9})\s+(\d{1,2})$', cleaned)
    if match:
        month_str, day = match.group(1), int(match.group(2))
        try:
            # Parse month abbreviation
            month_num = datetime.datetime.strptime(month_str[:3].capitalize(), '%b').month
            year = datetime.datetime.now().year
            return f"{year}-{month_num:02d}-{day:02d}"
        except ValueError:
            pass
            
    return None

def parse_amount(amount_str: str) -> float:
    """
    Removes currency symbols and formatting, converting to float.
    Returns None if conversion fails.
    """
    if not amount_str:
        return None
    # Remove dollar signs, spaces, commas, and parentheses for negative numbers (e.g. (10.00))
    cleaned = amount_str.strip()
    
    # Handle accounting parenthesis: (100.00) -> -100.00
    if cleaned.startswith('(') and cleaned.endswith(')'):
        cleaned = '-' + cleaned[1:-1]
        
    cleaned = re.sub(r'[^\d\.\-]', '', cleaned)
    try:
        return float(cleaned)
    except ValueError:
        return None

def parse_csv(file_content: str) -> list:
    """
    Parses CSV content and extracts potential columns.
    Returns a list of dicts with: date, raw_description, amount, is_debit
    """
    # Use StringIO to parse the string like a file
    f = io.StringIO(file_content)
    reader = csv.reader(f)
    
    rows = []
    headers = []
    
    # Read headers
    try:
        headers = [h.strip().lower() for h in next(reader)]
    except StopIteration:
        return []
        
    # Identify indices
    date_idx, desc_idx, amount_idx, debit_idx, credit_idx = -1, -1, -1, -1, -1
    
    for i, h in enumerate(headers):
        if 'date' in h:
            date_idx = i
        elif 'desc' in h or 'memo' in h or 'merchant' in h or 'payee' in h or 'transaction' in h:
            desc_idx = i
        elif 'amount' in h or 'value' in h:
            amount_idx = i
        elif 'debit' in h:
            debit_idx = i
        elif 'credit' in h:
            credit_idx = i
            
    # Fallback to column indices if header matches failed
    if date_idx == -1 and len(headers) > 0:
        date_idx = 0
    if desc_idx == -1 and len(headers) > 1:
        desc_idx = 1
    if amount_idx == -1 and debit_idx == -1:
        # Check third column
        if len(headers) > 2:
            amount_idx = 2

    # Parse rows
    for row in reader:
        if not row or len(row) <= max(date_idx, desc_idx, amount_idx, debit_idx, credit_idx):
            continue
            
        date_val = parse_date(row[date_idx])
        desc_val = row[desc_idx].strip() if desc_idx != -1 else ""
        
        # Resolve amount and is_debit
        amount = 0.0
        is_debit = 1
        
        if amount_idx != -1:
            raw_amt = parse_amount(row[amount_idx])
            if raw_amt is not None:
                amount = abs(raw_amt)
                is_debit = 1 if raw_amt < 0 else 0
        elif debit_idx != -1 and credit_idx != -1:
            debit_val = parse_amount(row[debit_idx])
            credit_val = parse_amount(row[credit_idx])
            if debit_val:
                amount = debit_val
                is_debit = 1
            elif credit_val:
                amount = credit_val
                is_debit = 0
                
        if date_val:
            rows.append({
                'date': date_val,
                'raw_description': desc_val,
                'amount': amount,
                'is_debit': is_debit
            })
            
    return rows

def parse_ofx_custom(ofx_text: str) -> list:
    """
    Custom regex-based OFX/QFX parser (failsafe if ofxparse library fails).
    """
    transactions = []
    
    # Split into transaction blocks
    trn_blocks = re.findall(r'<STMTTRN>(.*?)</STMTTRN>', ofx_text, re.DOTALL | re.IGNORECASE)
    if not trn_blocks:
        # Fallback if tags are not explicitly closed (standard for some SGML OFX)
        trn_blocks = ofx_text.split('<STMTTRN>')[1:]
        
    for block in trn_blocks:
        def get_tag(tag):
            # Matches <TAG>value or <TAG>value</TAG> until a newline or next tag
            match = re.search(rf'<{tag}>([^<\r\n]+)', block, re.IGNORECASE)
            return match.group(1).strip() if match else ""
            
        dtposted = get_tag('DTPOSTED')
        trnamt = get_tag('TRNAMT')
        name = get_tag('NAME')
        memo = get_tag('MEMO')
        
        if not dtposted or not trnamt:
            continue
            
        # Standardize date: YYYYMMDD... -> YYYY-MM-DD
        date_str = ""
        if len(dtposted) >= 8:
            date_str = f"{dtposted[:4]}-{dtposted[4:6]}-{dtposted[6:8]}"
        else:
            continue
            
        amount_val = float(trnamt)
        desc = name if name else memo
        
        transactions.append({
            'date': date_str,
            'raw_description': desc,
            'amount': abs(amount_val),
            'is_debit': 1 if amount_val < 0 else 0
        })
        
    return transactions

def parse_ofx(file_content: str) -> list:
    """
    Parses OFX content using ofxparse if available, falling back to regex parser.
    """
    if ofxparse_available:
        try:
            # ofxparse requires file-like stream
            f = io.StringIO(file_content)
            ofx = OfxParser.parse(f)
            transactions = []
            for account in ofx.accounts:
                statement = account.statement
                for tx in statement.transactions:
                    transactions.append({
                        'date': tx.date.strftime('%Y-%m-%d'),
                        'raw_description': tx.memo if tx.memo else tx.payee,
                        'amount': abs(float(tx.amount)),
                        'is_debit': 1 if float(tx.amount) < 0 else 0
                    })
            return transactions
        except Exception:
            # Fallback to custom regex parser if library parser fails
            return parse_ofx_custom(file_content)
    else:
        return parse_ofx_custom(file_content)

def parse_pdf(pdf_file_path_or_bytes) -> list:
    """
    Parses bank statements in PDF format using pdfplumber.
    Falls back to line-by-line regex if table extraction fails.
    """
    if not pdfplumber_available:
        raise ImportError("pdfplumber is not installed.")
        
    transactions = []
    
    # Try structured table extraction first
    with pdfplumber.open(pdf_file_path_or_bytes) as pdf:
        if len(pdf.pages) > MAX_PAGE_COUNT:
            raise ValueError(f"PDF page count ({len(pdf.pages)}) exceeds the maximum allowed limit of {MAX_PAGE_COUNT} pages.")
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    # Filter out empty cells
                    row = [str(cell or "").strip() for cell in row if cell is not None]
                    if len(row) < 3:
                        continue
                        
                    # Let's see if we can identify columns
                    date_val = None
                    amount_val = None
                    desc_cells = []
                    
                    for cell in row:
                        if not date_val:
                            parsed_d = parse_date(cell)
                            if parsed_d:
                                date_val = parsed_d
                                continue
                        
                        # Try to parse amount
                        if amount_val is None:
                            parsed_a = parse_amount(cell)
                            # Make sure it's not a year or code resembling an amount
                            if parsed_a is not None and '.' in cell:
                                amount_val = parsed_a
                                continue
                        
                        desc_cells.append(cell)
                        
                    if date_val and amount_val is not None:
                        transactions.append({
                            'date': date_val,
                            'raw_description': " ".join(desc_cells).strip(),
                            'amount': abs(amount_val),
                            'is_debit': 1 if amount_val < 0 or '-' in str(amount_val) else 0
                        })
                        
    # If structured table parsing extracted nothing, fall back to regex line-by-line
    if not transactions:
        with pdfplumber.open(pdf_file_path_or_bytes) as pdf:
            all_text = ""
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    all_text += text + "\n"
            
            transactions = parse_pdf_text_fallback(all_text)
            
    return transactions

def parse_pdf_text_fallback(text: str) -> list:
    """
    Parses raw text line-by-line using regexes to find transaction rows.
    """
    transactions = []
    
    # Common transaction patterns in PDF statements:
    # 1. Date (MM/DD or YYYY-MM-DD or Mon DD), followed by description, ending with a float amount
    # Date pattern matches: 08/12, 08-12, Aug 12, August 12, 2026-08-12
    date_pattern = r'(\d{2}[-/]\d{2}(?:[-/]\d{2,4})?|[A-Za-z]{3,9}\s+\d{1,2})'
    # Amount pattern matches: 12.50, -1,250.00, $5.00, (30.00)
    amount_pattern = r'(-?\$?\s*\d{1,3}(?:,\d{3})*\.\d{2}|\(\$?\d{1,3}(?:,\d{3})*\.\d{2}\))'
    
    pattern = re.compile(rf'^\s*{date_pattern}\s+(.*?)\s+{amount_pattern}\s*$', re.IGNORECASE)
    
    for line in text.split('\n'):
        line = line.strip()
        match = pattern.match(line)
        if match:
            date_str, desc, amount_str = match.groups()
            
            parsed_date = parse_date(date_str)
            parsed_amt = parse_amount(amount_str)
            
            if parsed_date and parsed_amt is not None:
                transactions.append({
                    'date': parsed_date,
                    'raw_description': desc.strip(),
                    'amount': abs(parsed_amt),
                    'is_debit': 1 if parsed_amt < 0 or '-' in amount_str or '(' in amount_str else 0
                })
                
    return transactions

def normalize_statement(file_name: str, file_content_bytes: bytes, account_id: int) -> list:
    """
    Determines file type, validates magic bytes and limits, parses it, and adds SHA-256 signatures.
    Returns a list of standardized, sanitized, and masked transactions ready for staging.
    """
    # Denial of Service limit checks
    if len(file_content_bytes) > MAX_FILE_SIZE:
        raise ValueError(f"Security Violation: File size ({len(file_content_bytes)} bytes) exceeds the maximum allowed limit of {MAX_FILE_SIZE} bytes.")

    # MIME sniffing check / Magic bytes validation
    if not validate_file_header(file_name, file_content_bytes):
        raise ValueError("Security Violation: File headers do not match the expected format of the selected file type.")

    file_lower = file_name.lower()
    raw_txs = []
    
    if file_lower.endswith('.pdf'):
        # Convert bytes to file-like object for pdfplumber
        pdf_file = io.BytesIO(file_content_bytes)
        raw_txs = parse_pdf(pdf_file)
    elif file_lower.endswith('.csv'):
        # Convert bytes to string
        csv_text = file_content_bytes.decode('utf-8', errors='ignore')
        raw_txs = parse_csv(csv_text)
    elif file_lower.endswith('.ofx') or file_lower.endswith('.qfx'):
        ofx_text = file_content_bytes.decode('utf-8', errors='ignore')
        raw_txs = parse_ofx(ofx_text)
    else:
        raise ValueError("Unsupported file extension. Please upload a PDF, CSV, or OFX file.")
        
    # Standardize description, clean and mask input values, and compute hash signatures
    normalized_txs = []
    for tx in raw_txs:
        date = tx['date']
        raw_desc = tx['raw_description']
        amount = tx['amount']
        is_debit = tx['is_debit']
        
        # Strip injection strings, control chars, and mask sensitive PII (SINs, CC cards, bank accounts)
        sanitized_desc = sanitize_text(raw_desc)
        masked_desc = mask_pii(sanitized_desc)
        
        # Generate the cryptographic deduplication signature
        sig = generate_transaction_hash(date, masked_desc, amount, account_id)
        
        normalized_txs.append({
            'account_id': account_id,
            'date': date,
            'raw_description': masked_desc,
            'clean_merchant': masked_desc.strip(),  # default clean to raw description
            'category_id': None,                 # will be assigned by rules engine
            'amount': amount,
            'is_debit': is_debit,
            'hash_signature': sig
        })
        
    return normalized_txs
