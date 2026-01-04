from fastapi import FastAPI, Depends, HTTPException
from .models import (
    LoginRequest,
    Document,
    QueryRequest,
    QueryResponse,
    UserSettings,
    TokenUpsertRequest,
    ContextualActionResponse,
    FeedbackRequest,
    ConversationHistory,
    QueryLog,
    AnalyticsResponse,
    LLMRequest,
)
from .auth import authenticate, create_access_token, get_current_user
from . import db
from .fga import FGAClient
from .token_vault import TokenVault
from . import integrations
from .llm import get_llm_client
from typing import List, Optional
from fastapi import Request
import os
from fastapi.responses import RedirectResponse, HTMLResponse
from urllib.parse import urlencode
from . import oidc
import time
import uuid

app = FastAPI(title="Privacy-Aware RAG Bot (Demo)")
fga_client = FGAClient()
token_vault = TokenVault()
llm_client = get_llm_client()

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

@app.get('/health')
def health_check():
    """Health check endpoint for monitoring and CI/CD readiness verification"""
    return {"status": "ok", "service": "Privacy-Aware RAG Bot"}

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


@app.get('/me/settings', response_model=UserSettings)
def get_settings(user=Depends(get_current_user)):
    settings = db.get_user_settings(user.sub)
    if not settings:
        raise HTTPException(status_code=404, detail='No settings found for user')
    return UserSettings(**settings)


@app.put('/me/settings', response_model=UserSettings)
def update_settings(payload: UserSettings, user=Depends(get_current_user)):
    db.set_user_settings(user.sub, city=payload.city, timezone=payload.timezone, theme=payload.theme)
    return payload


@app.post('/vault/tokens')
def store_token(req: TokenUpsertRequest, user=Depends(get_current_user)):
    token_vault.upsert(user.sub, req.provider, req.token)
    return {'status': 'stored', 'provider': req.provider}


@app.get('/vault/tokens/{provider}')
def read_token(provider: str, user=Depends(get_current_user)):
    token = token_vault.fetch(user.sub, provider)
    if not token:
        raise HTTPException(status_code=404, detail='Token not found for provider')
    # In a real vault you would not return the token directly; for demo we mask it.
    masked = token[:4] + '...' + token[-4:] if len(token) > 8 else '***masked***'
    return {'provider': provider, 'token_preview': masked}


@app.get('/assistant/contextual-weather', response_model=ContextualActionResponse)
def contextual_weather(user=Depends(get_current_user)):
    """Demonstrate context preservation: read first-party settings, then call a third-party API using a vault token."""
    settings = db.get_user_settings(user.sub)
    if not settings:
        raise HTTPException(status_code=404, detail='No settings found for user')

    # Fetch delegated token for third-party weather provider from the Token Vault
    weather_token = token_vault.fetch(user.sub, 'weather')
    # If user-specific token missing, optionally fall back to a shared token (if seeded)
    if not weather_token:
        weather_token = token_vault.fetch('shared', 'weather')

    weather = integrations.fetch_weather(settings.get('city', 'Seattle'), token=weather_token)
    message = (
        f"Hi {user.username}, your preferred city is {settings.get('city')}. "
        f"Current conditions there: {weather.get('description')} at {weather.get('temp_c')}°C."
    )
    return ContextualActionResponse(
        message=message,
        profile=user,
        settings=UserSettings(**settings),
        weather=weather,
    )

@app.post('/documents/add')
def add_document(doc: Document, user=Depends(get_current_user)):
    # Only managers can add documents in our demo
    if user.role != 'manager':
        raise HTTPException(status_code=403, detail='Only managers may add documents in this demo')
    db.add_document(doc.id, doc.title, doc.content, doc.sensitive)
    return {"status": "ok", "id": doc.id}

@app.post('/query', response_model=QueryResponse)
def query(req: QueryRequest, user=Depends(get_current_user)):
    start_time = time.time()
    
    # Generate session ID if not provided
    session_id = req.session_id or str(uuid.uuid4())
    
    # Add user query to conversation history
    db.add_conversation_message(session_id, user.sub, 'user', req.query)
    
    hits = db.search_documents(req.query)
    allowed = []
    retrieved_doc_ids = []
    
    for h in hits:
        doc_id = h['id']
        # For FGA checks we'll construct subject as user.sub (e.g., user:bob)
        subject = user.sub
        obj = f'document:{doc_id}'
        if fga_client.check(subject, 'can_view', obj):
            # Increment view count for analytics
            db.increment_doc_view_count(doc_id)
            
            doc = Document(
                id=doc_id, 
                title=h['title'], 
                content=h['content'], 
                sensitive=bool(h['sensitive']),
                author=h.get('author'),
                created_at=h.get('created_at'),
                updated_at=h.get('updated_at'),
                version=h.get('version'),
                department=h.get('department'),
                tags=h.get('tags'),
                view_count=h.get('view_count', 0),
                helpful_count=h.get('helpful_count', 0)
            )
            allowed.append(doc)
            retrieved_doc_ids.append(doc_id)
        else:
            # not allowed: skip
            pass
    
    # Optional: Generate LLM answer if enabled
    generated_answer = None
    confidence = None
    
    if os.getenv('USE_LLM') == '1' and allowed:
        try:
            # Get conversation history
            conv_history = db.get_conversation_history(session_id, limit=10)
            history_msgs = [
                type('ConversationMessage', (), msg)() 
                for msg in conv_history[:-1]  # Exclude current query
            ]
            
            llm_response = llm_client.generate_answer(req.query, allowed, history_msgs)
            generated_answer = llm_response.answer
            confidence = llm_response.confidence
            
            # Add assistant response to conversation history
            db.add_conversation_message(session_id, user.sub, 'assistant', 
                                       generated_answer, llm_response.citations)
        except Exception as e:
            # Non-fatal: continue without LLM answer
            print(f"LLM error: {e}")
    
    # Log query for analytics
    latency_ms = (time.time() - start_time) * 1000
    query_id = db.log_query(user.sub, req.query, session_id, retrieved_doc_ids, 
                           latency_ms, confidence)
    
    return QueryResponse(
        results=allowed, 
        query_id=query_id, 
        confidence=confidence,
        generated_answer=generated_answer
    )


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


@app.post('/admin/fga')
def admin_add_fga(body: dict, user=Depends(get_current_user)):
    """Add an FGA relationship. Body: {subject, relation, object}. Managers only."""
    if user.role != 'manager':
        raise HTTPException(status_code=403, detail='Only managers may modify FGA relationships')
    subject = body.get('subject')
    relation = body.get('relation')
    obj = body.get('object')
    if not subject or not relation or not obj:
        raise HTTPException(status_code=400, detail='subject, relation and object are required')
    db.add_relationship(subject, relation, obj)
    return {'status': 'ok', 'subject': subject, 'relation': relation, 'object': obj}


@app.delete('/admin/fga')
def admin_remove_fga(body: dict, user=Depends(get_current_user)):
    """Remove an FGA relationship. Body: {subject, relation, object}. Managers only."""
    if user.role != 'manager':
        raise HTTPException(status_code=403, detail='Only managers may modify FGA relationships')
    subject = body.get('subject')
    relation = body.get('relation')
    obj = body.get('object')
    if not subject or not relation or not obj:
        raise HTTPException(status_code=400, detail='subject, relation and object are required')
    ok = db.remove_relationship(subject, relation, obj)
    if not ok:
        raise HTTPException(status_code=404, detail='Relationship not found')
    return {'status': 'ok'}


@app.get('/admin/fga')
def admin_list_fga(user=Depends(get_current_user)):
    """List all FGA relationships. Managers only."""
    if user.role != 'manager':
        raise HTTPException(status_code=403, detail='Only managers may view FGA relationships')
    rels = db.list_relationships()
    return {'results': rels}


# AI Learning Endpoints

@app.post('/feedback')
def submit_feedback(feedback: FeedbackRequest, user=Depends(get_current_user)):
    """Submit feedback on a query result for AI learning"""
    try:
        db.add_feedback(
            feedback.query_id,
            feedback.rating,
            feedback.helpful,
            feedback.comment,
            feedback.relevant_doc_ids
        )
        return {'status': 'ok', 'query_id': feedback.query_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f'Failed to submit feedback: {str(e)}')


@app.get('/conversation/{session_id}', response_model=ConversationHistory)
def get_conversation(session_id: str, user=Depends(get_current_user)):
    """Get conversation history for a session"""
    messages = db.get_conversation_history(session_id, limit=50)
    if not messages:
        raise HTTPException(status_code=404, detail='No conversation found for this session')
    
    return ConversationHistory(
        session_id=session_id,
        user_id=user.sub,
        messages=messages,
        created_at=messages[0]['timestamp'] if messages else None,
        updated_at=messages[-1]['timestamp'] if messages else None
    )


@app.get('/analytics', response_model=AnalyticsResponse)
def get_analytics(user=Depends(get_current_user)):
    """Get analytics on queries, documents, and user feedback"""
    # Only managers can view analytics
    if user.role != 'manager':
        raise HTTPException(status_code=403, detail='Only managers may view analytics')
    
    analytics = db.get_analytics()
    return AnalyticsResponse(**analytics)


@app.get('/query-logs')
def get_query_logs(user=Depends(get_current_user), limit: int = 100):
    """Get query logs for analysis"""
    # Managers can see all logs, users can only see their own
    if user.role == 'manager':
        logs = db.get_query_logs(limit=limit)
    else:
        logs = db.get_query_logs(user_id=user.sub, limit=limit)
    
    return {'logs': logs}


@app.post('/llm/generate')
def generate_llm_answer(req: LLMRequest, user=Depends(get_current_user)):
    """Generate an answer using LLM with provided documents"""
    try:
        response = llm_client.generate_answer(req.query, req.context_docs, req.conversation_history)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'LLM generation failed: {str(e)}')

