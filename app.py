import hmac
import logging
import os

from dotenv import load_dotenv
from flask import Flask, jsonify, request

load_dotenv()

import qbo_client
import sheets_client
import token_store

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

SHEET_HEADER = [
    "Invoice ID",
    "Doc Number",
    "Txn Date",
    "Due Date",
    "Customer",
    "Total Amount",
    "Balance",
    "Currency",
    "Email Status",
]


def _invoice_to_row(inv):
    return [
        inv.get("Id", ""),
        inv.get("DocNumber", ""),
        inv.get("TxnDate", ""),
        inv.get("DueDate", ""),
        inv.get("CustomerRef", {}).get("name", ""),
        inv.get("TotalAmt", ""),
        inv.get("Balance", ""),
        inv.get("CurrencyRef", {}).get("value", ""),
        inv.get("EmailStatus", ""),
    ]


def _scheduler_authorized():
    expected = os.environ.get("CRON_SECRET")
    if not expected:
        logger.error("CRON_SECRET is not configured")
        return False
    return hmac.compare_digest(
        request.headers.get("Authorization", ""), f"Bearer {expected}"
    )


@app.route("/sync-invoices", methods=["POST", "GET"])
def sync_invoices():
    if not _scheduler_authorized():
        return jsonify({"status": "unauthorized"}), 401
    try:
        token = token_store.get_token()

        refreshed = qbo_client.refresh_access_token(token["refresh_token"])
        refreshed["realm_id"] = token["realm_id"]
        token_store.save_token(refreshed)

        invoices = qbo_client.fetch_invoices(refreshed["access_token"], refreshed["realm_id"])
        rows = [_invoice_to_row(inv) for inv in invoices]

        sheets_client.overwrite_sheet(
            spreadsheet_id=os.environ["GOOGLE_SHEET_ID"],
            sheet_name=os.environ.get("GOOGLE_SHEET_NAME", "Invoices"),
            header=SHEET_HEADER,
            rows=rows,
        )

        logger.info("Synced %d invoices to sheet", len(invoices))
        return jsonify({"status": "ok", "count": len(invoices)}), 200
    except Exception:
        logger.exception("sync-invoices failed")
        return jsonify({"status": "error"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
