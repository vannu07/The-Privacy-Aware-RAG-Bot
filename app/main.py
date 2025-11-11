from fastapi import FastAPI, Depends, HTTPException
from .models import LoginRequest, Document, QueryRequest, QueryResponse
from .auth import authenticate, create_access_token, get_current_user
from . import db
from .fga import FGAClient
from typing import List
from fastapi import Request
import os
from fastapi.responses import RedirectResponse, HTMLResponse
from urllib.parse import urlencode
from . import oidc

app = FastAPI(title="Privacy-Aware RAG Bot (Demo)")
fga_client = FGAClient()

# serve static callback page
from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.on_event('startup')
def startup_event():
    db.init_db()
    db.seed_sample_data()
    # If vector retrieval is enabled, build the vector index on startup to avoid lazy build during queries
    if os.getenv('USE_VECTOR') == '1':
        try:
            db.build_vector_store()
        except Exception:
            # non-fatal: continue with SQL fallback
            pass

@app.post('/login')
def login(req: LoginRequest):
    user = authenticate(req.username)
    if not user:
        raise HTTPException(status_code=401, detail='Invalid username')
    token = create_access_token(user)
    return {"access_token": token, "token_type": "bearer"}


@app.get('/auth/login')
def auth_login():
    """Redirects the user to Auth0 authorize endpoint using PKCE.
    Configure environment variables: AUTH0_DOMAIN, AUTH0_CLIENT_ID, AUTH0_AUDIENCE, AUTH0_REDIRECT_URI
    """
    domain = os.getenv('AUTH0_DOMAIN')
    client_id = os.getenv('AUTH0_CLIENT_ID')
    audience = os.getenv('AUTH0_AUDIENCE')
    redirect_uri = os.getenv('AUTH0_REDIRECT_URI')
    if not (domain and client_id and redirect_uri):
        raise HTTPException(status_code=500, detail='AUTH0_DOMAIN, AUTH0_CLIENT_ID and AUTH0_REDIRECT_URI must be set')
    pkce = oidc.create_pkce_state()
    params = {
        'response_type': 'code',
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'scope': 'openid profile email',
        'state': pkce['state'],
        'code_challenge': pkce['challenge'],
        'code_challenge_method': 'S256'
    }
    if audience:
        params['audience'] = audience
    auth_url = f'https://{domain}/authorize?{urlencode(params)}'
    return RedirectResponse(auth_url)


@app.get('/auth/callback')
def auth_callback(code: str | None = None, state: str | None = None):
    if not code or not state:
        raise HTTPException(status_code=400, detail='code and state required')
    verifier = oidc.pop_verifier_for_state(state)
    if not verifier:
        raise HTTPException(status_code=400, detail='invalid or expired state')
    redirect_uri = os.getenv('AUTH0_REDIRECT_URI')
    try:
        tokens = oidc.exchange_code_for_tokens(code, verifier, redirect_uri)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f'token exchange failed: {e}')
    # Return a small HTML page that shows tokens so the developer can copy them for testing
    payload = urlencode({'tokens': urlencode({'id_token': tokens.get('id_token', ''), 'access_token': tokens.get('access_token', '')})})
    # redirect to static page with tokens in query
    return RedirectResponse(f'/static/oidc_callback.html?tokens={urlencode([("", str(tokens))])}')

@app.post('/documents/add')
def add_document(doc: Document, user=Depends(get_current_user)):
    # Only managers can add documents in our demo
    if user.role != 'manager':
        raise HTTPException(status_code=403, detail='Only managers may add documents in this demo')
    db.add_document(doc.id, doc.title, doc.content, doc.sensitive)
    return {"status": "ok", "id": doc.id}

@app.post('/query', response_model=QueryResponse)
def query(req: QueryRequest, user=Depends(get_current_user)):
    hits = db.search_documents(req.query)
    allowed = []
    for h in hits:
        doc_id = h['id']
        # For FGA checks we'll construct subject as user.sub (e.g., user:bob)
        subject = user.sub
        obj = f'document:{doc_id}'
        if fga_client.check(subject, 'can_view', obj):
            allowed.append(Document(id=doc_id, title=h['title'], content=h['content'], sensitive=bool(h['sensitive'])))
        else:
            # not allowed: skip
            pass
    return QueryResponse(results=allowed)


@app.post('/mock-fga/check')
def mock_fga_check(body: dict, request: Request):
    """A mock FGA endpoint for local testing. Accepts {subject, relation, object} and
    returns {allowed: true|false} based on the local fga_relationships table."""
    subject = body.get('subject')
    relation = body.get('relation')
    obj = body.get('object')
    if not subject or not relation or not obj:
        raise HTTPException(status_code=400, detail='subject/relation/object required')
    allowed = db.check_relationship(subject, relation, obj)
    # also check role mapping for simple demo
    if not allowed and subject.startswith('user:'):
        username = subject.split(':', 1)[1]
        role_key = f'role:manager' if username == 'bob' else f'role:employee'
        allowed = db.check_relationship(role_key, relation, obj)
    return {'allowed': allowed}
