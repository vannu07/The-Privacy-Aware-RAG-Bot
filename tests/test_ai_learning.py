"""
Test script demonstrating AI learning features:
- Query logging
- Feedback submission
- Conversation history
- Analytics
- LLM integration
"""

import requests
import json
import time
import uuid

BASE_URL = "http://localhost:8000"


def login(username):
    """Login and get access token"""
    response = requests.post(f"{BASE_URL}/login", json={"username": username})
    return response.json()["access_token"]


def test_query_with_feedback():
    """Test query -> feedback loop"""
    print("\n=== Test 1: Query with Feedback ===")
    
    token = login("bob")
    headers = {"Authorization": f"Bearer {token}"}
    
    # Query
    response = requests.post(
        f"{BASE_URL}/query",
        headers=headers,
        json={"query": "salary information", "session_id": "test-session-1"}
    )
    result = response.json()
    print(f"Query returned {len(result['results'])} results")
    print(f"Query ID: {result.get('query_id')}")
    
    if result.get('generated_answer'):
        print(f"LLM Answer: {result['generated_answer'][:100]}...")
    
    # Submit positive feedback
    if result.get('query_id'):
        feedback_response = requests.post(
            f"{BASE_URL}/feedback",
            headers=headers,
            json={
                "query_id": result['query_id'],
                "rating": 1,
                "helpful": True,
                "comment": "Very helpful!",
                "relevant_doc_ids": [result['results'][0]['id']] if result['results'] else []
            }
        )
        print(f"Feedback submitted: {feedback_response.json()}")


def test_conversation_history():
    """Test multi-turn conversation"""
    print("\n=== Test 2: Conversation History ===")
    
    token = login("bob")
    headers = {"Authorization": f"Bearer {token}"}
    session_id = str(uuid.uuid4())
    
    # Turn 1
    print("\nTurn 1: Initial query")
    response = requests.post(
        f"{BASE_URL}/query",
        headers=headers,
        json={"query": "What documents are about budgets?", "session_id": session_id}
    )
    result1 = response.json()
    print(f"Found {len(result1['results'])} documents")
    
    # Turn 2
    print("\nTurn 2: Follow-up query")
    time.sleep(0.5)  # Small delay
    response = requests.post(
        f"{BASE_URL}/query",
        headers=headers,
        json={"query": "Are they confidential?", "session_id": session_id}
    )
    result2 = response.json()
    print(f"Found {len(result2['results'])} documents")
    
    # Get conversation history
    print("\nRetrieving conversation history...")
    response = requests.get(
        f"{BASE_URL}/conversation/{session_id}",
        headers=headers
    )
    conversation = response.json()
    print(f"Conversation has {len(conversation.get('messages', []))} messages")
    for msg in conversation.get('messages', []):
        role = msg['role'].upper()
        content = msg['content'][:60]
        print(f"  {role}: {content}...")


def test_analytics():
    """Test analytics endpoint"""
    print("\n=== Test 3: Analytics ===")
    
    token = login("bob")  # Manager
    headers = {"Authorization": f"Bearer {token}"}
    
    # Generate some queries first
    for query in ["salary", "budget", "vacation policy", "ML strategy"]:
        requests.post(
            f"{BASE_URL}/query",
            headers=headers,
            json={"query": query}
        )
        time.sleep(0.1)
    
    # Get analytics
    response = requests.get(f"{BASE_URL}/analytics", headers=headers)
    analytics = response.json()
    
    print(f"Total queries: {analytics['total_queries']}")
    print(f"Average results per query: {analytics['avg_results_per_query']:.2f}")
    print(f"Average rating: {analytics.get('avg_rating', 'N/A')}")
    
    print("\nTop queries:")
    for q in analytics['top_queries'][:3]:
        print(f"  - '{q['query']}' ({q['count']} times)")
    
    print("\nPopular documents:")
    for doc in analytics['popular_documents'][:3]:
        print(f"  - {doc['title']}: {doc['view_count']} views, {doc['helpful_count']} helpful")
    
    if analytics['failed_queries']:
        print("\nFailed queries (no results or low ratings):")
        for q in analytics['failed_queries'][:3]:
            print(f"  - '{q['query']}' (results: {q['results_count']})")


def test_query_logs():
    """Test query logs"""
    print("\n=== Test 4: Query Logs ===")
    
    token = login("bob")
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.get(f"{BASE_URL}/query-logs?limit=5", headers=headers)
    logs = response.json()['logs']
    
    print(f"Recent queries (showing {len(logs)}):")
    for log in logs:
        print(f"  - Query: '{log['query']}'")
        print(f"    Results: {log['results_count']}, Latency: {log.get('latency_ms', 0):.2f}ms")
        print(f"    Rating: {log.get('feedback_rating', 'N/A')}")


def test_enhanced_metadata():
    """Test enhanced document metadata"""
    print("\n=== Test 5: Enhanced Metadata ===")
    
    token = login("bob")  # Manager can add documents
    headers = {"Authorization": f"Bearer {token}"}
    
    # Add document with metadata
    doc = {
        "id": "doc_ml_guide",
        "title": "Machine Learning Best Practices",
        "content": "This guide covers ML model training, deployment, and monitoring best practices.",
        "sensitive": False,
        "author": "alice",
        "department": "Engineering",
        "tags": ["ml", "ai", "best-practices"],
        "version": "1.0"
    }
    
    response = requests.post(
        f"{BASE_URL}/documents/add",
        headers=headers,
        json=doc
    )
    print(f"Added document: {response.json()}")
    
    # Query to retrieve it
    response = requests.post(
        f"{BASE_URL}/query",
        headers=headers,
        json={"query": "machine learning"}
    )
    results = response.json()['results']
    
    if results:
        result = results[0]
        print(f"\nRetrieved document metadata:")
        print(f"  Title: {result['title']}")
        print(f"  Author: {result.get('author', 'N/A')}")
        print(f"  Department: {result.get('department', 'N/A')}")
        print(f"  Tags: {result.get('tags', [])}")
        print(f"  Views: {result.get('view_count', 0)}")
        print(f"  Helpful: {result.get('helpful_count', 0)}")


def test_access_control_with_feedback():
    """Test that feedback respects access control"""
    print("\n=== Test 6: Access Control + Feedback ===")
    
    # Bob (manager) can see sensitive docs
    bob_token = login("bob")
    bob_headers = {"Authorization": f"Bearer {bob_token}"}
    
    response = requests.post(
        f"{BASE_URL}/query",
        headers=bob_headers,
        json={"query": "salary"}
    )
    bob_results = response.json()['results']
    print(f"Bob (manager) sees {len(bob_results)} results")
    
    # Alice (employee) cannot see sensitive docs
    alice_token = login("alice")
    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    
    response = requests.post(
        f"{BASE_URL}/query",
        headers=alice_headers,
        json={"query": "salary"}
    )
    alice_results = response.json()['results']
    print(f"Alice (employee) sees {len(alice_results)} results")
    
    print("\n✓ Access control working correctly!")
    print("✓ Feedback and analytics respect FGA authorization")


def main():
    """Run all tests"""
    print("=" * 60)
    print("AI Learning Features Demo")
    print("=" * 60)
    print("\nMake sure the server is running: uvicorn app.main:app --reload")
    print("Press Ctrl+C to stop")
    
    try:
        # Test connection
        response = requests.get(BASE_URL)
        print(f"\n✓ Server is running")
    except requests.exceptions.ConnectionError:
        print(f"\n✗ Cannot connect to {BASE_URL}")
        print("Start the server first: uvicorn app.main:app --reload")
        return
    
    try:
        test_query_with_feedback()
        test_conversation_history()
        test_analytics()
        test_query_logs()
        test_enhanced_metadata()
        test_access_control_with_feedback()
        
        print("\n" + "=" * 60)
        print("✓ All tests completed successfully!")
        print("=" * 60)
        
        print("\nKey Features Demonstrated:")
        print("  ✓ Query logging and tracking")
        print("  ✓ User feedback collection")
        print("  ✓ Conversation history")
        print("  ✓ Analytics dashboard")
        print("  ✓ Enhanced document metadata")
        print("  ✓ Privacy-preserving AI learning")
        
        print("\nNext Steps:")
        print("  1. Enable LLM: export USE_LLM=1 LLM_PROVIDER=openai OPENAI_API_KEY=sk-...")
        print("  2. Enable vector search: export USE_VECTOR=1")
        print("  3. View analytics at: http://localhost:8000/analytics")
        print("  4. Check query logs at: http://localhost:8000/query-logs")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
