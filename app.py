import random
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import sys

# Ensure current directory is in sys.path for direct script execution
_current_dir = os.path.dirname(os.path.abspath(__file__))
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

try:
    from config import Config
    from db import init_db, query_db, execute_db, check_db_health
    from seed import seed_data
except ImportError:
    from .config import Config
    from .db import init_db, query_db, execute_db, check_db_health
    from .seed import seed_data

app = Flask(__name__)
CORS(app)

# Helper function to convert Decimal to float/int
def sanitize_record(row):
    if not row:
        return row
    result = {}
    for k, v in row.items():
        if hasattr(v, 'as_tuple') or type(v).__name__ == 'Decimal':
            result[k] = float(v)
        else:
            result[k] = v
    return result

# -------------------------------------------------------------
# MULTI-TENANCY HELPERS (Per-User Scoping)
# -------------------------------------------------------------
def get_current_user_id():
    """
    Extracts the authenticated user ID from:
    1. HTTP header 'X-User-Id'
    2. Query param 'userId' or 'user_id'
    3. JSON payload 'userId' or 'user_id'
    Fallback: returns first active user or 'USR-1691' if none specified.
    """
    # 1. Header
    uid = request.headers.get('X-User-Id')
    if uid and uid.strip() and uid.strip().lower() not in ('null', 'undefined', ''):
        return uid.strip()
    
    # 2. Query param
    uid = request.args.get('userId') or request.args.get('user_id')
    if uid and uid.strip() and uid.strip().lower() not in ('null', 'undefined', ''):
        return uid.strip()
        
    # 3. JSON body
    if request.is_json:
        try:
            body = request.get_json(silent=True) or {}
            uid = body.get('userId') or body.get('user_id')
            if uid and str(uid).strip() and str(uid).strip().lower() not in ('null', 'undefined', ''):
                return str(uid).strip()
        except Exception:
            pass

    # 4. Fallback default
    first_active = query_db("SELECT user_id FROM users WHERE is_active = 1 ORDER BY id ASC LIMIT 1;", one=True)
    if first_active and first_active.get('user_id'):
        return first_active['user_id']
    return 'USR-1691'

def ensure_user_metrics(user_id):
    """
    Ensures that a row in finance_metrics exists for the specific user.
    If not, creates it with 0.00 balances.
    Returns the metrics row sanitized.
    """
    row = query_db("SELECT * FROM finance_metrics WHERE user_id = %s LIMIT 1;", (user_id,), one=True)
    if not row:
        execute_db("""
            INSERT INTO finance_metrics (user_id, cash_in_hand, reserved_balance, today_collected, today_target)
            VALUES (%s, 0.00, 0.00, 0.00, 0.00)
            ON DUPLICATE KEY UPDATE updated_at = CURRENT_TIMESTAMP;
        """, (user_id,))
        row = query_db("SELECT * FROM finance_metrics WHERE user_id = %s LIMIT 1;", (user_id,), one=True)
    return sanitize_record(row) if row else {'cash_in_hand': 0.0, 'reserved_balance': 0.0, 'today_collected': 0.0, 'today_target': 0.0}

# -------------------------------------------------------------
# 1. HEALTH & METRICS ENDPOINTS
# -------------------------------------------------------------
@app.route('/api/health', methods=['GET'])
def health():
    db_ok, db_msg = check_db_health()
    return jsonify({
        'status': 'ok' if db_ok else 'degraded',
        'database': 'connected' if db_ok else 'disconnected',
        'message': db_msg,
        'app': 'Stitch Tamil Finance Flask API',
        'version': '2.6.0'
    }), (200 if db_ok else 500)

@app.route('/api/dashboard/summary', methods=['GET'])
def dashboard_summary():
    try:
        user_id = get_current_user_id()
        metrics_row = ensure_user_metrics(user_id)

        # 1. Loans metrics for user
        loans_row = query_db("""
            SELECT 
                COUNT(*) as total_count,
                COALESCE(SUM(total_amount), 0) as total_disbursed,
                COALESCE(SUM(CASE WHEN status != 'completed' THEN balance_amount ELSE 0 END), 0) as active_receivable,
                COALESCE(SUM(paid_amount), 0) as total_collected,
                COALESCE(SUM(CASE WHEN status = 'active' THEN emi_amount ELSE 0 END), 0) as active_emi_due
            FROM loans
            WHERE user_id = %s;
        """, (user_id,), one=True) or {}

        # 2. Savings metrics for user
        savings_row = query_db("""
            SELECT 
                COUNT(*) as total_count,
                COALESCE(SUM(total_saved), 0) as total_saved,
                COALESCE(SUM(CASE WHEN status = 'active' THEN daily_amount ELSE 0 END), 0) as active_daily_due
            FROM savings
            WHERE user_id = %s;
        """, (user_id,), one=True) or {}

        # 3. Investors metrics for user
        investors_row = query_db("""
            SELECT 
                COUNT(*) as total_count,
                COALESCE(SUM(invested_amount), 0) as total_invested,
                COALESCE(SUM(principal_repaid), 0) as total_principal_repaid,
                COALESCE(SUM(profit_repaid), 0) as total_profit_repaid,
                COALESCE(SUM(balance_amount), 0) as outstanding_balance
            FROM investors
            WHERE user_id = %s;
        """, (user_id,), one=True) or {}

        # 4. Reserve metrics for user
        reserve_row = query_db("""
            SELECT 
                COALESCE(SUM(CASE WHEN type = 'add' THEN amount ELSE 0 END), 0) as total_added,
                COALESCE(SUM(CASE WHEN type = 'reduce' THEN amount ELSE 0 END), 0) as total_reduced
            FROM reserve_transactions
            WHERE user_id = %s;
        """, (user_id,), one=True) or {}
        reserved_balance = max(0.0, float(reserve_row.get('total_added', 0)) - float(reserve_row.get('total_reduced', 0)))

        # 5. Today's collections from transactions for user
        today_loan_rep = query_db("""
            SELECT COALESCE(SUM(lr.amount), 0) as total_today
            FROM loan_repayments lr
            JOIN loans l ON lr.loan_id = l.id
            WHERE l.user_id = %s AND (lr.receipt_date LIKE %s OR lr.receipt_date LIKE %s OR DATE(lr.created_at) = CURDATE());
        """, (user_id, '%இன்று%', '%Today%'), one=True) or {}

        today_sav_rep = query_db("""
            SELECT COALESCE(SUM(si.amount), 0) as total_today
            FROM savings_installments si
            JOIN savings s ON si.savings_id = s.id
            WHERE s.user_id = %s AND (si.receipt_date LIKE %s OR si.receipt_date LIKE %s OR DATE(si.created_at) = CURDATE());
        """, (user_id, '%இன்று%', '%Today%'), one=True) or {}

        today_collected = float(today_loan_rep.get('total_today', 0)) + float(today_sav_rep.get('total_today', 0))
        active_emi_due = float(loans_row.get('active_emi_due', 0))
        active_daily_due = float(savings_row.get('active_daily_due', 0))
        today_target = active_emi_due + active_daily_due

        # 6. Cash in hand from metrics table for user
        cash_in_hand = float(metrics_row.get('cash_in_hand', 0.0))

        total_disbursed = float(loans_row.get('total_disbursed', 0))
        active_receivable = float(loans_row.get('active_receivable', 0))
        total_loans_count = int(loans_row.get('total_count', 0))

        total_savings_amount = float(savings_row.get('total_saved', 0))
        total_savings_count = int(savings_row.get('total_count', 0))

        total_invested = float(investors_row.get('total_invested', 0))
        outstanding_investments = float(investors_row.get('outstanding_balance', 0))
        total_investors_count = int(investors_row.get('total_count', 0))
        total_profit_paid = float(investors_row.get('total_profit_repaid', 0))

        # Net total business worth: Cash + Reserves + Receivables - Investor Liabilities
        total_net = cash_in_hand + reserved_balance + active_receivable - outstanding_investments

        # Real monthly interest/income calculation
        monthly_income = max(0.0, (active_receivable * 0.02) + (total_savings_amount * 0.01) - (total_profit_paid * 0.1))

        return jsonify({
            'success': True,
            'userId': user_id,
            'isRealTime': True,
            'cashInHand': cash_in_hand,
            'reservedBalance': reserved_balance,
            'todayCollected': today_collected,
            'todayTarget': today_target,
            'totalNet': total_net,
            'activeReceivable': active_receivable,
            'totalLoansCount': total_loans_count,
            'totalLoansDisbursed': total_disbursed,
            'totalSavingsCount': total_savings_count,
            'totalSavingsAmount': total_savings_amount,
            'totalInvestorsCount': total_investors_count,
            'totalInvested': total_invested,
            'outstandingInvestments': outstanding_investments,
            'totalProfitPaid': total_profit_paid,
            'monthlyIncome': monthly_income
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# -------------------------------------------------------------
# 2. LOANS ENDPOINTS (Scoped to User)
# -------------------------------------------------------------
@app.route('/api/loans', methods=['GET'])
def get_loans():
    try:
        user_id = get_current_user_id()
        search = request.args.get('search', '').strip().lower()
        status = request.args.get('status', 'all')

        query = "SELECT * FROM loans WHERE user_id = %s"
        args = [user_id]
        if status and status != 'all':
            query += " AND status = %s"
            args.append(status)

        rows = query_db(query + " ORDER BY created_at DESC;", args) or []
        loans = [sanitize_record(r) for r in rows]

        # Attach repayments history for each loan
        for l in loans:
            repayments = query_db("SELECT * FROM loan_repayments WHERE loan_id = %s ORDER BY created_at DESC;", (l['id'],)) or []
            l['history'] = [{
                'id': r['id'],
                'amount': float(r['amount']),
                'mode': r['payment_mode'],
                'modeEn': r['payment_mode_en'],
                'date': r['receipt_date'],
                'dateEn': r['receipt_date_en'],
                'status': r['status']
            } for r in repayments]

        # Apply search if present
        if search:
            loans = [
                l for l in loans if
                search in (l.get('customer_name') or '').lower() or
                search in (l.get('customer_name_en') or '').lower() or
                search in (l.get('phone') or '').lower() or
                search in (l.get('id') or '').lower()
            ]

        # Normalize camelCase for React Native
        normalized = []
        for l in loans:
            tot = float(l['total_amount'])
            taken = float(l.get('taken_amount') or 0.0)
            disbursed = float(l.get('disbursed_amount') or (tot - taken))
            normalized.append({
                'id': l['id'],
                'userId': l.get('user_id', user_id),
                'customerName': l['customer_name'],
                'customerNameEn': l['customer_name_en'],
                'customerCode': l['customer_code'],
                'phone': l['phone'],
                'address': l['address'],
                'addressEn': l['address_en'],
                'totalAmount': tot,
                'paidAmount': float(l['paid_amount']),
                'balanceAmount': float(l['balance_amount']),
                'emiAmount': float(l['emi_amount']),
                'takenAmount': taken,
                'disbursedAmount': disbursed,
                'interestRate': float(l['interest_rate']),
                'frequency': l['frequency'],
                'currentInstallment': int(l['current_installment']),
                'totalInstallments': int(l['total_installments']),
                'nextDueDate': l['next_due_date'],
                'nextDueDateEn': l['next_due_date_en'],
                'status': l['status'],
                'history': l['history']
            })

        return jsonify({'success': True, 'loans': normalized})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/loans/<loan_id>', methods=['GET'])
def get_loan(loan_id):
    try:
        user_id = get_current_user_id()
        clean_id = str(loan_id).replace('#', '').strip()
        row = query_db("SELECT * FROM loans WHERE (id = %s OR id = %s OR id LIKE %s) AND user_id = %s;", 
                       (clean_id, f"#{clean_id}", f"%{clean_id}%", user_id), one=True)
        if not row:
            # Fallback to check without user_id if needed
            row = query_db("SELECT * FROM loans WHERE id = %s OR id = %s OR id LIKE %s;", (clean_id, f"#{clean_id}", f"%{clean_id}%"), one=True)
        if not row:
            return jsonify({'success': False, 'error': 'Loan not found'}), 404
        loan = sanitize_record(row)
        actual_id = loan['id']
        repayments = query_db("SELECT * FROM loan_repayments WHERE loan_id = %s ORDER BY created_at DESC;", (actual_id,)) or []
        loan['history'] = [{
            'id': r['id'],
            'amount': float(r['amount']),
            'mode': r['payment_mode'],
            'modeEn': r['payment_mode_en'],
            'date': r['receipt_date'],
            'dateEn': r['receipt_date_en'],
            'status': r['status']
        } for r in repayments]
        return jsonify({'success': True, 'loan': loan})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/loans', methods=['POST'])
def create_loan():
    try:
        user_id = get_current_user_id()
        metrics = ensure_user_metrics(user_id)
        data = request.json or {}
        new_id = (data.get('id') or f"LN-{random.randint(1000, 9999)}").replace('#', '').strip()
        name = data.get('customerName', '')
        name_en = data.get('customerNameEn', name)
        phone = data.get('phone', '')
        address = data.get('address', 'மதுரை')
        address_en = data.get('addressEn', 'Madurai')
        total_amount = float(data.get('amount') or data.get('totalAmount') or 10000)
        taken_amount = float(data.get('takenAmount', 0))
        disbursed_amount = float(data.get('disbursedAmount') or (total_amount - taken_amount))
        emi = float(data.get('emi') or data.get('emiAmount') or (total_amount / 10))
        rate = float(data.get('interestRate', 0.0))
        frequency = data.get('frequency', 'வாராந்திரம் (Weekly)')
        tenure = int(data.get('tenureWeeks') or data.get('totalInstallments') or 10)

        # Check if loan with new_id already exists
        existing = query_db("SELECT id FROM loans WHERE id = %s;", (new_id,), one=True)
        if existing:
            new_id = f"LN-{random.randint(1000, 9999)}"

        # Strict validation: Only disburse if user's cash in hand is sufficient!
        current_cash = float(metrics.get('cash_in_hand', 0.0))
        if disbursed_amount > current_cash:
            return jsonify({
                'success': False,
                'error': f'கையிருப்புத் தொகை போதாது (Insufficient Cash in Hand: ₹{current_cash:,.2f}). கடன் வழங்க தேவையான தொகை: ₹{disbursed_amount:,.2f}. முதலீட்டை சேர்க்கவும் அல்லது இருப்பை சரிபார்க்கவும்.'
            }), 400

        execute_db("""
            INSERT INTO loans (id, user_id, customer_name, customer_name_en, customer_code, phone, address, address_en, total_amount, paid_amount, balance_amount, emi_amount, taken_amount, disbursed_amount, interest_rate, frequency, current_installment, total_installments, next_due_date, next_due_date_en, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 0.00, %s, %s, %s, %s, %s, %s, 0, %s, 'அடுத்த வாரம்', 'Next Week', 'active');
        """, (new_id, user_id, name, name_en, f"VP-{random.randint(100, 999)}", phone, address, address_en, total_amount, total_amount, emi, taken_amount, disbursed_amount, rate, frequency, tenure))

        # Deduct ONLY the net cash disbursed (given amount, e.g. 8000) from user's cash in hand!
        execute_db("UPDATE finance_metrics SET cash_in_hand = GREATEST(0.00, cash_in_hand - %s) WHERE user_id = %s;", (disbursed_amount, user_id))

        return jsonify({
            'success': True,
            'loanId': new_id,
            'userId': user_id,
            'totalAmount': total_amount,
            'takenAmount': taken_amount,
            'disbursedAmount': disbursed_amount,
            'message': 'Loan created successfully'
        }), 201
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/loans/<loan_id>/collect', methods=['POST'])
def collect_loan_payment(loan_id):
    try:
        user_id = get_current_user_id()
        data = request.json or {}
        amount = float(data.get('amount', 500))
        payment_mode = data.get('paymentMode', 'ரொக்கம்')
        payment_mode_en = data.get('paymentModeEn', 'Cash')

        clean_id = str(loan_id).replace('#', '').strip()
        loan = query_db("SELECT * FROM loans WHERE (id = %s OR id = %s) AND user_id = %s;", (clean_id, f"#{clean_id}", user_id), one=True)
        if not loan:
            loan = query_db("SELECT * FROM loans WHERE id = %s OR id = %s;", (clean_id, f"#{clean_id}"), one=True)
        if not loan:
            loan = query_db("SELECT * FROM loans WHERE id LIKE %s;", (f"%{clean_id}%",), one=True)

        # If not found, auto-recover/create loan record scoped to user
        if not loan:
            cust_name = data.get('customerName') or 'வாடிக்கையாளர்'
            cust_name_en = data.get('customerNameEn') or 'Customer'
            phone = data.get('phone') or '+91 98421 00000'
            tot_amt = float(data.get('totalAmount') or 10000.0)
            execute_db("""
                INSERT INTO loans (id, user_id, customer_name, customer_name_en, customer_code, phone, address, address_en, total_amount, paid_amount, balance_amount, emi_amount, taken_amount, disbursed_amount, interest_rate, frequency, current_installment, total_installments, next_due_date, next_due_date_en, status)
                VALUES (%s, %s, %s, %s, %s, %s, 'மதுரை', 'Madurai', %s, 0.00, %s, %s, 0.00, %s, 0.00, 'வாராந்திரம் (Weekly)', 0, 10, 'அடுத்த வாரம்', 'Next Week', 'active');
            """, (clean_id, user_id, cust_name, cust_name_en, f"VP-{random.randint(100, 999)}", phone, tot_amt, tot_amt, amount, tot_amt))
            loan = query_db("SELECT * FROM loans WHERE id = %s;", (clean_id,), one=True)

        target_user_id = loan.get('user_id') or user_id
        ensure_user_metrics(target_user_id)

        actual_id = loan['id']
        prev_balance = float(loan['balance_amount'])
        new_balance = max(0.0, prev_balance - amount)
        new_paid = float(loan['paid_amount']) + amount
        new_inst = int(loan['current_installment']) + 1
        new_status = 'completed' if new_balance == 0 else loan['status']

        rec_id = f"REC-2026-{random.randint(1000, 9999)}"
        now_ta = "இன்று | " + datetime.now().strftime("%I:%M %p")
        now_en = "Today | " + datetime.now().strftime("%I:%M %p")

        # 1. Update loan
        execute_db("""
            UPDATE loans 
            SET paid_amount = %s, balance_amount = %s, current_installment = %s, status = %s
            WHERE id = %s;
        """, (new_paid, new_balance, new_inst, new_status, actual_id))

        # 2. Insert repayment record
        execute_db("""
            INSERT INTO loan_repayments (id, loan_id, amount, payment_mode, payment_mode_en, receipt_date, receipt_date_en, previous_balance, new_balance, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'completed');
        """, (rec_id, actual_id, amount, payment_mode, payment_mode_en, now_ta, now_en, prev_balance, new_balance))

        # 3. Update cash in hand & today collected for user
        execute_db("""
            UPDATE finance_metrics 
            SET cash_in_hand = cash_in_hand + %s, today_collected = today_collected + %s
            WHERE user_id = %s;
        """, (amount, amount, target_user_id))

        receipt = {
            'receiptNo': f"#{rec_id}",
            'date': now_ta,
            'dateEn': now_en,
            'amount': amount,
            'customerName': loan['customer_name'],
            'customerNameEn': loan['customer_name_en'],
            'phone': loan['phone'],
            'loanId': f"#{actual_id}",
            'paymentMode': payment_mode,
            'paymentModeEn': payment_mode_en,
            'previousBalance': prev_balance,
            'newBalance': new_balance,
            'officer': 'கள அலுவலர் #4',
            'officerEn': 'Field Officer #4'
        }

        return jsonify({'success': True, 'receipt': receipt})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# -------------------------------------------------------------
# 3. SAVINGS ENDPOINTS (Scoped to User)
# -------------------------------------------------------------
@app.route('/api/savings', methods=['GET'])
def get_savings():
    try:
        user_id = get_current_user_id()
        rows = query_db("SELECT * FROM savings WHERE user_id = %s ORDER BY created_at DESC;", (user_id,)) or []
        savings = [sanitize_record(r) for r in rows]

        for s in savings:
            installments = query_db("SELECT * FROM savings_installments WHERE savings_id = %s ORDER BY created_at DESC;", (s['id'],)) or []
            s['history'] = [{
                'id': i['id'],
                'amount': float(i['amount']),
                'installments': int(i['installments_count']),
                'mode': i['payment_mode'],
                'modeEn': i['payment_mode_en'],
                'date': i['receipt_date'],
                'dateEn': i['receipt_date_en'],
                'balance': float(i['running_balance'])
            } for i in installments]

        normalized = []
        for s in savings:
            normalized.append({
                'id': s['id'],
                'userId': s.get('user_id', user_id),
                'customerName': s['customer_name'],
                'customerNameEn': s['customer_name_en'],
                'customerCode': s['customer_code'],
                'phone': s['phone'],
                'address': s['address'],
                'addressEn': s['address_en'],
                'schemeName': s['scheme_name'],
                'schemeNameEn': s['scheme_name_en'],
                'dailyAmount': s['daily_amount'],
                'paidInstallments': s['paid_installments'],
                'totalInstallments': s['total_installments'],
                'totalSaved': s['total_saved'],
                'targetAmount': s['target_amount'],
                'payoutAmount': s['payout_amount'],
                'bonusAmount': s['bonus_amount'],
                'startDate': s['start_date'],
                'startDateEn': s['start_date_en'],
                'status': s['status'],
                'history': s['history']
            })

        return jsonify({'success': True, 'savings': normalized})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/savings', methods=['POST'])
def create_savings():
    try:
        user_id = get_current_user_id()
        ensure_user_metrics(user_id)
        data = request.json or {}
        new_id = (data.get('id') or f"SV-{random.randint(100, 999)}").replace('#', '').strip()
        name = data.get('customerName', '')
        name_en = data.get('customerNameEn', name)
        phone = data.get('phone', '')
        daily_amount = float(data.get('dailyAmount', 100))
        total_days = int(data.get('totalInstallments', 105))
        initial_deposit = float(data.get('initialDeposit', 0.0))
        target = daily_amount * total_days
        payout = daily_amount * (total_days - 5)
        bonus = daily_amount * 5

        paid_inst = 1 if initial_deposit > 0 else 0
        total_saved = initial_deposit if initial_deposit > 0 else 0.00

        execute_db("""
            INSERT INTO savings (id, user_id, customer_name, customer_name_en, customer_code, phone, address, address_en, scheme_name, scheme_name_en, daily_amount, paid_installments, total_installments, total_saved, target_amount, payout_amount, bonus_amount, start_date, start_date_en, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'மதுரை', 'Madurai', 'தினசரி சேமிப்பு', 'Daily Savings', %s, %s, %s, %s, %s, %s, %s, 'இன்று', 'Today', 'active');
        """, (new_id, user_id, name, name_en, f"CUST-{random.randint(100, 999)}", phone, daily_amount, paid_inst, total_days, total_saved, target, payout, bonus))

        if initial_deposit > 0:
            rec_id = f"SAV-REC-{random.randint(1000, 9999)}"
            now_ta = "இன்று | " + datetime.now().strftime("%I:%M %p")
            now_en = "Today | " + datetime.now().strftime("%I:%M %p")
            execute_db("""
                INSERT INTO savings_installments (id, savings_id, installments_count, amount, payment_mode, payment_mode_en, receipt_date, receipt_date_en, running_balance)
                VALUES (%s, %s, 1, %s, 'ரொக்கம்', 'Cash', %s, %s, %s);
            """, (rec_id, new_id, initial_deposit, now_ta, now_en, initial_deposit))

            execute_db("""
                UPDATE finance_metrics 
                SET cash_in_hand = cash_in_hand + %s, today_collected = today_collected + %s
                WHERE user_id = %s;
            """, (initial_deposit, initial_deposit, user_id))

        metrics = query_db("SELECT cash_in_hand, today_collected FROM finance_metrics WHERE user_id = %s;", (user_id,), one=True)
        updated_cash = float(metrics['cash_in_hand']) if metrics else 0.0

        return jsonify({'success': True, 'savingsId': new_id, 'userId': user_id, 'cashInHand': updated_cash, 'message': 'Savings account created'}), 201
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/savings/<savings_id>/collect', methods=['POST'])
def collect_savings_payment(savings_id):
    try:
        user_id = get_current_user_id()
        data = request.json or {}
        inst_count = int(data.get('installments', 1))
        payment_mode = data.get('paymentMode', 'ரொக்கம்')
        payment_mode_en = data.get('paymentModeEn', 'Cash')

        clean_id = str(savings_id).replace('#', '').strip()
        savings = query_db("SELECT * FROM savings WHERE (id = %s OR id = %s) AND user_id = %s;", (clean_id, f"#{clean_id}", user_id), one=True)
        if not savings:
            savings = query_db("SELECT * FROM savings WHERE id = %s OR id = %s OR id LIKE %s;", (clean_id, f"#{clean_id}", f"%{clean_id}%"), one=True)
        if not savings:
            return jsonify({'success': False, 'error': 'Savings account not found'}), 404

        target_user_id = savings.get('user_id') or user_id
        ensure_user_metrics(target_user_id)

        daily_amt = float(savings['daily_amount'])
        collected_amt = inst_count * daily_amt
        new_paid = int(savings['paid_installments']) + inst_count
        new_total = float(savings['total_saved']) + collected_amt
        tot_inst = int(savings['total_installments'])
        new_status = 'matured' if new_paid >= tot_inst else savings['status']

        rec_id = f"SAV-REC-{random.randint(1000, 9999)}"
        now_ta = "இன்று | " + datetime.now().strftime("%I:%M %p")
        now_en = "Today | " + datetime.now().strftime("%I:%M %p")

        actual_id = savings['id']

        # 1. Update savings
        execute_db("""
            UPDATE savings
            SET paid_installments = %s, total_saved = %s, status = %s
            WHERE id = %s;
        """, (new_paid, new_total, new_status, actual_id))

        # 2. Insert installment
        execute_db("""
            INSERT INTO savings_installments (id, savings_id, installments_count, amount, payment_mode, payment_mode_en, receipt_date, receipt_date_en, running_balance)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
        """, (rec_id, actual_id, inst_count, collected_amt, payment_mode, payment_mode_en, now_ta, now_en, new_total))

        # 3. Update cash in hand for user
        execute_db("""
            UPDATE finance_metrics 
            SET cash_in_hand = cash_in_hand + %s, today_collected = today_collected + %s
            WHERE user_id = %s;
        """, (collected_amt, collected_amt, target_user_id))

        metrics = query_db("SELECT cash_in_hand, today_collected FROM finance_metrics WHERE user_id = %s;", (target_user_id,), one=True)
        updated_cash = float(metrics['cash_in_hand']) if metrics else 0.0

        receipt = {
            'receiptNo': f"#{rec_id}",
            'date': now_ta,
            'dateEn': now_en,
            'amount': collected_amt,
            'customerName': savings['customer_name'],
            'customerNameEn': savings['customer_name_en'],
            'customerCode': savings['customer_code'],
            'savingsId': f"#{savings_id}",
            'scheme': savings['scheme_name'],
            'schemeEn': savings['scheme_name_en'],
            'installmentsPaid': new_paid,
            'totalInstallments': tot_inst,
            'totalSaved': new_total,
            'paymentMode': payment_mode,
            'paymentModeEn': payment_mode_en
        }

        return jsonify({'success': True, 'receipt': receipt, 'cashInHand': updated_cash})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/savings/<savings_id>/payout', methods=['POST'])
def disburse_savings_payout(savings_id):
    try:
        user_id = get_current_user_id()
        data = request.json or {}
        payout_amt = float(data.get('payoutAmount', 10000))
        clean_id = str(savings_id).replace('#', '').strip()
        savings = query_db("SELECT * FROM savings WHERE id = %s OR id = %s;", (clean_id, f"#{clean_id}"), one=True)
        target_user_id = (savings.get('user_id') if savings else None) or user_id

        execute_db("UPDATE savings SET status = 'closed' WHERE id = %s;", (clean_id,))
        execute_db("UPDATE finance_metrics SET cash_in_hand = GREATEST(0.00, cash_in_hand - %s) WHERE user_id = %s;", (payout_amt, target_user_id))
        return jsonify({'success': True, 'message': 'Maturity payout disbursed successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# -------------------------------------------------------------
# 4. EMERGENCY RESERVED FUND ENDPOINTS (Scoped to User)
# -------------------------------------------------------------
@app.route('/api/reserved', methods=['GET'])
def get_reserved():
    try:
        user_id = get_current_user_id()
        metrics = ensure_user_metrics(user_id)
        reserved_balance = float(metrics.get('reserved_balance', 0.0))

        history = query_db("SELECT * FROM reserve_transactions WHERE user_id = %s ORDER BY created_at DESC;", (user_id,)) or []
        clean_history = [sanitize_record(h) for h in history]

        total_added = sum(float(h['amount']) for h in clean_history if h['type'] == 'add')
        total_reduced = sum(float(h['amount']) for h in clean_history if h['type'] == 'reduce')

        return jsonify({
            'success': True,
            'userId': user_id,
            'reservedBalance': reserved_balance,
            'totalAdded': total_added,
            'totalReduced': total_reduced,
            'history': clean_history
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/reserved/add', methods=['POST'])
def add_reserved():
    try:
        user_id = get_current_user_id()
        ensure_user_metrics(user_id)
        data = request.json or {}
        amt = float(data.get('amount', 5000))
        reason = data.get('reason', 'அவசரகால வணிக பாதுகாப்பு')
        reason_en = data.get('reasonEn', 'Emergency Business Safety Reserve')

        metrics = query_db("SELECT reserved_balance FROM finance_metrics WHERE user_id = %s;", (user_id,), one=True)
        current_bal = float(metrics['reserved_balance']) if metrics else 0.0
        new_bal = current_bal + amt

        txn_id = f"RES-TXN-{random.randint(100, 999)}"

        # 1. Update metrics: increase reserve only for user
        execute_db("""
            UPDATE finance_metrics 
            SET reserved_balance = reserved_balance + %s
            WHERE user_id = %s;
        """, (amt, user_id))

        # 2. Insert transaction
        execute_db("""
            INSERT INTO reserve_transactions (id, user_id, type, amount, reason, reason_en, balance_after, note, note_en)
            VALUES (%s, %s, 'add', %s, %s, %s, %s, 'பாதுகாப்பு நிதி சேர்க்கப்பட்டது', 'Added to reserve fund');
        """, (txn_id, user_id, amt, reason, reason_en, new_bal))

        return jsonify({'success': True, 'userId': user_id, 'newBalance': new_bal, 'message': 'Added to reserved fund successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/reserved/reduce', methods=['POST'])
def reduce_reserved():
    try:
        user_id = get_current_user_id()
        ensure_user_metrics(user_id)
        data = request.json or {}
        amt = float(data.get('amount', 5000))
        reason = data.get('reason', 'அவசர பணப்புழக்க தேவை')
        reason_en = data.get('reasonEn', 'Emergency Cash Flow Liquidity Need')

        metrics = query_db("SELECT reserved_balance FROM finance_metrics WHERE user_id = %s;", (user_id,), one=True)
        current_bal = float(metrics['reserved_balance']) if metrics else 0.0

        if amt > current_bal:
            return jsonify({'success': False, 'error': f'பாதுகாப்பு நிதி இருப்பு போதாது (Insufficient reserve balance: ₹{current_bal:,.2f})'}), 400

        new_bal = max(0.0, current_bal - amt)
        txn_id = f"RES-TXN-{random.randint(100, 999)}"

        execute_db("""
            UPDATE finance_metrics 
            SET reserved_balance = GREATEST(0.00, reserved_balance - %s)
            WHERE user_id = %s;
        """, (amt, user_id))

        execute_db("""
            INSERT INTO reserve_transactions (id, user_id, type, amount, reason, reason_en, balance_after, note, note_en)
            VALUES (%s, %s, 'reduce', %s, %s, %s, %s, 'திரும்பப் பெறப்பட்டது', 'Withdrawn from reserve');
        """, (txn_id, user_id, amt, reason, reason_en, new_bal))

        return jsonify({'success': True, 'userId': user_id, 'newBalance': new_bal, 'message': 'Reduced reserved fund successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# -------------------------------------------------------------
# 5. INVESTOR MANAGEMENT ENDPOINTS (Scoped to User)
# -------------------------------------------------------------
@app.route('/api/investors', methods=['GET'])
def get_investors():
    try:
        user_id = get_current_user_id()
        search = request.args.get('search', '').strip().lower()
        status = request.args.get('status', 'all')

        query = "SELECT * FROM investors WHERE user_id = %s"
        args = [user_id]
        if status and status != 'all':
            query += " AND status = %s"
            args.append(status)

        rows = query_db(query + " ORDER BY created_at DESC;", args) or []
        investors = [sanitize_record(r) for r in rows]

        for inv in investors:
            repayments = query_db("SELECT * FROM investor_repayments WHERE investor_id = %s ORDER BY created_at DESC;", (inv['id'],)) or []
            inv['history'] = [{
                'id': r['id'],
                'principalAmount': float(r['principal_amount']),
                'profitAmount': float(r['profit_amount']),
                'totalPaid': float(r['total_paid']),
                'mode': r['payment_mode'],
                'modeEn': r['payment_mode_en'],
                'date': r['receipt_date'],
                'dateEn': r['receipt_date_en'],
                'notes': r['notes']
            } for r in repayments]

        if search:
            investors = [
                i for i in investors if
                search in (i.get('name') or '').lower() or
                search in (i.get('name_en') or '').lower() or
                search in (i.get('phone') or '').lower() or
                search in (i.get('id') or '').lower()
            ]

        normalized = []
        for i in investors:
            normalized.append({
                'id': i['id'],
                'userId': i.get('user_id', user_id),
                'name': i['name'],
                'nameEn': i['name_en'],
                'phone': i['phone'],
                'investorType': i.get('investor_type') or 'external',
                'investedAmount': i['invested_amount'],
                'profitPercentage': i['profit_percentage'],
                'principalRepaid': i['principal_repaid'],
                'profitRepaid': i['profit_repaid'],
                'balanceAmount': i['balance_amount'],
                'investmentDate': i['investment_date'],
                'investmentDateEn': i['investment_date_en'],
                'notes': i['notes'],
                'status': i['status'],
                'history': i['history']
            })

        return jsonify({'success': True, 'investors': normalized})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/investors/<investor_id>', methods=['GET'])
def get_investor(investor_id):
    try:
        user_id = get_current_user_id()
        clean_id = str(investor_id).replace('#', '').strip()
        row = query_db("SELECT * FROM investors WHERE (id = %s OR id = %s OR id LIKE %s) AND user_id = %s;", 
                       (clean_id, f"#{clean_id}", f"%{clean_id}%", user_id), one=True)
        if not row:
            row = query_db("SELECT * FROM investors WHERE id = %s OR id = %s OR id LIKE %s;", (clean_id, f"#{clean_id}", f"%{clean_id}%"), one=True)
        if not row:
            return jsonify({'success': False, 'error': 'Investor not found'}), 404
        inv = sanitize_record(row)
        actual_id = inv['id']
        repayments = query_db("SELECT * FROM investor_repayments WHERE investor_id = %s ORDER BY created_at DESC;", (actual_id,)) or []
        inv['history'] = [{
            'id': r['id'],
            'principalAmount': float(r['principal_amount']),
            'profitAmount': float(r['profit_amount']),
            'totalPaid': float(r['total_paid']),
            'mode': r['payment_mode'],
            'modeEn': r['payment_mode_en'],
            'date': r['receipt_date'],
            'dateEn': r['receipt_date_en'],
            'notes': r['notes']
        } for r in repayments]
        return jsonify({'success': True, 'investor': inv})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/investors', methods=['POST'])
def create_investor():
    try:
        user_id = get_current_user_id()
        ensure_user_metrics(user_id)
        data = request.json or {}
        new_id = (data.get('id') or f"INV-{random.randint(100, 999)}").replace('#', '').strip()
        name = data.get('name', '')
        name_en = data.get('nameEn', name)
        phone = data.get('phone', '')
        investor_type = data.get('investorType', 'external') # 'self' (Owner/Me) or 'external' (Another Person)
        amount = float(data.get('investedAmount', 100000))
        rate = float(data.get('profitPercentage', 3.0))
        notes = data.get('notes', 'வணிக முதலீடு')
        now_ta = "இன்று"
        now_en = "Today"

        execute_db("""
            INSERT INTO investors (id, user_id, name, name_en, phone, investor_type, invested_amount, profit_percentage, principal_repaid, profit_repaid, balance_amount, investment_date, investment_date_en, notes, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0.00, 0.00, %s, %s, %s, %s, 'active');
        """, (new_id, user_id, name, name_en, phone, investor_type, amount, rate, amount, now_ta, now_en, notes))

        # Add investment capital to user's cash in hand
        execute_db("""
            UPDATE finance_metrics 
            SET cash_in_hand = cash_in_hand + %s 
            WHERE user_id = %s;
        """, (amount, user_id))

        return jsonify({'success': True, 'investorId': new_id, 'userId': user_id, 'investorType': investor_type, 'message': 'Investor added successfully'}), 201
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/investors/<investor_id>/repay', methods=['POST'])
def repay_investor(investor_id):
    try:
        user_id = get_current_user_id()
        data = request.json or {}
        principal_amt = float(data.get('principalAmount', 0.0))
        profit_amt = float(data.get('profitAmount', 0.0))
        payment_mode = data.get('paymentMode', 'ரொக்கம்')
        payment_mode_en = data.get('paymentModeEn', 'Cash')
        notes = data.get('notes', 'முதலீட்டாளர் திருப்பிச் செலுத்துதல்')

        if principal_amt <= 0 and profit_amt <= 0:
            return jsonify({'success': False, 'error': 'Either principal return or profit amount must be greater than zero'}), 400

        clean_id = str(investor_id).replace('#', '').strip()
        investor = query_db("SELECT * FROM investors WHERE (id = %s OR id = %s) AND user_id = %s;", (clean_id, f"#{clean_id}", user_id), one=True)
        if not investor:
            investor = query_db("SELECT * FROM investors WHERE id = %s OR id = %s OR id LIKE %s;", (clean_id, f"#{clean_id}", f"%{clean_id}%"), one=True)
        if not investor:
            return jsonify({'success': False, 'error': 'Investor not found'}), 404

        target_user_id = investor.get('user_id') or user_id
        ensure_user_metrics(target_user_id)

        current_balance = float(investor['balance_amount'])
        if principal_amt > current_balance:
            return jsonify({'success': False, 'error': f'Principal return exceeds outstanding investment balance (₹{current_balance})'}), 400

        total_paid = principal_amt + profit_amt

        # Check cash in hand of target user before paying investor!
        metrics = query_db("SELECT cash_in_hand FROM finance_metrics WHERE user_id = %s;", (target_user_id,), one=True)
        current_cash = float(metrics['cash_in_hand']) if metrics else 0.0
        if total_paid > current_cash:
            return jsonify({
                'success': False,
                'error': f'கையிருப்பு ரொக்கம் போதாது (Insufficient Cash in Hand: ₹{current_cash:,.2f}). முதலீட்டாளருக்கு பணம் செலுத்த முடியாது.'
            }), 400

        new_principal_repaid = float(investor['principal_repaid']) + principal_amt
        new_profit_repaid = float(investor['profit_repaid']) + profit_amt
        new_balance = max(0.0, float(investor['invested_amount']) - new_principal_repaid)
        new_status = 'settled' if new_balance == 0 else 'active'

        rec_id = f"INV-REC-{random.randint(1000, 9999)}"
        now_ta = "இன்று | " + datetime.now().strftime("%I:%M %p")
        now_en = "Today | " + datetime.now().strftime("%I:%M %p")

        actual_id = investor['id']

        # 1. Update investor
        execute_db("""
            UPDATE investors
            SET principal_repaid = %s, profit_repaid = %s, balance_amount = %s, status = %s
            WHERE id = %s;
        """, (new_principal_repaid, new_profit_repaid, new_balance, new_status, actual_id))

        # 2. Insert repayment record
        execute_db("""
            INSERT INTO investor_repayments (id, investor_id, principal_amount, profit_amount, total_paid, payment_mode, payment_mode_en, receipt_date, receipt_date_en, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """, (rec_id, actual_id, principal_amt, profit_amt, total_paid, payment_mode, payment_mode_en, now_ta, now_en, notes))

        # 3. Deduct total payout from cash in hand of user
        execute_db("""
            UPDATE finance_metrics 
            SET cash_in_hand = GREATEST(0.00, cash_in_hand - %s)
            WHERE user_id = %s;
        """, (total_paid, target_user_id))

        receipt = {
            'receiptNo': f"#{rec_id}",
            'date': now_ta,
            'dateEn': now_en,
            'investorId': f"#{investor_id}",
            'investorName': investor['name'],
            'investorNameEn': investor['name_en'] or investor['name'],
            'phone': investor['phone'],
            'principalAmount': principal_amt,
            'profitAmount': profit_amt,
            'totalPaid': total_paid,
            'previousBalance': current_balance,
            'newBalance': new_balance,
            'profitPercentage': float(investor['profit_percentage']),
            'paymentMode': payment_mode,
            'paymentModeEn': payment_mode_en,
            'notes': notes
        }

        return jsonify({'success': True, 'receipt': receipt, 'message': 'Investor repayment recorded successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# -------------------------------------------------------------
# 6. USER AUTHENTICATION ENDPOINTS (SIGNUP, LOGIN, STATUS APPROVAL)
# -------------------------------------------------------------
@app.route('/api/auth/signup', methods=['POST'])
def auth_signup():
    """
    Registers a new user account with Name, Mobile, Password, and Gender.
    Crucial Rule: By default is_active is set to FALSE (0).
    The user can only login once an admin sets is_active = TRUE (1) in database.
    """
    try:
        data = request.json or {}
        name = (data.get('name') or '').strip()
        mobile = (data.get('mobile') or '').strip().replace(' ', '').replace('-', '')
        password = data.get('password') or ''
        gender = (data.get('gender') or 'male').strip().lower()

        if not name or not mobile or not password:
            return jsonify({
                'success': False,
                'error': 'missing_fields',
                'message': 'பெயர், கைபேசி எண் மற்றும் கடவுச்சொல் கட்டாயமாகும்',
                'messageEn': 'Name, mobile number, and password are required'
            }), 400

        # Validate mobile length
        if len(mobile) < 10:
            return jsonify({
                'success': False,
                'error': 'invalid_mobile',
                'message': 'சரியான 10 இலக்க கைபேசி எண்ணை உள்ளிடவும்',
                'messageEn': 'Please enter a valid 10-digit mobile number'
            }), 400

        if len(password) < 4:
            return jsonify({
                'success': False,
                'error': 'weak_password',
                'message': 'கடவுச்சொல் குறைந்தது 4 எழுத்துக்கள் இருக்க வேண்டும்',
                'messageEn': 'Password must be at least 4 characters'
            }), 400

        # Check if mobile already exists
        existing = query_db("SELECT id, mobile FROM users WHERE mobile = %s;", (mobile,), one=True)
        if existing:
            return jsonify({
                'success': False,
                'error': 'mobile_exists',
                'message': 'இந்த கைபேசி எண் ஏற்கனவே பதிவு செய்யப்பட்டுள்ளது',
                'messageEn': 'This mobile number is already registered'
            }), 400

        # Generate unique user_id
        user_id = f"USR-{random.randint(1000, 9999)}"
        password_hash = generate_password_hash(password)

        execute_db("""
            INSERT INTO users (user_id, name, mobile, password_hash, gender, is_active)
            VALUES (%s, %s, %s, %s, %s, FALSE);
        """, (user_id, name, mobile, password_hash, gender))

        # Initialize finance metrics row for this new tenant
        ensure_user_metrics(user_id)

        return jsonify({
            'success': True,
            'userId': user_id,
            'name': name,
            'mobile': mobile,
            'gender': gender,
            'isActive': False,
            'message': 'கணக்கு வெற்றிகரமாக உருவாக்கப்பட்டது! நிர்வாகி அனுமதித்த பிறகு உள்நுழையலாம்.',
            'messageEn': 'Account created successfully! You can login once approved by admin in database.'
        }), 201

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    """
    Authenticates user with Mobile and Password.
    Strict Requirement: Checks is_active in MySQL database.
    If is_active is FALSE, returns HTTP 403 Forbidden with pending_approval error.
    """
    try:
        data = request.json or {}
        mobile = (data.get('mobile') or '').strip().replace(' ', '').replace('-', '')
        password = data.get('password') or ''

        if not mobile or not password:
            return jsonify({
                'success': False,
                'error': 'missing_credentials',
                'message': 'கைபேசி எண் மற்றும் கடவுச்சொல்லை உள்ளிடவும்',
                'messageEn': 'Please enter mobile number and password'
            }), 400

        user = query_db("""
            SELECT id, user_id, name, mobile, password_hash, gender, is_active 
            FROM users 
            WHERE mobile = %s;
        """, (mobile,), one=True)

        if not user or not check_password_hash(user['password_hash'], password):
            return jsonify({
                'success': False,
                'error': 'invalid_credentials',
                'message': 'தவறான கைபேசி எண் அல்லது கடவுச்சொல்',
                'messageEn': 'Invalid mobile number or password'
            }), 401

        # Check database is_active status
        is_active = bool(user['is_active'])
        if not is_active:
            return jsonify({
                'success': False,
                'error': 'pending_approval',
                'userId': user['user_id'],
                'name': user['name'],
                'mobile': user['mobile'],
                'isActive': False,
                'message': 'உங்கள் கணக்கு இன்னும் நிர்வாகியால் அங்கீகரிக்கப்படவில்லை. அனுமதி அளித்த பிறகு உள்நுழையலாம்.',
                'messageEn': 'Your account is pending admin approval. You can login once approved.'
            }), 403

        # Ensure metrics row exists for this user
        ensure_user_metrics(user['user_id'])

        # Login successful
        return jsonify({
            'success': True,
            'user': {
                'userId': user['user_id'],
                'name': user['name'],
                'mobile': user['mobile'],
                'gender': user['gender'],
                'isActive': True
            },
            'message': 'வெற்றிகரமாக உள்நுழைந்துள்ளீர்கள்!',
            'messageEn': 'Logged in successfully!'
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/auth/users', methods=['GET'])
def auth_list_users():
    """List all registered users and their active approval status."""
    try:
        rows = query_db("""
            SELECT user_id, name, mobile, gender, is_active, created_at 
            FROM users 
            ORDER BY created_at DESC;
        """) or []
        users = []
        for r in rows:
            users.append({
                'userId': r['user_id'],
                'name': r['name'],
                'mobile': r['mobile'],
                'gender': r['gender'],
                'isActive': bool(r['is_active']),
                'createdAt': str(r['created_at'])
            })
        return jsonify({'success': True, 'users': users})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/auth/users/<user_id>/status', methods=['POST'])
def auth_update_user_status(user_id):
    """Admin endpoint to toggle user approval status (true/false)."""
    try:
        data = request.json or {}
        new_status = bool(data.get('isActive', True))
        clean_id = user_id.replace('#', '').strip()

        user = query_db("SELECT id, user_id, name, mobile FROM users WHERE user_id = %s OR mobile = %s;", (clean_id, clean_id), one=True)
        if not user:
            return jsonify({'success': False, 'error': 'user_not_found', 'message': 'பயனர் கிடைக்கவில்லை'}), 404

        execute_db("UPDATE users SET is_active = %s WHERE id = %s;", (new_status, user['id']))

        return jsonify({
            'success': True,
            'userId': user['user_id'],
            'name': user['name'],
            'mobile': user['mobile'],
            'isActive': new_status,
            'message': f"பயனர் நிலை {'அங்கீகரிக்கப்பட்டது (Active)' if new_status else 'முடக்கப்பட்டது (Pending)'}"
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# -------------------------------------------------------------
# AUTO-INIT & RUN
# -------------------------------------------------------------
if __name__ == '__main__':
    print("=" * 60)
    print("🚀 Starting Stitch Tamil Finance Flask API...")
    print(f"📡 Port: {Config.PORT}")
    print(f"🗄️ Database: {Config.DB_USER}@{Config.DB_HOST}:{Config.DB_PORT}/{Config.DB_NAME}")
    print("=" * 60)
    
    # Initialize DB schema on boot
    init_db()
    
    app.run(host='0.0.0.0', port=Config.PORT, debug=False, use_reloader=False)
