#!/usr/bin/env python3
"""
Remote MySQL Sharding Deployment Script
Deploys and tests remote sharding on 10.0.116.184:3307/3308/3309
"""

import mysql.connector
from mysql.connector import Error
import logging
import sys
from typing import Dict, List, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Shard Configuration
SHARDS = {
    0: {"host": "10.0.116.184", "port": 3307, "db": "Machine_minds"},
    1: {"host": "10.0.116.184", "port": 3308, "db": "Machine_minds"},
    2: {"host": "10.0.116.184", "port": 3309, "db": "Machine_minds"}
}

DB_USER = "Machine_minds"
DB_PASSWORD = "password@123"

class RemoteShardingDeployer:
    """Handles deployment of sharding to remote MySQL instances"""
    
    def test_connectivity(self) -> bool:
        """Test connectivity to all shards"""
        logger.info("=" * 70)
        logger.info("STEP 1: Testing Remote Shard Connectivity")
        logger.info("=" * 70)
        
        all_connected = True
        
        for shard_id, config in SHARDS.items():
            try:
                conn = mysql.connector.connect(
                    host=config["host"],
                    port=config["port"],
                    user=DB_USER,
                    password=DB_PASSWORD,
                    database=config["db"]
                )
                
                cursor = conn.cursor()
                cursor.execute("SELECT @@hostname;")
                hostname = cursor.fetchone()[0]
                
                logger.info(f"[SHARD {shard_id}] Connected to {config['host']}:{config['port']}")
                logger.info(f"[SHARD {shard_id}] Hostname: {hostname}")
                
                cursor.close()
                conn.close()
            
            except Error as e:
                logger.error(f"[SHARD {shard_id}] Connection failed: {e}")
                all_connected = False
        
        if all_connected:
            logger.info("\n[OK] All shards are accessible!\n")
        else:
            logger.error("\n[ERROR] Some shards are not accessible!\n")
        
        return all_connected
    
    def create_schema(self) -> bool:
        """Create shard tables on each remote shard"""
        logger.info("=" * 70)
        logger.info("STEP 2: Creating Shard Tables on Remote Instances")
        logger.info("=" * 70)
        
        schema_files = {
            0: "sql/schema_shard0.sql",
            1: "sql/schema_shard1.sql",
            2: "sql/schema_shard2.sql"
        }
        
        all_created = True
        
        for shard_id, schema_file in schema_files.items():
            try:
                conn = mysql.connector.connect(
                    host=SHARDS[shard_id]["host"],
                    port=SHARDS[shard_id]["port"],
                    user=DB_USER,
                    password=DB_PASSWORD,
                    database=SHARDS[shard_id]["db"],
                    autocommit=False  # Keep all statements in transaction
                )
                
                cursor = conn.cursor()
                
                # Read SQL file
                try:
                    with open(schema_file, 'r') as f:
                        sql_content = f.read()
                    
                    # CRITICAL: Disable foreign key checks first
                    cursor.execute("SET FOREIGN_KEY_CHECKS=0;")
                    logger.debug(f"[SHARD {shard_id}] Foreign key checks disabled")
                    
                    # Split statements by semicolon
                    statements = [s.strip() for s in sql_content.split(';') if s.strip()]
                    
                    success_count = 0
                    
                    for i, statement in enumerate(statements):
                        # Skip comments
                        if statement.strip().startswith('--'):
                            continue
                        
                        try:
                            cursor.execute(statement)
                            success_count += 1
                            logger.debug(f"[SHARD {shard_id}] Statement {i+1} executed")
                        except Error as stmt_error:
                            error_msg = str(stmt_error)
                            # Foreign key errors are expected during schema creation, skip them
                            if "1824" in error_msg or "FOREIGN KEY" in error_msg:
                                logger.debug(f"[SHARD {shard_id}] Skipped FK error: {error_msg}")
                                continue
                            else:
                                logger.warning(f"[SHARD {shard_id}] Statement {i+1} error: {stmt_error}")
                    
                    # Re-enable foreign key checks
                    cursor.execute("SET FOREIGN_KEY_CHECKS=1;")
                    logger.debug(f"[SHARD {shard_id}] Foreign key checks re-enabled")
                    
                    # Commit all changes as single transaction
                    conn.commit()
                    logger.info(f"[SHARD {shard_id}] Schema created successfully ({success_count} statements)")
                
                except FileNotFoundError:
                    logger.warning(f"[SHARD {shard_id}] Schema file not found: {schema_file}")
                    logger.info(f"[SHARD {shard_id}] Skipping schema creation")
                
                cursor.close()
                conn.close()
            
            except Error as e:
                logger.error(f"[SHARD {shard_id}] Schema creation failed: {e}")
                all_created = False
        
        if all_created:
            logger.info("\n[OK] All shard schemas created!\n")
        else:
            logger.warning("\n[WARNING] Some schemas may not have been created\n")
        
        return all_created
    
    def verify_tables(self) -> bool:
        """Verify that all tables exist on remote shards"""
        logger.info("=" * 70)
        logger.info("STEP 3: Verifying Table Creation")
        logger.info("=" * 70)
        
        expected_tables = {
            0: ["shard_0_users", "shard_0_students", "shard_0_alumni_user", 
                "shard_0_companies", "shard_0_user_logs", "shard_0_resumes", "shard_0_applications"],
            1: ["shard_1_users", "shard_1_students", "shard_1_alumni_user",
                "shard_1_companies", "shard_1_user_logs", "shard_1_resumes", "shard_1_applications"],
            2: ["shard_2_users", "shard_2_students", "shard_2_alumni_user",
                "shard_2_companies", "shard_2_user_logs", "shard_2_resumes", "shard_2_applications"]
        }
        
        all_verified = True
        
        for shard_id, tables in expected_tables.items():
            try:
                conn = mysql.connector.connect(
                    host=SHARDS[shard_id]["host"],
                    port=SHARDS[shard_id]["port"],
                    user=DB_USER,
                    password=DB_PASSWORD,
                    database=SHARDS[shard_id]["db"]
                )
                
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES 
                    WHERE TABLE_SCHEMA = %s
                """, (SHARDS[shard_id]["db"],))
                
                existing_tables = [row[0] for row in cursor.fetchall()]
                
                logger.info(f"\n[SHARD {shard_id}] Tables on remote shard:")
                
                for table in tables:
                    if table in existing_tables:
                        logger.info(f"  [OK] {table}")
                    else:
                        logger.warning(f"  [MISSING] {table}")
                        all_verified = False
                
                cursor.close()
                conn.close()
            
            except Error as e:
                logger.error(f"[SHARD {shard_id}] Verification failed: {e}")
                all_verified = False
        
        if all_verified:
            logger.info("\n[OK] All tables verified!\n")
        else:
            logger.warning("\n[WARNING] Some tables are missing!\n")
        
        return all_verified
    
    def get_statistics(self) -> Dict:
        """Get statistics about remote shards"""
        logger.info("=" * 70)
        logger.info("STEP 4: Collecting Remote Shard Statistics")
        logger.info("=" * 70)
        
        stats = {}
        
        for shard_id in range(3):
            try:
                conn = mysql.connector.connect(
                    host=SHARDS[shard_id]["host"],
                    port=SHARDS[shard_id]["port"],
                    user=DB_USER,
                    password=DB_PASSWORD,
                    database=SHARDS[shard_id]["db"]
                )
                
                cursor = conn.cursor()
                
                shard_stats = {}
                tables = ["users", "students", "alumni_user", "companies", 
                         "user_logs", "resumes", "applications"]
                
                logger.info(f"\n[SHARD {shard_id}] Table Statistics:")
                
                for table in tables:
                    table_name = f"shard_{shard_id}_{table}"
                    
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                        count = cursor.fetchone()[0]
                        shard_stats[table] = count
                        logger.info(f"  {table_name:30} : {count:5} rows")
                    except Error:
                        shard_stats[table] = 0
                        logger.warning(f"  {table_name:30} : NOT FOUND")
                
                shard_stats['total'] = sum(shard_stats.values())
                logger.info(f"  {'TOTAL':30} : {shard_stats['total']:5} rows")
                
                stats[shard_id] = shard_stats
                cursor.close()
                conn.close()
            
            except Error as e:
                logger.error(f"[SHARD {shard_id}] Statistics collection failed: {e}")
        
        # Calculate grand totals
        grand_total = sum(shard['total'] for shard in stats.values())
        
        logger.info(f"\n" + "=" * 70)
        logger.info(f"GRAND TOTAL (All Shards): {grand_total} rows")
        logger.info(f"Average per shard: {grand_total / 3:.0f} rows")
        logger.info(f"=" * 70 + "\n")
        
        return stats
    
    def display_phpmyadmin_info(self):
        """Display phpMyAdmin access information"""
        logger.info("=" * 70)
        logger.info("phpMyAdmin Access Information")
        logger.info("=" * 70)
        
        phpmyadmin_urls = {
            0: "http://10.0.116.184:8083",
            1: "http://10.0.116.184:8081",
            2: "http://10.0.116.184:8082"
        }
        
        for shard_id, url in phpmyadmin_urls.items():
            logger.info(f"\nShard {shard_id} (Port {SHARDS[shard_id]['port']}):")
            logger.info(f"  URL:      {url}")
            logger.info(f"  Username: Machine_minds")
            logger.info(f"  Password: password@123")
            logger.info(f"  Database: Machine_minds")
    
    def run_deployment(self):
        """Run full deployment process"""
        logger.info("\n")
        logger.info("#" * 70)
        logger.info("# REMOTE MySQL SHARDING DEPLOYMENT")
        logger.info("# Team: Machine_minds")
        logger.info("# Host: 10.0.116.184")
        logger.info("# Shards: 3 (Ports 3307, 3308, 3309)")
        logger.info("#" * 70)
        logger.info("\n")
        
        # Step 1: Test connectivity
        if not self.test_connectivity():
            logger.error("Deployment aborted: Cannot connect to shards")
            return False
        
        # Step 2: Create schema
        self.create_schema()
        
        # Step 3: Verify tables
        if not self.verify_tables():
            logger.warning("Some tables may be missing")
        
        # Step 4: Collect statistics
        stats = self.get_statistics()
        
        # Display phpMyAdmin info
        self.display_phpmyadmin_info()
        
        logger.info("\n")
        logger.info("=" * 70)
        logger.info("DEPLOYMENT COMPLETE")
        logger.info("=" * 70)
        logger.info("\nNext Steps:")
        logger.info("1. Verify tables via phpMyAdmin or MySQL CLI")
        logger.info("2. Migrate data from local/original tables to remote shards")
        logger.info("3. Test query routing in your application")
        logger.info("4. Implement range queries across shards")
        logger.info("\n")

def main():
    deployer = RemoteShardingDeployer()
    deployer.run_deployment()

if __name__ == "__main__":
    main()
