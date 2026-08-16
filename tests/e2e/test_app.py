import os
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
        [".venv/bin/streamlit", "run", "app.py", "--server.port", "8503", "--server.headless", "true"],
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
    expect(page.get_by_role("tab")).to_have_count(5)
