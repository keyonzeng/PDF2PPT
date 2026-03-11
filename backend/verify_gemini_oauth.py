"""
Manual Verification Script for Gemini OAuth.

Usage:
    cd backend
    uv run python verify_gemini_oauth.py
"""
from app.services.auth_service import get_valid_credentials, get_token_path, get_secret_path
from app.services.llm_service import generate_speaker_notes
import os

def main():
    print("=== Gemini OAuth Verification ===\n")
    
    # 1. Check Prerequisites
    secret = get_secret_path()
    token = get_token_path()
    
    print(f"Client Secret: {secret} ({'EXISTS' if os.path.exists(secret) else 'MISSING'})")
    print(f"Token File:    {token} ({'EXISTS' if os.path.exists(token) else 'MISSING'})")
    
    if not os.path.exists(secret):
        print("\n❌ ERROR: client_secret.json not found!")
        print("Download from Google Cloud Console (OAuth 2.0 Desktop App).")
        print(f"Save to: {os.path.abspath(secret)}")
        return
    
    # 2. Attempt Auth
    print("\n[Attempting Authentication...]")
    creds = get_valid_credentials()
    
    if not creds:
        print("❌ Authentication FAILED.")
        return
    
    print("✅ Authentication SUCCESS!")
    
    # 3. Test API Call
    print("\n[Testing Gemini API Call...]")
    response = generate_speaker_notes("Hello! Confirm OAuth is working.", provider="gemini")
    
    if response:
        print(f"✅ Gemini Response:\n{response[:500]}...")
    else:
        print("❌ No response received.")

if __name__ == "__main__":
    main()
