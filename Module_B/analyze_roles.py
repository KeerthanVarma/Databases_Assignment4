import mysql.connector

# Check role_ids and understand the mapping
conn = mysql.connector.connect(
    host='10.0.116.184',
    port=3308,
    user='Machine_minds',
    password='password@123',
    database='Machine_minds'
)
cursor = conn.cursor(dictionary=True)

# Get all users with their role_id
cursor.execute("SELECT user_id, username, role_id, full_name FROM shard_1_users")
users = cursor.fetchall()

print("[Users in Shard 1 with role_id mapping]")
role_map = {}
for user in users:
    role_id = user['role_id']
    if role_id not in role_map:
        role_map[role_id] = []
    role_map[role_id].append(user['username'])
    print(f"  user_id={user['user_id']}, username={user['username']}, role_id={role_id}")

print("\n[Role ID Summary]")
for role_id, users_list in sorted(role_map.items()):
    print(f"  role_id={role_id}: {users_list}")

# Check students table
cursor.execute("SELECT COUNT(*) as count FROM shard_1_students")
result = cursor.fetchone()
print(f"\n[Students Table] Count: {result['count']}")

# Check alumni_user table
cursor.execute("SELECT COUNT(*) as count FROM shard_1_alumni_user")
result = cursor.fetchone()
print(f"[Alumni Table] Count: {result['count']}")

cursor.close()
conn.close()
