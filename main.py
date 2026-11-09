import os
import re
from datetime import datetime
from flask import Flask, request, jsonify
import gspread

# Load environment variables from .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = Flask(__name__)

# ==========================================
# 1. CONFIGURATION
# ==========================================
CREDENTIALS_FILE = os.getenv("CREDENTIALS_FILE", "credentials.json")
SHEET_NAME = os.getenv("SHEET_NAME", "upi_payment_tracker")
PORT = int(os.getenv("PORT", 5000))
HOST = os.getenv("HOST", "0.0.0.0")

# Keep True while testing with WhatsApp so NO message gets ignored.
# Change to False later when you only want real GPay/Paytm payment alerts.
ALLOW_ALL_TEST_MESSAGES = True

try:
    gc = gspread.service_account(filename=CREDENTIALS_FILE)
    sheet = gc.open(SHEET_NAME).sheet1
    print(f"✅ Successfully connected to Google Sheet: {SHEET_NAME}")
except Exception as e:
    print(f"❌ Error connecting to Google Sheets: {e}")
    sheet = None


# ==========================================
# 2. UNIFIED NOTIFICATION PARSER
# ==========================================
def parse_upi_notification(data):
    app_name = str(data.get('app_name', 'Unknown')).strip()
    title = str(data.get('title', '')).strip()
    text = str(data.get('text', '')).strip()

    combined_text = f"{title} {text}".replace('\n', ' ').strip()
    lower_text = combined_text.lower()

    # Check if this is from WhatsApp or if test mode is enabled
    is_whatsapp = "whatsapp" in app_name.lower() or app_name == "{app_name}"

    # 1. Check for payment keywords
    payment_keywords = ['paid', 'received', 'sent', 'debited', 'credited']
    has_payment_keyword = any(word in lower_text for word in payment_keywords)

    # 2. Extract Amount:
    # First try with ₹ / Rs / INR (e.g., "Paid ₹150" or "Rs. 500")
    amount_match = re.search(r'(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d{1,2})?)', combined_text, re.IGNORECASE)
    
    # Fallback for WhatsApp tests typed without ₹ symbol (e.g., "Paid 150 to Zomato")
    if not amount_match and has_payment_keyword:
        amount_match = re.search(r'(?:paid|received|sent|debited|credited)\s+([\d,]+(?:\.\d{1,2})?)', combined_text, re.IGNORECASE)

    # If it's a valid payment format (has keyword + amount)
    if has_payment_keyword and amount_match:
        amount = float(amount_match.group(1).replace(',', ''))

        # Check "paid you" FIRST so incoming GPay transfers count as CREDIT
        if any(phrase in lower_text for phrase in ['paid you', 'received', 'credited', 'sent you']):
            txn_type = 'CREDIT'
        elif any(word in lower_text for word in ['paid', 'sent', 'debited']):
            txn_type = 'DEBIT'
        else:
            txn_type = 'PAYMENT'

        # Extract Counterparty (handles both "Paid ₹1 to X" and "X paid you ₹1")
        before_paid_you = re.search(r'^([A-Za-z0-9\s&\.\-]+?)\s+(?:paid|sent)\s+you', combined_text, re.IGNORECASE)
        after_to_from = re.search(
            r'(?:to|from|at)\s+([A-Za-z0-9\s&\.\-]+?)(?:\s+(?:on|using|via|in|ref|upi|tap|bank)|$)',
            combined_text,
            re.IGNORECASE
        )

        if before_paid_you:
            counterparty = before_paid_you.group(1).strip()
        elif after_to_from:
            counterparty = after_to_from.group(1).strip()
        else:
            counterparty = title

    # If it's a normal WhatsApp chat (like "Hi" or "Testing") and test mode is ON:
    elif is_whatsapp or ALLOW_ALL_TEST_MESSAGES:
        txn_type = 'WHATSAPP_TEST'
        amount = 0.0
        counterparty = title  # Sender's name from WhatsApp notification title

    # Otherwise, ignore non-payment spam
    else:
        return None

    # Set Mode column
    if "whatsapp" in app_name.lower() or app_name == "{app_name}":
        mode = "TEST (WhatsApp)"
    elif any(upi_app in app_name.lower() for upi_app in ["pay", "gpay", "paytm", "phonepe"]):
        mode = "LIVE (UPI)"
    else:
        mode = "TEST"

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    return [timestamp, mode, app_name, txn_type, amount, counterparty, combined_text]


# ==========================================
# 3. FLASK WEBHOOK ROUTE
# ==========================================
@app.route('/', methods=['GET'])
def health():
    return jsonify({
        "status": "online",
        "sheet_connected": sheet is not None,
        "sheet_name": SHEET_NAME
    }), 200

@app.route('/', methods=['POST'])
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json(force=True, silent=True)
        
        if not data:
            return jsonify({"status": "error", "message": "Invalid or empty JSON payload"}), 400

        print(f"\n📩 Incoming Notification: {data}")

        row = parse_upi_notification(data)

        if row is None:
            print("⏭️ Ignored: Not a valid payment transaction.")
            return jsonify({"status": "ignored", "reason": "Non-payment notification"}), 200

        if sheet:
            sheet.append_row(row, value_input_option='USER_ENTERED')
            print(f"✅ Logged to Google Sheets: {row[3]} | Amount: ₹{row[4]} | From/To: {row[5]}")
            return jsonify({"status": "success", "logged_row": row}), 200
        else:
            print("❌ Google Sheet is not connected.")
            return jsonify({"status": "error", "message": "Google Sheet not connected"}), 500

    except Exception as e:
        print(f"❌ Server Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == '__main__':
    app.run(host=HOST, port=PORT, debug=True)
