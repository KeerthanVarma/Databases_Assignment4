"""
Remote MySQL Sharding Manager
Handles shard routing, connection pooling, and distributed queries
"""

import mysql.connector
from mysql.connector import pooling, Error
from typing import Dict, List, Optional, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Shard Configuration
SHARDS = {
    0: {"host": "10.0.116.184", "port": 3307, "db": "Machine_minds"},
    1: {"host": "10.0.116.184", "port": 3308, "db": "Machine_minds"},
    2: {"host": "10.0.116.184", "port": 3309, "db": "Machine_minds"}
}

# Connection Credentials
DB_USER = "Machine_minds"
DB_PASSWORD = "password@123"

# Connection pools for each shard
connection_pools = {}

class RemoteShardingManager:
    """Manages connections and queries across remote MySQL shards"""
    
    def __init__(self):
        """Initialize connection pools for all shards"""
        self.initialize_connection_pools()
    
    def initialize_connection_pools(self):
        """Create connection pools for each shard"""
        for shard_id, config in SHARDS.items():
            try:
                pool_name = f"shard_{shard_id}_pool"
                pool = pooling.MySQLConnectionPool(
                    pool_name=pool_name,
                    pool_size=5,
                    pool_reset_session=True,
                    host=config["host"],
                    port=config["port"],
                    database=config["db"],
                    user=DB_USER,
                    password=DB_PASSWORD
                )
                connection_pools[shard_id] = pool
                logger.info(f"[SHARD {shard_id}] Connection pool initialized: {config['host']}:{config['port']}")
            except Error as e:
                logger.error(f"[SHARD {shard_id}] Failed to initialize pool: {e}")
    
    @staticmethod
    def get_shard_id(user_id: int) -> int:
        """Calculate shard ID for user using hash function"""
        return user_id % 3
    
    def get_connection(self, shard_id: int):
        """Get connection from pool for specific shard"""
        try:
            if shard_id not in connection_pools:
                raise ValueError(f"Invalid shard ID: {shard_id}")
            
            conn = connection_pools[shard_id].get_connection()
            logger.debug(f"[SHARD {shard_id}] Connection obtained from pool")
            return conn
        except Error as e:
            logger.error(f"[SHARD {shard_id}] Failed to get connection: {e}")
            raise
    
    def get_table_name(self, base_table: str, shard_id: int) -> str:
        """Get shard-specific table name"""
        return f"shard_{shard_id}_{base_table}"
    
    # ========== TASK 4: Route Inserts to Correct Shard ==========
    
    def insert_user(self, user_id: int, username: str, email: str, 
                    password_hash: str, role_id: int, is_verified: bool,
                    created_at: str, full_name: str, contact_number: str,
                    status: str) -> bool:
        """Insert user into correct shard based on user_id"""
        shard_id = self.get_shard_id(user_id)
        table_name = self.get_table_name("users", shard_id)
        
        try:
            conn = self.get_connection(shard_id)
            cursor = conn.cursor()
            
            sql = f"""
            INSERT INTO {table_name} 
            (user_id, username, email, password_hash, role_id, is_verified, 
             created_at, full_name, contact_number, status, shard_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            values = (user_id, username, email, password_hash, role_id, 
                     is_verified, created_at, full_name, contact_number, 
                     status, shard_id)
            
            cursor.execute(sql, values)
            conn.commit()
            
            logger.info(f"[SHARD {shard_id}] User {user_id} inserted into {table_name}")
            return True
        
        except Error as e:
            logger.error(f"[SHARD {shard_id}] Error inserting user {user_id}: {e}")
            return False
        
        finally:
            cursor.close()
            conn.close()
    
    def insert_student(self, student_id: int, user_id: int, latest_cpi: float,
                      program: str, discipline: str, graduating_year: int,
                      active_backlogs: int, gender: str, tenth_percent: float,
                      tenth_passout_year: int, twelfth_percent: float,
                      twelfth_passout_year: int) -> bool:
        """Insert student into correct shard"""
        shard_id = self.get_shard_id(user_id)
        table_name = self.get_table_name("students", shard_id)
        
        try:
            conn = self.get_connection(shard_id)
            cursor = conn.cursor()
            
            sql = f"""
            INSERT INTO {table_name}
            (student_id, user_id, latest_cpi, program, discipline, graduating_year,
             active_backlogs, gender, tenth_percent, tenth_passout_year,
             twelfth_percent, twelfth_passout_year, shard_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            values = (student_id, user_id, latest_cpi, program, discipline,
                     graduating_year, active_backlogs, gender, tenth_percent,
                     tenth_passout_year, twelfth_percent, twelfth_passout_year,
                     shard_id)
            
            cursor.execute(sql, values)
            conn.commit()
            
            logger.info(f"[SHARD {shard_id}] Student {student_id} (user_id={user_id}) inserted")
            return True
        
        except Error as e:
            logger.error(f"[SHARD {shard_id}] Error inserting student: {e}")
            return False
        
        finally:
            cursor.close()
            conn.close()
    
    # ========== TASK 5: Route Lookups Correctly ==========
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """Get user from correct shard using user_id"""
        shard_id = self.get_shard_id(user_id)
        table_name = self.get_table_name("users", shard_id)
        
        try:
            conn = self.get_connection(shard_id)
            cursor = conn.cursor(dictionary=True)
            
            sql = f"SELECT * FROM {table_name} WHERE user_id = %s"
            cursor.execute(sql, (user_id,))
            
            result = cursor.fetchone()
            logger.info(f"[SHARD {shard_id}] Lookup user_id={user_id} {'found' if result else 'not found'}")
            return result
        
        except Error as e:
            logger.error(f"[SHARD {shard_id}] Error looking up user {user_id}: {e}")
            return None
        
        finally:
            cursor.close()
            conn.close()
    
    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Search for user by username - must query all shards"""
        logger.info(f"[CROSS-SHARD] Searching for username='{username}'")
        
        for shard_id in range(3):
            try:
                conn = self.get_connection(shard_id)
                cursor = conn.cursor(dictionary=True)
                
                table_name = self.get_table_name("users", shard_id)
                sql = f"SELECT * FROM {table_name} WHERE username = %s"
                cursor.execute(sql, (username,))
                
                result = cursor.fetchone()
                if result:
                    logger.info(f"[SHARD {shard_id}] Found username '{username}'")
                    cursor.close()
                    conn.close()
                    return result
                
                cursor.close()
                conn.close()
            
            except Error as e:
                logger.error(f"[SHARD {shard_id}] Error searching for username: {e}")
        
        logger.warning(f"[CROSS-SHARD] Username '{username}' not found in any shard")
        return None
    
    def get_student_by_user_id(self, user_id: int) -> Optional[Dict]:
        """Get student record for user from correct shard"""
        shard_id = self.get_shard_id(user_id)
        table_name = self.get_table_name("students", shard_id)
        
        try:
            conn = self.get_connection(shard_id)
            cursor = conn.cursor(dictionary=True)
            
            sql = f"SELECT * FROM {table_name} WHERE user_id = %s"
            cursor.execute(sql, (user_id,))
            
            result = cursor.fetchone()
            logger.info(f"[SHARD {shard_id}] Student lookup for user_id={user_id} {'found' if result else 'not found'}")
            return result
        
        except Error as e:
            logger.error(f"[SHARD {shard_id}] Error looking up student: {e}")
            return None
        
        finally:
            cursor.close()
            conn.close()
    
    # ========== TASK 6: Handle Range Queries Across Shards ==========
    
    def get_users_with_high_cpi(self, min_cpi: float) -> List[Dict]:
        """Range query: Get all students with CPI > min_cpi across all shards"""
        logger.info(f"[CROSS-SHARD] Range query: students with CPI > {min_cpi}")
        
        results = []
        
        for shard_id in range(3):
            try:
                conn = self.get_connection(shard_id)
                cursor = conn.cursor(dictionary=True)
                
                students_table = self.get_table_name("students", shard_id)
                users_table = self.get_table_name("users", shard_id)
                
                sql = f"""
                SELECT s.*, u.username, u.email
                FROM {students_table} s
                JOIN {users_table} u ON s.user_id = u.user_id
                WHERE s.latest_cpi > %s
                ORDER BY s.latest_cpi DESC
                """
                
                cursor.execute(sql, (min_cpi,))
                rows = cursor.fetchall()
                
                logger.info(f"[SHARD {shard_id}] Found {len(rows)} students with CPI > {min_cpi}")
                results.extend(rows)
                
                cursor.close()
                conn.close()
            
            except Error as e:
                logger.error(f"[SHARD {shard_id}] Error in range query: {e}")
        
        # Sort aggregated results
        results.sort(key=lambda x: x['latest_cpi'], reverse=True)
        logger.info(f"[CROSS-SHARD] Total {len(results)} students returned from all shards")
        return results
    
    def get_user_logs_date_range(self, start_date: str, end_date: str) -> List[Dict]:
        """Range query: Get user logs from all shards within date range"""
        logger.info(f"[CROSS-SHARD] Range query: logs between {start_date} and {end_date}")
        
        results = []
        
        for shard_id in range(3):
            try:
                conn = self.get_connection(shard_id)
                cursor = conn.cursor(dictionary=True)
                
                table_name = self.get_table_name("user_logs", shard_id)
                
                sql = f"""
                SELECT * FROM {table_name}
                WHERE start_time >= %s AND start_time <= %s
                ORDER BY start_time DESC
                """
                
                cursor.execute(sql, (start_date, end_date))
                rows = cursor.fetchall()
                
                logger.info(f"[SHARD {shard_id}] Found {len(rows)} logs in date range")
                results.extend(rows)
                
                cursor.close()
                conn.close()
            
            except Error as e:
                logger.error(f"[SHARD {shard_id}] Error in date range query: {e}")
        
        # Sort aggregated results by timestamp
        results.sort(key=lambda x: x['start_time'], reverse=True)
        logger.info(f"[CROSS-SHARD] Total {len(results)} logs returned from all shards")
        return results
    
    def get_all_users(self) -> List[Dict]:
        """Get all users from all shards"""
        logger.info("[CROSS-SHARD] Fetching all users from all shards")
        
        results = []
        
        for shard_id in range(3):
            try:
                conn = self.get_connection(shard_id)
                cursor = conn.cursor(dictionary=True)
                
                table_name = self.get_table_name("users", shard_id)
                sql = f"SELECT * FROM {table_name} ORDER BY user_id"
                
                cursor.execute(sql)
                rows = cursor.fetchall()
                
                logger.info(f"[SHARD {shard_id}] Retrieved {len(rows)} users")
                results.extend(rows)
                
                cursor.close()
                conn.close()
            
            except Error as e:
                logger.error(f"[SHARD {shard_id}] Error fetching users: {e}")
        
        # Sort by user_id
        results.sort(key=lambda x: x['user_id'])
        logger.info(f"[CROSS-SHARD] Total {len(results)} users from all shards")
        return results
    
    def get_statistics(self) -> Dict:
        """Get statistics about data distribution across shards"""
        logger.info("[CROSS-SHARD] Collecting statistics")
        
        stats = {
            "shards": {}
        }
        
        for shard_id in range(3):
            try:
                conn = self.get_connection(shard_id)
                cursor = conn.cursor(dictionary=True)
                
                shard_stats = {}
                
                # Count for each table
                tables = ["users", "students", "alumni_user", "companies", 
                         "user_logs", "resumes", "applications"]
                
                for table in tables:
                    table_name = self.get_table_name(table, shard_id)
                    sql = f"SELECT COUNT(*) as count FROM {table_name}"
                    cursor.execute(sql)
                    result = cursor.fetchone()
                    shard_stats[table] = result['count'] if result else 0
                
                shard_stats['total'] = sum(shard_stats.values())
                stats['shards'][shard_id] = shard_stats
                
                cursor.close()
                conn.close()
            
            except Error as e:
                logger.error(f"[SHARD {shard_id}] Error collecting statistics: {e}")
        
        # Calculate grand totals
        stats['grand_total'] = sum(
            shard_data['total'] 
            for shard_data in stats['shards'].values()
        )
        
        logger.info(f"[CROSS-SHARD] Grand total records: {stats['grand_total']}")
        return stats

# Global instance
remote_shard_manager = RemoteShardingManager()

# Convenience functions
def get_shard_id(user_id: int) -> int:
    """Get shard ID for user"""
    return remote_shard_manager.get_shard_id(user_id)

def get_user_by_id(user_id: int) -> Optional[Dict]:
    """Get user from correct shard"""
    return remote_shard_manager.get_user_by_id(user_id)

def insert_user(**kwargs) -> bool:
    """Insert user into correct shard"""
    return remote_shard_manager.insert_user(**kwargs)

def get_statistics() -> Dict:
    """Get cross-shard statistics"""
    return remote_shard_manager.get_statistics()
