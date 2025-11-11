import requests
import os

    assert 'doc_salary_2024' in ids
import requests
import requests
import os

BASE = os.getenv('BASE', 'http://127.0.0.1:8000')


def get_token(username):
    resp = requests.post(f'{BASE}/login', json={'username': username})
    resp.raise_for_status()
    return resp.json()['access_token']


def query(user_token, q):
    headers = {'Authorization': f'Bearer {user_token}'}
    resp = requests.post(f'{BASE}/query', json={'query': q}, headers=headers)
    resp.raise_for_status()
    return resp.json()


def test_manager_can_view_salary():
    bob = get_token('bob')
    data = query(bob, 'salary')
    ids = [d['id'] for d in data.get('results', [])]
    assert 'doc_salary_2024' in ids


def test_employee_cannot_view_salary():
    alice = get_token('alice')
    data = query(alice, 'salary')
    ids = [d['id'] for d in data.get('results', [])]
    assert 'doc_salary_2024' not in ids