import mysql.connector
from mysql.connector import Error

# Test connection to shards
shards = [
    ('10.0.116.184', 3307, 0),
    ('10.0.116.184', 3308, 1),
    ('10.0.116.184', 3309, 2),
]

print('=== Checking Sharded Tables ===\n')

for host, port, shard_id in shards:
    print(f'[Shard {shard_id}: {host}:{port}]')
    try:
        conn = mysql.connector.connect(host=host, port=port, user='root', password='password@123', database='Machine_minds')
        cursor = conn.cursor(dictionary=True)
        
        # Check if shard tables exist
        cursor.execute(f"SHOW TABLES LIKE 'shard_{shard_id}_%'")
        tables = cursor.fetchall()
        print(f'  Tables found: {len(tables)}')
        for table in tables:  
            table_name = list(table.values())[0]
            cursor.execute(f'SELECT COUNT(*) as cnt FROM {table_name}')
            count = cursor.fetchone()['cnt']
            print(f'    - {table_name}: {count} rows')
        
        conn.close()
    except Error as e:
        print(f'  ERROR: {e}')
    print()
