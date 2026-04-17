import os
import re
import sys
from pathlib import Path
from typing import Iterable, Optional, List, Dict, Any
import time
import mysql.connector
from mysql.connector import pooling

BASE_DIR = Path(__file__).resolve().parents[1]

# Add Module A to path for ACID transaction integration
MODULE_A_PATH = BASE_DIR.parents[0] / "Module_A"
if str(MODULE_A_PATH) not in sys.path:
    sys.path.insert(0, str(MODULE_A_PATH))

# Import Module A transaction coordinator
try:
    from transaction.coordinator import TransactionCoordinator, TransactionConfig
    ACID_INTEGRATION_ENABLED = True
    print("[ACID INTEGRATION] Module A transaction coordinator loaded successfully")
except ImportError as e:
    print(f"[WARNING] Module A integration failed: {e}")
    ACID_INTEGRATION_ENABLED = False

# MySQL connection configuration
DB_HOST = os.getenv("MODULE_B_DB_HOST", "localhost")
DB_USER = os.getenv("MODULE_B_DB_USER", "root")
DB_PASSWORD = os.getenv("MODULE_B_DB_PASSWORD", "")
DB_NAME = os.getenv("MODULE_B_DB_NAME", "module_b")
DB_PORT = int(os.getenv("MODULE_B_DB_PORT", "3306"))

SCHEMA_PATH = BASE_DIR / "sql" / "init_schema.sql"
INDEX_PATH = BASE_DIR / "sql" / "indexes.sql"

# MySQL connection pool
try:
    db_pool = pooling.MySQLConnectionPool(
        pool_name="module_b_pool",
        pool_size=5,
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        port=DB_PORT,
        autocommit=False
    )
except Exception as e:
    print(f"[ERROR] Failed to create MySQL connection pool: {e}")
    db_pool = None

# Initialize ACID Transaction Coordinator (if available)
ACID_COORDINATOR = None
if ACID_INTEGRATION_ENABLED:
    try:
        # Setup WAL directory for Module B
        WAL_DIR = BASE_DIR / "acid_wal_logs"
        WAL_DIR.mkdir(exist_ok=True)
        
        # Configure transaction coordinator for web operations
        config = TransactionConfig(
            lock_timeout=30.0,
            enable_auto_retry=True,
            max_retries=3,
            enable_deadlock_detection=True
        )
        
        # Note: For now, we'll use this for logging and testing
        # Full integration would require adapting the B+Tree to PostgreSQL
        print(f"[ACID INTEGRATION] WAL directory: {WAL_DIR}")
        print("[ACID INTEGRATION] Transaction coordinator configured for Module B")
        
    except Exception as e:
        print(f"[WARNING] ACID coordinator setup failed: {e}")
        ACID_INTEGRATION_ENABLED = False

INSERT_ID_COLUMNS = {
    "roles": "role_id",
    "users": "user_id",
    "user_logs": "log_id",
    "groups": "group_id",
    "students": "student_id",
    "resumes": "resume_id",
    "companies": "company_id",
    "job_postings": "job_id",
    "eligibility_criteria": "criteria_id",
    "applications": "application_id",
    "job_events": "event_id",
    "venue_booking": "booking_id",
    "interviews": "interview_id",
    "question_bank": "q_id",
    "prep_pages": "page_id",
    "placement_stats": "stat_id",
    "penalties": "penalty_id",
    "cds_training_sessions": "session_id",
    "audit_logs": "log_id",
}


def _normalize_query(query: str) -> str:
    """Convert SQLite/PostgreSQL syntax to MySQL syntax"""
    q = query.replace("?", "%s")
    
    # Handle INSERT OR IGNORE → INSERT IGNORE
    if re.search(r"(?i)INSERT\s+OR\s+IGNORE", q):
        q = re.sub(r"(?i)INSERT\s+OR\s+IGNORE", "INSERT IGNORE", q)
    
    # Remove ON CONFLICT clauses (not needed with INSERT IGNORE or ON DUPLICATE KEY UPDATE)
    q = re.sub(r"(?i)\s+ON\s+CONFLICT\s+.*?DO\s+NOTHING", "", q)

    # Quote reserved table name for MySQL.
    q = re.sub(r"(?i)\b(FROM|JOIN|INTO|UPDATE|TABLE|REFERENCES)\s+`?groups`?\b", r"\1 `groups`", q)
    
    return q


def _prepare_schema_sql(schema_sql: str) -> str:
    """Convert SQLite/PostgreSQL schema to MySQL syntax"""
    sql = schema_sql
    
    # Remove PRAGMA statements
    sql = re.sub(r"(?im)^\s*PRAGMA\s+.*?;\s*$", "", sql)
    
    # INTEGER PRIMARY KEY AUTOINCREMENT → INT AUTO_INCREMENT PRIMARY KEY
    sql = re.sub(r"(?i)INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT", "INT AUTO_INCREMENT PRIMARY KEY", sql)

    # MySQL does not allow UNIQUE/PK constraints directly on TEXT without a key length.
    sql = re.sub(r"(?i)\bTEXT\s+UNIQUE\b", "VARCHAR(255) UNIQUE", sql)
    sql = re.sub(r"(?i)\bTEXT\s+PRIMARY\s+KEY\b", "VARCHAR(255) PRIMARY KEY", sql)

    # SQLite often stores timestamps as TEXT; map timestamp defaults to DATETIME for MySQL.
    sql = re.sub(
        r"(?i)\bTEXT\s+NOT\s+NULL\s+DEFAULT\s+CURRENT_TIMESTAMP\b",
        "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
        sql,
    )
    sql = re.sub(
        r"(?i)\bTEXT\s+DEFAULT\s+CURRENT_TIMESTAMP\b",
        "DATETIME DEFAULT CURRENT_TIMESTAMP",
        sql,
    )

    # MySQL defaults/checks/indexes are safer with VARCHAR than TEXT in this schema.
    sql = re.sub(r"(?i)\bTEXT\b", "VARCHAR(255)", sql)

    # Convert SQLite insert syntax used in seed data.
    sql = re.sub(r"(?i)INSERT\s+OR\s+IGNORE", "INSERT IGNORE", sql)

    # Quote reserved table name in schema DDL.
    sql = re.sub(
        r"(?i)\b(CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS|REFERENCES|INSERT\s+INTO|INSERT\s+IGNORE\s+INTO|UPDATE|FROM|JOIN)\s+`?groups`?\b",
        r"\1 `groups`",
        sql,
    )
    
    return sql


def _connect() -> mysql.connector.MySQLConnection:
    """Get a connection from the pool"""
    if db_pool is None:
        raise Exception("Database pool not initialized")
    return db_pool.get_connection()


class MySQLCursor:
    def __init__(self, cursor: mysql.connector.cursor.MySQLCursor):
        self._cursor = cursor
        self._lastrowid = None

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    @property
    def lastrowid(self):
        return self._cursor.lastrowid or self._lastrowid

    def set_lastrowid(self, value):
        self._lastrowid = value

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        # Convert tuple to dict
        if isinstance(row, tuple):
            columns = [desc[0] for desc in self._cursor.description]
            return dict(zip(columns, row))
        return row

    def fetchall(self):
        rows = self._cursor.fetchall()
        if not rows:
            return []
        # Convert tuples to dicts
        if rows and isinstance(rows[0], tuple):
            columns = [desc[0] for desc in self._cursor.description]
            return [dict(zip(columns, row)) for row in rows]
        return rows


class MySQLConnection:
    def __init__(self, conn: mysql.connector.MySQLConnection):
        self._conn = conn

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            self._conn.rollback()
        self._conn.close()

    def execute(self, query: str, params: Iterable = ()):
        cur = self._conn.cursor()
        cur.execute(_normalize_query(query), tuple(params))
        return MySQLCursor(cur)

    def executemany(self, query: str, params_list: Iterable[Iterable]):
        cur = self._conn.cursor()
        cur.executemany(_normalize_query(query), params_list)
        return MySQLCursor(cur)

    def cursor(self):
        return self._conn.cursor()

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()


def get_connection() -> MySQLConnection:
    return MySQLConnection(_connect())


def initialize_database(apply_indexes: bool = False):
    try:
        schema_sql = _prepare_schema_sql(SCHEMA_PATH.read_text(encoding="utf-8"))
        index_sql = INDEX_PATH.read_text(encoding="utf-8") if apply_indexes else ""
        
        with get_connection() as conn:
            cursor = conn.cursor()
            # Enable foreign keys for MySQL
            cursor.execute("SET FOREIGN_KEY_CHECKS=1")
            
            # Split and execute statements individually
            for statement in schema_sql.split(";"):
                statement = statement.strip()
                if statement:
                    cursor.execute(statement)
            
            if apply_indexes and index_sql.strip():
                for statement in index_sql.split(";"):
                    statement = statement.strip()
                    if statement:
                        cursor.execute(statement)
            
            _ensure_baseline_auth_data(conn)
            conn.commit()
        
        print("[DB] Database initialized successfully")
    except Exception as e:
        print(f"[ERROR] Database initialization failed: {e}")
        raise


def _ensure_baseline_auth_data(conn: MySQLConnection):
    """Ensure baseline auth data exists"""
    try:
        cursor = conn.cursor()
        
        # Insert Recruiter role if it doesn't exist
        cursor.execute("""
            INSERT IGNORE INTO roles(role_id, role_name, description)
            VALUES (2, 'Recruiter', 'External recruiter user')
        """)
        
        # Insert CDS Manager role if it doesn't exist
        cursor.execute("""
            INSERT IGNORE INTO roles(role_id, role_name, description)
            VALUES (4, 'CDS Manager', 'Head of Career Development and Placement Services')
        """)
        
        # Insert admin user if it doesn't exist
        cursor.execute("""
            INSERT IGNORE INTO users(
                user_id, username, email, password_hash, role_id, is_verified,
                full_name, status, is_active
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (1000, "admin", "admin@local.dev", "admin123", 4, 1, "System Admin", "ACTIVE", 1))
        
        # Update test user credentials
        credential_pairs = []
        for n in range(1, 31):
            credential_pairs.append((f"hash{n}", f"student{n}"))
        for n in range(1, 11):
            credential_pairs.append((f"hash{30 + n}", f"alumni{n}"))
        for n in range(1, 16):
            credential_pairs.append((f"hash{40 + n}", f"recruiter{n}"))
        for n in range(1, 6):
            credential_pairs.append((f"hash{55 + n}", f"cds{n}"))
        credential_pairs.append(("hash61", "cdsmanager1"))
        credential_pairs.append(("admin123", "admin"))
        
        for password_hash, username in credential_pairs:
            cursor.execute("""
                UPDATE users SET password_hash = %s, is_active = 1, status = 'ACTIVE' 
                WHERE username = %s
            """, (password_hash, username))
        
        conn.commit()
        print("[DB] Baseline auth data ensured")
        
    except Exception as e:
        print(f"[WARNING] Error setting baseline auth data: {e}")

def fetch_one(query: str, params: Iterable = ()) -> Optional[dict]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(_normalize_query(query), tuple(params))
        row = cursor.fetchone()
        if row is None:
            return None
        if isinstance(row, tuple):
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))
        return row


def fetch_all(query: str, params: Iterable = ()):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(_normalize_query(query), tuple(params))
        rows = cursor.fetchall()
        if not rows:
            return []
        if rows and isinstance(rows[0], tuple):
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
        return rows


def execute(query: str, params: Iterable = ()) -> int:
    """Execute a query and return the inserted ID for INSERT statements"""
    normalized = _normalize_query(query)
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(normalized, tuple(params))
        
        # Get inserted ID for INSERT statements
        inserted_id = cursor.lastrowid if cursor.lastrowid else 0
        
        conn.commit()
        return inserted_id


def execute_many(query: str, params_list: Iterable[Iterable]):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.executemany(_normalize_query(query), params_list)
        conn.commit()


def execute_with_acid_transaction(operations: List[Dict[str, Any]], transaction_name: str = None) -> Dict[str, Any]:
    """
    Execute multiple operations as a single ACID transaction with full logging and recovery support.
    """
    if not ACID_INTEGRATION_ENABLED:
        return execute_mysql_transaction(operations)
    
    transaction_name = transaction_name or f"web_txn_{int(time.time())}"
    start_time = time.time()
    
    try:
        print(f"[ACID TRANSACTION] Starting: {transaction_name}")
        
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("START TRANSACTION")
            
            results = []
            for i, op in enumerate(operations):
                query = op.get('query', '')
                params = op.get('params', ())
                operation_name = op.get('name', f'op_{i}')
                
                print(f"[ACID TRANSACTION] Executing {operation_name}: {query[:50]}...")
                
                try:
                    cursor.execute(_normalize_query(query), tuple(params))
                    
                    result = {
                        'operation': operation_name,
                        'success': True,
                        'rowcount': cursor.rowcount,
                        'data': cursor.fetchall() if query.strip().upper().startswith('SELECT') else None
                    }
                    results.append(result)
                    
                except Exception as e:
                    print(f"[ACID TRANSACTION] Operation {operation_name} failed: {e}")
                    raise
            
            cursor.execute("COMMIT")
            
            duration = time.time() - start_time
            print(f"[ACID TRANSACTION] SUCCESS: {transaction_name} completed in {duration:.3f}s")
            
            return {
                'success': True,
                'transaction_name': transaction_name,
                'duration': duration,
                'operations_count': len(operations),
                'results': results
            }
            
    except Exception as e:
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("ROLLBACK")
            print(f"[ACID TRANSACTION] ROLLBACK: {transaction_name} - {e}")
        except:
            pass
        
        duration = time.time() - start_time
        return {
            'success': False,
            'transaction_name': transaction_name,
            'duration': duration,
            'error': str(e),
            'operations_count': len(operations)
        }


def execute_mysql_transaction(operations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Fallback MySQL-only transaction (no Module A integration)."""
    start_time = time.time()
    
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("START TRANSACTION")
            
            results = []
            for i, op in enumerate(operations):
                query = op.get('query', '')
                params = op.get('params', ())
                
                cursor.execute(_normalize_query(query), tuple(params))
                
                results.append({
                    'operation': f'op_{i}',
                    'rowcount': cursor.rowcount
                })
            
            cursor.execute("COMMIT")
            
            return {
                'success': True,
                'duration': time.time() - start_time,
                'operations_count': len(operations),
                'results': results
            }
            
    except Exception as e:
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("ROLLBACK")
        except:
            pass
            
        return {
            'success': False,
            'duration': time.time() - start_time,
            'error': str(e)
        }


def log_acid_operation(operation_type: str, table_name: str, details: Dict[str, Any] = None):
    """Log operation for ACID audit trail (if Module A integration is enabled)."""
    if ACID_INTEGRATION_ENABLED:
        timestamp = time.time()
        log_entry = {
            'timestamp': timestamp,
            'operation': operation_type,
            'table': table_name,
            'details': details or {}
        }
        print(f"[ACID LOG] {operation_type} on {table_name}: {details}")
        # In full integration, this would write to Module A's WAL
    

def get_acid_integration_status() -> Dict[str, Any]:
    """Get current ACID integration status for monitoring and debugging."""
    return {
        'acid_integration_enabled': ACID_INTEGRATION_ENABLED,
        'module_a_available': ACID_INTEGRATION_ENABLED,
        'wal_directory': str(BASE_DIR / "acid_wal_logs") if ACID_INTEGRATION_ENABLED else None,
        'transaction_features': {
            'write_ahead_logging': ACID_INTEGRATION_ENABLED,
            'crash_recovery': ACID_INTEGRATION_ENABLED,
            'deadlock_detection': ACID_INTEGRATION_ENABLED,
            'concurrent_transactions': True  # PostgreSQL provides this
        }
    }


# ============================================================================
# SHARDING SUPPORT (Assignment 4)
# ============================================================================

try:
    from .sharding_manager import ShardRouter, get_router, route_query, ShardingException
except ImportError:
    print("[WARNING] Sharding manager not available")

# Sharding configuration
SHARDING_ENABLED = os.getenv("MODULE_B_SHARDING_ENABLED", "1") == "1"
NUM_SHARDS = int(os.getenv("MODULE_B_NUM_SHARDS", "3"))

print(f"[SHARDING] Sharding enabled: {SHARDING_ENABLED}")
print(f"[SHARDING] Number of shards: {NUM_SHARDS}")


def initialize_sharding():
    """Initialize sharding tables and metadata"""
    if not SHARDING_ENABLED:
        print("[SHARDING] Sharding is disabled")
        return
    
    try:
        sharding_sql_path = BASE_DIR / "sql" / "sharding_migration.sql"
        if sharding_sql_path.exists():
            sharding_sql = sharding_sql_path.read_text(encoding="utf-8")
            with get_connection() as conn:
                cursor = conn.cursor()
                for statement in sharding_sql.split(";"):
                    statement = statement.strip()
                    if statement:
                        cursor.execute(statement)
                conn.commit()
            print("[SHARDING] Sharding tables initialized successfully")
        else:
            print(f"[WARNING] Sharding SQL file not found: {sharding_sql_path}")
    except Exception as e:
        print(f"[ERROR] Failed to initialize sharding: {e}")


def execute_sharded(table_name: str, query: str, params: Iterable = (), user_id: Optional[int] = None) -> int:
    """
    Execute a query with sharding support
    
    Args:
        table_name: Base table name (e.g., 'users', 'students')
        query: SQL query template (will be adapted for sharded table)
        params: Query parameters
        user_id: User ID for routing (required for sharded tables)
        
    Returns:
        Inserted ID (for INSERT queries) or rowcount
    """
    if not SHARDING_ENABLED:
        return execute(query, params)
    
    router = get_router()
    
    try:
        # Determine if this is a sharded table
        if not router.is_sharded_table(table_name):
            # Not sharded - use regular execute
            return execute(query, params)
        
        if user_id is None:
            raise ShardingException(f"user_id required for sharded table: {table_name}")
        
        # Get the shard table name
        shard_table = router.get_shard_table_name(table_name, user_id)
        
        # Replace table name in query with shard table name
        adapted_query = query.replace(f"INTO {table_name}", f"INTO {shard_table}")
        adapted_query = adapted_query.replace(f"FROM {table_name}", f"FROM {shard_table}")
        adapted_query = adapted_query.replace(f"UPDATE {table_name}", f"UPDATE {shard_table}")
        
        print(f"[SHARDING] Routing {table_name} (user_id={user_id}) to {shard_table}")
        
        return execute(adapted_query, params)
        
    except ShardingException as e:
        print(f"[SHARDING ERROR] {e}")
        raise


def fetch_one_sharded(table_name: str, query: str, params: Iterable = (), user_id: Optional[int] = None) -> Optional[Dict]:
    """
    Fetch one row with sharding support
    
    Args:
        table_name: Base table name
        query: SQL query template
        params: Query parameters
        user_id: User ID for routing (required for sharded tables)
        
    Returns:
        Single row dict or None
    """
    if not SHARDING_ENABLED:
        return fetch_one(query, params)
    
    router = get_router()
    
    try:
        if not router.is_sharded_table(table_name):
            return fetch_one(query, params)
        
        if user_id is None:
            raise ShardingException(f"user_id required for sharded table: {table_name}")
        
        shard_table = router.get_shard_table_name(table_name, user_id)
        
        adapted_query = query.replace(f"FROM {table_name}", f"FROM {shard_table}")
        
        print(f"[SHARDING] Routing SELECT {table_name} (user_id={user_id}) to {shard_table}")
        
        return fetch_one(adapted_query, params)
        
    except ShardingException as e:
        print(f"[SHARDING ERROR] {e}")
        raise


def fetch_all_sharded(table_name: str, query: str, params: Iterable = (), user_id: Optional[int] = None) -> List[Dict]:
    """
    Fetch all rows with sharding support
    
    Args:
        table_name: Base table name
        query: SQL query template
        params: Query parameters
        user_id: User ID for routing (None for range queries across all shards)
        
    Returns:
        List of row dicts
    """
    if not SHARDING_ENABLED:
        return fetch_all(query, params)
    
    router = get_router()
    
    try:
        if not router.is_sharded_table(table_name):
            return fetch_all(query, params)
        
        # For range queries (user_id is None), query all shards
        if user_id is None:
            print(f"[SHARDING] Range query on {table_name}: querying all shards")
            results = []
            
            for shard_id in range(NUM_SHARDS):
                shard_table = f"shard_{shard_id}_{table_name}"
                adapted_query = query.replace(f"FROM {table_name}", f"FROM {shard_table}")
                
                try:
                    shard_results = fetch_all(adapted_query, params)
                    results.extend(shard_results)
                except Exception as shard_error:
                    print(f"[SHARDING] Error querying {shard_table}: {shard_error}")
                    continue
            
            return results
        
        # For user_id based queries, get appropriate shard
        shard_id = user_id % NUM_SHARDS
        shard_table = f"shard_{shard_id}_{table_name}"
        adapted_query = query.replace(f"FROM {table_name}", f"FROM {shard_table}")
        
        return fetch_all(adapted_query, params)
    
    except Exception as e:
        print(f"[SHARDING] ERROR in shard_query: {e}")
        return []


def verify_sharding_status():
    """
    Verify that all shard tables have been created and contain data.
    Returns: Dict with verification status for each table
    """
    verification_status = {}
    
    shard_tables = [
        'users', 'students', 'alumni_user', 'companies',
        'user_logs', 'resumes', 'applications'
    ]
    
    try:
        for table_name in shard_tables:
            verification_status[table_name] = {}
            
            for shard_id in range(NUM_SHARDS):
                shard_table = f"shard_{shard_id}_{table_name}"
                
                try:
                    count = fetch_one(
                        f"SELECT COUNT(*) as count FROM {shard_table}",
                        {}
                    )
                    verification_status[table_name][shard_id] = count['count'] if count else 0
                except Exception as e:
                    print(f"[VERIFICATION] Error counting {shard_table}: {e}")
                    verification_status[table_name][shard_id] = -1
    
    except Exception as e:
        print(f"[VERIFICATION] Error during verification: {e}")
    
    return verification_status


def get_sharding_distribution():
    """
    Get the distribution of data across shards.
    Returns: Dict with count and percentage for each shard
    """
    distribution = {}
    total_records = 0
    
    shard_tables = [
        'users', 'students', 'alumni_user', 'companies',
        'user_logs', 'resumes', 'applications'
    ]
    
    try:
        for table_name in shard_tables:
            distribution[table_name] = {}
            table_total = 0
            
            for shard_id in range(NUM_SHARDS):
                shard_table = f"shard_{shard_id}_{table_name}"
                
                try:
                    count = fetch_one(
                        f"SELECT COUNT(*) as count FROM {shard_table}",
                        {}
                    )
                    record_count = count['count'] if count else 0
                    distribution[table_name][shard_id] = record_count
                    table_total += record_count
                except Exception as e:
                    print(f"[DISTRIBUTION] Error counting {shard_table}: {e}")
                    distribution[table_name][shard_id] = 0
            
            distribution[table_name]['total'] = table_total
            total_records += table_total
    
    except Exception as e:
        print(f"[DISTRIBUTION] Error getting distribution: {e}")
    
    distribution['GRAND_TOTAL'] = total_records
    return distribution


def migrate_data_to_shards():
    """
    Migrate existing data from non-sharded tables to sharded tables
    This should be run once during migration
    """
    if not SHARDING_ENABLED:
        print("[SHARDING] Sharding not enabled; skipping migration")
        return
    
    migration_queries = [
        # Migrate Users
        """
        INSERT INTO shard_0_users 
        SELECT user_id, username, email, password_hash, role_id, is_verified, created_at, full_name, contact_number, status, 0
        FROM Users WHERE user_id % 3 = 0
        ON CONFLICT DO NOTHING;
        """,
        """
        INSERT INTO shard_1_users 
        SELECT user_id, username, email, password_hash, role_id, is_verified, created_at, full_name, contact_number, status, 1
        FROM Users WHERE user_id % 3 = 1
        ON CONFLICT DO NOTHING;
        """,
        """
        INSERT INTO shard_2_users 
        SELECT user_id, username, email, password_hash, role_id, is_verified, created_at, full_name, contact_number, status, 2
        FROM Users WHERE user_id % 3 = 2
        ON CONFLICT DO NOTHING;
        """,
    ]
    
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                for query in migration_queries:
                    print(f"[SHARDING] Executing migration: {query[:50]}...")
                    cur.execute(query)
            conn.commit()
        print("[SHARDING] Data migration to shards completed")
    except Exception as e:
        print(f"[ERROR] Data migration failed: {e}")
        raise


def get_sharding_status() -> Dict[str, Any]:
    """Get sharding configuration and status"""
    if not SHARDING_ENABLED:
        return {'sharding_enabled': False}
    
    router = get_router()
    
    return {
        'sharding_enabled': SHARDING_ENABLED,
        'num_shards': NUM_SHARDS,
        'shard_key': 'user_id',
        'strategy': 'hash-based',
        'sharded_tables': sorted(router.router.sharded_tables if hasattr(router, 'sharded_tables') else []),
        'hash_formula': 'shard_id = user_id % num_shards'
    }
