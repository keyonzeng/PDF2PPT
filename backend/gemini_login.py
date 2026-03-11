"""
Gemini OAuth Login CLI

Usage:
    cd backend
    uv run python gemini_login.py
"""
from app.services.auth_service import get_valid_credentials, run_local_server_auth

def main():
    print("=== Gemini OAuth Login ===\n")
    
    creds = get_valid_credentials()
    if creds:
        print("✅ Already authenticated! Token is valid.")
        print("   To re-authenticate, delete token.json and run again.")
        return
    
    print("⚡ No valid token found. Starting OAuth flow...\n")
    creds = run_local_server_auth()
    
    if creds:
        print("\n✅ SUCCESS! You can now use Gemini API.")
    else:
        print("\n❌ Authentication failed. Please try again.")

if __name__ == "__main__":
    main()
