import re
from core.db import get_rules

def clean_merchant_name(raw_desc: str) -> str:
    """
    Cleans credit card and bank transaction descriptions by stripping out
    transaction IDs, store numbers, locations, dates, phone numbers, and common noise.
    
    Example: "STARBUCKS STORE #12345 CA 94103" -> "STARBUCKS"
    """
    if not raw_desc:
        return ""
        
    name = raw_desc.upper()
    
    # 1. Remove phone numbers (e.g. 800-555-0199 or 8005550199)
    name = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '', name)
    
    # 2. Clean URLs (e.g. WWW.NETFLIX.COM -> NETFLIX, NETFLIX.COM/BILL -> NETFLIX)
    name = re.sub(r'\bWWW\.', '', name)
    name = re.sub(r'\.[A-Z]{2,4}(?:/[A-Z0-9_]*)?\b', '', name)
    
    # 3. Remove store numbers, checkout numbers (e.g. STORE #1234, #44591)
    name = re.sub(r'\bSTORE\s*#?\d+\b', '', name)
    name = re.sub(r'#\s*\d+\b', '', name)
    
    # 4. Remove purchase details like dates (e.g. ON 08/12, ON 0812, 08-12)
    name = re.sub(r'\bON\s+\d{2}[-/]?\d{2}\b', '', name)
    
    # 5. Remove long numeric sequences (likely card tokens, swipe codes or terminal IDs)
    name = re.sub(r'\b\d{5,}\b', '', name)
    
    # 6. Remove state codes at the end of the line (e.g. SAN FRANCISCO CA)
    name = re.sub(r'\b[A-Z]{2}\s*$', '', name)
    
    # 7. Replace special characters and transaction markers with spaces
    name = re.sub(r'[*#_\-+=/\\:;]', ' ', name)
    
    # 8. Collapse multiple spaces and trim
    name = re.sub(r'\s+', ' ', name)
    name = name.strip()
    
    # Fallback: if description was fully numeric or fully cleaned out, return original trimmed
    return name if name else raw_desc.strip()

def suggest_regex_pattern(raw_desc: str) -> str:
    """
    Suggests a regex pattern for a merchant based on the cleaned description.
    Escapes special regex characters and uses case-insensitive match (?i).
    """
    cleaned = clean_merchant_name(raw_desc)
    # Match the words as a fragment anywhere in the description
    # E.g. "STARBUCKS" -> "(?i)STARBUCKS"
    escaped = re.escape(cleaned)
    return f"(?i){escaped}"

def categorize_transaction(raw_desc: str, rules: list) -> tuple:
    """
    Matches raw description against a list of rule dicts.
    Each rule has 'regex_pattern', 'target_category_id', and 'category_name'.
    Rules are expected to be pre-sorted by priority (descending).
    
    Returns:
        (category_id, clean_merchant)
    """
    cleaned_merchant = clean_merchant_name(raw_desc)
    
    for rule in rules:
        pattern = rule['regex_pattern']
        try:
            # Check if the regex matches
            if re.search(pattern, raw_desc, re.IGNORECASE) or re.search(pattern, cleaned_merchant, re.IGNORECASE):
                return rule['target_category_id'], cleaned_merchant
        except re.error:
            # Skip invalid regex patterns gracefully
            continue
            
    return None, cleaned_merchant

def apply_rules_to_staged(transactions: list, rules: list) -> list:
    """
    Categorizes and cleans a list of staged transaction dicts using active rules.
    """
    updated_txs = []
    for tx in transactions:
        cat_id, clean_name = categorize_transaction(tx['raw_description'], rules)
        
        # Clone and update properties
        tx_copy = dict(tx)
        tx_copy['clean_merchant'] = clean_name
        tx_copy['category_id'] = cat_id if cat_id is not None else tx.get('category_id')
        updated_txs.append(tx_copy)
        
    return updated_txs
