#!/usr/bin/env python3
"""
Test Suite: Verify API writes are correctly persisted to shards
This script tests end-to-end data updates through the API and verifies them in the database shards.
"""

import requests
import mysql.connector
import time
import json
from datetime import datetime

# Configuration
API_BASE = "http://localhost:8000"
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"

SHARD_CONFIG = [
    {"id": 0, "host": "10.0.116.184", "port": 3307},
    {"id": 1, "host": "10.0.116.184", "port": 3308},
    {"id": 2, "host": "10.0.116.184", "port": 3309},
]

DB_USER = "Machine_minds"
DB_PASSWORD = "password@123"
DB_NAME = "Machine_minds"

class ShardVerifier:
    def __init__(self):
        self.token = None
        self.login()
    
    def login(self):
        """Get admin token"""
        response = requests.post(f"{API_BASE}/login", json={
            "username": ADMIN_USER,
            "password": ADMIN_PASS
        })
        if response.status_code == 200:
            self.token = response.json().get("session_token")
            print(f"✓ Login successful. Token: {self.token[:20]}...\n")
            return True
        else:
            print(f"✗ Login failed: {response.status_code}")
            return False
    
    def get_headers(self):
        """Get auth headers"""
        return {"X-Session-Token": self.token}
    
    def get_shard_connection(self, shard_id):
        """Get MySQL connection to specific shard"""
        shard = SHARD_CONFIG[shard_id]
        return mysql.connector.connect(
            host=shard["host"],
            port=shard["port"],
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
    
    def determine_shard(self, user_id):
        """Calculate which shard a user belongs to"""
        return user_id % 3
    
    def test_1_user_profile_update(self):
        """Test 1: Update user profile and verify in shard"""
        print("\n" + "="*70)
        print("TEST 1: User Profile Update")
        print("="*70)
        
        # Pick a user to update
        user_id = 42
        shard_id = self.determine_shard(user_id)
        
        print(f"\nScenario: Update user {user_id}")
        print(f"Expected Shard: {shard_id} (user_id % 3 = {user_id} % 3 = {shard_id})")
        
        # Get current data
        print(f"\n[Step 1] Fetch current user data from shard...")
        conn = self.get_shard_connection(shard_id)
        cursor = conn.cursor(dictionary=True)
        cursor.execute(f"SELECT * FROM shard_{shard_id}_users WHERE user_id = %s", (user_id,))
        old_data = cursor.fetchone()
        
        if old_data:
            print(f"  Current Name: {old_data['full_name']}")
            print(f"  Current Email: {old_data['email']}")
            print(f"  Current Status: {old_data['status']}")
        else:
            print(f"  ✗ User not found in shard {shard_id}")
            cursor.close()
            conn.close()
            return False
        
        cursor.close()
        conn.close()
        
        # Update via API
        print(f"\n[Step 2] Update via API (port 8000)...")
        new_email = f"updated_{int(time.time())}@test.com"
        # Use uppercase to match database
        new_status = "INACTIVE" if old_data['status'] == "ACTIVE" else "ACTIVE"
        
        print(f"  New Email: {new_email}")
        print(f"  New Status: {new_status}")
        
        # Call PUT endpoint to update user
        update_payload = {
            "email": new_email,
            "status": new_status
        }
        update_response = requests.put(
            f"{API_BASE}/shards/users/{user_id}",
            json=update_payload,
            headers=self.get_headers()
        )
        
        if update_response.status_code == 200:
            print(f"  ✓ API update successful (HTTP 200)")
        else:
            print(f"  ✗ API update failed (HTTP {update_response.status_code})")
            print(f"  Response: {update_response.text[:200]}")
        
        # Verify in shard after update (wait a moment for consistency)
        print(f"\n[Step 3] Verify update in shard (database)...")
        time.sleep(1)
        
        conn = self.get_shard_connection(shard_id)
        cursor = conn.cursor(dictionary=True)
        cursor.execute(f"SELECT * FROM shard_{shard_id}_users WHERE user_id = %s", (user_id,))
        new_data = cursor.fetchone()
        
        if new_data:
            print(f"  Name in DB: {new_data['full_name']}")
            print(f"  Email in DB: {new_data['email']}")
            print(f"  Status in DB: {new_data['status']}")
            
            # Convert status to uppercase for comparison
            db_status = str(new_data['status']).upper() if new_data['status'] else ""
            
            if new_data['email'] == new_email and db_status == new_status:
                print(f"  ✓ PASS: Updates correctly persisted to shard {shard_id}")
                result = True
            else:
                print(f"  ✗ FAIL: Updates not persisted")
                print(f"    Expected email: {new_email}, Got: {new_data['email']}")
                print(f"    Expected status: {new_status}, Got: {db_status}")
                result = False
        else:
            print(f"  ✗ User disappeared from shard!")
            result = False
        
        cursor.close()
        conn.close()
        
        return result
    
    def test_2_cross_shard_verification(self):
        """Test 2: Verify data is ONLY in correct shard, not in others"""
        print("\n" + "="*70)
        print("TEST 2: Cross-Shard Data Isolation Verification")
        print("="*70)
        
        user_id = 42
        correct_shard = self.determine_shard(user_id)
        
        print(f"\nScenario: Verify user {user_id} exists ONLY in shard {correct_shard}")
        print(f"Expected: Found in shard {correct_shard}, NOT in others")
        
        found_count = 0
        found_shards = []
        
        for shard_id in range(3):
            conn = self.get_shard_connection(shard_id)
            cursor = conn.cursor(dictionary=True)
            cursor.execute(f"SELECT COUNT(*) as cnt FROM shard_{shard_id}_users WHERE user_id = %s", (user_id,))
            result = cursor.fetchone()
            count = result['cnt']
            
            if count > 0:
                found_count += count
                found_shards.append(shard_id)
                status = "✓" if shard_id == correct_shard else "✗ WRONG"
                print(f"  Shard {shard_id}: {count} record(s) {status}")
            else:
                print(f"  Shard {shard_id}: 0 records")
            
            cursor.close()
            conn.close()
        
        # Verify results
        if found_count == 1 and found_shards[0] == correct_shard:
            print(f"\n  ✓ PASS: User found in exactly one shard (shard {correct_shard})")
            return True
        else:
            print(f"\n  ✗ FAIL: Data integrity issue! Found in {found_shards}")
            return False
    
    def test_3_fan_out_verification(self):
        """Test 3: Verify fan-out query returns consistent data"""
        print("\n" + "="*70)
        print("TEST 3: Fan-out Query Consistency Check")
        print("="*70)
        
        print(f"\nScenario: Query all users via fan-out and verify they exist in shards")
        
        # Get users via API fan-out
        print(f"\n[Step 1] Get users via API fan-out endpoint...")
        response = requests.get(f"{API_BASE}/shards/users?limit=100", 
                               headers=self.get_headers())
        
        if response.status_code != 200:
            print(f"  ✗ API request failed: {response.status_code}")
            return False
        
        api_users = response.json().get('users', [])
        print(f"  API returned: {len(api_users)} users")
        
        # Verify each user exists in correct shard
        print(f"\n[Step 2] Verify each user exists in its shard...")
        all_verified = True
        verification_count = 0
        
        for user in api_users[:5]:  # Check first 5 for brevity
            user_id = user['user_id']
            shard_id = self.determine_shard(user_id)
            
            conn = self.get_shard_connection(shard_id)
            cursor = conn.cursor(dictionary=True)
            cursor.execute(f"SELECT user_id, full_name FROM shard_{shard_id}_users WHERE user_id = %s", 
                          (user_id,))
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if result:
                print(f"  ✓ User {user_id}: {result['full_name']} found in shard {shard_id}")
                verification_count += 1
            else:
                print(f"  ✗ User {user_id}: NOT found in shard {shard_id}!")
                all_verified = False
        
        if all_verified:
            print(f"\n  ✓ PASS: All {verification_count} checked users verified in shards")
            return True
        else:
            print(f"\n  ✗ FAIL: Some users not found in their shards")
            return False
    
    def test_4_shard_routing_formula(self):
        """Test 4: Verify shard routing API matches actual shard placement"""
        print("\n" + "="*70)
        print("TEST 4: Shard Routing Formula Verification")
        print("="*70)
        
        test_user_ids = [3, 6, 9, 42, 100]
        print(f"\nScenario: Verify routing formula matches actual data placement")
        
        all_correct = True
        
        for user_id in test_user_ids:
            expected_shard = self.determine_shard(user_id)
            
            # Check via API routing
            response = requests.get(f"{API_BASE}/shards/users/{user_id}", 
                                   headers=self.get_headers())
            
            if response.status_code == 200:
                api_shard = response.json().get('shard_id')
                
                # Verify in actual database
                conn = self.get_shard_connection(expected_shard)
                cursor = conn.cursor(dictionary=True)
                cursor.execute(f"SELECT COUNT(*) as cnt FROM shard_{expected_shard}_users WHERE user_id = %s", 
                              (user_id,))
                in_db = cursor.fetchone()['cnt'] > 0
                cursor.close()
                conn.close()
                
                if api_shard == expected_shard and in_db:
                    print(f"  ✓ User {user_id}: API says shard {api_shard}, found in DB shard {expected_shard}")
                else:
                    print(f"  ✗ User {user_id}: API={api_shard}, expected={expected_shard}, in_db={in_db}")
                    all_correct = False
            elif response.status_code == 404:
                print(f"  ~ User {user_id}: Not found (expected for some users)")
            else:
                print(f"  ✗ User {user_id}: API error {response.status_code}")
                all_correct = False
        
        if all_correct:
            print(f"\n  ✓ PASS: Routing formula verified for all test users")
            return True
        else:
            print(f"\n  ✗ FAIL: Some routing mismatches detected")
            return False
    
    def test_5_partition_integrity(self):
        """Test 5: Verify data partition integrity"""
        print("\n" + "="*70)
        print("TEST 5: Partition Integrity Check")
        print("="*70)
        
        print(f"\nScenario: Verify all users satisfy MOD(user_id, 3) = shard_id")
        
        violations = 0
        total_checked = 0
        
        for shard_id in range(3):
            conn = self.get_shard_connection(shard_id)
            cursor = conn.cursor(dictionary=True)
            
            # Get all users in this shard
            cursor.execute(f"SELECT user_id FROM shard_{shard_id}_users")
            users = cursor.fetchall()
            
            for user in users:
                user_id = user['user_id']
                expected_shard = user_id % 3
                
                if expected_shard != shard_id:
                    violations += 1
                    if violations <= 3:  # Show first 3 violations
                        print(f"  ✗ VIOLATION: user_id {user_id} in shard {shard_id}, should be in {expected_shard}")
                
                total_checked += 1
            
            cursor.close()
            conn.close()
        
        print(f"\n  Checked: {total_checked} users")
        print(f"  Violations: {violations}")
        
        if violations == 0:
            print(f"  ✓ PASS: Perfect partition integrity (0 violations)")
            return True
        else:
            print(f"  ✗ FAIL: Found {violations} partitioning violations")
            return False
    
    def run_all_tests(self):
        """Run all verification tests"""
        print("\n" + "="*80)
        print("COMPREHENSIVE SHARD WRITE VERIFICATION SUITE")
        print("="*80)
        print(f"Timestamp: {datetime.now().isoformat()}")
        print(f"API: {API_BASE}")
        print(f"Shards: 3 (ports 3307, 3308, 3309)")
        
        results = {
            "Test 1 - User Profile Update": self.test_1_user_profile_update(),
            "Test 2 - Cross-Shard Isolation": self.test_2_cross_shard_verification(),
            "Test 3 - Fan-out Consistency": self.test_3_fan_out_verification(),
            "Test 4 - Routing Formula": self.test_4_shard_routing_formula(),
            "Test 5 - Partition Integrity": self.test_5_partition_integrity(),
        }
        
        # Summary
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        
        passed = sum(1 for v in results.values() if v)
        total = len(results)
        
        for test_name, result in results.items():
            status = "✓ PASS" if result else "✗ FAIL"
            print(f"{status}: {test_name}")
        
        print(f"\n{'='*80}")
        print(f"TOTAL: {passed}/{total} tests passed")
        
        if passed == total:
            print("Status: ✓ ALL TESTS PASSED - Shards working correctly!")
        else:
            print(f"Status: ✗ {total - passed} test(s) failed - Check issues above")
        
        print(f"{'='*80}\n")
        
        return passed == total


def main():
    verifier = ShardVerifier()
    if verifier.token:
        verifier.run_all_tests()
    else:
        print("Failed to authenticate. Exiting.")


if __name__ == "__main__":
    main()
