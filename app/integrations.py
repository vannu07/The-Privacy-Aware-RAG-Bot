import os
import requests
from typing import Dict, Any

DEFAULT_FALLBACK = {
    "description": "clear skies",
    "temp_c": 21,
    "feels_like_c": 21,
    "provider": "offline-sample",
    "used_token": False,
    "note": "Returned cached sample because live call was skipped or failed."
}


def fetch_weather(city: str, token: str | None = None) -> Dict[str, Any]:
    """Fetch weather for a city. If WEATHER_API_MODE=live, call wttr.in; otherwise return cached sample.
    Token is optional and sent as a header to demonstrate delegated token usage.
    """
    mode = os.getenv('WEATHER_API_MODE', 'offline')
    if mode != 'live':
        result = DEFAULT_FALLBACK.copy()
        result["city"] = city
        result["used_token"] = bool(token)
        return result

    url = f"https://wttr.in/{city}"
    headers = {}
    if token:
        headers['X-User-Token'] = token
    params = {'format': 'j1'}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=6)
        resp.raise_for_status()
        data = resp.json()
        current = data['current_condition'][0]
        return {
            'city': city,
            'description': current['weatherDesc'][0]['value'],
            'temp_c': float(current['temp_C']),
            'feels_like_c': float(current['FeelsLikeC']),
            'provider': 'wttr.in',
            'used_token': bool(token)
        }
    except Exception as exc:
        fallback = DEFAULT_FALLBACK.copy()
        fallback["city"] = city
        fallback["error"] = str(exc)
        fallback["used_token"] = bool(token)
        return fallback
