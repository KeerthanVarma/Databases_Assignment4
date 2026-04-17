"""
Unified Sharded Database Abstraction Layer
Provides transparent access to sharded MySQL database for Module B website
Handles query routing, cross-shard aggregation, and automatic data sync
"""

import mysql.connector
from mysql.connector import Error, pooling
from typing import Dict, List, Optional, Tuple, Any
import logging
import json
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Shard Configuration
SHARDS = {
    0: {"host": "10.0.116.184", "port": 3307, "db": "Machine_minds"},
    1: {"host": "10.0.116.184", "port": 3308, "db": "Machine_minds"},
    2: {"host": "10.0.116.184", "port": 3309, "db": "Machine_minds"}
}

DB_USER = "Machine_minds"
DB_PASSWORD = "password@123"


class ShardedDatabaseManager:
    """Manages unified access to sharded MySQL database"""
    
    def __init__(self):
        """Initialize connection pools for all shards"""
        self.pools = {}
        self._initialize_pools()
        logger.info("[SHARDED DB] Database manager initialized")
    
    def _initialize_pools(self):
        """Create connection pools for each shard"""
        for shard_id, config in SHARDS.items():
            try:
                pool = pooling.MySQLConnectionPool(
                    pool_name=f"web_shard_{shard_id}",
                    pool_size=5,
                    pool_reset_session=True,
                    host=config["host"],
                    port=config["port"],
                    database=config["db"],
                    user=DB_USER,
                    password=DB_PASSWORD
                )
                self.pools[shard_id] = pool
                logger.info(f"[SHARD {shard_id}] Pool initialized at {config['host']}:{config['port']}")
            except Error as e:
                logger.error(f"[SHARD {shard_id}] Pool initialization failed: {e}")
                raise
    
    @staticmethod
    def get_shard_id(user_id: int) -> int:
        """Calculate shard ID for user"""
        return user_id % 3
    
    @staticmethod
    def get_table_name(base_table: str, shard_id: int) -> str:
        """Get shard-specific table name"""
        return f"shard_{shard_id}_{base_table}"
    
    def get_connection(self, shard_id: int):
        """Get connection from pool"""
        if shard_id not in self.pools:
            raise ValueError(f"Invalid shard ID: {shard_id}")
        return self.pools[shard_id].get_connection()
    
    # ========== SINGLE SHARD QUERIES ==========
    
    def execute_on_shard(self, shard_id: int, query: str, params: tuple = None, 
                        auto_commit: bool = True) -> bool:
        """Execute write query on specific shard"""
        conn = None
        try:
            conn = self.get_connection(shard_id)
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            
            if auto_commit:
                conn.commit()
            
            cursor.close()
            return True
        except Error as e:
            logger.error(f"[SHARD {shard_id}] Query execution failed: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()
    
    def fetch_from_shard(self, shard_id: int, query: str, params: tuple = None) -> List[Dict]:
        """Fetch data from specific shard"""
        conn = None
        try:
            conn = self.get_connection(shard_id)
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, params or ())
            result = cursor.fetchall()
            cursor.close()
            return result
        except Error as e:
            logger.error(f"[SHARD {shard_id}] Fetch failed: {e}")
            return []
        finally:
            if conn:
                conn.close()
    
    # ========== MULTI-SHARD QUERIES ==========
    
    def fetch_from_all_shards(self, query_template: str, params: tuple = None) -> List[Dict]:
        """Execute query on all shards and aggregate results"""
        all_results = []
        for shard_id in SHARDS.keys():
            query = query_template.replace("{shard_id}", str(shard_id))
            results = self.fetch_from_shard(shard_id, query, params)
            all_results.extend(results)
        return all_results
    
    # ========== USER QUERIES ==========
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """Get user by ID from correct shard"""
        shard_id = self.get_shard_id(user_id)
        table_name = self.get_table_name("users", shard_id)
        
        query = f"""
        SELECT * FROM {table_name}
        WHERE user_id = %s
        """
        
        results = self.fetch_from_shard(shard_id, query, (user_id,))
        return results[0] if results else None
    
    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Get user by username (searches all shards)"""
        query_template = f"""
        SELECT * FROM shard_{{shard_id}}_users
        WHERE username = %s
        """
        results = self.fetch_from_all_shards(query_template, (username,))
        return results[0] if results else None
    
    def get_all_users_by_role(self, role_id: int) -> List[Dict]:
        """Get all users with specific role (across all shards)"""
        query_template = f"""
        SELECT * FROM shard_{{shard_id}}_users
        WHERE role_id = %s
        """
        return self.fetch_from_all_shards(query_template, (role_id,))
    
    def insert_user(self, user_id: int, username: str, email: str, 
                   password_hash: str, role_id: int, is_verified: bool,
                   full_name: str, contact_number: str, status: str) -> bool:
        """Insert user into correct shard"""
        shard_id = self.get_shard_id(user_id)
        table_name = self.get_table_name("users", shard_id)
        
        query = f"""
        INSERT INTO {table_name}
        (user_id, username, email, password_hash, role_id, is_verified,
         created_at, full_name, contact_number, status, shard_id)
        VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s, %s, %s, %s)
        """
        
        return self.execute_on_shard(
            shard_id, query,
            (user_id, username, email, password_hash, role_id, is_verified,
             full_name, contact_number, status, shard_id)
        )
    
    def update_user(self, user_id: int, updates: Dict[str, Any]) -> bool:
        """Update user in correct shard"""
        shard_id = self.get_shard_id(user_id)
        table_name = self.get_table_name("users", shard_id)
        
        # Build SET clause
        set_clauses = []
        values = []
        for key, value in updates.items():
            if key not in ["user_id", "shard_id"]:  # Prevent modification of keys
                set_clauses.append(f"{key} = %s")
                values.append(value)
        
        if not set_clauses:
            return False
        
        values.append(user_id)
        query = f"""
        UPDATE {table_name}
        SET {', '.join(set_clauses)}
        WHERE user_id = %s
        """
        
        return self.execute_on_shard(shard_id, query, tuple(values))
    
    # ========== STUDENT QUERIES ==========
    
    def get_student_by_user_id(self, user_id: int) -> Optional[Dict]:
        """Get student record by user_id"""
        shard_id = self.get_shard_id(user_id)
        table_name = self.get_table_name("students", shard_id)
        
        query = f"""
        SELECT * FROM {table_name}
        WHERE user_id = %s
        """
        
        results = self.fetch_from_shard(shard_id, query, (user_id,))
        return results[0] if results else None
    
    def get_all_students(self) -> List[Dict]:
        """Get all students (across all shards)"""
        query_template = f"""
        SELECT * FROM shard_{{shard_id}}_students
        """
        return self.fetch_from_all_shards(query_template)
    
    def insert_student(self, student_id: int, user_id: int, cpi: float,
                      program: str, discipline: str, graduating_year: int,
                      backlogs: int, gender: str) -> bool:
        """Insert student into correct shard"""
        shard_id = self.get_shard_id(user_id)
        table_name = self.get_table_name("students", shard_id)
        
        query = f"""
        INSERT INTO {table_name}
        (student_id, user_id, latest_cpi, program, discipline, graduating_year,
         active_backlogs, gender, shard_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        return self.execute_on_shard(
            shard_id, query,
            (student_id, user_id, cpi, program, discipline, graduating_year,
             backlogs, gender, shard_id)
        )
    
    # ========== COMPANY QUERIES ==========
    
    def get_company_by_user_id(self, user_id: int) -> Optional[Dict]:
        """Get company by recruiter user_id"""
        shard_id = self.get_shard_id(user_id)
        table_name = self.get_table_name("companies", shard_id)
        
        query = f"""
        SELECT * FROM {table_name}
        WHERE user_id = %s
        """
        
        results = self.fetch_from_shard(shard_id, query, (user_id,))
        return results[0] if results else None
    
    def get_all_companies(self) -> List[Dict]:
        """Get all companies (across all shards)"""
        query_template = f"""
        SELECT * FROM shard_{{shard_id}}_companies
        """
        return self.fetch_from_all_shards(query_template)
    
    def insert_company(self, company_id: int, user_id: int, company_name: str,
                      industry_sector: str, org_type: str) -> bool:
        """Insert company into correct shard"""
        shard_id = self.get_shard_id(user_id)
        table_name = self.get_table_name("companies", shard_id)
        
        query = f"""
        INSERT INTO {table_name}
        (company_id, user_id, company_name, industry_sector, type_of_organization, shard_id)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        
        return self.execute_on_shard(
            shard_id, query,
            (company_id, user_id, company_name, industry_sector, org_type, shard_id)
        )
    
    # ========== ALUMNI QUERIES ==========
    
    def get_alumni_by_user_id(self, user_id: int) -> Optional[Dict]:
        """Get alumni record by user_id"""
        shard_id = self.get_shard_id(user_id)
        table_name = self.get_table_name("alumni_user", shard_id)
        
        query = f"""
        SELECT * FROM {table_name}
        WHERE user_id = %s
        """
        
        results = self.fetch_from_shard(shard_id, query, (user_id,))
        return results[0] if results else None
    
    def get_all_alumni(self) -> List[Dict]:
        """Get all alumni (across all shards)"""
        query_template = f"""
        SELECT * FROM shard_{{shard_id}}_alumni_user
        """
        return self.fetch_from_all_shards(query_template)
    
    # ========== CROSS-SHARD ANALYTICS ==========
    
    def get_shard_statistics(self) -> Dict[int, Dict[str, int]]:
        """Get statistics for each shard"""
        stats = {}
        
        for shard_id in SHARDS.keys():
            try:
                conn = self.get_connection(shard_id)
                cursor = conn.cursor(dictionary=True)
                
                tables = ['users', 'students', 'companies', 'alumni_user']
                shard_stats = {}
                
                for table in tables:
                    full_table = self.get_table_name(table, shard_id)
                    cursor.execute(f"SELECT COUNT(*) as cnt FROM {full_table}")
                    shard_stats[table] = cursor.fetchone()['cnt']
                
                cursor.close()
                conn.close()
                stats[shard_id] = shard_stats
            except Error as e:
                logger.error(f"[SHARD {shard_id}] Stats fetch failed: {e}")
        
        return stats
    
    def log_query_analytics(self, query_type: str, shard_id: int, 
                           execution_time_ms: float, success: bool):
        """Log query execution for analytics"""
        logger.info(f"[QUERY] Type: {query_type}, Shard: {shard_id}, "
                   f"Time: {execution_time_ms}ms, Success: {success}")


# Global database manager instance
db_manager = None


def get_db_manager() -> ShardedDatabaseManager:
    """Get or create global database manager"""
    global db_manager
    if db_manager is None:
        db_manager = ShardedDatabaseManager()
    return db_manager


def initialize_sharded_db():
    """Initialize sharded database manager"""
    global db_manager
    db_manager = ShardedDatabaseManager()
    return db_manager
