import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import Header, HTTPException, status

from .db import execute, fetch_one

BASE_DIR = Path(__file__).resolve().parents[1]
LOG_PATH = BASE_DIR / "logs" / "audit.log"

SESSION_HOURS = 8
ADMIN_ROLES = {"admin", "CDS Manager"}
CDS_ROLES = ADMIN_ROLES | {"CDS Team"}
RECRUITER_ROLES = ADMIN_ROLES | {"Recruiter"}

# Role mapping: role_id -> role_name
# 1: Student
# 2: Recruiter
# 3: CDS Team
# 4: CDS Manager (admin-like)
# 5: Alumni
ROLE_ID_MAPPING = {
    1: "Student",
    2: "Recruiter",
    3: "CDS Team",
    4: "CDS Manager",
    5: "Alumni",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def map_role_id_to_role(role_id: Optional[int]) -> str:
    """Map role_id to role name, default to 'Student'"""
    if role_id is None:
        return "Student"
    return ROLE_ID_MAPPING.get(role_id, "Student")


def log_audit(actor_user_id: Optional[int], action: str, table_name: str, record_id: Optional[str], request_path: str, status_value: str):
    line = f"{utc_now().isoformat()} actor={actor_user_id} action={action} table={table_name} record={record_id} path={request_path} status={status_value}"
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")

    try:
        execute(
            """
            INSERT INTO audit_logs(actor_user_id, action, table_name, record_id, request_path, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (actor_user_id, action, table_name, record_id, request_path, status_value),
        )
    except Exception:
        # Audit logging failure shouldn't block main operations
        pass


def query_all_shards_for_user(username: str):
    """Query all shards to find a user by username with full details"""
    try:
        from .sharded_db import get_db_manager
        
        db_manager = get_db_manager()
        for shard_id in range(3):
            table_name = f"shard_{shard_id}_users"
            query = f"SELECT user_id, username, password_hash, role_id FROM {table_name} WHERE username = %s"
            try:
                pool = db_manager.pools[shard_id]
                conn = pool.get_connection()
                cursor = conn.cursor(dictionary=True)
                cursor.execute(query, (username,))
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


def authenticate_user(username: str, password: str):
    """Authenticate user and return user info with proper role"""
    # Try to find user in sharded database
    user = query_all_shards_for_user(username)
    if not user:
        return None
    if password != user["password_hash"]:
        return None
    
    # Map role_id to role name
    role = map_role_id_to_role(user.get("role_id"))
    
    # Return user with mapped role
    return {
        "user_id": user["user_id"],
        "username": user["username"],
        "role": role,
        "role_id": user.get("role_id")
    }


def create_session(user_id: int) -> str:
    """Create a session token and store in user's shard"""
    token = generate_session_token()
    expires_at = utc_now() + timedelta(hours=SESSION_HOURS)
    
    # Store session in user's shard
    try:
        from .sharded_db import get_db_manager
        
        shard_id = user_id % 3
        table_name = f"shard_{shard_id}_sessions"
        db_manager = get_db_manager()
        pool = db_manager.pools[shard_id]
        conn = pool.get_connection()
        cursor = conn.cursor()
        
        # Create table if not exists
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                session_id INT AUTO_INCREMENT PRIMARY KEY,
                session_token VARCHAR(255) UNIQUE,
                user_id INT,
                expires_at VARCHAR(50)
            )
        """)
        
        cursor.execute(
            f"INSERT INTO {table_name}(session_token, user_id, expires_at) VALUES (%s, %s, %s)",
            (token, user_id, expires_at.isoformat())
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception:
        pass  # Session creation failure shouldn't block login
    
    return token


def get_session_user(session_token: str):
    """Get session user from sharded database with proper role"""
    try:
        from .sharded_db import get_db_manager
        
        db_manager = get_db_manager()
        # Check all shards for session
        for shard_id in range(3):
            try:
                table_name = f"shard_{shard_id}_sessions"
                pool = db_manager.pools[shard_id]
                conn = pool.get_connection()
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    f"SELECT session_token, user_id, expires_at FROM {table_name} WHERE session_token = %s",
                    (session_token,)
                )
                session = cursor.fetchone()
                cursor.close()
                conn.close()
                
                if session:
                    expiry = datetime.fromisoformat(session["expires_at"])
                    if expiry < utc_now():
                        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
                    
                    # Get user info including role_id
                    user_id = session["user_id"]
                    user_shard = user_id % 3
                    user_table = f"shard_{user_shard}_users"
                    user_pool = db_manager.pools[user_shard]
                    user_conn = user_pool.get_connection()
                    user_cursor = user_conn.cursor(dictionary=True)
                    user_cursor.execute(
                        f"SELECT user_id, username, role_id FROM {user_table} WHERE user_id = %s",
                        (user_id,)
                    )
                    user = user_cursor.fetchone()
                    user_cursor.close()
                    user_conn.close()
                    
                    if user:
                        role = map_role_id_to_role(user.get("role_id"))
                        return {
                            "user_id": user["user_id"],
                            "username": user["username"],
                            "role": role,
                            "role_id": user.get("role_id"),
                            "expires_at": session["expires_at"]
                        }
            except HTTPException:
                raise
            except Exception:
                continue
        
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session token")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session token")


def current_user_dependency(x_session_token: Optional[str] = Header(default=None)):
    """Dependency for protected endpoints - returns current user or raises 401"""
    if not x_session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No session found")
    return get_session_user(x_session_token)


def require_admin(user_row, request_path: Optional[str] = None, table_name: str = "authorization"):
    """Check if user has admin role"""
    if user_row["role"] not in ADMIN_ROLES:
        if request_path:
            actor_user_id = user_row["user_id"] if "user_id" in user_row.keys() else None
            log_audit(
                actor_user_id,
                "DENY",
                table_name,
                None,
                request_path,
                "forbidden",
            )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")


def is_admin_user(user_row) -> bool:
    """Check if user is admin"""
    return user_row["role"] in ADMIN_ROLES


def is_cds_user(user_row) -> bool:
    """Check if user is CDS staff or manager"""
    return user_row["role"] in CDS_ROLES


def is_recruiter_user(user_row) -> bool:
    """Check if user is recruiter or admin"""
    return user_row["role"] in RECRUITER_ROLES


def require_cds_access(user_row, request_path: Optional[str] = None, table_name: str = "authorization"):
    """Check if user has CDS access"""
    if user_row["role"] not in CDS_ROLES:
        if request_path:
            actor_user_id = user_row["user_id"] if "user_id" in user_row.keys() else None
            log_audit(
                actor_user_id,
                "DENY",
                table_name,
                None,
                request_path,
                "forbidden",
            )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CDS role required")


def require_recruiter_access(user_row, request_path: Optional[str] = None, table_name: str = "authorization"):
    """Check if user has recruiter access"""
    if user_row["role"] not in RECRUITER_ROLES:
        if request_path:
            actor_user_id = user_row["user_id"] if "user_id" in user_row.keys() else None
            log_audit(
                actor_user_id,
                "DENY",
                table_name,
                None,
                request_path,
                "forbidden",
            )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Recruiter role required")
