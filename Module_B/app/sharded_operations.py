"""Sharded database operations wrapper for Module B"""

from typing import Optional, Dict, Any, List
from .sharded_db import get_sharded_db_manager


def query_user_by_username(username: str) -> Optional[Dict]:
    """Query all shards to find user by username"""
    try:
        db_manager = get_sharded_db_manager()
        for shard_id in range(3):
            try:
                table_name = f"shard_{shard_id}_users"
                pool = db_manager.pools[shard_id]
                conn = pool.get_connection()
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    f"SELECT user_id, username, password_hash, is_active FROM {table_name} WHERE username = %s",
                    (username,)
                )
                user = cursor.fetchone()
                cursor.close()
                conn.close()
                if user:
                    return user
            except Exception:
                continue
        return None
    except Exception:
        return None


def get_user_by_id(user_id: int) -> Optional[Dict]:
    """Get user by ID (uses sharding key)"""
    try:
        db_manager = get_sharded_db_manager()
        shard_id = user_id % 3
        table_name = f"shard_{shard_id}_users"
        pool = db_manager.pools[shard_id]
        conn = pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            f"SELECT user_id, username, is_active FROM {table_name} WHERE user_id = %s",
            (user_id,)
        )
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        return user
    except Exception:
        return None


def create_session_sharded(user_id: int, session_token: str, expires_at: str) -> bool:
    """Store session in sharded database"""
    try:
        db_manager = get_sharded_db_manager()
        shard_id = user_id % 3
        pool = db_manager.pools[shard_id]
        conn = pool.get_connection()
        cursor = conn.cursor()
        
        # Create sessions table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id INT AUTO_INCREMENT PRIMARY KEY,
                session_token VARCHAR(255) UNIQUE,
                user_id INT,
                expires_at VARCHAR(50)
            )
        """)
        
        cursor.execute(
            "INSERT INTO sessions(session_token, user_id, expires_at) VALUES (%s, %s, %s)",
            (session_token, user_id, expires_at)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception:
        return False


def get_session_by_token(session_token: str) -> Optional[Dict]:
    """Get session from any shard"""
    try:
        db_manager = get_sharded_db_manager()
        for shard_id in range(3):
            try:
                pool = db_manager.pools[shard_id]
                conn = pool.get_connection()
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    "SELECT session_token, user_id, expires_at FROM sessions WHERE session_token = %s",
                    (session_token,)
                )
                session = cursor.fetchone()
                cursor.close()
                conn.close()
                if session:
                    return session
            except Exception:
                continue
        return None
    except Exception:
        return None


def execute_sharded(query: str, params: tuple = (), user_id: Optional[int] = None) -> bool:
    """Execute query on appropriate shard"""
    try:
        if user_id is None:
            # Execute on all shards if no user_id
            db_manager = get_sharded_db_manager()
            for shard_id in range(3):
                try:
                    pool = db_manager.pools[shard_id]
                    conn = pool.get_connection()
                    cursor = conn.cursor()
                    cursor.execute(query, params)
                    conn.commit()
                    cursor.close()
                    conn.close()
                except Exception:
                    continue
            return True
        else:
            # Execute on correct shard for user_id
            shard_id = user_id % 3
            db_manager = get_sharded_db_manager()
            pool = db_manager.pools[shard_id]
            conn = pool.get_connection()
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            cursor.close()
            conn.close()
            return True
    except Exception:
        return False


def fetch_from_shard(query: str, params: tuple = (), shard_id: int = 0) -> Optional[Dict]:
    """Fetch single row from specific shard"""
    try:
        db_manager = get_sharded_db_manager()
        pool = db_manager.pools[shard_id]
        conn = pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, params)
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result
    except Exception:
        return None


def fetch_all_from_shard(query: str, params: tuple = (), shard_id: int = 0) -> List[Dict]:
    """Fetch all rows from specific shard"""
    try:
        db_manager = get_sharded_db_manager()
        pool = db_manager.pools[shard_id]
        conn = pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, params)
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        return results if results else []
    except Exception:
        return []


def fetch_from_all_shards(query: str, params: tuple = ()) -> List[Dict]:
    """Fetch and aggregate results from all shards"""
    try:
        all_results = []
        db_manager = get_sharded_db_manager()
        for shard_id in range(3):
            try:
                pool = db_manager.pools[shard_id]
                conn = pool.get_connection()
                cursor = conn.cursor(dictionary=True)
                cursor.execute(query, params)
                results = cursor.fetchall()
                cursor.close()
                conn.close()
                if results:
                    all_results.extend(results)
            except Exception:
                continue
        return all_results
    except Exception:
        return []
