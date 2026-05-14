"""
Authentication Module - JWT-based user authentication
认证模块 - 基于JWT的用户认证
"""
import hashlib
import json
import os
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import wraps
from typing import Any

import bcrypt
import jwt
from flask import g, jsonify, request

DB_PATH = "/workspace/seller_data.db"
import database

SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
ALGORITHM = "HS256"
TOKEN_EXPIRATION_HOURS = 24

PERMISSION_HIERARCHY = {
    'admin': ['admin', 'manager', 'viewer'],
    'manager': ['manager', 'viewer'],
    'viewer': ['viewer']
}

PERMISSIONS = {
    'view_dashboard': ['admin', 'manager', 'viewer'],
    'view_inventory': ['admin', 'manager', 'viewer'],
    'edit_inventory': ['admin', 'manager'],
    'view_orders': ['admin', 'manager', 'viewer'],
    'edit_orders': ['admin', 'manager'],
    'view_analytics': ['admin', 'manager', 'viewer'],
    'export_data': ['admin', 'manager'],
    'manage_users': ['admin'],
    'manage_settings': ['admin'],
    'manage_schedules': ['admin', 'manager'],
    'view_reviews': ['admin', 'manager', 'viewer'],
    'respond_reviews': ['admin', 'manager'],
    'manage_notifications': ['admin', 'manager', 'viewer'],
}


@dataclass
class User:
    """User model"""
    user_id: str
    email: str
    password_hash: str
    role: str
    created_at: str
    last_login: str | None
    is_active: bool


@dataclass
class UserSession:
    """User session model"""
    session_id: str
    user_id: str
    token: str
    created_at: str
    expires_at: str
    ip_address: str | None
    user_agent: str | None


class AuthManager:
    """Authentication manager with JWT support"""

    def __init__(self, secret_key: str = SECRET_KEY):
        self.secret_key = secret_key
        self.algorithm = ALGORITHM
        self.token_expiration = TOKEN_EXPIRATION_HOURS

    def _get_db_connection(self):
        """Get database connection"""
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def register_user(self, email: str, password: str, role: str = "viewer") -> dict[str, Any]:
        """Register a new user
        
        Args:
            email: User email (unique)
            password: Plain text password
            role: User role (admin/manager/viewer)
        
        Returns:
            Dict with success status and user_id or error message
        """

        email = email.strip().lower()

        if role not in ["admin", "manager", "viewer"]:
            return {"success": False, "error": "Invalid role"}

        if len(password) < 8:
            return {"success": False, "error": "Password must be at least 8 characters"}

        conn = self._get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT user_id FROM users WHERE email = ?", (email,))
        if cursor.fetchone():
            conn.close()
            return {"success": False, "error": "Email already registered"}

        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        user_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()

        cursor.execute('''
            INSERT INTO users (user_id, email, password_hash, role, created_at, last_login, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, email, password_hash, role, created_at, None, True))

        conn.commit()
        conn.close()

        return {"success": True, "user_id": user_id, "email": email, "role": role}

    def authenticate_user(self, email: str, password: str) -> dict[str, Any] | None:
        """Authenticate user with email and password
        
        Args:
            email: User email
            password: Plain text password
        
        Returns:
            User dict if authenticated, None otherwise
        """
        email = email.strip().lower()

        conn = self._get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT user_id, email, password_hash, role, created_at, last_login, is_active
            FROM users WHERE email = ?
        ''', (email,))

        row = cursor.fetchone()

        if not row:
            conn.close()
            return None

        user = {
            "user_id": row["user_id"],
            "email": row["email"],
            "password_hash": row["password_hash"],
            "role": row["role"],
            "created_at": row["created_at"],
            "last_login": row["last_login"],
            "is_active": bool(row["is_active"])
        }

        if not bcrypt.checkpw(password.encode('utf-8'), user["password_hash"].encode('utf-8')):
            conn.close()
            return None

        if not user["is_active"]:
            conn.close()
            return None

        last_login = datetime.now().isoformat()
        cursor.execute("UPDATE users SET last_login = ? WHERE user_id = ?", (last_login, user["user_id"]))
        conn.commit()
        conn.close()

        return user

    def generate_token(self, user_id: str, remember_me: bool = False) -> str:
        """Generate JWT token for user
        
        Args:
            user_id: User ID
            remember_me: If True, extend expiration to 30 days
        
        Returns:
            JWT token string
        """
        expiration_hours = 720 if remember_me else self.token_expiration

        payload = {
            "user_id": user_id,
            "exp": datetime.utcnow() + timedelta(hours=expiration_hours),
            "iat": datetime.utcnow(),
            "jti": str(uuid.uuid4())
        }

        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return token

    def verify_token(self, token: str) -> dict[str, Any] | None:
        """Verify and decode JWT token
        
        Args:
            token: JWT token string
        
        Returns:
            Decoded payload dict if valid, None otherwise
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    def create_session(self, user_id: str, token: str, ip_address: str | None = None,
                      user_agent: str | None = None) -> str:
        """Create a user session
        
        Args:
            user_id: User ID
            token: JWT token
            ip_address: Client IP address
            user_agent: Client user agent
        
        Returns:
            Session ID
        """
        session_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        expires_at = (datetime.utcnow() + timedelta(hours=self.token_expiration)).isoformat()

        conn = self._get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO user_sessions (session_id, user_id, token, created_at, expires_at, ip_address, user_agent)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (session_id, user_id, token, created_at, expires_at, ip_address, user_agent))

        conn.commit()
        conn.close()

        return session_id

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Get session by ID
        
        Args:
            session_id: Session ID
        
        Returns:
            Session dict or None
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT session_id, user_id, token, created_at, expires_at, ip_address, user_agent
            FROM user_sessions WHERE session_id = ?
        ''', (session_id,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return {
            "session_id": row["session_id"],
            "user_id": row["user_id"],
            "token": row["token"],
            "created_at": row["created_at"],
            "expires_at": row["expires_at"],
            "ip_address": row["ip_address"],
            "user_agent": row["user_agent"]
        }

    def delete_session(self, session_id: str) -> bool:
        """Delete a session
        
        Args:
            session_id: Session ID
        
        Returns:
            True if deleted, False if not found
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM user_sessions WHERE session_id = ?", (session_id,))
        deleted = cursor.rowcount > 0

        conn.commit()
        conn.close()

        return deleted

    def delete_user_sessions(self, user_id: str) -> int:
        """Delete all sessions for a user
        
        Args:
            user_id: User ID
        
        Returns:
            Number of sessions deleted
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM user_sessions WHERE user_id = ?", (user_id,))
        deleted = cursor.rowcount

        conn.commit()
        conn.close()

        return deleted

    def cleanup_expired_sessions(self) -> int:
        """Delete expired sessions
        
        Returns:
            Number of sessions deleted
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()

        now = datetime.utcnow().isoformat()
        cursor.execute("DELETE FROM user_sessions WHERE expires_at < ?", (now,))
        deleted = cursor.rowcount

        conn.commit()
        conn.close()

        return deleted

    def change_password(self, user_id: str, old_password: str, new_password: str) -> dict[str, Any]:
        """Change user password
        
        Args:
            user_id: User ID
            old_password: Current password
            new_password: New password
        
        Returns:
            Dict with success status and message
        """
        if len(new_password) < 8:
            return {"success": False, "error": "Password must be at least 8 characters"}

        conn = self._get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT password_hash FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return {"success": False, "error": "User not found"}

        if not bcrypt.checkpw(old_password.encode('utf-8'), row["password_hash"].encode('utf-8')):
            conn.close()
            return {"success": False, "error": "Current password is incorrect"}

        new_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cursor.execute("UPDATE users SET password_hash = ? WHERE user_id = ?", (new_hash, user_id))

        conn.commit()
        conn.close()

        return {"success": True, "message": "Password changed successfully"}

    def reset_password_request(self, email: str) -> dict[str, Any]:
        """Generate password reset token
        
        Args:
            email: User email
        
        Returns:
            Dict with success status and reset token (or None for security)
        """
        email = email.strip().lower()

        conn = self._get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT user_id FROM users WHERE email = ?", (email,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return {"success": True, "message": "If email exists, reset instructions will be sent"}

        user_id = row["user_id"]
        reset_token = secrets.token_urlsafe(32)
        reset_token_hash = hashlib.sha256(reset_token.encode()).hexdigest()
        expires_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()

        cursor.execute('''
            INSERT OR REPLACE INTO password_resets (user_id, reset_token_hash, expires_at, created_at)
            VALUES (?, ?, ?, ?)
        ''', (user_id, reset_token_hash, expires_at, datetime.utcnow().isoformat()))

        conn.commit()
        conn.close()

        return {"success": True, "reset_token": reset_token, "user_id": user_id}

    def verify_reset_token(self, reset_token: str) -> str | None:
        """Verify password reset token
        
        Args:
            reset_token: Reset token from email
        
        Returns:
            User ID if valid, None otherwise
        """
        reset_token_hash = hashlib.sha256(reset_token.encode()).hexdigest()

        conn = self._get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT user_id, expires_at FROM password_resets
            WHERE reset_token_hash = ?
        ''', (reset_token_hash,))

        row = cursor.fetchone()

        if not row:
            conn.close()
            return None

        expires_at = datetime.fromisoformat(row["expires_at"])
        if datetime.utcnow() > expires_at:
            conn.close()
            return None

        user_id = row["user_id"]
        cursor.execute("DELETE FROM password_resets WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()

        return user_id

    def reset_password(self, reset_token: str, new_password: str) -> dict[str, Any]:
        """Reset password using token
        
        Args:
            reset_token: Reset token from email
            new_password: New password
        
        Returns:
            Dict with success status
        """
        if len(new_password) < 8:
            return {"success": False, "error": "Password must be at least 8 characters"}

        user_id = self.verify_reset_token(reset_token)

        if not user_id:
            return {"success": False, "error": "Invalid or expired reset token"}

        new_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        conn = self._get_db_connection()
        cursor = conn.cursor()

        cursor.execute("UPDATE users SET password_hash = ? WHERE user_id = ?", (new_hash, user_id))
        cursor.execute("DELETE FROM user_sessions WHERE user_id = ?", (user_id,))

        conn.commit()
        conn.close()

        return {"success": True, "message": "Password reset successfully"}

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        """Get user by ID
        
        Args:
            user_id: User ID
        
        Returns:
            User dict or None
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT user_id, email, role, created_at, last_login, is_active
            FROM users WHERE user_id = ?
        ''', (user_id,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return {
            "user_id": row["user_id"],
            "email": row["email"],
            "role": row["role"],
            "created_at": row["created_at"],
            "last_login": row["last_login"],
            "is_active": bool(row["is_active"])
        }

    def get_all_users(self) -> list[dict[str, Any]]:
        """Get all users
        
        Returns:
            List of user dicts
        """
        conn = self._get_db_connection()
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

    def update_user(self, user_id: str, updates: dict[str, Any]) -> bool:
        """Update user
        
        Args:
            user_id: User ID
            updates: Dict with fields to update (email, role, etc.)
        
        Returns:
            True if updated, False otherwise
        """
        if not updates:
            return False

        conn = self._get_db_connection()
        cursor = conn.cursor()

        set_clauses = []
        values = []
        for key, value in updates.items():
            if key in ['email', 'role']:
                set_clauses.append(f"{key} = ?")
                values.append(value)

        if not set_clauses:
            conn.close()
            return False

        values.append(user_id)
        query = f"UPDATE users SET {', '.join(set_clauses)} WHERE user_id = ?"
        cursor.execute(query, values)
        updated = cursor.rowcount > 0

        conn.commit()
        conn.close()

        return updated

    def delete_user(self, user_id: str) -> bool:
        """Delete user
        
        Args:
            user_id: User ID
        
        Returns:
            True if deleted, False otherwise
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        deleted = cursor.rowcount > 0

        conn.commit()
        conn.close()

        return deleted

    def update_user_active(self, user_id: str, is_active: bool) -> bool:
        """Update user active status
        
        Args:
            user_id: User ID
            is_active: Active status
        
        Returns:
            True if updated, False otherwise
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()

        cursor.execute("UPDATE users SET is_active = ? WHERE user_id = ?", (is_active, user_id))
        updated = cursor.rowcount > 0

        conn.commit()
        conn.close()

        return updated


auth_service = AuthManager()


def get_user_permissions(role: str) -> list[str]:
    """Get all permissions for a role"""
    user_permissions = set()
    for permission, allowed_roles in PERMISSIONS.items():
        if role in allowed_roles:
            user_permissions.add(permission)
    return list(user_permissions)


def check_permission(role: str, permission: str) -> bool:
    """Check if a role has a specific permission"""
    return permission in PERMISSIONS and role in PERMISSIONS[permission]


def has_minimum_role(user_role: str, required_role: str) -> bool:
    """Check if user has minimum required role"""
    hierarchy = PERMISSION_HIERARCHY.get(user_role, [])
    return required_role in hierarchy


def login_required(f):
    """Decorator to require login for a route"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        session_id = None
        api_key_info = None

        if 'X-API-Key' in request.headers:
            api_key = request.headers['X-API-Key']
            api_key_info = database.validate_api_key(api_key)
            if api_key_info:
                g.current_user = {
                    'user_id': api_key_info['user_id'],
                    'email': api_key_info['email'],
                    'role': api_key_info['role'],
                    'is_active': True,
                    'auth_method': 'api_key',
                    'rate_limit': api_key_info['rate_limit']
                }
                g.api_key_id = api_key_info['key_id']
                return f(*args, **kwargs)

        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                scheme, token = auth_header.split(' ', 1)
                if scheme.lower() != 'bearer':
                    token = None
            except ValueError:
                token = None

        if not token:
            session_id = request.cookies.get('session_id')
            if session_id:
                session = auth_service.get_session(session_id)
                if session:
                    token = session['token']

        if not token:
            return jsonify({'error': 'Authentication required'}), 401

        payload = auth_service.verify_token(token)
        if not payload:
            return jsonify({'error': 'Invalid or expired token'}), 401

        user = auth_service.get_user(payload['user_id'])
        if not user:
            return jsonify({'error': 'User not found'}), 401

        if not user['is_active']:
            return jsonify({'error': 'Account is disabled'}), 403

        user['auth_method'] = 'session'
        g.current_user = user
        g.token = token
        g.session_id = session_id

        return f(*args, **kwargs)

    return decorated_function


def role_required(required_role: str):
    """Decorator to require a minimum role"""
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if not has_minimum_role(g.current_user['role'], required_role):
                return jsonify({'error': 'Insufficient permissions'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def permission_required(permission: str):
    """Decorator to require a specific permission"""
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if not check_permission(g.current_user['role'], permission):
                return jsonify({'error': 'Permission denied'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def get_current_user() -> dict[str, Any] | None:
    """Get the current authenticated user from Flask g object"""
    return getattr(g, 'current_user', None)


def get_user_role() -> str | None:
    """Get the current user's role"""
    user = get_current_user()
    return user['role'] if user else None


def is_admin() -> bool:
    """Check if current user is admin"""
    return get_user_role() == 'admin'


def is_manager() -> bool:
    """Check if current user is manager or above"""
    role = get_user_role()
    return role in ['admin', 'manager'] if role else False


def create_api_key_for_user(user_id: str, name: str, rate_limit: int = 60) -> dict[str, Any] | None:
    """Create an API key for a user
    
    Args:
        user_id: User ID
        name: Key description/name
        rate_limit: Requests per minute (default: 60)
    
    Returns:
        Dict with key_id and the actual API key (only returned once), or None if user not found
    """
    return database.create_api_key(user_id, name, rate_limit)


def list_user_api_keys(user_id: str) -> list[dict[str, Any]]:
    """List all API keys for a user
    
    Args:
        user_id: User ID
    
    Returns:
        List of API key info (without the actual key hash)
    """
    return database.get_user_api_keys(user_id)


def revoke_user_api_key(key_id: str, user_id: str) -> bool:
    """Revoke an API key
    
    Args:
        key_id: The key ID to revoke
        user_id: User ID for ownership verification
    
    Returns:
        True if revoked, False otherwise
    """
    return database.revoke_api_key(key_id, user_id)


class AuditLogger:
    """Simple audit logger for tracking user actions"""

    def __init__(self, log_path: str = "/workspace/audit.log"):
        self.log_path = log_path

    def log(self, action: str, user_id: str = None, details: dict[str, Any] = None):
        """Log an audit event"""
        entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'action': action,
            'user_id': user_id,
            'details': details or {},
            'ip_address': request.remote_addr if request else None,
            'user_agent': request.headers.get('User-Agent') if request else None
        }

        try:
            with open(self.log_path, 'a') as f:
                f.write(json.dumps(entry) + '\n')
        except Exception:
            pass

    def get_logs(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent audit logs"""
        logs = []
        try:
            if os.path.exists(self.log_path):
                with open(self.log_path) as f:
                    lines = f.readlines()
                    for line in lines[-limit:]:
                        try:
                            logs.append(json.loads(line.strip()))
                        except json.JSONDecodeError:
                            continue
        except Exception:
            pass

        return list(reversed(logs))


audit_logger = AuditLogger()
