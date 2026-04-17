#!/usr/bin/env python3
"""
Comprehensive Data Migration Script
Migrates all production data from schema_fixed.sql into remote MySQL shards
Handles proper data distribution across shards based on user_id
"""

import mysql.connector
from mysql.connector import Error, pooling
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(asctime)s - %(message)s'
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

class DataMigrator:
    """Handles migration of production data into shards"""
    
    def __init__(self):
        """Initialize connection pools"""
        self.pools = {}
        self.connections = {}
        self._initialize_pools()
    
    def _initialize_pools(self):
        """Create connection pools for each shard"""
        for shard_id, config in SHARDS.items():
            try:
                pool = pooling.MySQLConnectionPool(
                    pool_name=f"migrate_shard_{shard_id}",
                    pool_size=3,
                    host=config["host"],
                    port=config["port"],
                    database=config["db"],
                    user=DB_USER,
                    password=DB_PASSWORD
                )
                self.pools[shard_id] = pool
                logger.info(f"[SHARD {shard_id}] Pool initialized")
            except Error as e:
                logger.error(f"[SHARD {shard_id}] Pool initialization failed: {e}")
                raise
    
    def get_connection(self, shard_id: int):
        """Get connection for shard"""
        return self.pools[shard_id].get_connection()
    
    @staticmethod
    def get_shard_id(user_id: int) -> int:
        """Calculate shard ID"""
        return user_id % 3
    
    @staticmethod
    def get_table_name(base_name: str, shard_id: int) -> str:
        """Get shard-specific table name"""
        return f"shard_{shard_id}_{base_name}"
    
    # ========== MIGRATION METHODS ==========
    
    def migrate_roles(self):
        """Migrate roles (replicate to all shards)"""
        logger.info("\n" + "="*70)
        logger.info("MIGRATING: Roles")
        logger.info("="*70)
        
        roles_data = [
            (1, 'Student', 'Current student eligible for placements'),
            (2, 'Recruiter', 'Company representative posting jobs and hiring students'),
            (3, 'CDS Team', 'Placement cell coordinators managing drives'),
            (4, 'CDS Manager', 'Head of Career Development and Placement Services'),
            (5, 'Alumni', 'Graduated student providing referrals, guidance, and training')
        ]
        
        for shard_id in SHARDS.keys():
            try:
                conn = self.get_connection(shard_id)
                cursor = conn.cursor()
                
                for role_id, role_name, description in roles_data:
                    sql = f"""
                    INSERT IGNORE INTO roles (role_id, role_name, description)
                    VALUES (%s, %s, %s)
                    """
                    cursor.execute(sql, (role_id, role_name, description))
                
                conn.commit()
                logger.info(f"[SHARD {shard_id}] ✓ Inserted {len(roles_data)} roles")
                cursor.close()
                conn.close()
            except Error as e:
                logger.error(f"[SHARD {shard_id}] ✗ Failed to insert roles: {e}")
    
    def migrate_users(self):
        """Migrate users to correct shards"""
        logger.info("\n" + "="*70)
        logger.info("MIGRATING: Users (Distributed by user_id % 3)")
        logger.info("="*70)
        
        # Complete user data from schema_fixed.sql
        users_data = [
            # Students (user_id 1-30)
            (1, 'student1', 'aarav.patel@gmail.com', 'hash1', 1, True, 'Aarav Patel', '+919876540001', 'ACTIVE'),
            (2, 'student2', 'vivaan.shah@gmail.com', 'hash2', 1, True, 'Vivaan Shah', '+919876540002', 'ACTIVE'),
            (3, 'student3', 'aditya.mehta@gmail.com', 'hash3', 1, True, 'Aditya Mehta', '+919876540003', 'ACTIVE'),
            (4, 'student4', 'krishna.patel@gmail.com', 'hash4', 1, True, 'Krishna Patel', '+919876540004', 'ACTIVE'),
            (5, 'student5', 'ishaan.shah@gmail.com', 'hash5', 1, True, 'Ishaan Shah', '+919876540005', 'ACTIVE'),
            (6, 'student6', 'rohan.desai@gmail.com', 'hash6', 1, True, 'Rohan Desai', '+919876540006', 'ACTIVE'),
            (7, 'student7', 'arjun.joshi@gmail.com', 'hash7', 1, True, 'Arjun Joshi', '+919876540007', 'ACTIVE'),
            (8, 'student8', 'dhruv.patel@gmail.com', 'hash8', 1, True, 'Dhruv Patel', '+919876540008', 'ACTIVE'),
            (9, 'student9', 'kabir.shah@gmail.com', 'hash9', 1, True, 'Kabir Shah', '+919876540009', 'ACTIVE'),
            (10, 'student10', 'dev.patel@gmail.com', 'hash10', 1, True, 'Dev Patel', '+919876540010', 'ACTIVE'),
            (11, 'student11', 'jay.shah@gmail.com', 'hash11', 1, True, 'Jay Shah', '+919876540011', 'ACTIVE'),
            (12, 'student12', 'neel.mehta@gmail.com', 'hash12', 1, True, 'Neel Mehta', '+919876540012', 'ACTIVE'),
            (13, 'student13', 'om.patel@gmail.com', 'hash13', 1, True, 'Om Patel', '+919876540013', 'ACTIVE'),
            (14, 'student14', 'raj.shah@gmail.com', 'hash14', 1, True, 'Raj Shah', '+919876540014', 'ACTIVE'),
            (15, 'student15', 'karan.patel@gmail.com', 'hash15', 1, True, 'Karan Patel', '+919876540015', 'ACTIVE'),
            (16, 'student16', 'aryan.shah@gmail.com', 'hash16', 1, True, 'Aryan Shah', '+919876540016', 'ACTIVE'),
            (17, 'student17', 'harsh.patel@gmail.com', 'hash17', 1, True, 'Harsh Patel', '+919876540017', 'ACTIVE'),
            (18, 'student18', 'yash.shah@gmail.com', 'hash18', 1, True, 'Yash Shah', '+919876540018', 'ACTIVE'),
            (19, 'student19', 'meet.patel@gmail.com', 'hash19', 1, True, 'Meet Patel', '+919876540019', 'ACTIVE'),
            (20, 'student20', 'parth.shah@gmail.com', 'hash20', 1, True, 'Parth Shah', '+919876540020', 'ACTIVE'),
            (21, 'student21', 'nirav.patel@gmail.com', 'hash21', 1, True, 'Nirav Patel', '+919876540021', 'ACTIVE'),
            (22, 'student22', 'vraj.shah@gmail.com', 'hash22', 1, True, 'Vraj Shah', '+919876540022', 'ACTIVE'),
            (23, 'student23', 'sahil.patel@gmail.com', 'hash23', 1, True, 'Sahil Patel', '+919876540023', 'ACTIVE'),
            (24, 'student24', 'manav.shah@gmail.com', 'hash24', 1, True, 'Manav Shah', '+919876540024', 'ACTIVE'),
            (25, 'student25', 'tirth.patel@gmail.com', 'hash25', 1, True, 'Tirth Patel', '+919876540025', 'ACTIVE'),
            (26, 'student26', 'kunal.shah@gmail.com', 'hash26', 1, True, 'Kunal Shah', '+919876540026', 'ACTIVE'),
            (27, 'student27', 'jatin.patel@gmail.com', 'hash27', 1, True, 'Jatin Patel', '+919876540027', 'ACTIVE'),
            (28, 'student28', 'deep.shah@gmail.com', 'hash28', 1, True, 'Deep Shah', '+919876540028', 'ACTIVE'),
            (29, 'student29', 'hiren.patel@gmail.com', 'hash29', 1, True, 'Hiren Patel', '+919876540029', 'ACTIVE'),
            (30, 'student30', 'rahul.shah@gmail.com', 'hash30', 1, True, 'Rahul Shah', '+919876540030', 'ACTIVE'),
            # Alumni (user_id 31-40)
            (31, 'alumni1', 'amit.shah@gmail.com', 'hash31', 5, True, 'Amit Shah', '+919876540031', 'ACTIVE'),
            (32, 'alumni2', 'rahul.mehta@gmail.com', 'hash32', 5, True, 'Rahul Mehta', '+919876540032', 'ACTIVE'),
            (33, 'alumni3', 'suresh.patel@gmail.com', 'hash33', 5, True, 'Suresh Patel', '+919876540033', 'ACTIVE'),
            (34, 'alumni4', 'mahesh.shah@gmail.com', 'hash34', 5, True, 'Mahesh Shah', '+919876540034', 'ACTIVE'),
            (35, 'alumni5', 'rajesh.patel@gmail.com', 'hash35', 5, True, 'Rajesh Patel', '+919876540035', 'ACTIVE'),
            (36, 'alumni6', 'anil.shah@gmail.com', 'hash36', 5, True, 'Anil Shah', '+919876540036', 'ACTIVE'),
            (37, 'alumni7', 'sunil.patel@gmail.com', 'hash37', 5, True, 'Sunil Patel', '+919876540037', 'ACTIVE'),
            (38, 'alumni8', 'rakesh.shah@gmail.com', 'hash38', 5, True, 'Rakesh Shah', '+919876540038', 'ACTIVE'),
            (39, 'alumni9', 'mukesh.patel@gmail.com', 'hash39', 5, True, 'Mukesh Patel', '+919876540039', 'ACTIVE'),
            (40, 'alumni10', 'naresh.shah@gmail.com', 'hash40', 5, True, 'Naresh Shah', '+919876540040', 'ACTIVE'),
            # Recruiters (user_id 41-55)
            (41, 'recruiter1', 'hr.tcs@gmail.com', 'hash41', 2, True, 'Priya Sharma', '+919876540041', 'ACTIVE'),
            (42, 'recruiter2', 'hr.infosys@gmail.com', 'hash42', 2, True, 'Anjali Verma', '+919876540042', 'ACTIVE'),
            (43, 'recruiter3', 'hr.google@gmail.com', 'hash43', 2, True, 'Sneha Iyer', '+919876540043', 'ACTIVE'),
            (44, 'recruiter4', 'hr.microsoft@gmail.com', 'hash44', 2, True, 'Riya Kapoor', '+919876540044', 'ACTIVE'),
            (45, 'recruiter5', 'hr.amazon@gmail.com', 'hash45', 2, True, 'Pooja Singh', '+919876540045', 'ACTIVE'),
            (46, 'recruiter6', 'hr.meta@gmail.com', 'hash46', 2, True, 'Neha Agarwal', '+919876540046', 'ACTIVE'),
            (47, 'recruiter7', 'hr.ibm@gmail.com', 'hash47', 2, True, 'Kavya Nair', '+919876540047', 'ACTIVE'),
            (48, 'recruiter8', 'hr.oracle@gmail.com', 'hash48', 2, True, 'Isha Menon', '+919876540048', 'ACTIVE'),
            (49, 'recruiter9', 'hr.intel@gmail.com', 'hash49', 2, True, 'Megha Pillai', '+919876540049', 'ACTIVE'),
            (50, 'recruiter10', 'hr.nvidia@gmail.com', 'hash50', 2, True, 'Nisha Reddy', '+919876540050', 'ACTIVE'),
            (51, 'recruiter11', 'hr.adobe@gmail.com', 'hash51', 2, True, 'Ritu Sharma', '+919876540051', 'ACTIVE'),
            (52, 'recruiter12', 'hr.salesforce@gmail.com', 'hash52', 2, True, 'Simran Kaur', '+919876540052', 'ACTIVE'),
            (53, 'recruiter13', 'hr.uber@gmail.com', 'hash53', 2, True, 'Divya Jain', '+919876540053', 'ACTIVE'),
            (54, 'recruiter14', 'hr.netflix@gmail.com', 'hash54', 2, True, 'Payal Gupta', '+919876540054', 'ACTIVE'),
            (55, 'recruiter15', 'hr.accenture@gmail.com', 'hash55', 2, True, 'Komal Shah', '+919876540055', 'ACTIVE'),
            # CDS Team (user_id 56-60)
            (56, 'cds1', 'cds1@college.edu', 'hash56', 3, True, 'Placement Coordinator 1', '+919876540056', 'ACTIVE'),
            (57, 'cds2', 'cds2@college.edu', 'hash57', 3, True, 'Placement Coordinator 2', '+919876540057', 'ACTIVE'),
            (58, 'cds3', 'cds3@college.edu', 'hash58', 3, True, 'Placement Coordinator 3', '+919876540058', 'ACTIVE'),
            (59, 'cds4', 'cds4@college.edu', 'hash59', 3, True, 'Placement Coordinator 4', '+919876540059', 'ACTIVE'),
            (60, 'cds5', 'cds5@college.edu', 'hash60', 3, True, 'Placement Coordinator 5', '+919876540060', 'ACTIVE'),
            # CDS Manager (user_id 61)
            (61, 'cdsmanager1', 'manager@college.edu', 'hash61', 4, True, 'Placement Manager', '+919876540061', 'ACTIVE'),
        ]
        
        total_inserted = 0
        shard_distribution = {0: 0, 1: 0, 2: 0}
        
        for user_id, username, email, pwd_hash, role_id, is_verified, full_name, contact, status in users_data:
            shard_id = self.get_shard_id(user_id)
            table_name = self.get_table_name("users", shard_id)
            
            try:
                conn = self.get_connection(shard_id)
                cursor = conn.cursor()
                
                sql = f"""
                INSERT IGNORE INTO {table_name}
                (user_id, username, email, password_hash, role_id, is_verified, 
                 created_at, full_name, contact_number, status, shard_id)
                VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s, %s, %s, %s)
                """
                
                cursor.execute(sql, (user_id, username, email, pwd_hash, role_id, 
                                    is_verified, full_name, contact, status, shard_id))
                conn.commit()
                
                shard_distribution[shard_id] += 1
                total_inserted += 1
                
                cursor.close()
                conn.close()
            except Error as e:
                logger.error(f"[SHARD {shard_id}] ✗ Failed to insert user {user_id}: {e}")
        
        logger.info(f"\n✓ Total users inserted: {total_inserted}")
        logger.info(f"  Shard 0: {shard_distribution[0]} users")
        logger.info(f"  Shard 1: {shard_distribution[1]} users")
        logger.info(f"  Shard 2: {shard_distribution[2]} users")
    
    def migrate_students(self):
        """Migrate students to same shard as their user_id"""
        logger.info("\n" + "="*70)
        logger.info("MIGRATING: Students (Same shard as user_id)")
        logger.info("="*70)
        
        students_data = [
            (230001, 1, 9.12, 'B.Tech', 'Computer Science', 2026, 0, 'Male', 95.2, 2020, 93.4, 2022),
            (230002, 2, 8.75, 'B.Tech', 'Computer Science', 2026, 0, 'Male', 92.3, 2020, 91.2, 2022),
            (230003, 3, 8.21, 'B.Tech', 'Electronics', 2026, 0, 'Male', 90.4, 2020, 88.6, 2022),
            (230004, 4, 7.95, 'B.Tech', 'Mechanical', 2026, 1, 'Male', 88.3, 2020, 85.1, 2022),
            (230005, 5, 9.30, 'B.Tech', 'Computer Science', 2026, 0, 'Male', 96.1, 2020, 94.2, 2022),
            (230006, 6, 8.66, 'B.Tech', 'Civil', 2026, 0, 'Male', 91.4, 2020, 89.3, 2022),
            (230007, 7, 7.88, 'B.Tech', 'Chemical', 2026, 2, 'Male', 87.2, 2020, 84.5, 2022),
            (230008, 8, 8.91, 'B.Tech', 'Electrical', 2026, 0, 'Male', 93.6, 2020, 90.2, 2022),
            (230009, 9, 9.41, 'B.Tech', 'Computer Science', 2026, 0, 'Male', 97.2, 2020, 95.8, 2022),
            (230010, 10, 8.03, 'B.Tech', 'Mathematics', 2026, 0, 'Male', 89.5, 2020, 87.3, 2022),
            (230011, 11, 7.76, 'B.Tech', 'Physics', 2026, 1, 'Male', 85.3, 2020, 83.7, 2022),
            (230012, 12, 8.88, 'B.Tech', 'Biotechnology', 2026, 0, 'Male', 92.7, 2020, 91.5, 2022),
            (230013, 13, 9.55, 'B.Tech', 'Aerospace', 2026, 0, 'Male', 98.1, 2020, 96.2, 2022),
            (230014, 14, 8.46, 'B.Tech', 'Production', 2026, 0, 'Male', 90.8, 2020, 88.4, 2022),
            (230015, 15, 8.11, 'B.Tech', 'Metallurgy', 2026, 0, 'Male', 88.9, 2020, 86.3, 2022),
            (230016, 16, 7.64, 'B.Tech', 'Artificial Intelligence', 2026, 2, 'Male', 84.3, 2020, 82.1, 2022),
            (230017, 17, 9.67, 'B.Tech', 'Data Science', 2026, 0, 'Male', 97.9, 2020, 96.4, 2022),
            (230018, 18, 8.34, 'B.Tech', 'Robotics', 2026, 0, 'Male', 91.2, 2020, 89.5, 2022),
            (230019, 19, 8.97, 'B.Tech', 'Computer Science', 2026, 0, 'Male', 94.3, 2020, 92.6, 2022),
            (230020, 20, 7.83, 'B.Tech', 'Electronics', 2026, 1, 'Male', 86.8, 2020, 84.9, 2022),
            (230021, 21, 8.42, 'B.Tech', 'Mechanical', 2026, 0, 'Male', 90.3, 2020, 88.2, 2022),
            (230022, 22, 9.02, 'B.Tech', 'Civil', 2026, 0, 'Male', 95.1, 2020, 93.7, 2022),
            (230023, 23, 8.16, 'B.Tech', 'Chemical', 2026, 0, 'Male', 89.7, 2020, 87.4, 2022),
            (230024, 24, 8.69, 'B.Tech', 'Electrical', 2026, 0, 'Male', 92.5, 2020, 90.1, 2022),
            (230025, 25, 7.92, 'B.Tech', 'Mathematics', 2026, 1, 'Male', 87.1, 2020, 85.3, 2022),
            (230026, 26, 8.81, 'B.Tech', 'Physics', 2026, 0, 'Male', 93.8, 2020, 91.7, 2022),
            (230027, 27, 9.28, 'B.Tech', 'Biotechnology', 2026, 0, 'Male', 96.4, 2020, 94.8, 2022),
            (230028, 28, 8.93, 'B.Tech', 'Aerospace', 2026, 0, 'Male', 94.7, 2020, 92.9, 2022),
            (230029, 29, 8.54, 'B.Tech', 'Production', 2026, 0, 'Male', 91.6, 2020, 89.8, 2022),
            (230030, 30, 9.74, 'B.Tech', 'Artificial Intelligence', 2026, 0, 'Male', 98.6, 2020, 97.1, 2022),
        ]
        
        total_inserted = 0
        
        for student_id, user_id, cpi, program, discipline, grad_year, backlogs, gender, tenth, tenth_yr, twelfth, twelfth_yr in students_data:
            shard_id = self.get_shard_id(user_id)
            table_name = self.get_table_name("students", shard_id)
            
            try:
                conn = self.get_connection(shard_id)
                cursor = conn.cursor()
                
                sql = f"""
                INSERT IGNORE INTO {table_name}
                (student_id, user_id, latest_cpi, program, discipline, graduating_year, 
                 active_backlogs, gender, tenth_percent, tenth_passout_year,
                 twelfth_percent, twelfth_passout_year, shard_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                
                cursor.execute(sql, (student_id, user_id, cpi, program, discipline, grad_year,
                                    backlogs, gender, tenth, tenth_yr, twelfth, twelfth_yr, shard_id))
                conn.commit()
                total_inserted += 1
                
                cursor.close()
                conn.close()
            except Error as e:
                logger.error(f"[SHARD {shard_id}] ✗ Failed to insert student {student_id}: {e}")
        
        logger.info(f"✓ Total students inserted: {total_inserted}")
    
    def verify_migration(self):
        """Verify that all data has been migrated correctly"""
        logger.info("\n" + "="*70)
        logger.info("VERIFYING MIGRATION")
        logger.info("="*70)
        
        total_users = 0
        total_students = 0
        
        for shard_id in SHARDS.keys():
            try:
                conn = self.get_connection(shard_id)
                cursor = conn.cursor(dictionary=True)
                
                # Count users
                cursor.execute(f"SELECT COUNT(*) as cnt FROM {self.get_table_name('users', shard_id)}")
                user_count = cursor.fetchone()['cnt']
                total_users += user_count
                
                # Count students
                cursor.execute(f"SELECT COUNT(*) as cnt FROM {self.get_table_name('students', shard_id)}")
                student_count = cursor.fetchone()['cnt']
                total_students += student_count
                
                logger.info(f"\n[SHARD {shard_id}]")
                logger.info(f"  Users: {user_count}")
                logger.info(f"  Students: {student_count}")
                
                # Show sample users
                cursor.execute(f"SELECT user_id, username, email FROM {self.get_table_name('users', shard_id)} LIMIT 3")
                samples = cursor.fetchall()
                for user in samples:
                    logger.info(f"    - User {user['user_id']}: {user['username']} ({user['email']})")
                
                cursor.close()
                conn.close()
            except Error as e:
                logger.error(f"[SHARD {shard_id}] ✗ Verification failed: {e}")
        
        logger.info(f"\n{'='*70}")
        logger.info(f"MIGRATION SUMMARY")
        logger.info(f"{'='*70}")
        logger.info(f"Total Users: {total_users}")
        logger.info(f"Total Students: {total_students}")
        logger.info(f"{'='*70}\n")

def main():
    """Run migration"""
    try:
        logger.info("="*70)
        logger.info("PRODUCTION DATA MIGRATION TO REMOTE SHARDS")
        logger.info("="*70 + "\n")
        
        migrator = DataMigrator()
        
        # Perform migration
        migrator.migrate_roles()
        migrator.migrate_users()
        migrator.migrate_students()
        
        # Verify
        migrator.verify_migration()
        
        logger.info("✅ Migration completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        raise

if __name__ == "__main__":
    main()
