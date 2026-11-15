from fiance.db import get_db_connection, query_db

def seed_data():
    """Seeds initial sample records if tables are empty."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Seed Finance Metrics
        metrics_count = query_db("SELECT COUNT(*) as cnt FROM finance_metrics;", one=True)['cnt']
        if metrics_count == 0:
            cursor.execute("""
                INSERT INTO finance_metrics (cash_in_hand, reserved_balance, today_collected, today_target)
                VALUES (84200.00, 35000.00, 11200.00, 14500.00);
            """)

        # 2. Seed Loans
        loan_count = query_db("SELECT COUNT(*) as cnt FROM loans;", one=True)['cnt']
        if loan_count == 0:
            cursor.execute("""
                INSERT INTO loans (id, customer_name, customer_name_en, customer_code, phone, address, address_en, total_amount, paid_amount, balance_amount, emi_amount, interest_rate, frequency, current_installment, total_installments, next_due_date, next_due_date_en, status)
                VALUES 
                ('LN-1042', 'மு. வீரபாண்டியன்', 'M. Veerapandian', 'VP-402', '+91 98421 70243', '12, தெற்கு மாசி வீதி, மதுரை தெற்கு', '12, South Masi Street, Madurai South', 10000.00, 4600.00, 5400.00, 500.00, 2.00, 'வாராந்திரம் (Weekly)', 6, 12, '07 நவம்பர் 2026', '07 Nov 2026', 'active'),
                ('LN-1043', 'சு. ஆனந்தன்', 'S. Anandan', 'AN-109', '+91 98432 11090', '45, நேதாஜி ரோடு, மளிகை கடை, மதுரை', '45, Netaji Road, Grocery Store, Madurai', 25000.00, 18000.00, 7000.00, 1000.00, 2.00, 'வாராந்திரம் (Weekly)', 18, 25, '05 நவம்பர் 2026', '05 Nov 2026', 'active'),
                ('LN-1045', 'க. சக்திவேல்', 'K. Sakthivel', 'SK-304', '+91 99441 55672', '88, காமராஜர் சாலை, மதுரை', '88, Kamarajar Salai, Madurai', 30000.00, 6000.00, 24000.00, 1500.00, 2.50, 'வாராந்திரம் (Weekly)', 4, 20, '25 அக்டோபர் 2026', '25 Oct 2026', 'pending'),
                ('LN-1039', 'செல்வி. மீனா', 'Ms. Meena', 'MN-512', '+91 97890 44321', '14, மேல வாசல், மதுரை', '14, Mela Vaasal, Madurai', 15000.00, 15000.00, 0.00, 750.00, 2.00, 'வாராந்திரம் (Weekly)', 20, 20, 'நிறைவுற்றது', 'Completed', 'completed');
            """)

            # Repayment history for LN-1042 & LN-1043
            cursor.execute("""
                INSERT INTO loan_repayments (id, loan_id, amount, payment_mode, payment_mode_en, receipt_date, receipt_date_en, officer, officer_en, previous_balance, new_balance, status)
                VALUES
                ('REC-2026-8842', 'LN-1042', 500.00, 'ரொக்கம்', 'Cash', '03 அக் 2026 | 04:30 PM', '03 Oct 2026 | 04:30 PM', 'கள அலுவலர் #4', 'Field Officer #4', 5900.00, 5400.00, 'completed'),
                ('REC-2026-8810', 'LN-1042', 500.00, 'GPay', 'GPay', '26 செப் 2026 | 11:15 AM', '26 Sep 2026 | 11:15 AM', 'கள அலுவலர் #4', 'Field Officer #4', 6400.00, 5900.00, 'completed'),
                ('REC-2026-8835', 'LN-1043', 1000.00, 'ரொக்கம்', 'Cash', '28 அக் 2026 | 10:20 AM', '28 Oct 2026 | 10:20 AM', 'கள அலுவலர் #4', 'Field Officer #4', 8000.00, 7000.00, 'completed');
            """)

        # 3. Seed Savings
        savings_count = query_db("SELECT COUNT(*) as cnt FROM savings;", one=True)['cnt']
        if savings_count == 0:
            cursor.execute("""
                INSERT INTO savings (id, customer_name, customer_name_en, customer_code, phone, address, address_en, scheme_name, scheme_name_en, daily_amount, paid_installments, total_installments, total_saved, target_amount, payout_amount, bonus_amount, start_date, start_date_en, status)
                VALUES
                ('SV-104', 'திருமதி. லதா மகேந்திரன்', 'Mrs. Latha Mahendran', 'CUST-104', '+91 98421 70243', '12, தெற்கு மாசி வீதி, மதுரை தெற்கு', '12, South Masi Street, Madurai South', 'தினசரி சேமிப்பு திட்டம் (Daily Savings)', 'Daily Savings Scheme (105 Days)', 100.00, 82, 105, 8200.00, 10500.00, 10000.00, 500.00, '15 ஜனவரி 2025', '15 Jan 2025', 'active'),
                ('SV-102', 'சு. ஆனந்தன் (மளிகை கடை)', 'S. Anandan (Grocery)', 'CUST-109', '+91 98432 11090', '45, நேதாஜி ரோடு, மளிகை கடை, மதுரை', '45, Netaji Road, Grocery Store, Madurai', 'தினசரி சேமிப்பு திட்டம் (105 நாட்கள்)', 'Daily Savings Scheme (105 Days)', 100.00, 105, 105, 10500.00, 10500.00, 10000.00, 500.00, '01 நவம்பர் 2024', '01 Nov 2024', 'matured'),
                ('SV-105', 'செல்வி. மீனா', 'Ms. Meena', 'CUST-112', '+91 97890 44321', '14, மேல வாசல், மதுரை', '14, Mela Vaasal, Madurai', 'தினசரி சேமிப்பு திட்டம் (₹200 திட்டம்)', 'Daily ₹200 Savings Scheme', 200.00, 45, 100, 9000.00, 20000.00, 19000.00, 1000.00, '10 ஜூன் 2026', '10 Jun 2026', 'active');
            """)

            cursor.execute("""
                INSERT INTO savings_installments (id, savings_id, installments_count, amount, payment_mode, payment_mode_en, receipt_date, receipt_date_en, running_balance)
                VALUES
                ('SAV-REC-8291', 'SV-104', 1, 100.00, 'ரொக்கம்', 'Cash', '30 அக் 2026', '30 Oct 2026', 8200.00),
                ('SAV-REC-8280', 'SV-104', 1, 100.00, 'ரொக்கம்', 'Cash', '29 அக் 2026', '29 Oct 2026', 8100.00);
            """)

        # 4. Seed Reserve Transactions
        reserve_count = query_db("SELECT COUNT(*) as cnt FROM reserve_transactions;", one=True)['cnt']
        if reserve_count == 0:
            cursor.execute("""
                INSERT INTO reserve_transactions (id, type, amount, reason, reason_en, balance_after, note, note_en)
                VALUES
                ('RES-TXN-006', 'add', 10000.00, 'காலாண்டு உபரி லாபம் ஒதுக்கீடு', 'Quarterly Surplus Profit Allocation', 35000.00, 'Q3 லாபத்தில் இருந்து பாதுகாப்பு நிதிக்கு ஒதுக்கப்பட்டது', 'Transferred from Q3 profit to security reserve'),
                ('RES-TXN-005', 'reduce', 5000.00, 'அவசர பணப்புழக்க தேவை', 'Emergency Cash Flow Liquidity Need', 25000.00, 'தீபாவளி பண்டிகை கடன் விநியோகத்திற்காக தற்காலிக மாற்றம்', 'Temporary transfer for festival loan capital'),
                ('RES-TXN-004', 'add', 15000.00, 'அவசரகால வணிக பாதுகாப்பு', 'Emergency Business Safety Reserve', 30000.00, 'அவசரகால பாதுகாப்பு நிதி உயர்வு', 'Increase in emergency reserve buffer');
            """)

        # 5. Seed Investors & Repayments
        investor_count = query_db("SELECT COUNT(*) as cnt FROM investors;", one=True)['cnt']
        if investor_count == 0:
            cursor.execute("""
                INSERT INTO investors (id, name, name_en, phone, invested_amount, profit_percentage, principal_repaid, profit_repaid, balance_amount, investment_date, investment_date_en, notes, status)
                VALUES
                ('INV-101', 'ஆர். ராமலிங்கம்', 'R. Ramalingam', '+91 98410 23456', 200000.00, 2.50, 50000.00, 15000.00, 150000.00, '10 ஜனவரி 2026', '10 Jan 2026', 'வணிக விரிவாக்க மூலதன முதலீடு', 'active'),
                ('INV-102', 'மு. சுப்பிரமணியன்', 'M. Subramanian', '+91 98425 67890', 150000.00, 3.00, 0.00, 9000.00, 150000.00, '01 பிப்ரவரி 2026', '01 Feb 2026', 'ஆண்டு முதலீட்டு ஒப்பந்தம்', 'active'),
                ('INV-103', 'ப. ஜெயலட்சுமி', 'P. Jayalakshmi', '+91 97891 34567', 100000.00, 2.00, 100000.00, 12000.00, 0.00, '15 நவம்பர் 2025', '15 Nov 2025', 'முழுமையாக தீர்க்கப்பட்ட முதலீடு', 'settled');
            """)

            cursor.execute("""
                INSERT INTO investor_repayments (id, investor_id, principal_amount, profit_amount, total_paid, payment_mode, payment_mode_en, receipt_date, receipt_date_en, notes)
                VALUES
                ('INV-REC-901', 'INV-101', 50000.00, 5000.00, 55000.00, 'வங்கி பரிமாற்றம்', 'Bank', '15 ஏப்ரல் 2026', '15 Apr 2026', 'முதன்மை பகுதி திரும்ப மற்றும் மாதாந்திர லாபம்'),
                ('INV-REC-892', 'INV-101', 0.00, 5000.00, 5000.00, 'GPay', 'GPay', '15 மார்ச் 2026', '15 Mar 2026', 'மார்ச் மாத லாபப் பங்கு'),
                ('INV-REC-880', 'INV-102', 0.00, 4500.00, 4500.00, 'வங்கி பரிமாற்றம்', 'Bank', '01 ஏப்ரல் 2026', '01 Apr 2026', 'ஏப்ரல் மாத லாபப் பங்கு');
            """)

        conn.close()
        print("✓ Initial sample data seeded into MySQL successfully!")
        return True
    except Exception as e:
        print(f"✗ Seed Notice: {e}")
        return False

if __name__ == '__main__':
    from fiance.db import init_db
    init_db()
    seed_data()
