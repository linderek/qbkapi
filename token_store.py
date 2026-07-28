"""Reads/writes the QuickBooks OAuth token in Upstash Redis (REST API).

Stored under the fixed key "qbo:token" as a JSON blob:
{access_token, refresh_token, realm_id, access_token_expires_at, refresh_token_expires_at}
"""

import json
import os

import requests

TOKEN_KEY = "qbo:token"


def _headers():
    return {"Authorization": f"Bearer {os.environ['UPSTASH_REDIS_REST_TOKEN']}"}


def get_token():
    url = os.environ["UPSTASH_REDIS_REST_URL"]
    resp = requests.get(f"{url}/get/{TOKEN_KEY}", headers=_headers())
    resp.raise_for_status()
    result = resp.json()["result"]
    if result is None:
        raise RuntimeError(f"No token found in Upstash under key '{TOKEN_KEY}'")
    return json.loads(result)


def save_token(token):
    url = os.environ["UPSTASH_REDIS_REST_URL"]
    resp = requests.post(
        f"{url}/set/{TOKEN_KEY}",
        headers=_headers(),
        data=json.dumps(token),
    )
    resp.raise_for_status()
