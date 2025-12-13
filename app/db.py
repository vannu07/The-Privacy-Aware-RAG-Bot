import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Tuple
import os
from .vector_store import VectorStore

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
        sensitive INTEGER DEFAULT 0
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

def add_document(doc_id: str, title: str, content: str, sensitive: bool = False):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO documents (id, title, content, sensitive) VALUES (?, ?, ?, ?)",
        (doc_id, title, content, 1 if sensitive else 0)
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
            cur.execute("SELECT id, title, content, sensitive FROM documents WHERE id=?", (h['id'],))
            r = cur.fetchone()
            if r:
                results.append(dict(r))
        conn.close()
        return results
    else:
        conn = get_conn()
        cur = conn.cursor()
        q = f"%{keyword}%"
        cur.execute("SELECT id, title, content, sensitive FROM documents WHERE title LIKE ? OR content LIKE ?", (q, q))
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]

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
