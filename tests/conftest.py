import pytest
import sys
import os
import tempfile
import sqlite3
import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

sys.path.insert(0, '/workspace')

os.environ['FLASK_ENV'] = 'testing'
os.environ['TESTING'] = 'true'

with patch('flask.Flask.run'):
    import web_app as web_app_module
    
    web_app_module.app.config['TESTING'] = True
    web_app_module.app.config['WTF_CSRF_ENABLED'] = False
    web_app_module.app.config['SECRET_KEY'] = 'test-secret-key-for-testing'
    web_app_module.app.config['DEBUG'] = False
    
    test_app = web_app_module.app


@pytest.fixture(scope='session')
def app():
    """Create application for testing"""
    return test_app


@pytest.fixture(scope='session')
def _db():
    """Create database for testing"""
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    conn.execute('''
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

    conn.execute('''
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

    conn.execute('''
        CREATE TABLE IF NOT EXISTS password_resets (
            user_id TEXT PRIMARY KEY,
            reset_token_hash TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    conn.commit()
    conn.close()

    import auth
    original_db_path = auth.DB_PATH
    auth.DB_PATH = db_path

    yield db_path

    auth.DB_PATH = original_db_path
    os.unlink(db_path)


@pytest.fixture(scope='function')
def db(_db):
    """Reset database for each test"""
    conn = sqlite3.connect(_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("DELETE FROM user_sessions")
    cursor.execute("DELETE FROM password_resets")
    cursor.execute("DELETE FROM users")

    conn.commit()
    conn.close()

    yield _db


@pytest.fixture(scope='function')
def client(app):
    """Flask test client fixture"""
    return app.test_client()


@pytest.fixture(scope='function')
def app_context(app):
    """Flask application context fixture"""
    with app.app_context():
        yield


@pytest.fixture(scope='function')
def demo_user(db):
    """Create a demo user for testing"""
    import bcrypt
    from auth import auth_service

    user_id = str(uuid.uuid4())
    email = 'demo@example.com'
    password = 'DemoPassword123'
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    role = 'manager'

    conn = sqlite3.connect(db)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO users (user_id, email, password_hash, role, created_at, last_login, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, email, password_hash, role, datetime.now().isoformat(), None, True))

    conn.commit()
    conn.close()

    return {
        'user_id': user_id,
        'email': email,
        'password': password,
        'role': role
    }


@pytest.fixture(scope='function')
def auth_client(client, app, demo_user):
    """Authenticated test client with logged-in demo user"""
    from auth import auth_service

    token = auth_service.generate_token(demo_user['user_id'])
    session_id = auth_service.create_session(
        demo_user['user_id'],
        token,
        ip_address='127.0.0.1',
        user_agent='pytest-client'
    )

    client.set_cookie('session_id', session_id)
    client.set_cookie('auth_token', token)

    return client


@pytest.fixture(scope='function')
def mock_mcp_tool():
    """Mock MCP tool responses"""
    return patch('web_app.call_mcp_tool', return_value={'success': True, 'data': '{}'})


@pytest.fixture(scope='function')
def mock_database():
    """Mock database operations"""
    from contextlib import contextmanager
    
    @contextmanager
    def _mock():
        with patch('web_app._get_db_connection') as mock:
            mock_conn = MagicMock()
            mock_conn.row_factory = sqlite3.Row
            mock.cursor.return_value = mock_conn.cursor.return_value
            yield mock

    return _mock


@pytest.fixture(scope='function')
def sample_inventory():
    """Sample inventory data for testing"""
    return [
        {
            'sku': 'SKU-001',
            'product_name': 'Test Product 1',
            'platform': 'amazon',
            'current_stock': 50,
            'threshold': 10
        },
        {
            'sku': 'SKU-002',
            'product_name': 'Test Product 2',
            'platform': '1688',
            'current_stock': 5,
            'threshold': 15
        },
        {
            'sku': 'SKU-003',
            'product_name': 'Test Product 3',
            'platform': 'amazon',
            'current_stock': 8,
            'threshold': 20
        }
    ]


@pytest.fixture(scope='function')
def sample_orders():
    """Sample orders data for testing"""
    return [
        {
            'order_id': 'ORD-001',
            'purchase_date': datetime.now().isoformat(),
            'status': 'Shipped',
            'total_amount': 29.99,
            'currency': 'USD',
            'fulfillment_channel': 'FBA',
            'number_of_items': 1
        },
        {
            'order_id': 'ORD-002',
            'purchase_date': datetime.now().isoformat(),
            'status': 'Pending',
            'total_amount': 49.99,
            'currency': 'USD',
            'fulfillment_channel': 'FBM',
            'number_of_items': 2
        }
    ]


@pytest.fixture(scope='function')
def sample_reviews():
    """Sample reviews data for testing"""
    return [
        {
            'review_id': 'REV-001',
            'rating': 5,
            'reviewer': 'TestUser1',
            'product_name': 'Test Product 1',
            'review_text': 'Great product!',
            'review_date': datetime.now().isoformat(),
            'helpful_count': 10
        },
        {
            'review_id': 'REV-002',
            'rating': 2,
            'reviewer': 'TestUser2',
            'product_name': 'Test Product 1',
            'review_text': 'Poor quality',
            'review_date': datetime.now().isoformat(),
            'helpful_count': 3
        }
    ]


@pytest.fixture(scope='function')
def sample_competitors():
    """Sample competitor data for testing"""
    return [
        {
            'asin': 'ASIN001',
            'product_name': 'Competitor Product 1',
            'price': 24.99,
            'rating': 4.5,
            'seller': 'Competitor Seller',
            'reviews_count': 100
        },
        {
            'asin': 'ASIN002',
            'product_name': 'Competitor Product 2',
            'price': 19.99,
            'rating': 4.0,
            'seller': 'Another Seller',
            'reviews_count': 50
        }
    ]


@pytest.fixture
def sample_tasks():
    """Sample tasks data for testing"""
    return [
        {
            'task_id': 'TASK-001',
            'title': 'Test Task 1',
            'description': 'Test description 1',
            'status': 'pending',
            'priority': 'high',
            'due_date': (datetime.now() + timedelta(days=7)).isoformat(),
            'created_at': datetime.now().isoformat()
        },
        {
            'task_id': 'TASK-002',
            'title': 'Test Task 2',
            'description': 'Test description 2',
            'status': 'completed',
            'priority': 'low',
            'due_date': (datetime.now() + timedelta(days=14)).isoformat(),
            'created_at': datetime.now().isoformat()
        }
    ]


@pytest.fixture
def sample_notifications():
    """Sample notifications data for testing"""
    return [
        {
            'id': 'NOTIF-001',
            'type': 'low_stock',
            'message': 'Low stock alert for SKU-001',
            'severity': 'warning',
            'created_at': datetime.now().isoformat(),
            'read': False
        },
        {
            'id': 'NOTIF-002',
            'type': 'review_alert',
            'message': 'New negative review received',
            'severity': 'critical',
            'created_at': datetime.now().isoformat(),
            'read': True
        }
    ]


@pytest.fixture
def sample_analytics():
    """Sample analytics data for testing"""
    return {
        'total_revenue': 15000.00,
        'total_orders': 150,
        'average_order_value': 100.00,
        'top_products': [
            {'sku': 'SKU-001', 'revenue': 5000.00, 'units_sold': 100},
            {'sku': 'SKU-002', 'revenue': 3000.00, 'units_sold': 60}
        ],
        'inventory_turnover': 4.5,
        'low_stock_count': 5,
        'pending_orders': 12
    }
