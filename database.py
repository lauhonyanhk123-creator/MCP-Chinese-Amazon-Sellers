
"""
数据持久化模块 - 存储和管理产品数据
Data persistence module - Store and manage product data
"""
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path

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
    
    conn.commit()
    conn.close()


def save_product_profile(sku: str, **kwargs):
    """Save or update a product profile"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    kwargs["last_updated"] = datetime.now().isoformat()
    
    columns = ", ".join(kwargs.keys())
    placeholders = ", ".join(["?"] * len(kwargs))
    updates = ", ".join([f"{k} = ?" for k in kwargs.keys()])
    
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
        'SELECT * FROM product_profiles WHERE last_updated &lt; ?',
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


def is_data_fresh(sku: str, max_hours: int = 24) -&gt; tuple[bool, timedelta]:
    """Check if product data is fresh"""
    profile = get_product_profile(sku)
    
    if not profile:
        return False, None
    
    last_updated = datetime.fromisoformat(profile["last_updated"])
    age = datetime.now() - last_updated
    
    return age &lt; timedelta(hours=max_hours), age


# Initialize the database when module is loaded
init_db()

