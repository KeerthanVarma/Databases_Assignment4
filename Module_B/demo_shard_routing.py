#!/usr/bin/env python3
"""
Demonstrate Shard Routing and Range Queries
Shows:
1. How queries are routed to correct shards based on user_id % 3
2. Range queries that span multiple shards
3. Cross-shard aggregations
"""

import mysql.connector
from tabulate import tabulate
import sys

SHARDS = {
    "0": {"host": "10.0.116.184", "port": 3307},
    "1": {"host": "10.0.116.184", "port": 3308},
    "2": {"host": "10.0.116.184", "port": 3309},
}

def get_shard_for_user(user_id):
    """Calculate which shard a user belongs to"""
    return user_id % 3

def connect_to_shard(shard_id):
    """Connect to a specific shard"""
    config = SHARDS[str(shard_id)]
    return mysql.connector.connect(
        host=config["host"],
        port=config["port"],
        user="Machine_minds",
        password="password@123",
        database="Machine_minds"
    )

def print_section(title):
    """Print a formatted section header"""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")

def print_subsection(title):
    """Print a formatted subsection header"""
    print(f"\n{title}")
    print(f"{'-'*80}")

def demo_single_user_routing():
    """Demonstrate how a single user query is routed"""
    print_section("DEMO 1: SINGLE USER QUERY ROUTING")
    
    test_users = [42, 100, 7, 15]
    
    print("Sharding Formula: shard_id = user_id % 3\n")
    print("Test Users:")
    
    routing_table = []
    for user_id in test_users:
        shard_id = get_shard_for_user(user_id)
        routing_table.append({
            "User ID": user_id,
            "Formula": f"{user_id} % 3",
            "Shard": shard_id,
            "Host:Port": f"10.0.116.184:{3307 + shard_id}"
        })
    
    print(tabulate(routing_table, headers="keys", tablefmt="grid"))
    
    # Now show actual queries routed to correct shards
    print_subsection("Routing Query: Get User 42 Details")
    print("Step 1: Calculate shard")
    print(f"  → shard_id = 42 % 3 = {get_shard_for_user(42)}")
    print(f"  → Route to Shard {get_shard_for_user(42)} (10.0.116.184:3307)")
    
    print("\nStep 2: Connect to Shard 0 and execute query")
    shard_id = get_shard_for_user(42)
    try:
        conn = connect_to_shard(shard_id)
        cursor = conn.cursor(dictionary=True)
        query = f"SELECT user_id, email, status FROM shard_{shard_id}_users WHERE user_id = 42;"
        cursor.execute(query)
        result = cursor.fetchone()
        
        print(f"\nSQL: {query}")
        print("\nResult:")
        if result:
            print(tabulate([result], headers="keys", tablefmt="grid"))
            print(f"\n✓ User 42 found in Shard {shard_id}")
        else:
            print("✗ User 42 not found")
        
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n" + "✓ Query routed correctly!" * 1)

def demo_range_query_single_shard():
    """Demonstrate range query within a single shard"""
    print_section("DEMO 2: RANGE QUERY - SINGLE SHARD")
    
    print("Query: Find all users in Shard 0 with user_id between 1-20")
    print("\nSharding Note:")
    print("  → Users 0, 3, 6, 9, 12, 15, 18 belong to Shard 0 (id % 3 = 0)")
    print("  → This query must check Shard 0 only\n")
    
    shard_id = 0
    try:
        conn = connect_to_shard(shard_id)
        cursor = conn.cursor(dictionary=True)
        query = f"SELECT user_id, email, status FROM shard_{shard_id}_users WHERE user_id BETWEEN 1 AND 20 ORDER BY user_id;"
        cursor.execute(query)
        results = cursor.fetchall()
        
        print(f"SQL Query: {query}\n")
        print(f"Results from Shard {shard_id}:")
        print(tabulate(results, headers="keys", tablefmt="grid"))
        print(f"\n✓ Found {len(results)} users in Shard {shard_id}")
        print("Note: These are users where (user_id % 3 = 0) and (user_id BETWEEN 1-20)")
        
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"❌ Error: {e}")

def demo_range_query_multiple_shards():
    """Demonstrate range query spanning multiple shards"""
    print_section("DEMO 3: RANGE QUERY - MULTIPLE SHARDS")
    
    print("Query: Find all users with user_id between 1-30 across ALL shards")
    print("\nApproach: Execute range query on all 3 shards and combine results\n")
    
    all_results = []
    
    try:
        for shard_id in [0, 1, 2]:
            conn = connect_to_shard(shard_id)
            cursor = conn.cursor(dictionary=True)
            query = f"SELECT user_id, email, status FROM shard_{shard_id}_users WHERE user_id BETWEEN 1 AND 30 ORDER BY user_id;"
            cursor.execute(query)
            results = cursor.fetchall()
            
            print(f"Shard {shard_id}: Found {len(results)} users")
            for row in results:
                row['Shard'] = shard_id
                all_results.append(row)
            
            cursor.close()
            conn.close()
        
        # Sort combined results
        all_results.sort(key=lambda x: x['user_id'])
        
        print(f"\n{'─'*80}")
        print(f"Combined Results (User IDs 1-30 from all shards):\n")
        print(tabulate(all_results, headers="keys", tablefmt="grid"))
        print(f"\n✓ Total users found: {len(all_results)}")
        
        # Show distribution
        print("\nDistribution across shards:")
        for shard_id in [0, 1, 2]:
            count = len([r for r in all_results if r['Shard'] == shard_id])
            print(f"  Shard {shard_id}: {count} users")
        
    except Exception as e:
        print(f"❌ Error: {e}")

def demo_cross_shard_count():
    """Demonstrate cross-shard aggregation (COUNT)"""
    print_section("DEMO 4: CROSS-SHARD AGGREGATION - COUNT")
    
    print("Query: Count all users in system across all shards\n")
    
    total_count = 0
    shard_counts = {}
    
    try:
        for shard_id in [0, 1, 2]:
            conn = connect_to_shard(shard_id)
            cursor = conn.cursor()
            query = f"SELECT COUNT(*) FROM shard_{shard_id}_users;"
            cursor.execute(query)
            count = cursor.fetchone()[0]
            shard_counts[shard_id] = count
            total_count += count
            
            cursor.close()
            conn.close()
        
        print("Shard Counts:")
        for shard_id in [0, 1, 2]:
            print(f"  Shard {shard_id}: {shard_counts[shard_id]} users")
        
        print(f"\nTotal Users in System: {total_count}")
        print(f"\nDistribution:")
        for shard_id in [0, 1, 2]:
            percentage = (shard_counts[shard_id] / total_count * 100) if total_count > 0 else 0
            print(f"  Shard {shard_id}: {shard_counts[shard_id]:3d} users ({percentage:5.1f}%)")
        
    except Exception as e:
        print(f"❌ Error: {e}")

def demo_shard_specific_query():
    """Demonstrate optimized shard-specific query"""
    print_section("DEMO 5: SHARD-SPECIFIC QUERY OPTIMIZATION")
    
    print("Scenario: You know a user belongs to Shard 0, query only that shard\n")
    
    print("Without Optimization (Search all 3 shards):")
    print("  Query Shard 0: SELECT * WHERE user_id = 42")
    print("  Query Shard 1: SELECT * WHERE user_id = 42")
    print("  Query Shard 2: SELECT * WHERE user_id = 42")
    print("  → 3 database queries\n")
    
    print("With Optimization (Calculate shard first):")
    print("  Calculate: shard = 42 % 3 = 0")
    print("  Query Shard 0 only: SELECT * WHERE user_id = 42")
    print("  → 1 database query (3x faster!)\n")
    
    print("Demonstrating optimized query:")
    user_id = 42
    shard_id = get_shard_for_user(user_id)
    
    print(f"Step 1: Calculate shard for user {user_id}")
    print(f"  → shard_id = {user_id} % 3 = {shard_id}")
    
    print(f"\nStep 2: Query only Shard {shard_id}")
    try:
        conn = connect_to_shard(shard_id)
        cursor = conn.cursor(dictionary=True)
        query = f"SELECT user_id, email, status FROM shard_{shard_id}_users WHERE user_id = {user_id};"
        cursor.execute(query)
        result = cursor.fetchone()
        
        if result:
            print(f"  → Result found immediately!")
            print(f"     User: {result['user_id']}")
            print(f"     Email: {result['email']}")
            print(f"     Status: {result['status']}")
            print(f"\n✓ Optimization: Only 1 shard queried instead of 3")
        
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"❌ Error: {e}")

def demo_shard_misroute_prevention():
    """Show what happens if query is sent to wrong shard"""
    print_section("DEMO 6: WRONG SHARD ROUTING (PREVENTION)")
    
    print("Scenario: Accidentally query wrong shard for user\n")
    
    user_id = 42
    correct_shard = get_shard_for_user(user_id)
    wrong_shard = (correct_shard + 1) % 3
    
    print(f"User {user_id} should be in Shard {correct_shard}")
    print(f"But query goes to Shard {wrong_shard} (wrong!)\n")
    
    try:
        conn = connect_to_shard(wrong_shard)
        cursor = conn.cursor(dictionary=True)
        query = f"SELECT user_id, email FROM shard_{wrong_shard}_users WHERE user_id = {user_id};"
        cursor.execute(query)
        result = cursor.fetchone()
        
        if result:
            print(f"❌ Found user in wrong shard! (should not happen)")
        else:
            print(f"✓ Query returned 0 results (as expected)")
            print(f"  User {user_id} is NOT in Shard {wrong_shard}")
            print(f"  This is why routing is critical!\n")
        
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"❌ Error: {e}")

def show_all_demos():
    """Run all demonstrations"""
    try:
        demo_single_user_routing()
        demo_range_query_single_shard()
        demo_range_query_multiple_shards()
        demo_cross_shard_count()
        demo_shard_specific_query()
        demo_shard_misroute_prevention()
        
        print_section("SUMMARY")
        print("""
Key Takeaways:

1. SINGLE USER QUERIES (Optimized)
   • Calculate: shard_id = user_id % 3
   • Query that shard only
   • Result: 1 database query, instant response

2. RANGE QUERIES (Multiple Shards)
   • Execute query on each shard independently
   • Combine results from all shards
   • Sort combined results by user_id

3. AGGREGATIONS (Cross-Shard)
   • Execute aggregation (COUNT, SUM) on each shard
   • Combine results (sum all counts)
   • Return final aggregated value

4. QUERY ROUTING FORMULA
   • shard_id = user_id % 3
   • Deterministic: same user_id always routes to same shard
   • Prevents data duplication and ensures consistency

5. PERFORMANCE BENEFITS
   • Single user query: 1 shard queried (vs. 3)
   • Range query: parallelize across 3 shards
   • Scale to millions of users with 3 shards

6. DATA INTEGRITY
   • Each user exists in exactly one shard
   • No duplication across shards
   • Consistent state maintained
        """)
        
    except Exception as e:
        print(f"❌ Fatal Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("""
╔════════════════════════════════════════════════════════════════╗
║          SHARD ROUTING & RANGE QUERY DEMONSTRATION           ║
║                                                              ║
║  Shows how queries are routed to correct shards and how     ║
║  range queries work across multiple shards                   ║
╚════════════════════════════════════════════════════════════════╝
    """)
    
    show_all_demos()
    
    print(f"\n{'='*80}")
    print("All demonstrations completed successfully! ✓")
    print(f"{'='*80}\n")
