"""Writes rows to Google Sheets using a service account (full overwrite)."""

import json
import os

from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _credentials():
    info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)


def _sheets_service():
    return build("sheets", "v4", credentials=_credentials(), cache_discovery=False)


def _drive_service():
    return build("drive", "v3", credentials=_credentials(), cache_discovery=False)


def read_sheet(spreadsheet_id, sheet_name):
    service = _sheets_service().spreadsheets().values()
    result = service.get(spreadsheetId=spreadsheet_id, range=sheet_name).execute()
    return result.get("values", [])


def read_sheet_with_links(spreadsheet_id, sheet_name):
    """Like read_sheet, but each row gets one extra trailing element: the
    hyperlink set on that row's first cell (empty string if none)."""
    result = (
        _sheets_service()
        .spreadsheets()
        .get(
            spreadsheetId=spreadsheet_id,
            ranges=[sheet_name],
            fields="sheets.data.rowData.values(formattedValue,hyperlink)",
        )
        .execute()
    )

    sheets = result.get("sheets", [])
    if not sheets:
        return []
    row_data = sheets[0].get("data", [{}])[0].get("rowData", [])

    rows = []
    for row in row_data:
        cells = row.get("values", [])
        values = [cell.get("formattedValue", "") for cell in cells]
        url = cells[0].get("hyperlink", "") if cells else ""
        rows.append(values + [url])
    return rows


def overwrite_sheet(spreadsheet_id, sheet_name, header, rows):
    service = _sheets_service().spreadsheets().values()
    full_range = f"{sheet_name}!A:Z"

    service.clear(spreadsheetId=spreadsheet_id, range=full_range, body={}).execute()
    service.update(
        spreadsheetId=spreadsheet_id,
        range=f"{sheet_name}!A1",
        valueInputOption="RAW",
        body={"values": [header] + rows},
    ).execute()


def _find_spreadsheet_in_folder(drive_service, folder_id, name):
    safe_name = name.replace("\\", "\\\\").replace("'", "\\'")
    query = (
        f"name = '{safe_name}' and '{folder_id}' in parents "
        "and mimeType = 'application/vnd.google-apps.spreadsheet' and trashed = false"
    )
    result = drive_service.files().list(
        q=query,
        fields="files(id, name)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
        corpora="allDrives",
    ).execute()
    files = result.get("files", [])
    return files[0]["id"] if files else None


def _find_folder_in_folder(drive_service, parent_folder_id, name):
    safe_name = name.replace("\\", "\\\\").replace("'", "\\'")
    query = (
        f"name = '{safe_name}' and '{parent_folder_id}' in parents "
        "and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    )
    result = drive_service.files().list(
        q=query,
        fields="files(id, name)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
        corpora="allDrives",
    ).execute()
    files = result.get("files", [])
    return files[0]["id"] if files else None


def sync_customer_folder(parent_folder_id, folder_name):
    """Find-or-create a folder named `folder_name` under `parent_folder_id`,
    return its folder id."""
    drive_service = _drive_service()
    folder_id = _find_folder_in_folder(drive_service, parent_folder_id, folder_name)

    if folder_id is None:
        created = drive_service.files().create(
            body={
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [parent_folder_id],
            },
            fields="id",
            supportsAllDrives=True,
        ).execute()
        folder_id = created["id"]

    return folder_id


def write_customer_sheet(folder_id, customer_name, header, rows):
    """Find-or-create a spreadsheet named `customer_name` in `folder_id`, then
    overwrite its (first tab's) contents with header + rows."""
    drive_service = _drive_service()
    spreadsheet_id = _find_spreadsheet_in_folder(drive_service, folder_id, customer_name)

    if spreadsheet_id is None:
        created = drive_service.files().create(
            body={
                "name": customer_name,
                "mimeType": "application/vnd.google-apps.spreadsheet",
                "parents": [folder_id],
            },
            fields="id",
            supportsAllDrives=True,
        ).execute()
        spreadsheet_id = created["id"]

    values = _sheets_service().spreadsheets().values()
    values.clear(spreadsheetId=spreadsheet_id, range="A1:Z", body={}).execute()
    values.update(
        spreadsheetId=spreadsheet_id,
        range="A1",
        valueInputOption="RAW",
        body={"values": [header] + rows},
    ).execute()
