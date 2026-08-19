import os
import sys
import time
import subprocess
import pytest
from playwright.sync_api import Page, expect

# Run Streamlit server locally in the background during e2e tests
@pytest.fixture(scope="module", autouse=True)
def run_streamlit():
    # Start Streamlit server on a test port (e.g. 8503)
    env = os.environ.copy()
    # Add src to python path
    env["PYTHONPATH"] = os.path.abspath(os.path.join(os.path.dirname(__file__), "../..", "src"))
    
    server_process = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app.py", "--server.port", "8503", "--server.headless", "true"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    
    # Wait for the server to spin up
    time.sleep(6)
    
    yield
    
    # Terminate the server after test execution
    server_process.terminate()
    server_process.wait()

def test_lock_screen(page: Page):
    # Navigate to the Streamlit app
    page.goto("http://localhost:8503")
    
    # Wait for heading to be visible
    page.wait_for_selector("h1:has-text('Vault Finance 🔒')", timeout=25000)
    
    # Verify title
    expect(page.get_by_role("heading", name="Vault Finance 🔒")).to_be_visible()
    
    # Verify warning instructions
    expect(page.get_by_text("Enter your Master Passphrase")).to_be_visible()
    
    # Check that input field exists
    expect(page.get_by_placeholder("Enter Passphrase...")).to_be_visible()

def test_unlock_flow(page: Page):
    # This test handles both SQLCipher mode and SQLite fallback mode robustly.
    page.goto("http://localhost:8503")
    page.wait_for_selector("h1:has-text('Vault Finance 🔒')", timeout=25000)
    
    # 1. Type wrong password to test lock behavior (only fails if database is encrypted)
    password_input = page.get_by_placeholder("Enter Passphrase...")
    password_input.fill("wrong_password")
    
    unlock_btn = page.get_by_role("button", name="Unlock Vault")
    unlock_btn.click()
    
    time.sleep(3)
    
    # Check if the error message is shown (indicating encrypted database is active)
    error_indicator = page.get_by_text("Invalid passphrase")
    
    if error_indicator.is_visible():
        # SQLCipher is active: the app remains locked
        expect(page.get_by_placeholder("Enter Passphrase...")).to_be_visible()
        
        # 2. Enter correct password to unlock
        password_input.fill("demo123")
        unlock_btn.click()
        time.sleep(5)
        
    # Standard SQLite fallback or successful decryption: the app is now unlocked
    expect(page.get_by_placeholder("Enter Passphrase...")).not_to_be_visible()
    
    # Verify main tabs are visible
    expect(page.get_by_role("tab", name="📈 Dashboard")).to_be_visible()
    expect(page.get_by_role("tab", name="📂 Ledger")).to_be_visible()
    expect(page.get_by_role("tab", name="📥 Statement Ingestion")).to_be_visible()
    expect(page.get_by_role("tab", name="🏠 Mortgage & Debt")).to_be_visible()
    expect(page.get_by_role("tab", name="⚙️ Rules & Settings")).to_be_visible()

def test_create_custom_rule(page: Page):
    # Navigate to app and unlock
    page.goto("http://localhost:8503")
    page.wait_for_selector("h1:has-text('Vault Finance 🔒')", timeout=25000)
    
    password_input = page.get_by_placeholder("Enter Passphrase...")
    password_input.fill("demo123")
    unlock_btn = page.get_by_role("button", name="Unlock Vault")
    unlock_btn.click()
    
    # Wait for app unlock
    page.get_by_role("tab", name="📈 Dashboard").wait_for(timeout=25000)
    
    # Go to Rules & Settings tab
    page.get_by_role("tab", name="⚙️ Rules & Settings").click()
    
    # Wait for the rules header to be visible
    page.wait_for_selector("text=System Configurations", timeout=20000)
    
    # Expand "Create Custom Match Rule"
    page.get_by_text("Create Custom Match Rule").click()
    
    # Fill in regex pattern
    import random
    unique_pattern = f"(?i)disneyplus_{random.randint(10000, 99999)}"
    page.get_by_placeholder("e.g. (?i)netflix|prime video").fill(unique_pattern)
    
    # Save the rule
    page.get_by_role("button", name="Save Rule").click()
    
    # Wait for the rerun and page reload to finish
    time.sleep(4)
    

    # Go to Rules & Settings tab again (since rerun resets to the default tab)
    page.get_by_role("tab", name="⚙️ Rules & Settings").click()
    time.sleep(3)
    
    # Expand "Delete Existing Rule" expander
    page.get_by_text("Delete Existing Rule").click()
    time.sleep(2)
    
    # Click the selectbox to open the dropdown options
    page.locator("div[data-testid='stSelectbox']:has-text('Rule to Delete') input").click()
    time.sleep(2)
    
    # Verify the new rule is listed in the dropdown options
    page.wait_for_selector(f"text={unique_pattern}", timeout=20000, state="attached")
    expect(page.get_by_text(unique_pattern).first).to_be_attached()
