# UPI Payment Tracker System

A webhook system that captures incoming UPI payment notifications from an Android phone (via **MacroDroid**), parses the transaction details (Amount, Debit/Credit, Counterparty, App Name) in real-time, displays them in your IDE terminal, and logs them into structured columns in a **Google Sheet**.

---

## 🚀 How It Works

```
┌────────────────────────────────────────┐
│        Android Phone (MacroDroid)      │
│  Captures UPI Alerts (GPay, PhonePe,   │
│  Paytm) or WhatsApp (for testing)      │
└───────────────────┬────────────────────┘
                    │ HTTP POST (ngrok / local network)
                    ▼
┌────────────────────────────────────────┐
│           Flask Webhook Server         │
│  1. Receives notification JSON payload │
│  2. Filters non-payment notifications  │
│  3. Regex extracts amount & party      │
│  4. Classifies DEBIT vs CREDIT         │
│  5. Tags mode (LIVE UPI vs TEST)       │
└───────────────────┬────────────────────┘
                    │ gspread (Google Auth API)
                    ▼
┌────────────────────────────────────────┐
│              Google Sheets             │
│  Appends structured row (Cols A to G): │
│  [Timestamp, Mode, App, Txn Type,      │
│   Amount, Counterparty, Raw Text]      │
└────────────────────────────────────────┘
```

---

## 📊 Google Sheets Architecture & Real-Time Dashboard

The spreadsheet is divided into two sections: an **Automated Inbound Log** (Columns A–G) and a **Live Monitor Dashboard** (Columns I–L). Column H acts as a spacer.

### 1. Inbound Transaction Log (Columns A to G)

In your Google Sheet (e.g., `upi_payment_tracker`), Row 1 contains the following headers:

| Col A | Col B | Col C | Col D | Col E | Col F | Col G |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Timestamp** | **Mode** | **App Name** | **Type** | **Amount** | **Counterparty** | **Raw Notification** |

- **Formatting Highlights:**
  - `Mode`: Green badge for `LIVE (UPI)`, subtle tag for `TEST (WhatsApp)`.
  - `Type`: Highlighted badges for `CREDIT` vs `WHATSAPP_TEST` / `DEBIT`.
  - `Amount`: Formatted as Indian Rupee currency (`₹ #,##0.00`).

---

### 2. ⚡ Real-Time Monitor Dashboard (Columns I to L)

Built directly alongside the transaction stream without blocking Python's `append_row()`:

* **Top KPI Scorecards (Rows 2–4):**
  - **TOTAL EVENTS**: Total inbound logs (`=COUNTA(A2:A)`)
  - **LIVE UPI**: Count of successful payments (`=COUNTIF(B2:B, "LIVE (UPI)")`)
  - **TEST / PINGS**: Count of test messages (`=COUNTIF(B2:B, "TEST (WhatsApp)")`)
  - **TOTAL CREDITED**: Total INR volume settled (`=SUMIF(D2:D, "CREDIT", E2:E)`)

* **Breakdown Tables (Rows 6–10):**
  - **Breakdown by Mode**: Aggregates event volume by `LIVE (UPI)` vs `TEST (WhatsApp)`.
  - **Integration by App**: Splits volume across apps (`GPay`, `WhatsApp`, etc.).

* **Recent Live Credits Stream (Rows 12–16):**
  - Filtered stream showing the latest live credits (*Timestamp*, *App*, *Amount*, *Counterparty*) using open-ended formulas.

> 💡 **Design Note:** Placing the analytics dashboard in Columns I–L ensures open-ended formulas update instantly while Python continues appending incoming transactions in Columns A–G seamlessly.

---

## 📁 Repository Structure

```text
├── .env                     # Local environment settings (git-ignored)
├── .env.example             # Template for environment variables
├── .gitignore               # Protects credentials.json and .env from Git
├── credentials.json         # Google Cloud Service Account key (git-ignored)
├── credentials.example.json # Template for Service Account JSON
├── main.py                  # Flask webhook receiver and Google Sheets logging
├── requirements.txt         # Required Python packages
└── README.md                # Documentation and setup instructions
```

---

## 🛠️ Prerequisites

1. **Python 3.8+**
2. **Android Phone** with **MacroDroid** installed
3. **Google Cloud Platform (GCP)** account with **Google Sheets API** & **Google Drive API** enabled
4. A **Google Sheet** named `upi_payment_tracker`
5. [ngrok](https://ngrok.com/) (to forward mobile webhook requests to your computer)

---

## ⚙️ Setup Instructions

### 1. Install Dependencies

```bash
# Create and activate a virtual environment (optional)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install required packages
pip install -r requirements.txt
```

---

### 2. Google Cloud Service Account & Sheet Permissions

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project and enable both **Google Sheets API** and **Google Drive API**.
3. Create a **Service Account** under **APIs & Services > Credentials**.
4. In the Service Account, go to **Keys** > **Add Key** > **Create new key (JSON)**.
5. Save the downloaded JSON file as `credentials.json` in the root folder of this project.
6. Open your Google Sheet, click **Share**, and give **Editor** access to the `client_email` found inside `credentials.json`.

---

### 3. MacroDroid Configuration (Android Phone)

Set up a Macro in MacroDroid to catch incoming notifications:

1. **Trigger:**
   - Tap `+` > **Device Events** > **Notification** > **Notification Received**.
   - Select **Select Application(s)**:
     - For testing: Select **WhatsApp**
     - For live UPI: Select **Google Pay**, **PhonePe**, **Paytm**, **BHIM**, etc.
2. **Action:**
   - Tap `+` > **Connectivity** > **HTTP Request**.
   - **Method:** `POST`
   - **URL:** `https://<YOUR-NGROK-ID>.ngrok-free.app/webhook` (or `/`)
   - **Content-Type:** `application/json`
   - **Request Body (JSON):**
     ```json
     {
       "app_name": "{not_app_name}",
       "title": "{not_title}",
       "text": "{not_body}"
     }
     ```
3. Save and enable the Macro.

---

## 🏃 Running the System

### Step 1: Start ngrok
In a separate terminal window, forward port 5000:
```bash
ngrok http 5000
```
Copy the forwarding URL (e.g. `https://abc1234.ngrok-free.app`).

### Step 2: Start the Webhook Server
```bash
python3 main.py
```

### Step 3: Test a Payment Notification
Send a test message on WhatsApp (e.g. `"Paid 150 to Zomato"`) or receive a live UPI alert. You will see the parsed output in your terminal and a new row added to your Google Sheet!

---

## 🔒 Security

- `credentials.json` and `.env` are listed in `.gitignore` and will **never** be pushed to GitHub.
- Keep your Service Account keys private.
