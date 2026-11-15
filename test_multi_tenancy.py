import json
import urllib.request
import urllib.error

BASE_URL = 'http://127.0.0.1:5000'

def api_call(path, method='GET', data=None, user_id=None):
    url = f"{BASE_URL}{path}"
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    if user_id:
        headers['X-User-Id'] = user_id

    req_data = json.dumps(data).encode('utf-8') if data else None
    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as res:
            return res.status, json.loads(res.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8')
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {'error': body}

def run_tests():
    print("=== MULTI-TENANCY & DATA ISOLATION TEST ===")
    
    # Test 1: User 1 (USR-1691)
    status, u1_sum = api_call('/api/dashboard/summary', user_id='USR-1691')
    assert status == 200, f"User 1 summary failed: {u1_sum}"
    print(f"✓ User 1 (USR-1691) - Cash: ₹{u1_sum['cashInHand']}, Reserve: ₹{u1_sum['reservedBalance']}")

    # Test 2: User 2 (USR-5421)
    status, u2_sum = api_call('/api/dashboard/summary', user_id='USR-5421')
    assert status == 200, f"User 2 summary failed: {u2_sum}"
    print(f"✓ User 2 (USR-5421) Initial - Cash: ₹{u2_sum['cashInHand']}, Loans: {u2_sum['totalLoansCount']}, Savings: {u2_sum['totalSavingsCount']}")
    assert u2_sum['cashInHand'] == 0.0, f"Expected 0 cash for User 2, got {u2_sum['cashInHand']}"
    assert u2_sum['totalLoansCount'] == 0, f"Expected 0 loans for User 2, got {u2_sum['totalLoansCount']}"

    # Test 3: User 2 adds investment (₹50,000)
    status, inv_res = api_call('/api/investors', method='POST', data={
        'name': 'சுரேஷ் குமார்',
        'nameEn': 'Suresh Kumar',
        'phone': '9841011111',
        'investorType': 'external',
        'investedAmount': 50000,
        'profitPercentage': 3.0,
        'notes': 'User 2 private investor'
    }, user_id='USR-5421')
    assert status == 201, f"User 2 investor creation failed: {inv_res}"
    print(f"✓ User 2 added ₹50,000 investment. Investor ID: {inv_res['investorId']}")

    # Test 4: Verify User 2 cash in hand is now ₹50,000
    status, u2_sum2 = api_call('/api/dashboard/summary', user_id='USR-5421')
    assert u2_sum2['cashInHand'] == 50000.0, f"Expected ₹50,000 cash for User 2, got {u2_sum2['cashInHand']}"
    print(f"✓ User 2 Cash in Hand updated to ₹{u2_sum2['cashInHand']}")

    # Test 5: Verify User 1 did NOT receive User 2's ₹50,000!
    status, u1_sum2 = api_call('/api/dashboard/summary', user_id='USR-1691')
    assert u1_sum2['cashInHand'] == u1_sum['cashInHand'], f"User 1 cash leaked! Was {u1_sum['cashInHand']}, now {u1_sum2['cashInHand']}"
    status, u1_invs = api_call('/api/investors', user_id='USR-1691')
    for inv in u1_invs.get('investors', []):
        assert inv['name'] != 'சுரேஷ் குமார்', "Data leakage! User 1 sees User 2 investor!"
    print("✓ Confirmed: User 1 did NOT receive User 2's investment! Total isolation maintained.")

    # Test 6: User 2 creates a loan (disbursed ₹8,000, taken ₹2,000 from ₹10,000 total)
    status, loan_res = api_call('/api/loans', method='POST', data={
        'customerName': 'ராமு செட்டியார்',
        'customerNameEn': 'Ramu Chettiar',
        'phone': '9841022222',
        'totalAmount': 10000,
        'takenAmount': 2000,
        'disbursedAmount': 8000,
        'emiAmount': 1000,
        'tenureWeeks': 10
    }, user_id='USR-5421')
    assert status == 201, f"User 2 loan creation failed: {loan_res}"
    print(f"✓ User 2 created loan: {loan_res['loanId']}, Disbursed: ₹{loan_res['disbursedAmount']}")

    # Test 7: Verify User 2 cash in hand is 50000 - 8000 = 42000
    status, u2_sum3 = api_call('/api/dashboard/summary', user_id='USR-5421')
    assert u2_sum3['cashInHand'] == 42000.0, f"Expected ₹42,000 for User 2, got {u2_sum3['cashInHand']}"
    assert u2_sum3['totalLoansCount'] == 1, f"Expected 1 loan for User 2, got {u2_sum3['totalLoansCount']}"
    print(f"✓ User 2 Cash: ₹{u2_sum3['cashInHand']}, Loans: {u2_sum3['totalLoansCount']}")

    # Test 8: Verify User 1 sees 0 of User 2's loans
    status, u1_loans = api_call('/api/loans', user_id='USR-1691')
    for l in u1_loans.get('loans', []):
        assert l['customerName'] != 'ராமு செட்டியார்', "Data leakage! User 1 sees User 2 loan!"
    print("✓ Confirmed: User 1 has ZERO visibility into User 2's loans!")

    # Test 9: Complete Signup -> Pending Approval -> Activation -> Login flow
    mobile_test = '9876543210'
    status, signup_res = api_call('/api/auth/signup', method='POST', data={
        'name': 'கார்த்திக் ராஜா',
        'mobile': mobile_test,
        'password': 'password123',
        'gender': 'male'
    })
    if status == 201:
        u3_id = signup_res['userId']
        print(f"✓ User 3 Signup success: {u3_id}, isActive: {signup_res['isActive']}")
    else:
        # Already created
        users = api_call('/api/auth/users')[1]['users']
        u3_id = [u['userId'] for u in users if u['mobile'] == mobile_test][0]
        # set inactive
        api_call(f'/api/auth/users/{u3_id}/status', method='POST', data={'isActive': False})
        print(f"✓ Using existing User 3: {u3_id}")

    # Test 10: User 3 Login before activation must fail with 403 pending_approval
    status, login_fail = api_call('/api/auth/login', method='POST', data={
        'mobile': mobile_test,
        'password': 'password123'
    })
    assert status == 403, f"Expected 403 for unapproved user, got {status}: {login_fail}"
    assert login_fail['error'] == 'pending_approval'
    print("✓ Login before admin activation correctly BLOCKED with 403 'pending_approval'!")

    # Test 11: Admin activates User 3
    status, act_res = api_call(f'/api/auth/users/{u3_id}/status', method='POST', data={'isActive': True})
    assert status == 200 and act_res['isActive'] is True
    print(f"✓ Admin activated User 3: {u3_id}")

    # Test 12: User 3 Login now succeeds with 200
    status, login_ok = api_call('/api/auth/login', method='POST', data={
        'mobile': mobile_test,
        'password': 'password123'
    })
    assert status == 200 and login_ok['success'] is True
    print(f"✓ User 3 Login succeeded after admin activation! User: {login_ok['user']['name']}")

    # Test 13: User 3 summary starts completely clean at 0
    status, u3_sum = api_call('/api/dashboard/summary', user_id=u3_id)
    assert u3_sum['cashInHand'] == 0.0
    assert u3_sum['totalLoansCount'] == 0
    assert u3_sum['totalSavingsCount'] == 0
    assert u3_sum['totalInvestorsCount'] == 0
    print(f"✓ User 3 Fresh Dashboard verified: Cash: ₹{u3_sum['cashInHand']}, 0 Loans, 0 Savings, 0 Investors!")

    print("\n🎉 ALL MULTI-TENANT ISOLATION TESTS PASSED WITH 100% SUCCESS!")

if __name__ == '__main__':
    run_tests()
