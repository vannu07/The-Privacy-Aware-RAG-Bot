import os
import requests

BASE = os.getenv('BASE', 'http://127.0.0.1:8000')


def get_token(username):
    resp = requests.post(f'{BASE}/login', json={'username': username})
    resp.raise_for_status()
    return resp.json()['access_token']


def test_manager_can_add_and_remove_relationship():
    bob = get_token('bob')
    headers = {'Authorization': f'Bearer {bob}'}
    payload = {'subject': 'user:alice', 'relation': 'can_view', 'object': 'document:doc_budget_q4'}

    # add
    r = requests.post(f'{BASE}/admin/fga', json=payload, headers=headers)
    assert r.status_code == 200
    assert r.json().get('status') == 'ok'

    # list and verify
    r2 = requests.get(f'{BASE}/admin/fga', headers=headers)
    assert r2.status_code == 200
    found = any((rel.get('subject') == payload['subject'] and rel.get('object') == payload['object']) for rel in r2.json().get('results', []))
    assert found

    # remove
    r3 = requests.delete(f'{BASE}/admin/fga', json=payload, headers=headers)
    assert r3.status_code == 200

    # ensure it's gone
    r4 = requests.get(f'{BASE}/admin/fga', headers=headers)
    assert r4.status_code == 200
    found_after = any((rel.get('subject') == payload['subject'] and rel.get('object') == payload['object']) for rel in r4.json().get('results', []))
    assert not found_after


def test_employee_cannot_modify_relationships():
    alice = get_token('alice')
    headers = {'Authorization': f'Bearer {alice}'}
    payload = {'subject': 'user:alice', 'relation': 'can_view', 'object': 'document:doc_budget_q4'}
    r = requests.post(f'{BASE}/admin/fga', json=payload, headers=headers)
    assert r.status_code == 403
*** End Patch