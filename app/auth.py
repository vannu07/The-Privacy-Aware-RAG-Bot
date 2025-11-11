import os
from datetime import datetime, timedelta
from jose import jwt, JWTError, jwk
from jose.utils import base64url_decode
from fastapi import HTTPException, Depends, Header
from .models import User
import os
import requests

SECRET = os.getenv('APP_SECRET', 'devsecret')
ALGORITHM = 'HS256'
ACCESS_TOKEN_EXPIRE_MINUTES = 60*24

# Simple demo user store
USERS = {
    'alice': {'sub': 'user:alice', 'username': 'alice', 'role': 'employee', 'department': 'engineering'},
    'bob': {'sub': 'user:bob', 'username': 'bob', 'role': 'manager', 'department': 'hr'},
}

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET, algorithm=ALGORITHM)
    return encoded_jwt


def authenticate(username: str):
    user = USERS.get(username)
    if not user:
        return None
    return user


def get_current_user(authorization: str | None = Header(None)) -> User:
    if not authorization:
        raise HTTPException(status_code=401, detail='Missing Authorization header')
    try:
        scheme, _, token = authorization.partition(' ')
        if scheme.lower() != 'bearer' or not token:
            raise HTTPException(status_code=401, detail='Invalid Authorization header')
        # If AUTH0_DOMAIN/AUDIENCE are set, validate using Auth0 JWKS
        auth0_domain = os.getenv('AUTH0_DOMAIN')
        auth0_audience = os.getenv('AUTH0_AUDIENCE')
        if auth0_domain and auth0_audience:
            jwks_url = f'https://{auth0_domain}/.well-known/jwks.json'
            try:
                jwks = requests.get(jwks_url, timeout=5).json()
            except Exception:
                raise HTTPException(status_code=401, detail='Unable to fetch JWKS')
            try:
                unverified_header = jwt.get_unverified_header(token)
            except JWTError:
                raise HTTPException(status_code=401, detail='Invalid token header')

            kid = unverified_header.get('kid')
            rsa_key = None
            for key in jwks.get('keys', []):
                if key.get('kid') == kid:
                    rsa_key = {
                        'kty': key.get('kty'),
                        'kid': key.get('kid'),
                        'use': key.get('use'),
                        'n': key.get('n'),
                        'e': key.get('e')
                    }
                    break

            if rsa_key is None:
                raise HTTPException(status_code=401, detail='Appropriate JWKS key not found')

            try:
                public_key = jwk.construct(rsa_key)
                message, encoded_sig = token.rsplit('.', 1)
                decoded_sig = base64url_decode(encoded_sig.encode('utf-8'))
                if not public_key.verify(message.encode('utf-8'), decoded_sig):
                    raise HTTPException(status_code=401, detail='Invalid token signature')
                # Decode claims
                payload = jwt.decode(token, public_key.to_pem().decode('utf-8'), algorithms=['RS256'], audience=auth0_audience)
            except Exception:
                raise HTTPException(status_code=401, detail='Token verification failed')

            # Map Auth0 claims to our User model; common claims: sub, nickname/email, roles in claims
            user_dict = {
                'sub': payload.get('sub'),
                'username': payload.get('nickname') or payload.get('name') or payload.get('email') or payload.get('sub'),
                'role': payload.get('https://example.com/role') or payload.get('role') or 'employee',
                'department': payload.get('https://example.com/department') or None
            }
            return User(**user_dict)
        else:
            payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
            # payload should include sub, username, role, department
            return User(**payload)
    except JWTError:
        raise HTTPException(status_code=401, detail='Invalid token')
