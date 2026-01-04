import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Tuple
import os
from .vector_store import VectorStore
from datetime import datetime
import uuid
import json

DB_PATH = Path(__file__).parent / "data.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id TEXT PRIMARY KEY,
        title TEXT,
        content TEXT,
        sensitive INTEGER DEFAULT 0,
        author TEXT,
        created_at TEXT,
        updated_at TEXT,
        version TEXT,
        department TEXT,
        tags TEXT,
        view_count INTEGER DEFAULT 0,
        helpful_count INTEGER DEFAULT 0
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS fga_relationships (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject TEXT,
        relation TEXT,
        object TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_settings (
        user_sub TEXT PRIMARY KEY,
        city TEXT,
        timezone TEXT,
        theme TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS token_vault (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_sub TEXT,
        provider TEXT,
        token TEXT,
        UNIQUE(user_sub, provider)
    )
    """)
    # New tables for AI learning
    cur.execute("""
    CREATE TABLE IF NOT EXISTS query_logs (
        query_id TEXT PRIMARY KEY,
        user_id TEXT,
        query TEXT,
        session_id TEXT,
        results_count INTEGER,
        retrieved_doc_ids TEXT,
        timestamp TEXT,
        latency_ms REAL,
        confidence REAL,
        feedback_rating INTEGER
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        query_id TEXT,
        rating INTEGER,
        helpful INTEGER,
        comment TEXT,
        relevant_doc_ids TEXT,
        timestamp TEXT,
        FOREIGN KEY (query_id) REFERENCES query_logs(query_id)
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS conversation_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        user_id TEXT,
        role TEXT,
        content TEXT,
        doc_ids TEXT,
        timestamp TEXT
    )
    """)
    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_query_logs_user ON query_logs(user_id)
    """)
    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_query_logs_timestamp ON query_logs(timestamp)
    """)
    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_conversation_session ON conversation_history(session_id)
    """)
    conn.commit()
    conn.close()
    # Build vector store on demand if enabled; leave lazy building to get_vector_store
    return


_vector_store = None


def build_vector_store():
    """Build the module-level vector store from documents in the DB.
    Returns the VectorStore instance."""
    global _vector_store
    vs = VectorStore()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, title, content FROM documents")
    rows = cur.fetchall()
    docs = [(r['id'], r['title'] + "\n" + r['content']) for r in rows]
    conn.close()
    vs.build(docs)
    _vector_store = vs
    return _vector_store


def get_vector_store():
    global _vector_store
    if _vector_store is None:
        _vector_store = build_vector_store()
    return _vector_store

def add_document(doc_id: str, title: str, content: str, sensitive: bool = False, author: str = None, 
                 department: str = None, tags: List[str] = None):
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()
    tags_json = json.dumps(tags) if tags else None
    cur.execute(
        """INSERT OR REPLACE INTO documents 
           (id, title, content, sensitive, author, created_at, updated_at, version, department, tags, view_count, helpful_count) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)""",
        (doc_id, title, content, 1 if sensitive else 0, author, now, now, "1.0", department, tags_json)
    )
    conn.commit()
    conn.close()

def search_documents(keyword: str) -> List[Dict[str, Any]]:
    # If vector search is enabled, use it
    if os.getenv('USE_VECTOR') == '1':
        vs = get_vector_store()
        hits = vs.search(keyword, k=10)
        # map to full documents
        results = []
        conn = get_conn()
        cur = conn.cursor()
        for h in hits:
            cur.execute("""SELECT id, title, content, sensitive, author, created_at, updated_at, 
                          version, department, tags, view_count, helpful_count 
                          FROM documents WHERE id=?""", (h['id'],))
            r = cur.fetchone()
            if r:
                doc_dict = dict(r)
                if doc_dict.get('tags'):
                    doc_dict['tags'] = json.loads(doc_dict['tags'])
                results.append(doc_dict)
        conn.close()
        return results
    else:
        conn = get_conn()
        cur = conn.cursor()
        q = f"%{keyword}%"
        cur.execute("""SELECT id, title, content, sensitive, author, created_at, updated_at, 
                      version, department, tags, view_count, helpful_count 
                      FROM documents WHERE title LIKE ? OR content LIKE ?""", (q, q))
        rows = cur.fetchall()
        conn.close()
        results = []
        for r in rows:
            doc_dict = dict(r)
            if doc_dict.get('tags'):
                doc_dict['tags'] = json.loads(doc_dict['tags'])
            results.append(doc_dict)
        return results

def add_relationship(subject: str, relation: str, obj: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO fga_relationships (subject, relation, object) VALUES (?, ?, ?)", (subject, relation, obj))
    conn.commit()
    conn.close()


def remove_relationship(subject: str, relation: str, obj: str) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM fga_relationships WHERE subject=? AND relation=? AND object=?", (subject, relation, obj))
    affected = cur.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def list_relationships() -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT subject, relation, object FROM fga_relationships ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def check_relationship(subject: str, relation: str, obj: str) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM fga_relationships WHERE subject=? AND relation=? AND object=? LIMIT 1", (subject, relation, obj))
    res = cur.fetchone()
    conn.close()
    return res is not None

# seed helper
def seed_sample_data():
    # Documents
    add_document('doc_salary_2024', 'Salary - Engineering', 'Employee salaries for 2024. Confidential HR data.', sensitive=True)
    add_document('doc_budget_q4', 'Budget Q4', 'Quarter 4 budget planning and allocations.', sensitive=False)
    # Relationships (FGA-like)
    # manager:bob can view salary doc
    add_relationship('user:bob', 'can_view', 'document:doc_salary_2024')
    # everyone can view budget
    add_relationship('role:employee', 'can_view', 'document:doc_budget_q4')
    add_relationship('role:manager', 'can_view', 'document:doc_budget_q4')

    # User settings (first-party profile data consumed by the assistant)
    set_user_settings('user:alice', city='Seattle', timezone='America/Los_Angeles', theme='light')
    set_user_settings('user:bob', city='New York', timezone='America/New_York', theme='dark')

    # Optional: seed third-party tokens for demo (used by Token Vault)
    weather_token = os.getenv('WEATHER_API_TOKEN')
    if weather_token:
        upsert_token('user:alice', 'weather', weather_token)
        upsert_token('user:bob', 'weather', weather_token)


def set_user_settings(user_sub: str, city: str, timezone: str | None = None, theme: str | None = None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO user_settings (user_sub, city, timezone, theme) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(user_sub) DO UPDATE SET city=excluded.city, timezone=excluded.timezone, theme=excluded.theme",
        (user_sub, city, timezone, theme)
    )
    conn.commit()
    conn.close()


def get_user_settings(user_sub: str) -> Dict[str, Any] | None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT city, timezone, theme FROM user_settings WHERE user_sub=?", (user_sub,))
    row = cur.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def upsert_token(user_sub: str, provider: str, token: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO token_vault (user_sub, provider, token) VALUES (?, ?, ?) "
        "ON CONFLICT(user_sub, provider) DO UPDATE SET token=excluded.token",
        (user_sub, provider, token)
    )
    conn.commit()
    conn.close()


def get_token(user_sub: str, provider: str) -> str | None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT token FROM token_vault WHERE user_sub=? AND provider=?", (user_sub, provider))
    row = cur.fetchone()
    conn.close()
    if row:
        return row['token']
    return None


def list_tokens(user_sub: str) -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT provider, token FROM token_vault WHERE user_sub=?", (user_sub,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# AI Learning Functions

def log_query(user_id: str, query: str, session_id: str, retrieved_docs: List[str], 
              latency_ms: float = None, confidence: float = None) -> str:
    """Log a query for analytics and learning"""
    query_id = str(uuid.uuid4())
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO query_logs 
           (query_id, user_id, query, session_id, results_count, retrieved_doc_ids, timestamp, latency_ms, confidence)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (query_id, user_id, query, session_id, len(retrieved_docs), json.dumps(retrieved_docs), 
         datetime.utcnow().isoformat(), latency_ms, confidence)
    )
    conn.commit()
    conn.close()
    return query_id


def add_feedback(query_id: str, rating: int, helpful: bool = None, 
                 comment: str = None, relevant_doc_ids: List[str] = None):
    """Add user feedback to a query"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO feedback (query_id, rating, helpful, comment, relevant_doc_ids, timestamp)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (query_id, rating, 1 if helpful else 0 if helpful is not None else None, 
         comment, json.dumps(relevant_doc_ids) if relevant_doc_ids else None, datetime.utcnow().isoformat())
    )
    # Update query log with feedback rating
    cur.execute("UPDATE query_logs SET feedback_rating = ? WHERE query_id = ?", (rating, query_id))
    # Update document helpful counts
    if relevant_doc_ids:
        for doc_id in relevant_doc_ids:
            cur.execute("UPDATE documents SET helpful_count = helpful_count + 1 WHERE id = ?", (doc_id,))
    conn.commit()
    conn.close()


def get_query_logs(user_id: str = None, limit: int = 100) -> List[Dict[str, Any]]:
    """Get query logs for analytics"""
    conn = get_conn()
    cur = conn.cursor()
    if user_id:
        cur.execute(
            """SELECT * FROM query_logs WHERE user_id = ? 
               ORDER BY timestamp DESC LIMIT ?""", (user_id, limit))
    else:
        cur.execute("SELECT * FROM query_logs ORDER BY timestamp DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    results = []
    for r in rows:
        log = dict(r)
        log['retrieved_doc_ids'] = json.loads(log['retrieved_doc_ids']) if log['retrieved_doc_ids'] else []
        results.append(log)
    return results


def add_conversation_message(session_id: str, user_id: str, role: str, 
                             content: str, doc_ids: List[str] = None):
    """Add a message to conversation history"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO conversation_history (session_id, user_id, role, content, doc_ids, timestamp)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (session_id, user_id, role, content, json.dumps(doc_ids) if doc_ids else None, 
         datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()


def get_conversation_history(session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Get conversation history for a session"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT role, content, doc_ids, timestamp FROM conversation_history 
           WHERE session_id = ? ORDER BY timestamp ASC LIMIT ?""", (session_id, limit))
    rows = cur.fetchall()
    conn.close()
    results = []
    for r in rows:
        msg = dict(r)
        msg['doc_ids'] = json.loads(msg['doc_ids']) if msg['doc_ids'] else []
        results.append(msg)
    return results


def get_analytics() -> Dict[str, Any]:
    """Get analytics data for AI learning insights"""
    conn = get_conn()
    cur = conn.cursor()
    
    # Total queries
    cur.execute("SELECT COUNT(*) as total FROM query_logs")
    total_queries = cur.fetchone()['total']
    
    # Average results per query
    cur.execute("SELECT AVG(results_count) as avg FROM query_logs")
    avg_results = cur.fetchone()['avg'] or 0
    
    # Average rating
    cur.execute("SELECT AVG(feedback_rating) as avg FROM query_logs WHERE feedback_rating IS NOT NULL")
    avg_rating = cur.fetchone()['avg']
    
    # Top queries (most frequent)
    cur.execute("""
        SELECT query, COUNT(*) as count 
        FROM query_logs 
        GROUP BY query 
        ORDER BY count DESC 
        LIMIT 10
    """)
    top_queries = [dict(r) for r in cur.fetchall()]
    
    # Popular documents (most retrieved and helpful)
    cur.execute("""
        SELECT id, title, view_count, helpful_count 
        FROM documents 
        ORDER BY helpful_count DESC, view_count DESC 
        LIMIT 10
    """)
    popular_docs = [dict(r) for r in cur.fetchall()]
    
    # Failed queries (no results or low ratings)
    cur.execute("""
        SELECT query, results_count, feedback_rating 
        FROM query_logs 
        WHERE results_count = 0 OR feedback_rating < 0
        ORDER BY timestamp DESC 
        LIMIT 10
    """)
    failed_queries = [dict(r) for r in cur.fetchall()]
    
    conn.close()
    
    return {
        'total_queries': total_queries,
        'avg_results_per_query': float(avg_results),
        'avg_rating': float(avg_rating) if avg_rating else None,
        'top_queries': top_queries,
        'popular_documents': popular_docs,
        'failed_queries': failed_queries
    }


def increment_doc_view_count(doc_id: str):
    """Increment view count when a document is accessed"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE documents SET view_count = view_count + 1 WHERE id = ?", (doc_id,))
    conn.commit()
    conn.close()

