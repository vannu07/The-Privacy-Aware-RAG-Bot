# AI Learning Features Documentation

## Overview

This document describes the AI learning capabilities added to the Privacy-Aware RAG Bot, designed to help the system continuously improve through user feedback, analytics, and intelligent retrieval.

## Features Added

### 1. Feedback & Rating System

**Purpose**: Collect user feedback on query results to improve retrieval quality and identify knowledge gaps.

**Endpoints**:
```http
POST /feedback
```

**Request Body**:
```json
{
  "query_id": "uuid-from-query-response",
  "rating": 1,  // -1 to 1 or 1-5 scale
  "helpful": true,
  "comment": "This answered my question perfectly",
  "relevant_doc_ids": ["doc_salary_2024"]
}
```

**Use Cases**:
- Track which documents are most helpful
- Identify low-quality responses
- Fine-tune retrieval algorithms
- Detect content gaps

### 2. Conversation History

**Purpose**: Enable multi-turn conversations with context preservation.

**Endpoints**:
```http
GET /conversation/{session_id}
```

**Features**:
- Automatic conversation tracking per session
- Context-aware responses using history
- Document reference tracking across turns
- Session-based memory

**Usage**:
```bash
# Include session_id in query request to maintain context
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query": "What is the budget?", "session_id": "session-123"}'
```

### 3. Query Logging & Analytics

**Purpose**: Track and analyze query patterns for continuous improvement.

**Endpoints**:
```http
GET /query-logs?limit=100
GET /analytics  # Managers only
```

**Analytics Dashboard Includes**:
- Total queries processed
- Average results per query
- Average user ratings
- Top/popular queries
- Most helpful documents
- Failed queries (no results or low ratings)
- Query latency metrics

**Example Response**:
```json
{
  "total_queries": 1523,
  "avg_results_per_query": 3.4,
  "avg_rating": 0.8,
  "top_queries": [
    {"query": "salary information", "count": 45},
    {"query": "budget Q4", "count": 32}
  ],
  "popular_documents": [
    {
      "id": "doc_salary_2024",
      "title": "Salary - Engineering",
      "view_count": 156,
      "helpful_count": 89
    }
  ],
  "failed_queries": [
    {"query": "vacation policy", "results_count": 0}
  ]
}
```

### 4. Enhanced Document Metadata

**Purpose**: Enrich documents with metadata to improve AI understanding and tracking.

**New Document Fields**:
- `author`: Document creator
- `created_at`: Creation timestamp
- `updated_at`: Last modification timestamp
- `version`: Document version
- `department`: Owning department
- `tags`: Categorization tags
- `view_count`: Number of times accessed
- `helpful_count`: Number of positive feedback instances

**Example**:
```python
db.add_document(
    'doc_ml_guide',
    'Machine Learning Best Practices',
    'Content here...',
    sensitive=False,
    author='alice',
    department='Engineering',
    tags=['ml', 'best-practices', 'ai']
)
```

### 5. LLM Integration (RAG)

**Purpose**: Generate natural language answers from retrieved documents.

**Configuration**:
```bash
# Enable LLM answer generation
export USE_LLM=1

# Choose provider: 'mock', 'openai', or 'anthropic'
export LLM_PROVIDER=openai
export OPENAI_API_KEY=sk-...
export LLM_MODEL=gpt-4-turbo-preview

# Or use Anthropic
export LLM_PROVIDER=anthropic
export ANTHROPIC_API_KEY=sk-ant-...
export LLM_MODEL=claude-3-sonnet-20240229
```

**Features**:
- Context-aware answer generation
- Automatic citation of source documents
- Conversation history integration
- Confidence scoring
- Privacy-preserving (only uses authorized documents)

**Response Format**:
```json
{
  "results": [...],
  "query_id": "uuid",
  "confidence": 0.85,
  "generated_answer": "Based on [doc_salary_2024], the average engineering salary..."
}
```

**Direct LLM Endpoint**:
```http
POST /llm/generate
```

```json
{
  "query": "What is the Q4 budget?",
  "context_docs": [...],
  "conversation_history": [...]
}
```

### 6. Hybrid Search (Vector + Keyword)

**Purpose**: Combine semantic and keyword search for better retrieval accuracy.

**Configuration**:
```bash
export USE_VECTOR=1  # Enable vector search
```

**How It Works**:
1. **Vector Search**: Uses sentence embeddings (all-MiniLM-L6-v2) for semantic similarity
2. **Keyword Search**: BM25-like algorithm for exact term matching
3. **Fusion**: Combines both with configurable weights (default: 50/50)

**Benefits**:
- Handles synonyms and paraphrasing (vector)
- Handles exact term matches (keyword)
- More robust to diverse query styles
- Better recall and precision

**Customization**:
The vector store search method supports:
```python
results = vector_store.search(
    query="machine learning",
    k=10,           # Top-k results
    hybrid=True,    # Enable hybrid mode
    alpha=0.7       # 70% vector, 30% keyword
)
```

## Database Schema

### New Tables

#### query_logs
```sql
CREATE TABLE query_logs (
    query_id TEXT PRIMARY KEY,
    user_id TEXT,
    query TEXT,
    session_id TEXT,
    results_count INTEGER,
    retrieved_doc_ids TEXT,  -- JSON array
    timestamp TEXT,
    latency_ms REAL,
    confidence REAL,
    feedback_rating INTEGER
)
```

#### feedback
```sql
CREATE TABLE feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_id TEXT,
    rating INTEGER,
    helpful INTEGER,
    comment TEXT,
    relevant_doc_ids TEXT,  -- JSON array
    timestamp TEXT
)
```

#### conversation_history
```sql
CREATE TABLE conversation_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    user_id TEXT,
    role TEXT,  -- 'user' or 'assistant'
    content TEXT,
    doc_ids TEXT,  -- JSON array
    timestamp TEXT
)
```

## Usage Examples

### Example 1: Query with Feedback Loop

```python
import requests

# 1. Login
response = requests.post('http://localhost:8000/login', 
                        json={'username': 'bob'})
token = response.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

# 2. Query with session
response = requests.post('http://localhost:8000/query',
                        headers=headers,
                        json={
                            'query': 'What is the Q4 budget?',
                            'session_id': 'my-session-123'
                        })
result = response.json()
query_id = result['query_id']

# 3. Submit feedback
requests.post('http://localhost:8000/feedback',
             headers=headers,
             json={
                 'query_id': query_id,
                 'rating': 1,
                 'helpful': True,
                 'relevant_doc_ids': ['doc_budget_q4']
             })

# 4. Continue conversation
response = requests.post('http://localhost:8000/query',
                        headers=headers,
                        json={
                            'query': 'Who approved it?',
                            'session_id': 'my-session-123'
                        })
```

### Example 2: Analytics for Improvement

```python
# Get analytics (managers only)
response = requests.get('http://localhost:8000/analytics',
                       headers=headers)
analytics = response.json()

# Identify failed queries to add new content
failed_queries = analytics['failed_queries']
print(f"Users searched for '{failed_queries[0]['query']}' but found nothing")

# Identify popular documents to prioritize updates
popular_docs = analytics['popular_documents']
print(f"Most helpful: {popular_docs[0]['title']} with {popular_docs[0]['helpful_count']} positive ratings")
```

### Example 3: Multi-turn Conversation

```python
session_id = str(uuid.uuid4())

# Turn 1
response = requests.post('http://localhost:8000/query',
                        headers=headers,
                        json={
                            'query': 'What is our ML strategy?',
                            'session_id': session_id
                        })

# Turn 2 - with context from turn 1
response = requests.post('http://localhost:8000/query',
                        headers=headers,
                        json={
                            'query': 'When was it last updated?',
                            'session_id': session_id
                        })

# Get full conversation
response = requests.get(f'http://localhost:8000/conversation/{session_id}',
                       headers=headers)
conversation = response.json()
```

## AI Learning Workflow

```
┌─────────────────┐
│  User Query     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Log Query       │◄─── Track for analytics
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Hybrid Search   │──── Vector + Keyword
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ FGA Filter      │──── Privacy enforcement
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ LLM Generate    │──── Answer with citations
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ User Feedback   │──── Rate & comment
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Update Metrics  │──── helpful_count, analytics
└─────────────────┘
         │
         ▼
┌─────────────────┐
│ Active Learning │──── Retrain/adjust based on feedback
└─────────────────┘
```

## Configuration

### Environment Variables

```bash
# Core features
USE_VECTOR=1          # Enable vector search (0=SQL only)
USE_LLM=1             # Enable LLM answer generation

# LLM Provider
LLM_PROVIDER=mock     # Options: mock, openai, anthropic
LLM_MODEL=gpt-4-turbo-preview
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Auth0 (existing)
AUTH0_DOMAIN=...
AUTH0_CLIENT_ID=...
AUTH0_AUDIENCE=...
```

## Future Enhancements

### Active Learning
- Flag uncertain responses for human review
- Automatically request labels for edge cases
- Iteratively improve model based on corrections

### Advanced Analytics
- Query intent classification
- Entity extraction from queries
- Semantic clustering of queries
- A/B testing different retrieval strategies

### Reinforcement Learning
- Learn from implicit feedback (clicks, dwell time)
- Optimize ranking based on user behavior
- Personalized retrieval per user

### Knowledge Graph
- Build relationships between documents
- Enable graph-based retrieval
- Improve context understanding

## Testing

Run the test suite:
```bash
# All tests
pytest

# Specific AI learning tests
pytest tests/test_feedback.py
pytest tests/test_analytics.py
pytest tests/test_conversation.py
```

## Monitoring

Key metrics to monitor:
- Average query latency
- Feedback rating distribution
- Failed query rate
- Document coverage (% of docs ever retrieved)
- User engagement (queries per session)
- LLM confidence scores

## Privacy & Security

All AI learning features respect:
- ✅ FGA authorization checks
- ✅ Document-level access control
- ✅ User data isolation
- ✅ No cross-user learning without authorization
- ✅ Feedback anonymization options
- ✅ GDPR-compliant data retention

## Support

For issues or questions about AI learning features:
- Check analytics dashboard for insights
- Review query logs for patterns
- Submit feedback for continuous improvement
- Contact: @vannu07
