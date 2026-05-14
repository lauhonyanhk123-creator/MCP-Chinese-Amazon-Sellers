
"""
数据持久化模块 - 存储和管理产品数据
Data persistence module - Store and manage product data
"""
import json
import sqlite3
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).parent / "seller_data.db"


def init_db():
    """Initialize the database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Product profiles table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS product_profiles (
            sku TEXT PRIMARY KEY,
            product_name TEXT,
            cost_cny REAL,
            shipping_to_amazon_usd REAL,
            amazon_referral_fee_percent REAL,
            fba_fee_usd REAL,
            monthly_storage_fee_usd REAL,
            advertising_acos_percent REAL,
            payment_processing_fee_percent REAL,
            return_rate_percent REAL,
            customs_duty_percent REAL,
            overhead_percent REAL,
            last_updated TEXT,
            last_synced_from_1688 TEXT,
            notes TEXT
        )
    ''')

    # User settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')

    # Historical snapshots table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historical_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_date TEXT NOT NULL,
            snapshot_type TEXT NOT NULL,
            data TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_snapshot_type_date 
        ON historical_snapshots (snapshot_type, snapshot_date)
    ''')

    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'viewer',
            created_at TEXT NOT NULL,
            last_login TEXT,
            is_active INTEGER NOT NULL DEFAULT 1
        )
    ''')

    # User sessions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            token TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            ip_address TEXT,
            user_agent TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    # Password reset tokens table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS password_resets (
            user_id TEXT PRIMARY KEY,
            reset_token_hash TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_users_email 
        ON users (email)
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_sessions_user_id 
        ON user_sessions (user_id)
    ''')

    # Audit logs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_logs (
            log_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            action TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            resource_id TEXT,
            details TEXT,
            ip_address TEXT,
            user_agent TEXT,
            timestamp TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_audit_user_id
        ON audit_logs (user_id)
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_audit_timestamp
        ON audit_logs (timestamp)
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_audit_action
        ON audit_logs (action)
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_audit_resource
        ON audit_logs (resource_type, resource_id)
    ''')

    # API keys table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_keys (
            key_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            key_hash TEXT NOT NULL,
            name TEXT,
            created_at TEXT NOT NULL,
            last_used TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            rate_limit INTEGER NOT NULL DEFAULT 60,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_api_keys_user_id
        ON api_keys (user_id)
    ''')

    conn.commit()
    conn.close()


def save_product_profile(sku: str, **kwargs):
    """Save or update a product profile"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    kwargs["last_updated"] = datetime.now().isoformat()

    columns = ", ".join(kwargs.keys())
    placeholders = ", ".join(["?"] * len(kwargs))
    updates = ", ".join([f"{k} = ?" for k in kwargs])

    sql = f'''
        INSERT OR REPLACE INTO product_profiles (sku, {columns})
        VALUES (?, {placeholders})
    '''

    cursor.execute(sql, [sku] + list(kwargs.values()) + list(kwargs.values()))
    conn.commit()
    conn.close()


def get_product_profile(sku: str):
    """Get a product profile by SKU"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM product_profiles WHERE sku = ?', (sku,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return dict(row)
    return None


def get_all_product_profiles():
    """Get all product profiles"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM product_profiles ORDER BY last_updated DESC')
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def delete_product_profile(sku: str):
    """Delete a product profile"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM product_profiles WHERE sku = ?', (sku,))
    conn.commit()
    conn.close()


def get_stale_product_profiles(hours: int = 24):
    """Get product profiles that haven't been updated recently"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()

    cursor.execute(
        'SELECT * FROM product_profiles WHERE last_updated < ?',
        (cutoff,)
    )
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def save_user_setting(key: str, value):
    """Save a user setting"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT OR REPLACE INTO user_settings (key, value)
        VALUES (?, ?)
    ''', (key, json.dumps(value)))

    conn.commit()
    conn.close()


def get_user_setting(key: str, default=None):
    """Get a user setting"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT value FROM user_settings WHERE key = ?', (key,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return json.loads(row[0])
    return default


def is_data_fresh(sku: str, max_hours: int = 24) -> tuple[bool, timedelta]:
    """Check if product data is fresh"""
    profile = get_product_profile(sku)

    if not profile:
        return False, None

    last_updated = datetime.fromisoformat(profile["last_updated"])
    age = datetime.now() - last_updated

    return age < timedelta(hours=max_hours), age


# Historical Snapshot Methods

def save_snapshot(snapshot_type: str, data: Any) -> int:
    """Save a historical snapshot
    
    Args:
        snapshot_type: Type of snapshot ('inventory', 'orders', 'reviews', 'competitors')
        data: Data to store (will be JSON serialized)
    
    Returns:
        The ID of the inserted snapshot
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    snapshot_date = date.today().isoformat()
    created_at = datetime.now().isoformat()
    data_json = json.dumps(data)

    cursor.execute('''
        INSERT INTO historical_snapshots (snapshot_date, snapshot_type, data, created_at)
        VALUES (?, ?, ?, ?)
    ''', (snapshot_date, snapshot_type, data_json, created_at))

    snapshot_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return snapshot_id


def get_snapshots(
    snapshot_type: str,
    start_date: str | None = None,
    end_date: str | None = None
) -> list[dict[str, Any]]:
    """Get historical snapshots of a specific type within a date range
    
    Args:
        snapshot_type: Type of snapshot ('inventory', 'orders', 'reviews', 'competitors')
        start_date: Start date in ISO format (YYYY-MM-DD), defaults to 30 days ago
        end_date: End date in ISO format (YYYY-MM-DD), defaults to today
    
    Returns:
        List of snapshot dictionaries
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if end_date is None:
        end_date = date.today().isoformat()
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=30)).date().isoformat()

    cursor.execute('''
        SELECT id, snapshot_date, snapshot_type, data, created_at
        FROM historical_snapshots
        WHERE snapshot_type = ?
          AND snapshot_date >= ?
          AND snapshot_date <= ?
        ORDER BY snapshot_date DESC
    ''', (snapshot_type, start_date, end_date))

    rows = cursor.fetchall()
    conn.close()

    snapshots = []
    for row in rows:
        snapshot = {
            'id': row['id'],
            'snapshot_date': row['snapshot_date'],
            'snapshot_type': row['snapshot_type'],
            'data': json.loads(row['data']),
            'created_at': row['created_at']
        }
        snapshots.append(snapshot)

    return snapshots


def get_latest_snapshot(snapshot_type: str) -> dict[str, Any] | None:
    """Get the most recent snapshot of a specific type
    
    Args:
        snapshot_type: Type of snapshot ('inventory', 'orders', 'reviews', 'competitors')
    
    Returns:
        The latest snapshot dictionary or None if no snapshot exists
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, snapshot_date, snapshot_type, data, created_at
        FROM historical_snapshots
        WHERE snapshot_type = ?
        ORDER BY snapshot_date DESC, created_at DESC
        LIMIT 1
    ''', (snapshot_type,))

    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            'id': row['id'],
            'snapshot_date': row['snapshot_date'],
            'snapshot_type': row['snapshot_type'],
            'data': json.loads(row['data']),
            'created_at': row['created_at']
        }
    return None


def cleanup_old_snapshots(days_to_keep: int = 90) -> int:
    """Delete snapshots older than specified days
    
    Args:
        days_to_keep: Number of days of snapshots to retain (default: 90)
    
    Returns:
        Number of snapshots deleted
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).date().isoformat()

    cursor.execute('''
        DELETE FROM historical_snapshots
        WHERE snapshot_date < ?
    ''', (cutoff_date,))

    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()

    return deleted_count


def get_snapshot_dates(snapshot_type: str, days: int = 30) -> list[str]:
    """Get list of dates that have snapshots for a given type
    
    Args:
        snapshot_type: Type of snapshot
        days: Number of days to look back
    
    Returns:
        List of date strings
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    start_date = (datetime.now() - timedelta(days=days)).date().isoformat()
    end_date = date.today().isoformat()

    cursor.execute('''
        SELECT DISTINCT snapshot_date
        FROM historical_snapshots
        WHERE snapshot_type = ?
          AND snapshot_date >= ?
          AND snapshot_date <= ?
        ORDER BY snapshot_date
    ''', (snapshot_type, start_date, end_date))

    dates = [row[0] for row in cursor.fetchall()]
    conn.close()

    return dates


# Initialize the database when module is loaded
init_db()


# User Management Functions

def create_user(user_id: str, email: str, password_hash: str, role: str = "viewer",
                created_at: str | None = None) -> bool:
    """Create a new user"""
    if created_at is None:
        created_at = datetime.now().isoformat()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT INTO users (user_id, email, password_hash, role, created_at, last_login, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, email, password_hash, role, created_at, None, True))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False


def get_user_by_email(email: str) -> dict[str, Any] | None:
    """Get user by email"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        SELECT user_id, email, password_hash, role, created_at, last_login, is_active
        FROM users WHERE email = ?
    ''', (email,))

    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "user_id": row["user_id"],
            "email": row["email"],
            "password_hash": row["password_hash"],
            "role": row["role"],
            "created_at": row["created_at"],
            "last_login": row["last_login"],
            "is_active": bool(row["is_active"])
        }
    return None


def get_user_by_id(user_id: str) -> dict[str, Any] | None:
    """Get user by ID"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        SELECT user_id, email, password_hash, role, created_at, last_login, is_active
        FROM users WHERE user_id = ?
    ''', (user_id,))

    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "user_id": row["user_id"],
            "email": row["email"],
            "password_hash": row["password_hash"],
            "role": row["role"],
            "created_at": row["created_at"],
            "last_login": row["last_login"],
            "is_active": bool(row["is_active"])
        }
    return None


def get_all_users() -> list[dict[str, Any]]:
    """Get all users"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        SELECT user_id, email, role, created_at, last_login, is_active
        FROM users ORDER BY created_at DESC
    ''')

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "user_id": row["user_id"],
            "email": row["email"],
            "role": row["role"],
            "created_at": row["created_at"],
            "last_login": row["last_login"],
            "is_active": bool(row["is_active"])
        }
        for row in rows
    ]


def update_user_last_login(user_id: str) -> bool:
    """Update user's last login timestamp"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    last_login = datetime.now().isoformat()
    cursor.execute("UPDATE users SET last_login = ? WHERE user_id = ?", (last_login, user_id))
    updated = cursor.rowcount > 0

    conn.commit()
    conn.close()

    return updated


def update_user_active_status(user_id: str, is_active: bool) -> bool:
    """Update user's active status"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("UPDATE users SET is_active = ? WHERE user_id = ?", (is_active, user_id))
    updated = cursor.rowcount > 0

    conn.commit()
    conn.close()

    return updated


def delete_user(user_id: str) -> bool:
    """Delete a user and their sessions"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM user_sessions WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM password_resets WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM api_keys WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    deleted = cursor.rowcount > 0

    conn.commit()
    conn.close()

    return deleted


# API Key Management Functions

def generate_api_key() -> str:
    """Generate a secure random API key
    
    Returns:
        A secure random API key in format: csb_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
    """
    import secrets
    return f"csb_{secrets.token_urlsafe(32)}"


def create_api_key(user_id: str, name: str, rate_limit: int = 60) -> dict[str, Any] | None:
    """Create a new API key for a user
    
    Args:
        user_id: User ID
        name: Key description/name
        rate_limit: Requests per minute (default: 60)
    
    Returns:
        Dict with key_id and the actual API key (only returned once), or None if user not found
    """
    import bcrypt

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        conn.close()
        return None

    key_id = str(uuid.uuid4())
    raw_api_key = generate_api_key()
    key_hash = bcrypt.hashpw(raw_api_key.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    created_at = datetime.now().isoformat()

    cursor.execute('''
        INSERT INTO api_keys (key_id, user_id, key_hash, name, created_at, is_active, rate_limit)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (key_id, user_id, key_hash, name, created_at, True, rate_limit))

    conn.commit()
    conn.close()

    return {
        "key_id": key_id,
        "api_key": raw_api_key,
        "name": name,
        "rate_limit": rate_limit,
        "created_at": created_at
    }


def validate_api_key(api_key: str) -> dict[str, Any] | None:
    """Validate an API key and return user info
    
    Args:
        api_key: The API key to validate
    
    Returns:
        Dict with user_id and rate_limit if valid, None otherwise
    """
    import bcrypt

    if not api_key or not api_key.startswith('csb_'):
        return None

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        SELECT ak.key_id, ak.user_id, ak.key_hash, ak.name, ak.created_at, 
               ak.is_active, ak.rate_limit, u.email, u.role, u.is_active as user_active
        FROM api_keys ak
        JOIN users u ON ak.user_id = u.user_id
    ''')

    for row in cursor.fetchall():
        try:
            if bcrypt.checkpw(api_key.encode('utf-8'), row['key_hash'].encode('utf-8')):
                if row['is_active'] and row['user_active']:
                    cursor.execute('''
                        UPDATE api_keys SET last_used = ? WHERE key_id = ?
                    ''', (datetime.now().isoformat(), row['key_id']))
                    conn.commit()

                    conn.close()
                    return {
                        "user_id": row['user_id'],
                        "key_id": row['key_id'],
                        "email": row['email'],
                        "role": row['role'],
                        "rate_limit": row['rate_limit']
                    }
        except Exception:
            continue

    conn.close()
    return None


def revoke_api_key(key_id: str, user_id: str | None = None) -> bool:
    """Deactivate an API key
    
    Args:
        key_id: The key ID to revoke
        user_id: Optional user ID to ensure ownership
    
    Returns:
        True if revoked, False if not found or not authorized
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if user_id:
        cursor.execute('''
            UPDATE api_keys SET is_active = 0 
            WHERE key_id = ? AND user_id = ?
        ''', (key_id, user_id))
    else:
        cursor.execute('''
            UPDATE api_keys SET is_active = 0 
            WHERE key_id = ?
        ''', (key_id,))

    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()

    return updated


def get_user_api_keys(user_id: str) -> list[dict[str, Any]]:
    """List all API keys for a user
    
    Args:
        user_id: User ID
    
    Returns:
        List of API key info (without the actual key hash)
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        SELECT key_id, name, created_at, last_used, is_active, rate_limit
        FROM api_keys
        WHERE user_id = ?
        ORDER BY created_at DESC
    ''', (user_id,))

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "key_id": row['key_id'],
            "name": row['name'],
            "created_at": row['created_at'],
            "last_used": row['last_used'],
            "is_active": bool(row['is_active']),
            "rate_limit": row['rate_limit']
        }
        for row in rows
    ]

