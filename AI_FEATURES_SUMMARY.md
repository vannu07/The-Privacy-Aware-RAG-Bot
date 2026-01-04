# AI Learning Features - Quick Reference

## 🎯 What Was Added

### 1. **Feedback & Rating System** 📊
- Users rate query results (thumbs up/down or 1-5 scale)
- Track which documents are most helpful
- Identify knowledge gaps
- Improve retrieval quality over time

**Endpoint**: `POST /feedback`

### 2. **Conversation Memory** 💬
- Multi-turn dialogue support
- Context preserved across queries in a session
- LLM uses previous conversation for better answers
- Document references tracked per turn

**Endpoint**: `GET /conversation/{session_id}`

### 3. **Query Analytics** 📈
- Total queries, average results, ratings
- Top/popular queries
- Most helpful documents
- Failed queries (for content gap analysis)
- Query latency tracking

**Endpoint**: `GET /analytics` (managers only)

### 4. **Enhanced Metadata** 🏷️
- Author, department, tags
- Version tracking
- View counts
- Helpful counts
- Creation/update timestamps

### 5. **LLM Integration** 🤖
- Natural language answer generation
- Automatic document citations
- Multiple provider support (OpenAI, Anthropic, Mock)
- Conversation-aware responses
- Confidence scoring

**Config**: `USE_LLM=1`, `LLM_PROVIDER=openai`

### 6. **Hybrid Search** 🔍
- Vector search (semantic similarity)
- Keyword search (BM25-like)
- Fusion algorithm (configurable weights)
- Better accuracy than either alone

**Config**: `USE_VECTOR=1`

---

## 🚀 Quick Start

### Enable All Features

```bash
# In your terminal or .env file
export USE_VECTOR=1           # Enable hybrid search
export USE_LLM=1              # Enable answer generation
export LLM_PROVIDER=mock      # Use mock LLM (no API key needed)

# Or use real LLM
export LLM_PROVIDER=openai
export OPENAI_API_KEY=sk-...
export LLM_MODEL=gpt-4-turbo-preview
```

### Run Demo

```bash
# Start server
uvicorn app.main:app --reload

# In another terminal, run the demo
python tests/test_ai_learning.py
```

---

## 📝 Example Workflow

```python
import requests

# 1. Login
token = requests.post('http://localhost:8000/login', 
                     json={'username': 'bob'}).json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

# 2. Query with session for conversation
response = requests.post('http://localhost:8000/query',
                        headers=headers,
                        json={
                            'query': 'What is the Q4 budget?',
                            'session_id': 'my-session'
                        })
result = response.json()

# 3. Get LLM-generated answer with citations
print(result['generated_answer'])  
# "Based on [doc_budget_q4], the Q4 budget is..."

# 4. Follow-up question (with context)
response = requests.post('http://localhost:8000/query',
                        headers=headers,
                        json={
                            'query': 'Who approved it?',
                            'session_id': 'my-session'  # Same session
                        })

# 5. Submit feedback
requests.post('http://localhost:8000/feedback',
             headers=headers,
             json={
                 'query_id': result['query_id'],
                 'rating': 1,  # Thumbs up
                 'helpful': True
             })

# 6. View analytics (managers only)
analytics = requests.get('http://localhost:8000/analytics',
                        headers=headers).json()
print(f"Total queries: {analytics['total_queries']}")
print(f"Avg rating: {analytics['avg_rating']}")
```

---

## 🗄️ New Database Tables

- **query_logs**: All queries with metadata (user, session, latency, confidence)
- **feedback**: User ratings and comments on queries
- **conversation_history**: Multi-turn dialogue messages
- **Enhanced documents table**: Added author, tags, view_count, helpful_count, etc.

---

## 🎨 API Endpoints Added

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/feedback` | POST | Submit query feedback |
| `/conversation/{session_id}` | GET | Get conversation history |
| `/analytics` | GET | View usage analytics (managers) |
| `/query-logs` | GET | View query logs |
| `/llm/generate` | POST | Direct LLM answer generation |

---

## 📊 Analytics Dashboard Data

```json
{
  "total_queries": 1523,
  "avg_results_per_query": 3.4,
  "avg_rating": 0.8,
  "top_queries": [
    {"query": "salary information", "count": 45}
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

---

## 🔒 Privacy Preserved

✅ All features respect FGA authorization  
✅ Users only see documents they're allowed to access  
✅ Analytics aggregated to prevent data leakage  
✅ Conversation history isolated per user  
✅ Feedback linked to authorized queries only  

---

## 🎓 AI Learning Loop

```
User Query
    ↓
Log for Analytics
    ↓
Hybrid Search (Vector + Keyword)
    ↓
FGA Filter (Privacy)
    ↓
LLM Generate Answer
    ↓
User Rates Result
    ↓
Update Metrics (helpful_count, etc.)
    ↓
Improve System (retrain, adjust)
```

---

## 📖 Full Documentation

- **[AI_LEARNING.md](AI_LEARNING.md)**: Comprehensive guide
- **[README.md](README.md)**: Main project documentation
- **[tests/test_ai_learning.py](tests/test_ai_learning.py)**: Working examples

---

## 🎯 Benefits for AI Training

1. **Supervised Learning**: Feedback labels for training data
2. **Relevance Tuning**: Adjust ranking based on helpful_count
3. **Query Understanding**: Analyze popular queries and intents
4. **Content Gaps**: Identify failed queries → add new documents
5. **Personalization**: User-specific preferences over time
6. **A/B Testing**: Compare retrieval strategies
7. **Active Learning**: Flag uncertain cases for review
8. **Continuous Improvement**: Real-time learning from usage

---

## 🔧 Optional Dependencies

```bash
# For OpenAI
pip install openai>=1.0.0

# For Anthropic Claude
pip install anthropic>=0.8.0

# Already included
# - sentence-transformers (embeddings)
# - faiss-cpu (vector search)
# - numpy (numerical operations)
```

---

## 🎉 Result

Your RAG bot now:
- ✅ Learns from user feedback
- ✅ Remembers conversation context
- ✅ Tracks what works and what doesn't
- ✅ Generates natural language answers
- ✅ Combines semantic + keyword search
- ✅ Provides rich analytics
- ✅ Maintains privacy and security

**All while preserving document-level authorization! 🔒**
