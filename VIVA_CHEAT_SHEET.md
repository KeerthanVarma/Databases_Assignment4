# Viva Cheat Sheet - Quick Reference

## CONCEPTS AT A GLANCE

### 1. Shard Key Features
```
✓ Immutable (never changes)
✓ High cardinality (millions of unique values)
✓ Uniformly distributed (no hotspots)
✓ Your choice: user_id

❌ Never choose:
- role_id (low cardinality → hotspots)
- email (mutable → migration issues)
- timestamp (clusters recent records)
```

### 2. Sharding vs Partitioning
```
SHARDING:                          PARTITIONING:
- Multiple databases/servers       - Single database
- Application routing              - Database handles
- Horizontal scale (add servers)   - Vertical scale (upgrade RAM)
- Complex (YOUR PROJECT)           - Simple (built-in)
```

### 3. Three Types of Sharding
```
1. HASH-BASED (YOUR PROJECT)    2. RANGE-BASED           3. DIRECTORY-BASED
   shard = hash(user_id) % 3       shard = user_id / 100    shard = lookup_table[user_id]
   ✓ Uniform distribution          ✗ Hotspots              ✓ Perfect control
   ✓ No lookup table              ✓ Range queries          ✗ Extra latency
   ✗ Hard to rebalance            ✗ Uneven load           ✗ Single point of failure
```

### 4. Formula for Shard ID
```
shard_id = xxHash64(str(user_id).encode()).intdigest() % 3

Example: user_id = 100
shard_id = xxHash64("100".encode()).intdigest() % 3 = 1
Location: shard_1_users, shard_1_sessions, shard_1_students
```

### 5. Scatter-Gather Query
```
┌─────────────────────────────────────┐
│  Query all 3 shards in parallel     │ SCATTER
├─────────────────────────────────────┤
│  Each shard processes independently │ EXECUTE
├─────────────────────────────────────┤
│  Collect results from all shards    │ GATHER
├─────────────────────────────────────┤
│  Aggregate/merge results            │ COMBINE
└─────────────────────────────────────┘

Used for: COUNT(*), SUM(), Range queries, Full table scans
```

### 6. Routing Layer
```
YOUR PROJECT: APPLICATION LAYER (FastAPI)
                    ↓
    ┌───────────────────────────────┐
    │ Python/FastAPI Server         │
    │ ├─ Calculate shard_id         │
    │ ├─ Get shard_table_name       │
    │ ├─ Select connection pool     │
    │ └─ Execute on correct shard   │
    └───────────┬───────────────────┘
                ↓
    ┌───────────────────────────────┐
    │ 3 Remote MySQL Instances      │
    │ ├─ :3307 (Shard 0)            │
    │ ├─ :3308 (Shard 1)            │
    │ └─ :3309 (Shard 2)            │
    └───────────────────────────────┘

NOT at database layer (no native sharding support in MySQL)
```

### 7. CAP Theorem - Your System
```
Consistency ✓        Availability ✓        Partition Tolerance ✗
───────────────      ──────────────        ────────────────────
- No replication     - 3 shards             - No replicas
- ACID in MySQL      - If 1 fails, 2 work   - Shard down = data down
- Strong consistency - Pooled connections   - No failover
- User stays in      - Most queries work    - Single copy only
  same shard
```

### 8. Hash-Based vs Range-Based
```
                   HASH-BASED               RANGE-BASED
Distribution       Uniform ✓                Skewed ✗ (hotspots)
Range queries      All shards               Single shard ✓
Setup              Easy                     Easy
Rebalancing        Hard (rehash)            Hard (migrate)
Hotspots           None ✓                   Recent data ✗
YOUR PROJECT       ✓ USED                   ✗
```

### 9. Directory Sharding Entity
```
NOT used in your project, but if implemented:

Table: shard_mapping
┌─────────┬──────────┐
│user_id  │shard_id  │
├─────────┼──────────┤
│1        │0         │
│2        │1         │
│3        │2         │
└─────────┴──────────┘

How: SELECT shard_id FROM shard_mapping WHERE user_id = X

Problem: Extra lookup latency before every query ✗
```

### 10. Consistency & Session Bug Fix
```
BUG: Admin login failed immediately
└─ Login: 200 OK (token generated) ✓
└─ isAuth: 401 Invalid session token ✗

ROOT CAUSE: Admin user placed in wrong shard
├─ hash(user_id=100) % 3 = 1 (should be Shard 1)
├─ But admin created in Shard 0 ✗
├─ Sessions created in Shard 1 ✓
├─ Session lookup: found in Shard 1 ✓
└─ User lookup: NOT in Shard 1 (in Shard 0) ✗

FIX: Move admin to correct shard
└─ DELETE from shard_0_users WHERE user_id=100
└─ INSERT into shard_1_users (admin user data)
└─ Now hash and actual location match ✓

LESSON: Data placement must match hash formula
```

## IMPLEMENTATION FILES

| File | What | Key Function |
|------|------|--------------|
| `sharding_manager.py` | Routing logic | `get_shard_id(user_id)` |
| `sharded_db.py` | Connection pooling | Pool management & execution |
| `auth.py` | Sessions | `create_session()`, `get_session_user()` |
| `main.py` | API routes | Endpoint handlers |
| `sharding_endpoints.py` | Admin tools | Routing demo, distribution |

## ONE-LINER DEFINITIONS

```
Shard key:          Field determining which shard owns a record
Sharding:           Horizontal partitioning across multiple servers
Partitioning:       Splitting data within single server
Scatter-gather:     Query all shards, combine results
Hash-based:         shard_id = hash(key) % num_shards
Range-based:        shard_id = key / range_size
Directory:          Lookup table maps key → shard
Routing:            Determining which shard to query (app layer)
Consistency:        All copies of data are identical
CAP theorem:        Choose 2 of Consistency, Availability, Partition
```

## WHAT TO SAY ABOUT YOUR PROJECT

### 1. Shard Key
"We use **user_id** as shard key because it's immutable, has high cardinality, and ensures all data for a user stays in one shard."

### 2. Sharding Type
"We implemented **hash-based sharding** using xxHash64: `shard_id = hash(user_id) % 3`. This gives uniform distribution across 3 shards with ~20 users each."

### 3. Routing
"Routing is done at the **application layer** in Python/FastAPI. For each request, we calculate which shard to query and route accordingly."

### 4. Consistency
"We maintain **strong consistency** because each user's record exists in exactly one shard (no replication). Sessions are stored in the same shard as the user."

### 5. Scatter-Gather
"For queries requiring data from multiple shards (like COUNT), we use **scatter-gather**: query all shards in parallel, then aggregate results."

### 6. CAP Theorem
"Our system prioritizes **Consistency and Availability** over Partition Tolerance. If a shard becomes unreachable, users in that shard are unavailable (no failover), but data remains consistent."

### 7. Performance
"With 3 shards, queries are **3x faster** than a single server. Each shard handles only ~20 users, so queries complete quickly."

### 8. Scalability
"We can **add more shards** horizontally to scale further. This is true horizontal scaling—no single server is a bottleneck."

## QUESTIONS THEY MIGHT ASK

### Q: What happens if a shard fails?
**A:** "Without replication, that shard's data becomes unavailable. We prioritize consistency over availability, so we don't serve stale data. In production, you'd add replication across multiple servers per shard."

### Q: Can you query across shards?
**A:** "Yes, using scatter-gather. We send the query to all 3 shards, they execute independently, and we aggregate results. Slower than single-shard queries, but necessary for non-shard-key queries."

### Q: How many shards should you have?
**A:** "Depends on data size and throughput. We chose 3 as a balance between parallelism and management complexity. Too few = hotspots, too many = coordination overhead."

### Q: Why xxHash64 instead of modulo?
**A:** "Pure modulo (user_id % 3) has poor distribution. xxHash64 provides cryptographically uniform distribution, ensuring balanced load across shards."

### Q: What if you need to add a 4th shard?
**A:** "Adding shards requires rehashing: for each user, recalculate `hash(user_id) % 4` (now 4 instead of 3) and migrate data accordingly. Data movement required."

### Q: Is your system eventually consistent?
**A:** "No, we have strong consistency. Each user's data lives in one shard (no replication), so there's no eventual consistency problem."

### Q: How do you handle transactions across shards?
**A:** "We avoid cross-shard transactions. All data for a user is in one shard, so transactions are single-shard ACID. If cross-shard needed, use distributed transactions (hard)."

### Q: Why application layer routing, not database layer?
**A:** "Application layer gives us maximum flexibility. We can implement any sharding strategy, work with any database type, and integrate with our ACID coordinator from Module A."

## VIVA PERFORMANCE TIPS

✓ **Draw diagrams**: Show 3 shards, data flow, routing
✓ **Give examples**: "For user_id=100, hash gives shard 1, so we query shard_1_users"
✓ **Reference your code**: Point to specific files/functions
✓ **Mention the fix**: Explain how you debugged and fixed the session issue
✓ **Show distribution**: "61 users distributed as 21/18/22 across 3 shards"
✓ **Highlight trade-offs**: "We chose consistency over partition tolerance"
✓ **Know your limits**: Be honest about what's not replicated/backed up

## QUICK FACTS ABOUT YOUR PROJECT

- **Hash Function**: xxHash64 (10GB/s)
- **Shards**: 3 (ports 3307, 3308, 3309)
- **Shard Key**: user_id
- **Formula**: shard_id = hash(user_id) % 3
- **Total Users**: 61
- **Distribution**: ~20 users per shard
- **Consistency**: Strong (no replication)
- **Routing**: Application layer (FastAPI)
- **Query Types**: Single-shard (fast) + Scatter-gather (multi-shard)
- **CAP Choice**: Consistency + Availability (no partition tolerance)
- **Bug Fixed**: Admin user shard mismatch (session verification)

---

**Last Updated**: April 19, 2026
**Status**: Ready for Viva ✓
