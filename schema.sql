-- Stitch Tamil Finance MySQL Schema
-- Character Set: utf8mb4 for full Tamil unicode support

CREATE DATABASE IF NOT EXISTS tamil_finance_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE tamil_finance_db;

-- 1. LOANS TABLE
CREATE TABLE IF NOT EXISTS loans (
    id VARCHAR(32) PRIMARY KEY,
    user_id VARCHAR(32) NOT NULL,
    customer_name VARCHAR(128) NOT NULL,
    customer_name_en VARCHAR(128),
    customer_code VARCHAR(64),
    phone VARCHAR(32) NOT NULL,
    address TEXT,
    address_en TEXT,
    total_amount DECIMAL(12, 2) NOT NULL,
    paid_amount DECIMAL(12, 2) DEFAULT 0.00,
    balance_amount DECIMAL(12, 2) NOT NULL,
    emi_amount DECIMAL(12, 2) NOT NULL,
    taken_amount DECIMAL(12, 2) DEFAULT 0.00,
    disbursed_amount DECIMAL(12, 2) DEFAULT 0.00,
    interest_rate DECIMAL(5, 2) DEFAULT 2.00,
    frequency VARCHAR(64) DEFAULT 'வாராந்திரம் (Weekly)',
    current_installment INT DEFAULT 0,
    total_installments INT DEFAULT 12,
    next_due_date VARCHAR(64),
    next_due_date_en VARCHAR(64),
    status VARCHAR(32) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. LOAN REPAYMENTS TABLE
CREATE TABLE IF NOT EXISTS loan_repayments (
    id VARCHAR(32) PRIMARY KEY,
    loan_id VARCHAR(32) NOT NULL,
    amount DECIMAL(12, 2) NOT NULL,
    payment_mode VARCHAR(64) DEFAULT 'ரொக்கம்',
    payment_mode_en VARCHAR(64) DEFAULT 'Cash',
    receipt_date VARCHAR(64) NOT NULL,
    receipt_date_en VARCHAR(64),
    officer VARCHAR(64) DEFAULT 'கள அலுவலர் #4',
    officer_en VARCHAR(64) DEFAULT 'Field Officer #4',
    previous_balance DECIMAL(12, 2) NOT NULL,
    new_balance DECIMAL(12, 2) NOT NULL,
    status VARCHAR(32) DEFAULT 'completed',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (loan_id) REFERENCES loans(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. SAVINGS ACCOUNTS TABLE
CREATE TABLE IF NOT EXISTS savings (
    id VARCHAR(32) PRIMARY KEY,
    user_id VARCHAR(32) NOT NULL,
    customer_name VARCHAR(128) NOT NULL,
    customer_name_en VARCHAR(128),
    customer_code VARCHAR(64),
    phone VARCHAR(32) NOT NULL,
    address TEXT,
    address_en TEXT,
    scheme_name VARCHAR(128) NOT NULL,
    scheme_name_en VARCHAR(128),
    daily_amount DECIMAL(12, 2) NOT NULL,
    paid_installments INT DEFAULT 0,
    total_installments INT DEFAULT 105,
    total_saved DECIMAL(12, 2) DEFAULT 0.00,
    target_amount DECIMAL(12, 2) NOT NULL,
    payout_amount DECIMAL(12, 2) NOT NULL,
    bonus_amount DECIMAL(12, 2) DEFAULT 0.00,
    start_date VARCHAR(64),
    start_date_en VARCHAR(64),
    status VARCHAR(32) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. SAVINGS INSTALLMENTS TABLE
CREATE TABLE IF NOT EXISTS savings_installments (
    id VARCHAR(32) PRIMARY KEY,
    savings_id VARCHAR(32) NOT NULL,
    installments_count INT DEFAULT 1,
    amount DECIMAL(12, 2) NOT NULL,
    payment_mode VARCHAR(64) DEFAULT 'ரொக்கம்',
    payment_mode_en VARCHAR(64) DEFAULT 'Cash',
    receipt_date VARCHAR(64) NOT NULL,
    receipt_date_en VARCHAR(64),
    running_balance DECIMAL(12, 2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (savings_id) REFERENCES savings(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. EMERGENCY RESERVE TRANSACTIONS TABLE
CREATE TABLE IF NOT EXISTS reserve_transactions (
    id VARCHAR(32) PRIMARY KEY,
    user_id VARCHAR(32) NOT NULL,
    type VARCHAR(16) NOT NULL, -- 'add' or 'reduce'
    amount DECIMAL(12, 2) NOT NULL,
    reason VARCHAR(255) NOT NULL,
    reason_en VARCHAR(255),
    balance_after DECIMAL(12, 2) NOT NULL,
    note TEXT,
    note_en TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 6. FINANCE METRICS TABLE (Cash in Hand, Reserves, Daily Targets per User)
CREATE TABLE IF NOT EXISTS finance_metrics (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id VARCHAR(32) UNIQUE NOT NULL,
    cash_in_hand DECIMAL(14, 2) DEFAULT 0.00,
    reserved_balance DECIMAL(14, 2) DEFAULT 0.00,
    today_collected DECIMAL(12, 2) DEFAULT 0.00,
    today_target DECIMAL(12, 2) DEFAULT 0.00,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 7. INVESTORS TABLE
CREATE TABLE IF NOT EXISTS investors (
    id VARCHAR(32) PRIMARY KEY,
    user_id VARCHAR(32) NOT NULL,
    name VARCHAR(128) NOT NULL,
    name_en VARCHAR(128),
    phone VARCHAR(32) NOT NULL,
    investor_type VARCHAR(32) DEFAULT 'external', -- 'self' (Owner/Me) or 'external' (Another Person)
    invested_amount DECIMAL(12, 2) NOT NULL,
    profit_percentage DECIMAL(5, 2) DEFAULT 3.00,
    principal_repaid DECIMAL(12, 2) DEFAULT 0.00,
    profit_repaid DECIMAL(12, 2) DEFAULT 0.00,
    balance_amount DECIMAL(12, 2) NOT NULL,
    investment_date VARCHAR(64),
    investment_date_en VARCHAR(64),
    notes TEXT,
    status VARCHAR(32) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 8. INVESTOR REPAYMENTS TABLE (Manual Principal Return + Profit Return)
CREATE TABLE IF NOT EXISTS investor_repayments (
    id VARCHAR(32) PRIMARY KEY,
    investor_id VARCHAR(32) NOT NULL,
    principal_amount DECIMAL(12, 2) NOT NULL,
    profit_amount DECIMAL(12, 2) NOT NULL,
    total_paid DECIMAL(12, 2) NOT NULL,
    payment_mode VARCHAR(64) DEFAULT 'ரொக்கம்',
    payment_mode_en VARCHAR(64) DEFAULT 'Cash',
    receipt_date VARCHAR(64) NOT NULL,
    receipt_date_en VARCHAR(64),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (investor_id) REFERENCES investors(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 9. USERS AUTHENTICATION TABLE
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(32) UNIQUE NOT NULL,
    name VARCHAR(128) NOT NULL,
    mobile VARCHAR(20) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    gender VARCHAR(20) NOT NULL, -- 'male', 'female', 'other'
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

