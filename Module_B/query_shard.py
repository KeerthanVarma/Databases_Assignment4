#!/usr/bin/env python3
"""
Simple shard query tool - no interactive shell needed
Usage: python query_shard.py <shard_id> "<SQL_QUERY>"
Example: python query_shard.py 0 "SELECT COUNT(*) FROM shard_0_users;"
"""

import mysql.connector
import sys
from tabulate import tabulate

SHARDS = {
    "0": {"host": "10.0.116.184", "port": 3307},
    "1": {"host": "10.0.116.184", "port": 3308},
    "2": {"host": "10.0.116.184", "port": 3309},
}

def query_shard(shard_id, sql_query):
    """Execute query on a specific shard"""
    if shard_id not in SHARDS:
        print(f"❌ Shard {shard_id} not found (0-2)")
        return
    
    config = SHARDS[shard_id]
    
    try:
        conn = mysql.connector.connect(
            host=config["host"],
            port=config["port"],
            user="Machine_minds",
            password="password@123",
            database="Machine_minds"
        )
        
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql_query)
        
        if sql_query.strip().upper().startswith("SELECT"):
            results = cursor.fetchall()
            
            if not results:
                print(f"(0 rows)")
                return
            
            # Pretty print results
            print(tabulate(results, headers="keys", tablefmt="grid"))
            print(f"\n({len(results)} rows)")
        else:
            conn.commit()
            print(f"✓ Executed. Rows affected: {cursor.rowcount}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

def count_users_all_shards():
    """Show user count in all shards"""
    print("\n📊 User count in each shard:\n")
    for shard_id in ["0", "1", "2"]:
        try:
            config = SHARDS[shard_id]
            conn = mysql.connector.connect(
                host=config["host"],
                port=config["port"],
                user="Machine_minds",
                password="password@123",
                database="Machine_minds"
            )
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM shard_{shard_id}_users;")
            count = cursor.fetchone()[0]
            print(f"  Shard {shard_id} ({config['host']}:{config['port']}): {count} users")
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"  Shard {shard_id}: ❌ Error - {e}")

def find_user_across_shards(user_id):
    """Find which shard contains a user"""
    print(f"\n🔍 Searching for User {user_id}...\n")
    found = False
    
    for shard_id in ["0", "1", "2"]:
        try:
            config = SHARDS[shard_id]
            conn = mysql.connector.connect(
                host=config["host"],
                port=config["port"],
                user="Machine_minds",
                password="password@123",
                database="Machine_minds"
            )
            cursor = conn.cursor(dictionary=True)
            cursor.execute(f"SELECT user_id, email, status FROM shard_{shard_id}_users WHERE user_id = {user_id};")
            result = cursor.fetchone()
            
            if result:
                print(f"✓ Found in Shard {shard_id} ({config['host']}:{config['port']}):")
                print(f"  Email: {result['email']}")
                print(f"  Status: {result['status']}")
                found = True
            else:
                print(f"✗ Not in Shard {shard_id}")
            
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"  Shard {shard_id}: ❌ Error - {e}")
    
    if not found:
        print(f"\n❌ User {user_id} not found in any shard")
    print()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python query_shard.py --count                    # Count users in all shards")
        print("  python query_shard.py --find <user_id>           # Find user across shards")
        print("  python query_shard.py <shard> '<SQL_QUERY>'      # Execute SQL on shard")
        print("\nExamples:")
        print('  python query_shard.py 0 "SELECT * FROM shard_0_users LIMIT 5;"')
        print('  python query_shard.py --find 42')
        print("  python query_shard.py --count")
        sys.exit(1)
    
    if sys.argv[1] == "--count":
        count_users_all_shards()
    elif sys.argv[1] == "--find":
        if len(sys.argv) < 3:
            print("❌ Usage: python query_shard.py --find <user_id>")
            sys.exit(1)
        find_user_across_shards(sys.argv[2])
    else:
        shard_id = sys.argv[1]
        if len(sys.argv) < 3:
            print("❌ Usage: python query_shard.py <shard_id> '<SQL_QUERY>'")
            sys.exit(1)
        sql_query = sys.argv[2]
        query_shard(shard_id, sql_query)
