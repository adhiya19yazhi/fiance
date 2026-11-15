# 🌾 Stitch Tamil Finance - Python Flask & MySQL Backend

Backend REST API and MySQL database integration for the Stitch Tamil Finance Management Expo React Native mobile application.

## 🗄️ Database Credentials & Specifications

- **Database Engine**: MySQL 8.0 (InnoDB)
- **Database Name**: `tamil_finance_db`
- **User**: `root`
- **Password**: `Adhi1998$`
- **Host**: `127.0.0.1` (Port: `3306`)
- **Encoding**: `utf8mb4` with `utf8mb4_unicode_ci` (full Tamil Unicode & script fidelity)

---

## 🚀 Quick Start

### 1. Start the Flask Backend Server

```bash
cd backend
./start_backend.sh
```

Or manually:
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

The server starts at `http://0.0.0.0:5000` with CORS enabled.

---

## 📱 Mobile App Connection

- **Default API URL**: `http://192.168.1.42:5000` (works across physical Android/iOS devices on Wi-Fi, emulators, and web).
- **Settings Screen**: You can also verify or update the API URL live in the app's **Settings (அமைப்புகள்) → API சேவையக முகவரி (API Server URL)**.

---

## 📡 REST API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Healthcheck and MySQL connectivity status |
| `GET` | `/api/dashboard/summary` | Real-time cash in hand, receivables, targets, net balance |
| `GET` | `/api/loans` | List loans with search and status filtering (`all`, `active`, `pending`, `completed`) |
| `GET` | `/api/loans/<loan_id>` | Specific loan details with repayment receipt history |
| `POST` | `/api/loans` | Disburse new microfinance loan |
| `POST` | `/api/loans/<loan_id>/collect` | Record EMI collection, update balances, generate receipt |
| `GET` | `/api/savings` | List daily savings accounts with installment records |
| `POST` | `/api/savings` | Open new daily savings scheme account |
| `POST` | `/api/savings/<savings_id>/collect` | Record daily savings deposit collection |
| `POST` | `/api/savings/<savings_id>/payout` | Disburse matured savings balance |
| `GET` | `/api/reserved` | Emergency safety reserve balance and transaction history |
| `POST` | `/api/reserved/add` | Transfer surplus to emergency reserve fund |
| `POST` | `/api/reserved/reduce` | Withdraw emergency reserve fund to cash-in-hand |
