"""
Audit Logging Module - Track all user actions and system changes
"""
import sqlite3
import json
import csv
import uuid
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import List, Dict, Any, Optional
from enum import Enum

DB_PATH = Path(__file__).parent / "seller_data.db"


class AuditAction(str, Enum):
    CREATE = "CREATE"
    READ = "READ"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    EXPORT = "EXPORT"
    IMPORT = "IMPORT"
    SYNC = "SYNC"
    PRICE_CHANGE = "PRICE_CHANGE"
    INVENTORY_UPDATE = "INVENTORY_UPDATE"
    ORDER_CREATE = "ORDER_CREATE"
    ORDER_UPDATE = "ORDER_UPDATE"
    ORDER_CANCEL = "ORDER_CANCEL"
    ADMIN_ACTION = "ADMIN_ACTION"
    SETTINGS_CHANGE = "SETTINGS_CHANGE"
    API_CALL = "API_CALL"


class ResourceType(str, Enum):
    USER = "user"
    PRODUCT = "product"
    ORDER = "order"
    INVENTORY = "inventory"
    PRICE = "price"
    REVIEW = "review"
    COMPETITOR = "competitor"
    SETTINGS = "settings"
    SCHEDULE = "schedule"
    EXPORT = "export"
    TASK = "task"
    NOTIFICATION = "notification"
    LICENSE = "license"


class AuditLogger:
    """Audit logging system for tracking all user actions and system changes"""

    @staticmethod
    def _get_connection():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def log_action(
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> str:
        """
        Log an action to the audit log.

        Args:
            user_id: ID of the user performing the action
            action: Action type (CREATE, READ, UPDATE, DELETE, etc.)
            resource_type: Type of resource being acted upon
            resource_id: ID of the specific resource (optional)
            details: Additional details as dict (old/new values, etc.)
            ip_address: Client IP address
            user_agent: Client user agent string

        Returns:
            The log_id of the created audit entry
        """
        log_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        details_json = json.dumps(details) if details else None

        conn = AuditLogger._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO audit_logs (
                log_id, user_id, action, resource_type, resource_id,
                details, ip_address, user_agent, timestamp
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (log_id, user_id, action, resource_type, resource_id,
              details_json, ip_address, user_agent, timestamp))

        conn.commit()
        conn.close()

        return log_id

    @staticmethod
    def get_logs(
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get audit logs with optional filters.

        Args:
            user_id: Filter by user ID
            action: Filter by action type
            resource_type: Filter by resource type
            resource_id: Filter by resource ID
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of audit log entries
        """
        conn = AuditLogger._get_connection()
        cursor = conn.cursor()

        conditions = []
        params = []

        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if action:
            conditions.append("action = ?")
            params.append(action)
        if resource_type:
            conditions.append("resource_type = ?")
            params.append(resource_type)
        if resource_id:
            conditions.append("resource_id = ?")
            params.append(resource_id)
        if start_date:
            conditions.append("timestamp >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("timestamp <= ?")
            params.append(end_date)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        cursor.execute(f'''
            SELECT * FROM audit_logs
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        ''', params + [limit, offset])

        rows = cursor.fetchall()
        conn.close()

        logs = []
        for row in rows:
            log = {
                'log_id': row['log_id'],
                'user_id': row['user_id'],
                'action': row['action'],
                'resource_type': row['resource_type'],
                'resource_id': row['resource_id'],
                'details': json.loads(row['details']) if row['details'] else None,
                'ip_address': row['ip_address'],
                'user_agent': row['user_agent'],
                'timestamp': row['timestamp']
            }
            logs.append(log)

        return logs

    @staticmethod
    def get_log_count(
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> int:
        """Get total count of logs matching filters"""
        conn = AuditLogger._get_connection()
        cursor = conn.cursor()

        conditions = []
        params = []

        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if action:
            conditions.append("action = ?")
            params.append(action)
        if resource_type:
            conditions.append("resource_type = ?")
            params.append(resource_type)
        if start_date:
            conditions.append("timestamp >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("timestamp <= ?")
            params.append(end_date)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        cursor.execute(f'''
            SELECT COUNT(*) as count FROM audit_logs
            WHERE {where_clause}
        ''', params)

        result = cursor.fetchone()
        conn.close()

        return result['count'] if result else 0

    @staticmethod
    def get_user_activity(user_id: str, days: int = 30) -> Dict[str, Any]:
        """
        Get activity summary for a specific user.

        Args:
            user_id: User ID to get activity for
            days: Number of days to look back

        Returns:
            Activity summary with action counts and recent actions
        """
        conn = AuditLogger._get_connection()
        cursor = conn.cursor()

        start_date = (datetime.now() - timedelta(days=days)).isoformat()

        cursor.execute('''
            SELECT action, COUNT(*) as count
            FROM audit_logs
            WHERE user_id = ? AND timestamp >= ?
            GROUP BY action
        ''', (user_id, start_date))

        action_counts = {row['action']: row['count'] for row in cursor.fetchall()}

        cursor.execute('''
            SELECT action, resource_type, COUNT(*) as count
            FROM audit_logs
            WHERE user_id = ? AND timestamp >= ?
            GROUP BY action, resource_type
            ORDER BY count DESC
        ''', (user_id, start_date))

        resource_counts = []
        for row in cursor.fetchall():
            resource_counts.append({
                'action': row['action'],
                'resource_type': row['resource_type'],
                'count': row['count']
            })

        cursor.execute('''
            SELECT * FROM audit_logs
            WHERE user_id = ? AND timestamp >= ?
            ORDER BY timestamp DESC
            LIMIT 10
        ''', (user_id, start_date))

        recent_actions = []
        for row in cursor.fetchall():
            recent_actions.append({
                'log_id': row['log_id'],
                'action': row['action'],
                'resource_type': row['resource_type'],
                'resource_id': row['resource_id'],
                'timestamp': row['timestamp']
            })

        conn.close()

        return {
            'user_id': user_id,
            'days': days,
            'total_actions': sum(action_counts.values()),
            'action_counts': action_counts,
            'resource_counts': resource_counts,
            'recent_actions': recent_actions
        }

    @staticmethod
    def get_resource_history(
        resource_type: str,
        resource_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get the change history for a specific resource.

        Args:
            resource_type: Type of resource
            resource_id: ID of the resource
            limit: Maximum number of history entries

        Returns:
            List of changes made to the resource
        """
        conn = AuditLogger._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM audit_logs
            WHERE resource_type = ? AND resource_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (resource_type, resource_id, limit))

        rows = cursor.fetchall()
        conn.close()

        history = []
        for row in rows:
            history.append({
                'log_id': row['log_id'],
                'user_id': row['user_id'],
                'action': row['action'],
                'details': json.loads(row['details']) if row['details'] else None,
                'ip_address': row['ip_address'],
                'timestamp': row['timestamp']
            })

        return history

    @staticmethod
    def export_logs(
        format: str = 'csv',
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> str:
        """
        Export audit logs to CSV or JSON format.

        Args:
            format: Export format ('csv' or 'json')
            Other filters same as get_logs()

        Returns:
            Filename of the exported file
        """
        logs = AuditLogger.get_logs(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            start_date=start_date,
            end_date=end_date,
            limit=10000,
            offset=0
        )

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        if format == 'json':
            filename = f"audit_logs_{timestamp}.json"
            filepath = Path(__file__).parent / "exports" / filename
            filepath.parent.mkdir(exist_ok=True)

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(logs, f, indent=2, ensure_ascii=False)

        else:
            filename = f"audit_logs_{timestamp}.csv"
            filepath = Path(__file__).parent / "exports" / filename
            filepath.parent.mkdir(exist_ok=True)

            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                if logs:
                    writer = csv.DictWriter(f, fieldnames=logs[0].keys())
                    writer.writeheader()
                    writer.writerows(logs)

        return filename

    @staticmethod
    def get_action_statistics(days: int = 30) -> Dict[str, Any]:
        """
        Get statistics about actions over a period.

        Args:
            days: Number of days to analyze

        Returns:
            Statistics dictionary
        """
        conn = AuditLogger._get_connection()
        cursor = conn.cursor()

        start_date = (datetime.now() - timedelta(days=days)).isoformat()

        cursor.execute('''
            SELECT action, COUNT(*) as count
            FROM audit_logs
            WHERE timestamp >= ?
            GROUP BY action
            ORDER BY count DESC
        ''', (start_date,))

        action_stats = [{'action': row['action'], 'count': row['count']}
                       for row in cursor.fetchall()]

        cursor.execute('''
            SELECT resource_type, COUNT(*) as count
            FROM audit_logs
            WHERE timestamp >= ?
            GROUP BY resource_type
            ORDER BY count DESC
        ''', (start_date,))

        resource_stats = [{'resource_type': row['resource_type'], 'count': row['count']}
                          for row in cursor.fetchall()]

        cursor.execute('''
            SELECT user_id, COUNT(*) as count
            FROM audit_logs
            WHERE timestamp >= ?
            GROUP BY user_id
            ORDER BY count DESC
            LIMIT 10
        ''', (start_date,))

        user_stats = [{'user_id': row['user_id'], 'count': row['count']}
                      for row in cursor.fetchall()]

        conn.close()

        return {
            'days': days,
            'action_stats': action_stats,
            'resource_stats': resource_stats,
            'user_stats': user_stats
        }

    @staticmethod
    def cleanup_old_logs(days_to_keep: int = 90) -> int:
        """
        Delete audit logs older than specified days.

        Args:
            days_to_keep: Number of days of logs to retain

        Returns:
            Number of logs deleted
        """
        conn = AuditLogger._get_connection()
        cursor = conn.cursor()

        cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).isoformat()

        cursor.execute('''
            DELETE FROM audit_logs
            WHERE timestamp < ?
        ''', (cutoff_date,))

        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()

        return deleted_count

    @staticmethod
    def get_recent_logs(limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get recent audit logs.

        Args:
            limit: Maximum number of logs to return

        Returns:
            List of recent audit log entries
        """
        conn = AuditLogger._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT log_id, user_id, action, resource_type, resource_id,
                   details, ip_address, user_agent, timestamp
            FROM audit_logs
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))

        logs = []
        for row in cursor.fetchall():
            logs.append({
                'log_id': row[0],
                'user_id': row[1],
                'action': row[2],
                'resource_type': row[3],
                'resource_id': row[4],
                'details': json.loads(row[5]) if row[5] else {},
                'ip_address': row[6],
                'user_agent': row[7],
                'timestamp': row[8]
            })

        conn.close()
        return logs


def init_audit_db():
    """Initialize the audit logs table if it doesn't exist"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

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

    conn.commit()
    conn.close()


init_audit_db()
