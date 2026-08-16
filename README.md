# Vault Finance — Secure Local-First Personal Finance Manager

Vault Finance is a 100% offline, private, and encrypted personal finance application. It parses statements (PDFs, CSVs, OFX/QFX) for checking accounts, credit cards, and mortgages, applies priority-based regex categorization rules, and draws premium interactive Plotly dashboards and debt accelerator payoff curves.

All data is stored locally and encrypted at rest with AES-256 using SQLCipher. There is zero telemetry, zero cloud integration, and zero outbound network requests.

---

## System Requirements

To build and run Vault Finance with database encryption enabled, you must have the SQLCipher C libraries installed on your host system.

### OS-Level SQLCipher Installation

#### macOS (via Homebrew)
```bash
# 1. Install SQLCipher and OpenSSL
brew install sqlcipher openssl@3

# 2. Add flags so python compilation links correctly during library build (if compiling from source)
export LDFLAGS="-L$(brew --prefix sqlcipher)/lib -L$(brew --prefix openssl@3)/lib"
export CPPFLAGS="-I$(brew --prefix sqlcipher)/include -I$(brew --prefix openssl@3)/include"
```

#### Ubuntu / Debian
```bash
sudo apt-get update
sudo apt-get install -y sqlcipher libsqlcipher-dev openssl libssl-dev
```

#### Windows
For Windows, installing pre-compiled wheels is recommended:
```cmd
pip install sqlcipher3-binary
```
If compile issues persist, Vault Finance will automatically fall back to standard unencrypted SQLite mode and display a prominent warning banner.

---

## Local Installation

1. Clone or copy the project files to a local directory:
   ```bash
   cd /Users/shiviprabhakar/.gemini/antigravity-ide/scratch/local_finance_app
   ```

2. Initialize a Python virtual environment:
   ```bash
   python3 -m venv .venv
   ```

3. Install the required Python dependencies:
   ```bash
   .venv/bin/pip install -r requirements.txt
   ```

4. *(Optional)* Install SQLCipher Python bindings:
   ```bash
   # Attempt standard binary wheel
   .venv/bin/pip install sqlcipher3-binary
   
   # Or compile against system libraries
   .venv/bin/pip install sqlcipher3
   ```

---

## Running the Application

Start the Streamlit application using the local virtual environment's Streamlit binary:

```bash
.venv/bin/streamlit run app.py
```

The application will launch in your browser (typically at `http://localhost:8501`).

---

## Verification & Testing

To run the automated test suite and verify cryptographic hashing, schema migrations, custom OFX parsing, and rules-engine classifications:

```bash
.venv/bin/python verify.py
```

---

## Security Specifications

1. **Passphrase Hashing & Verification**: Your master passphrase is never stored in plain text. On startup, the passphrase is sent directly to SQLCipher as the decryption key. A test query reads `sqlite_master` to verify decryption success.
2. **Transaction Deduplication**: Every transaction computes an SHA-256 hash:
   `sha256(date | raw_description | amount | account_id)`
   This prevents reloading identical transactions, even across multiple statement uploads.
3. **Completely Local**: Running the app requires zero internet access. All Plotly charts, pdfplumber page extractions, and rules are executed locally on your CPU.
