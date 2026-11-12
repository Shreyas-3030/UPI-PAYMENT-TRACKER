import os
import re
from datetime import datetime
from flask import Flask, request, jsonify
import gspread
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

CREDENTIALS_FILE = os.getenv("CREDENTIALS_FILE", "credentials.json")
SHEET_NAME = os.getenv("SHEET_NAME", "upi_payment_tracker")
PORT = int(os.getenv("PORT", 5000))
HOST = os.getenv("HOST", "0.0.0.0")

try:
    gc = gspread.service_account(filename=CREDENTIALS_FILE)
    sheet = gc.open(SHEET_NAME).sheet1
except Exception:
    sheet = None


def parse_upi_notification(data):
    app_name = str(data.get('app_name', 'Unknown')).strip()
    title = str(data.get('title', '')).strip()
    text = str(data.get('text', '')).strip()
    combined_text = f"{title} {text}".replace('\n', ' ').strip()
    lower_text = combined_text.lower()

    payment_keywords = ['paid', 'received', 'sent', 'debited', 'credited']
    has_keyword = any(word in lower_text for word in payment_keywords)

    amount_match = re.search(r'(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d{1,2})?)', combined_text, re.IGNORECASE)
    if not amount_match and has_keyword:
        amount_match = re.search(r'(?:paid|received|sent|debited|credited)\s+([\d,]+(?:\.\d{1,2})?)', combined_text, re.IGNORECASE)

    if has_keyword and amount_match:
        amount = float(amount_match.group(1).replace(',', ''))
        txn_type = 'CREDIT' if any(p in lower_text for p in ['paid you', 'received', 'credited', 'sent you']) else 'DEBIT'

        before_paid_you = re.search(r'^([A-Za-z0-9\s&\.\-]+?)\s+(?:paid|sent)\s+you', combined_text, re.IGNORECASE)
        after_to_from = re.search(r'(?:to|from|at)\s+([A-Za-z0-9\s&\.\-]+?)(?:\s+(?:on|using|via|in|ref|upi|tap|bank)|$)', combined_text, re.IGNORECASE)

        if before_paid_you:
            counterparty = before_paid_you.group(1).strip()
        elif after_to_from:
            counterparty = after_to_from.group(1).strip()
        else:
            counterparty = title
    elif "whatsapp" in app_name.lower():
        txn_type, amount, counterparty = 'WHATSAPP_TEST', 0.0, title
    else:
        return None

    mode = "TEST (WhatsApp)" if "whatsapp" in app_name.lower() else "LIVE (UPI)"
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    return [timestamp, mode, app_name, txn_type, amount, counterparty, combined_text]


@app.route('/', methods=['GET'])
def health():
    return jsonify({"status": "online", "sheet_connected": sheet is not None}), 200


@app.route('/', methods=['POST'])
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json(force=True, silent=True) or {}
    row = parse_upi_notification(data)

    if not row:
        return jsonify({"status": "ignored"}), 200

    if sheet:
        sheet.append_row(row, value_input_option='USER_ENTERED')
        return jsonify({"status": "success", "logged_row": row}), 200

    return jsonify({"status": "error", "message": "Google Sheet not connected"}), 500


if __name__ == '__main__':
    app.run(host=HOST, port=PORT, debug=True)
