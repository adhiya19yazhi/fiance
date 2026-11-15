import os
import pymysql
import pymysql.cursors
from fiance.config import Config

def get_server_connection():
    """Connects to MySQL server (without specific DB) to allow DB creation."""
    return pymysql.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )

def get_db_connection():
    """Connects to the specific tamil_finance_db database."""
    return pymysql.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )

def init_db():
    """Initializes the MySQL database and executes schema.sql."""
    try:
        # 1. Create database if not exists
        conn = get_server_connection()
        with conn.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{Config.DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        conn.close()

        # 2. Execute schema.sql inside tamil_finance_db
        db_conn = get_db_connection()
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
        if os.path.exists(schema_path):
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema_sql = f.read()
            
            # Split and execute individual statements
            with db_conn.cursor() as cursor:
                statements = [s.strip() for s in schema_sql.split(';') if s.strip()]
                for statement in statements:
                    lines = [l for l in statement.splitlines() if not l.strip().startswith('--')]
                    clean_sql = '\n'.join(lines).strip()
                    if clean_sql and not clean_sql.upper().startswith('CREATE DATABASE') and not clean_sql.upper().startswith('USE'):
                        cursor.execute(clean_sql)
        db_conn.close()
        print("✓ MySQL Database and Tables initialized successfully!")
        return True, "Initialized"
    except Exception as e:
        print(f"✗ DB Init Notice: {e}")
        return False, str(e)

def query_db(query, args=(), one=False):
    """Executes a SELECT query and returns list of dicts (or single dict)."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, args)
            rv = cursor.fetchall()
            return (rv[0] if rv else None) if one else rv
    finally:
        conn.close()

def execute_db(query, args=()):
    """Executes an INSERT, UPDATE, or DELETE query."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, args)
            return cursor.lastrowid
    finally:
        conn.close()

def check_db_health():
    """Returns True if MySQL is reachable and responsive."""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 as is_healthy;")
            row = cursor.fetchone()
        conn.close()
        return True, "MySQL Connected and Healthy"
    except Exception as e:
        return False, str(e)
