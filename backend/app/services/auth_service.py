"""
Antigravity-style OAuth Service for Gemini.

Implements Openclaw's OAuth flow using a local HTTP server callback.
"""
import os
import json
import hashlib
import base64
import secrets
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlencode, urlparse, parse_qs
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import requests
from app.core.config import settings

# Openclaw's Public Client ID
ANTIGRAVITY_CLIENT_ID = "1071006060591-tmhssin2h21lcre235vtolojh4g403ep.apps.googleusercontent.com"

SCOPES = [
    'https://www.googleapis.com/auth/cloud-platform',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
]

TOKEN_URI = "https://oauth2.googleapis.com/token"

def build_callback_handler(auth_state: dict):
    class OAuthCallbackHandler(BaseHTTPRequestHandler):
        """Handle OAuth redirect callback."""

        def log_message(self, format, *args):
            pass

        def do_GET(self):
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)

            if 'code' in params:
                auth_state['code'] = params['code'][0]
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b"""
                    <html><body style="font-family: sans-serif; text-align: center; padding-top: 50px;">
                    <h1>Authentication Successful!</h1>
                    <p>You can close this window and return to the terminal.</p>
                    </body></html>
                """)
            elif 'error' in params:
                auth_state['error'] = params.get('error_description', params['error'])[0]
                self.send_response(400)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(f"<html><body><h1>Error: {auth_state['error']}</h1></body></html>".encode())
            else:
                self.send_response(404)
                self.end_headers()

    return OAuthCallbackHandler

def get_token_path() -> str:
    return settings.GOOGLE_TOKEN_PATH

def generate_pkce():
    """Generate PKCE code verifier and challenge."""
    verifier = secrets.token_urlsafe(32)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).decode().rstrip('=')
    return verifier, challenge

def build_auth_url(redirect_uri: str, code_challenge: str, state: str) -> str:
    """Build the authorization URL."""
    params = {
        'client_id': ANTIGRAVITY_CLIENT_ID,
        'response_type': 'code',
        'redirect_uri': redirect_uri,
        'scope': ' '.join(SCOPES),
        'code_challenge': code_challenge,
        'code_challenge_method': 'S256',
        'state': state,
        'access_type': 'offline',
        'prompt': 'consent',
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"

def exchange_code(code: str, redirect_uri: str, code_verifier: str) -> Credentials | None:
    """Exchange authorization code for tokens."""
    data = {
        'client_id': ANTIGRAVITY_CLIENT_ID,
        'code': code,
        'code_verifier': code_verifier,
        'grant_type': 'authorization_code',
        'redirect_uri': redirect_uri,
    }
    
    try:
        resp = requests.post(TOKEN_URI, data=data, timeout=30)
        if resp.status_code != 200:
            print(f"Token exchange error: {resp.status_code} - {resp.text}")
            return None
            
        tokens = resp.json()
        
        creds = Credentials(
            token=tokens.get('access_token'),
            refresh_token=tokens.get('refresh_token'),
            token_uri=TOKEN_URI,
            client_id=ANTIGRAVITY_CLIENT_ID,
            scopes=SCOPES,
        )
        return creds
    except Exception as e:
        print(f"Token exchange failed: {e}")
        return None

def load_credentials() -> Credentials | None:
    """Load existing credentials from token file."""
    path = get_token_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r') as f:
            data = json.load(f)
        return Credentials(
            token=data.get('token'),
            refresh_token=data.get('refresh_token'),
            token_uri=TOKEN_URI,
            client_id=ANTIGRAVITY_CLIENT_ID,
            scopes=SCOPES,
        )
    except Exception as e:
        print(f"Error loading credentials: {e}")
        return None

def save_credentials(creds: Credentials):
    """Save credentials to token file."""
    path = get_token_path()
    data = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'client_id': ANTIGRAVITY_CLIENT_ID,
        'scopes': list(SCOPES),
    }
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"Credentials saved to {path}")

def refresh_credentials(creds: Credentials) -> Credentials | None:
    """Refresh expired credentials."""
    if not creds.refresh_token:
        return None
    try:
        creds.refresh(Request())
        save_credentials(creds)
        return creds
    except Exception as e:
        print(f"Failed to refresh: {e}")
        return None

def run_local_server_auth() -> Credentials | None:
    """Run OAuth flow with local HTTP server callback."""
    auth_state = {"code": None, "error": None}
    
    # Generate PKCE
    code_verifier, code_challenge = generate_pkce()
    state = secrets.token_hex(16)
    
    # Find available port
    port = 51121
    redirect_uri = f"http://localhost:{port}/oauth-callback"
    
    # Start local server
    server = HTTPServer(('localhost', port), build_callback_handler(auth_state))
    server.timeout = 120  # 2 minute timeout
    
    # Build and display auth URL
    auth_url = build_auth_url(redirect_uri, code_challenge, state)
    
    print("\n" + "=" * 70)
    print("Opening browser for Google authentication...")
    print("If browser doesn't open, manually visit:")
    print(f"\n{auth_url}")
    print("=" * 70)
    
    # Open browser
    webbrowser.open(auth_url)
    
    print("\nWaiting for authentication callback...")
    
    # Handle one request (the callback)
    server.handle_request()
    server.server_close()
    
    if auth_state["error"]:
        print(f"Authentication error: {auth_state['error']}")
        return None
    
    if not auth_state["code"]:
        print("No authorization code received.")
        return None
    
    print("Authorization code received! Exchanging for token...")
    
    # Exchange code for tokens
    creds = exchange_code(auth_state["code"], redirect_uri, code_verifier)
    if creds:
        save_credentials(creds)
        return creds
    return None

def get_valid_credentials() -> Credentials | None:
    """Main entry point: Get valid credentials."""
    creds = load_credentials()
    
    if creds and creds.valid:
        return creds
    
    if creds and creds.expired and creds.refresh_token:
        refreshed = refresh_credentials(creds)
        if refreshed and refreshed.valid:
            return refreshed
    
    return None

# CLI Entry Point
if __name__ == "__main__":
    print("=== Gemini OAuth Login ===")
    
    creds = get_valid_credentials()
    if creds:
        print("\n✅ Already authenticated! Token is valid.")
    else:
        print("\n⚡ Starting OAuth flow...")
        creds = run_local_server_auth()
        if creds:
            print("\n✅ Authentication successful!")
        else:
            print("\n❌ Authentication failed.")
