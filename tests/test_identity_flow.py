import os
import sys
from pathlib import Path
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import app

os.environ.setdefault('WEATHER_API_MODE', 'offline')


def auth_header(token: str):
    return {'Authorization': f'Bearer {token}'}


def test_contextual_weather_flow_offline_mode():
    with TestClient(app) as client:
        login = client.post('/login', json={'username': 'bob'})
        assert login.status_code == 200
        token = login.json()['access_token']

        # Read first-party settings
        settings_resp = client.get('/me/settings', headers=auth_header(token))
        assert settings_resp.status_code == 200
        settings = settings_resp.json()
        assert settings['city']

        # Store a delegated token in the vault for this user
        store_resp = client.post(
            '/vault/tokens',
            headers=auth_header(token),
            json={'provider': 'weather', 'token': 'demo-weather-token'},
        )
        assert store_resp.status_code == 200

        # Call the contextual assistant endpoint
        ctx_resp = client.get('/assistant/contextual-weather', headers=auth_header(token))
        assert ctx_resp.status_code == 200
        data = ctx_resp.json()
        assert settings['city'] in data['message']
        assert data['weather']['used_token'] is True
