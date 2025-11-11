import os
import base64
import hashlib
import secrets
import time
from typing import Dict, Any
import requests

# Simple in-memory store for PKCE verifiers and states. For demo only.
_STORE: Dict[str, Dict[str, Any]] = {}


def generate_code_verifier(length: int = 64) -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(length)).decode('utf-8').rstrip('=')


def code_challenge_from_verifier(verifier: str) -> str:
    m = hashlib.sha256()
    m.update(verifier.encode('utf-8'))
    digest = m.digest()
    return base64.urlsafe_b64encode(digest).decode('utf-8').rstrip('=')


def create_pkce_state(expire_seconds: int = 300) -> Dict[str, str]:
    state = secrets.token_urlsafe(16)
    verifier = generate_code_verifier()
    challenge = code_challenge_from_verifier(verifier)
    _STORE[state] = {'verifier': verifier, 'challenge': challenge, 'expires_at': time.time() + expire_seconds}
    return {'state': state, 'verifier': verifier, 'challenge': challenge}


def pop_verifier_for_state(state: str) -> str | None:
    entry = _STORE.pop(state, None)
    if not entry:
        return None
    if entry.get('expires_at', 0) < time.time():
        return None
    return entry.get('verifier')


def exchange_code_for_tokens(code: str, verifier: str, redirect_uri: str) -> Dict[str, Any]:
    domain = os.getenv('AUTH0_DOMAIN')
    client_id = os.getenv('AUTH0_CLIENT_ID')
    # For public clients PKCE is sufficient; if you have a client secret, you can add it here.
    token_url = f'https://{domain}/oauth/token'
    payload = {
        'grant_type': 'authorization_code',
        'client_id': client_id,
        'code': code,
        'code_verifier': verifier,
        'redirect_uri': redirect_uri,
    }
    resp = requests.post(token_url, json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()
