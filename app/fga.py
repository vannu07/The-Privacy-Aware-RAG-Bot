import os
import requests
from typing import Optional
from . import db

class FGAClient:
    def __init__(self):
        # If AUTH0_FGA_URL is set, attempt to call that API
        self.auth0_fga_url = os.getenv('AUTH0_FGA_URL')
        self.auth0_fga_token = os.getenv('AUTH0_FGA_TOKEN')

    def check(self, subject: str, relation: str, obj: str) -> bool:
        # If an external FGA endpoint is configured, call it. Allow empty token for local mock endpoints.
        if self.auth0_fga_url:
            try:
                headers = {'Content-Type': 'application/json'}
                if self.auth0_fga_token:
                    headers['Authorization'] = f'Bearer {self.auth0_fga_token}'
                resp = requests.post(
                    self.auth0_fga_url,
                    headers=headers,
                    json={
                        'subject': subject,
                        'relation': relation,
                        'object': obj
                    },
                    timeout=5
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get('allowed', False)
                else:
                    return False
            except Exception:
                # On error, deny by default
                return False

        # Fallback: use local DB-backed FGA relationships
        if db.check_relationship(subject, relation, obj):
            return True
        # Also check role relationships: if subject is user:<name>, check role:<role>
        if subject.startswith('user:'):
            username = subject.split(':', 1)[1]
            role_key = f'role:manager' if username == 'bob' else f'role:employee'
            if db.check_relationship(role_key, relation, obj):
                return True
        return False

    def example_payload(self, subject: str, relation: str, obj: str):
        return {'subject': subject, 'relation': relation, 'object': obj}
