import requests
import os

BASE = os.getenv('BASE', 'http://127.0.0.1:8000')


def test_health_check():
    """Test that health check endpoint returns OK status"""
    resp = requests.get(f'{BASE}/health')
    resp.raise_for_status()
    data = resp.json()
    assert data['status'] == 'ok'
    assert data['service'] == 'Privacy-Aware RAG Bot'
