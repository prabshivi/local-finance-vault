# Vault Finance — Secure Local-First Personal Finance Manager

Vault Finance is a 100% offline, private, and encrypted personal finance application. It supports separate **Personal**, **Incorporation**, and **Combined** profiles, connects to bank institutions via a Plaid-style offline connection simulator, parses statement uploads (PDF, CSV, OFX/QFX) locally, applies priority-based regex rules, and draws premium interactive dashboards.

All data is stored locally and encrypted at rest with AES-256 using SQLCipher. There is zero telemetry, zero cloud integration, and zero outbound network requests.

---

## Features

### 1. 💼 Multi-Profile Financial Separation
* **Personal Profile**: Tracks full-time salary deposits from **Empire Life** along with personal accounts (Chase, Fidelity, Amex), utilities, auto loans, and mortgages.
* **Incorporation Profile**: Tracks contract income from **Petline** along with business checking accounts, business cards, and corporate SaaS expenses.
* **Combined Profile**: Aggregates metrics to show total combined net worth, aggregated cash flows, and combined expense structures.

### 2. 🔗 Offline Bank Connection Portal
* A simulated, local-first connection portal to link bank accounts (Chase, Fidelity, Wells Fargo, Amex, TD Bank, Empire Life, Petline) directly from any tab.
* Implements mock credentials verification, 2FA/MFA challenges, and instant local ledger synchronization.

### 3. ✨ Premium Cyber-Cyan Glassmorphic UI
* Animated floating background gradient orbs and finance-related symbols (💵, 📈, 🔒, ₿, 💰) that translate, scale, and rotate dynamically.
* Glassmorphism cards with electric cyan accents, hover vertical translation offsets, and neon box-shadow glows.
* Dark-adapted high-contrast Plotly visualizations mapping cash flows and net worth history.

---

## Project Structure

```
├── .streamlit/          # Streamlit theme and font configuration
├── src/                 # Main source directory
│   ├── app.py           # Core application UI logic and layouts
│   ├── core/            # Cryptographic, parser, and DB core scripts
│   └── seed_data.py     # Database seeder generating transactions
├── tests/               # Unit and e2e test files
│   ├── conftest.py      # Pytest path and runner overrides
│   ├── e2e/             # Playwright browser integration tests
│   └── unit/            # Core DB and crypto unit test cases
├── app.py               # Root wrapper entrypoint to run src/app.py
├── requirements.txt     # Python packages list
└── README.md            # Project documentation
```

---

## System Requirements

To run Vault Finance with database encryption enabled, you must have the SQLCipher C libraries installed on your host system.

### OS-Level SQLCipher Installation

#### macOS (via Homebrew)
```bash
# 1. Install SQLCipher and OpenSSL
brew install sqlcipher openssl@3

# 2. Add flags so python compilation links correctly during library build
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
*If SQLCipher compilation or bindings are not detected on the host system, Vault Finance will automatically fall back to standard unencrypted SQLite mode and display a warning banner.*

---

## Local Installation

1. Clone or copy the project files to a local directory:
   ```bash
   cd local-finance-vault
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

Start the Streamlit application using the root virtual environment's Streamlit binary:

```bash
.venv/bin/streamlit run app.py
```

The application will launch in your browser (typically at `http://localhost:8501` or fallback port `8502`).

---

## Verification & Testing

To run the automated unit test suite and verify cryptographic hashing, schema migrations, custom OFX parsing, and rules-engine classifications:

```bash
.venv/bin/pytest tests/unit/ tests/test_parser.py tests/test_security.py
```

---

## Security Specifications

1. **Passphrase Hashing & Verification**: Your master passphrase is never stored in plain text. On startup, the passphrase is sent directly to SQLCipher as the decryption key. A test query reads `sqlite_master` to verify decryption success.
2. **Zero-Trust Salt & Keys**: Uses robust key derivation functions with standard 250,000 iterations to secure local database records.
3. **Transaction Deduplication**: Every transaction computes an SHA-256 hash:
   `sha256(date | raw_description | amount | account_id)`
   This prevents reloading identical transactions, even across multiple statement uploads.
4. **Completely Local**: Running the app requires zero internet access. All Plotly charts, pdfplumber page extractions, and rules are executed locally on your CPU.
