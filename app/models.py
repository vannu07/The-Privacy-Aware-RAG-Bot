from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class User(BaseModel):
    sub: str
    username: str
    role: str
    department: Optional[str] = None

class LoginRequest(BaseModel):
    username: str

class Document(BaseModel):
    id: str
    title: str
    content: str
    sensitive: bool = False
    # Enhanced metadata for AI learning
    author: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    version: Optional[str] = None
    department: Optional[str] = None
    tags: Optional[List[str]] = None
    view_count: Optional[int] = 0
    helpful_count: Optional[int] = 0

class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None  # For conversation tracking

class QueryResponse(BaseModel):
    results: List[Document]
    query_id: Optional[str] = None  # For feedback tracking
    confidence: Optional[float] = None
    generated_answer: Optional[str] = None  # LLM-generated response


class UserSettings(BaseModel):
    city: str
    timezone: Optional[str] = None
    theme: Optional[str] = None


class TokenUpsertRequest(BaseModel):
    provider: str
    token: str


class ContextualActionResponse(BaseModel):
    message: str
    profile: User
    settings: UserSettings
    weather: dict


# New models for AI learning capabilities

class FeedbackRequest(BaseModel):
    query_id: str
    rating: int  # 1-5 or -1 (thumbs down) to 1 (thumbs up)
    helpful: Optional[bool] = None
    comment: Optional[str] = None
    relevant_doc_ids: Optional[List[str]] = None  # Which docs were actually useful


class ConversationMessage(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: Optional[str] = None
    doc_ids: Optional[List[str]] = None  # Documents referenced


class ConversationHistory(BaseModel):
    session_id: str
    user_id: str
    messages: List[ConversationMessage]
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class QueryLog(BaseModel):
    query_id: str
    user_id: str
    query: str
    session_id: Optional[str] = None
    results_count: int
    retrieved_doc_ids: List[str]
    timestamp: str
    latency_ms: Optional[float] = None
    confidence: Optional[float] = None
    feedback_rating: Optional[int] = None


class AnalyticsResponse(BaseModel):
    total_queries: int
    avg_results_per_query: float
    top_queries: List[dict]
    popular_documents: List[dict]
    failed_queries: List[dict]
    avg_rating: Optional[float] = None


class LLMRequest(BaseModel):
    query: str
    context_docs: List[Document]
    conversation_history: Optional[List[ConversationMessage]] = None


class LLMResponse(BaseModel):
    answer: str
    confidence: float
    citations: List[str]  # Document IDs used
