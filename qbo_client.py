"""QuickBooks Online OAuth token refresh + Invoice fetching."""

import os
import time

import requests

TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
PAGE_SIZE = 1000


def refresh_access_token(refresh_token):
    resp = requests.post(
        TOKEN_URL,
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        auth=(os.environ["INTUIT_CLIENT_ID"], os.environ["INTUIT_CLIENT_SECRET"]),
        headers={"Accept": "application/json"},
    )
    resp.raise_for_status()
    data = resp.json()
    now = time.time()
    return {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "access_token_expires_at": now + data["expires_in"],
        "refresh_token_expires_at": now + data["x_refresh_token_expires_in"],
    }


def fetch_invoices(access_token, realm_id):
    base_url = os.environ.get(
        "QUICKBOOKS_BASE_URL", "https://sandbox-quickbooks.api.intuit.com/v3"
    )
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}

    invoices = []
    start_position = 1
    while True:
        query = (
            f"SELECT * FROM Invoice ORDERBY Id "
            f"STARTPOSITION {start_position} MAXRESULTS {PAGE_SIZE}"
        )
        resp = requests.get(
            f"{base_url}/company/{realm_id}/query",
            params={"query": query},
            headers=headers,
        )
        resp.raise_for_status()
        batch = resp.json().get("QueryResponse", {}).get("Invoice", [])
        invoices.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        start_position += PAGE_SIZE
    return invoices
