import requests
import time

BASE = 'http://127.0.0.1:8000'


def get_token(username):
    resp = requests.post(f'{BASE}/login', json={'username': username})
    resp.raise_for_status()
    return resp.json()['access_token']


def query(user_token, q):
    headers = {'Authorization': f'Bearer {user_token}'}
    resp = requests.post(f'{BASE}/query', json={'query': q}, headers=headers)
    return resp


if __name__ == '__main__':
    print('Waiting 1s for server to be ready...')
    time.sleep(1)
    bob = get_token('bob')
    alice = get_token('alice')

    print('Manager (bob) querying for salary...')
    r1 = query(bob, 'salary')
    print('Status:', r1.status_code, 'Results:', r1.json())

    print('Employee (alice) querying for salary...')
    r2 = query(alice, 'salary')
    print('Status:', r2.status_code, 'Results:', r2.json())

    # Expect: bob has one result, alice zero results
    assert r1.status_code == 200
    assert len(r1.json().get('results', [])) >= 1
    assert r2.status_code == 200
    assert len(r2.json().get('results', [])) == 0
    print('Test passed: manager can view sensitive doc; employee cannot.')
