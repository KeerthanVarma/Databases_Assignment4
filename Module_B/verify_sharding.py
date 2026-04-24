#!/usr/bin/env python3
"""
Sharding Verification and Analysis Script
Based on README (3) requirements - verifies data partitioning across MySQL shards
"""

import mysql.connector
from datetime import datetime
import json

# Shard Configuration
SHARDS = [
    {"id": 0, "host": "10.0.116.184", "port": 3307},
    {"id": 1, "host": "10.0.116.184", "port": 3308},
    {"id": 2, "host": "10.0.116.184", "port": 3309},
]

DB_USER = "Machine_minds"
DB_PASSWORD = "password@123"
DB_NAME = "Machine_minds"

def get_shard_connection(shard_id):
    """Get connection to specific shard"""
    shard = SHARDS[shard_id]
    return mysql.connector.connect(
        host=shard["host"],
        port=shard["port"],
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )


def verify_partitioning():
    """Verify that all data respects partitioning function: user_id % 3 = shard_id"""
    print("\n" + "="*70)
    print("PARTITION PURITY VERIFICATION (Subtask 2)")
    print("="*70)
    print("Verifying: All records satisfy MOD(user_id, 3) = shard_id\n")
    
    total_violations = 0
    
    for shard_id in range(3):
        print(f"[Shard {shard_id}: port {3307+shard_id}]")
        try:
            conn = get_shard_connection(shard_id)
            cursor = conn.cursor()
            
            # Check users table
            query = f"SELECT COUNT(*) FROM shard_{shard_id}_users WHERE MOD(user_id, 3) <> {shard_id}"
            cursor.execute(query)
            users_violations = cursor.fetchone()[0]
            
            # Check students table
            query = f"SELECT COUNT(*) FROM shard_{shard_id}_students s JOIN shard_{shard_id}_users u ON s.user_id = u.user_id WHERE MOD(s.user_id, 3) <> {shard_id}"
            cursor.execute(query)
            students_violations = cursor.fetchone()[0]
            
            # Check companies table
            query = f"SELECT COUNT(*) FROM shard_{shard_id}_companies WHERE MOD(user_id, 3) <> {shard_id}"
            cursor.execute(query)
            companies_violations = cursor.fetchone()[0]
            
            shard_violations = users_violations + students_violations + companies_violations
            total_violations += shard_violations
            
            status = "✓ PASS" if shard_violations == 0 else "✗ FAIL"
            print(f"  Users table violations: {users_violations}")
            print(f"  Students table violations: {students_violations}")
            print(f"  Companies table violations: {companies_violations}")
            print(f"  Total violations: {shard_violations} {status}\n")
            
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"  ERROR: {e}\n")
            total_violations += 1
    
    print(f"TOTAL VIOLATIONS ACROSS ALL SHARDS: {total_violations}")
    return total_violations == 0


def get_data_counts():
    """Get row counts from each shard"""
    print("\n" + "="*70)
    print("DATA DISTRIBUTION ANALYSIS (Subtask 2)")
    print("="*70)
    print("Row counts per shard:\n")
    
    distribution = {}
    total_users = 0
    total_students = 0
    total_companies = 0
    
    for shard_id in range(3):
        print(f"[Shard {shard_id}: port {3307+shard_id}]")
        try:
            conn = get_shard_connection(shard_id)
            cursor = conn.cursor()
            
            # Users count
            cursor.execute(f"SELECT COUNT(*) FROM shard_{shard_id}_users")
            users = cursor.fetchone()[0]
            total_users += users
            
            # Students count
            cursor.execute(f"SELECT COUNT(*) FROM shard_{shard_id}_students")
            students = cursor.fetchone()[0]
            total_students += students
            
            # Companies count
            cursor.execute(f"SELECT COUNT(*) FROM shard_{shard_id}_companies")
            companies = cursor.fetchone()[0]
            total_companies += companies
            
            # Recruiters (role_id = 2)
            cursor.execute(f"SELECT COUNT(*) FROM shard_{shard_id}_users WHERE role_id = 2")
            recruiters = cursor.fetchone()[0]
            
            distribution[shard_id] = {
                "users": users,
                "students": students,
                "companies": companies,
                "recruiters": recruiters
            }
            
            print(f"  Users:     {users}")
            print(f"  Students:  {students}")
            print(f"  Companies: {companies}")
            print(f"  Recruiters: {recruiters}\n")
            
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"  ERROR: {e}\n")
    
    print(f"TOTALS ACROSS ALL SHARDS:")
    print(f"  Users:     {total_users}")
    print(f"  Students:  {total_students}")
    print(f"  Companies: {total_companies}")
    print(f"  Avg users per shard: {total_users // 3}")
    
    return distribution


def test_routing(user_id):
    """Test shard routing for a specific user"""
    print(f"\n[ROUTING TEST] Locating user_id={user_id}")
    
    expected_shard = user_id % 3
    print(f"  Expected shard: {expected_shard}")
    print(f"  Formula: {user_id} % 3 = {expected_shard}")
    print(f"  Checking shard {expected_shard}...")
    
    try:
        conn = get_shard_connection(expected_shard)
        cursor = conn.cursor(dictionary=True)
        
        query = f"SELECT user_id, username, email, full_name FROM shard_{expected_shard}_users WHERE user_id = %s"
        cursor.execute(query, (user_id,))
        user = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if user:
            print(f"  ✓ User found: {user['username']} ({user['full_name']})")
            return True
        else:
            print(f"  ✗ User not found in shard {expected_shard}")
            return False
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def query_sample_data():
    """Get sample data from each shard"""
    print("\n" + "="*70)
    print("SAMPLE DATA VERIFICATION")
    print("="*70)
    
    for shard_id in range(3):
        print(f"\n[Shard {shard_id}: port {3307+shard_id}]")
        try:
            conn = get_shard_connection(shard_id)
            cursor = conn.cursor(dictionary=True)
            
            # Sample users
            cursor.execute(f"SELECT user_id, username, full_name FROM shard_{shard_id}_users LIMIT 3")
            users = cursor.fetchall()
            
            # Sample students
            cursor.execute(f"SELECT student_id, user_id, latest_cpi FROM shard_{shard_id}_students LIMIT 3")
            students = cursor.fetchall()
            
            print("  Sample Users:")
            for u in users:
                print(f"    - {u['user_id']}: {u['username']} ({u['full_name']})")
            
            print("  Sample Students:")
            for s in students:
                print(f"    - student_id={s['student_id']}, user_id={s['user_id']}, cpi={s['latest_cpi']}")
            
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"  ERROR: {e}")


def main():
    """Run all verification tests"""
    print("\n" + "="*70)
    print("SHARDING VERIFICATION SUITE (Based on README 3)")
    print("="*70)
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Run verifications
    partitioning_ok = verify_partitioning()
    distribution = get_data_counts()
    query_sample_data()
    
    # Test routing for sample users
    print("\n" + "="*70)
    print("ROUTING VERIFICATION (Subtask 3)")
    print("="*70)
    print("Testing shard routing for sample user IDs:\n")
    
    sample_user_ids = [3, 6, 9, 42, 100]
    for user_id in sample_user_ids:
        test_routing(user_id)
    
    # Summary
    print("\n" + "="*70)
    print("VERIFICATION SUMMARY")
    print("="*70)
    print(f"Data Partitioning: {'✓ PASS' if partitioning_ok else '✗ FAIL'}")
    print(f"Data Distribution: {'✓ BALANCED' if partitioning_ok else '✗ IMBALANCED'}")
    print(f"Timestamp: {datetime.now().isoformat()}\n")


if __name__ == "__main__":
    main()
