"""Writes rows to a Google Sheet using a service account (full overwrite)."""

import json
import os

from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _service():
    info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def read_sheet(spreadsheet_id, sheet_name):
    service = _service().spreadsheets().values()
    result = service.get(spreadsheetId=spreadsheet_id, range=sheet_name).execute()
    return result.get("values", [])


def overwrite_sheet(spreadsheet_id, sheet_name, header, rows):
    service = _service().spreadsheets().values()
    full_range = f"{sheet_name}!A:Z"

    service.clear(spreadsheetId=spreadsheet_id, range=full_range, body={}).execute()
    service.update(
        spreadsheetId=spreadsheet_id,
        range=f"{sheet_name}!A1",
        valueInputOption="RAW",
        body={"values": [header] + rows},
    ).execute()
