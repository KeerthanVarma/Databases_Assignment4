# Assignment 4: Sharding Implementation - Design Document

## 1. Shard Key Selection & Justification

### Chosen Shard Key: `user_id`

**Rationale:**

| Criteria | Evaluation |
|----------|-----------|
| **High Cardinality** | ✅ `user_id` is a SERIAL PRIMARY KEY with distinct values for each user. Supports hundreds of thousands of users without skew. |
| **Query-Aligned** | ✅ Almost all API endpoints filter by `user_id` or related user entities (student_id maps to user_id, company owner via user_id). |
| **Stable** | ✅ `user_id` never changes after user creation; no risk of record moving between shards. |

### Alternative Candidates Considered:
- **Date Range (created_at)**: Would cause temporal skew (new users would accumulate in one shard)
- **Region/Location**: Not present in core schema; would require additional tracking
- **Hash of Primary Key**: Functionally equivalent to our chosen hash-based approach on `user_id`

---

## 2. Partitioning Strategy

### Chosen Strategy: **Hash-Based**

**Formula:**
```
shard_id = user_id % num_shards
```

**Number of Shards:** 3 (shard_0, shard_1, shard_2)

**Advantages:**
- Uniform distribution across 3 shards
- Deterministic routing (same user_id always goes to same shard)
- No need for lookup tables or range management
- Easy to extend to more shards in future

**Expected Distribution:**
- Each shard should contain ~1/3 of users
- With 45 users in demo data: ~15 users per shard
- No significant skew expected

---

## 3. Data Partitioning Strategy

### Tables to Shard (User-Dependent):

| Table | Shard Key | Reason |
|-------|-----------|--------|
| **Users** | user_id | Primary shard table |
| **User_Logs** | user_id (FK) | Logs tied to user activity |
| **Students** | user_id (FK) | Each student has one user |
| **Alumni_User** | user_id (FK) | Each alumnus has one user |
| **Companies** | user_id (FK) | Company owner is a user |
| **Resumes** | user_id (via student) | Resume belongs to student who has user_id |
| **Applications** | user_id (via student) | Application filed by student with user_id |

### Shard Table Naming Convention:
```
shard_0_<table_name>  # e.g., shard_0_users, shard_0_students
shard_1_<table_name>
shard_2_<table_name>
```

### Tables NOT Sharded (Reference/System Tables):
- **Roles** (small, referenced by all shards)
- **Job_Postings, Job_Events, Interviews, Eligibility_Criteria, etc.** (company-centric; would require cross-shard joins if sharded by user_id)
- These remain centralized and accessible by all shards

---

## 4. Query Routing Logic

### Single-Key Lookup (e.g., get user by user_id):
```python
def route_user_query(user_id):
    shard_id = user_id % num_shards
    return query_shard(f"shard_{shard_id}_users", user_id)
```

### Insert Operation (e.g., create new user):
```python
def route_insert_user(new_user_data):
    # user_id is auto-generated; compute shard after insertion
    shard_id = new_user_data['user_id'] % num_shards
    insert_into_shard(f"shard_{shard_id}_users", new_user_data)
```

### Range Queries (e.g., get all users by role):
```python
def route_range_query(query_template):
    results = []
    for shard_id in range(num_shards):
        results.extend(query_shard(f"shard_{shard_id}_users", query_template))
    return merge_results(results)
```

---

## 5. Horizontal vs. Vertical Scaling

| Aspect | Horizontal (Sharding) | Vertical (Single Server) |
|--------|----------------------|--------------------------|
| **Scalability** | Data + queries distributed across nodes | Single machine limits |
| **Cost** | Multiple machines (lower cost per node) | High-end hardware (expensive) |
| **Complexity** | Routing logic, cross-shard queries | Simpler architecture |
| **Availability** | Shard failure affects subset of users | Complete outage |
| **Parallelism** | Queries on different shards run in parallel | Sequential on single server |

**Conclusion:** Horizontal scaling via sharding is preferred for large-scale systems, providing better availability and cost efficiency despite added complexity.

---

## 6. Consistency Analysis

### Challenge:
When multiple shards exist, ensuring data consistency is complex:
- **Single-shard queries**: Consistent (isolated transactions within shard)
- **Cross-shard queries**: Potential inconsistency if data changes during query execution
- **Distributed transactions**: Expensive (2PC not fully supported in all databases)

### Our Approach:
1. **Within-shard consistency**: Use PostgreSQL's ACID properties for single-shard operations
2. **Cross-shard queries**: Accept eventual consistency for read operations
3. **No distributed transactions**: Keep relationships within same shard to avoid cross-shard joins

### When Consistency Breaks:
- If a user's data is updated in shard_0 while simultaneously reading their company's jobs (centralized table)
- During shard rebalancing (if adding new shards without full re-sharding)

---

## 7. Availability Analysis

### Single Shard Failure:
**Impact:** Users in failed shard (1/3 of user base) cannot perform operations

**Mitigation Options:**
1. **Replication:** Each shard replicated to standby node (not implemented in scope)
2. **Read Replicas:** Query replicas when primary fails (partial availability)
3. **Failover Cluster:** Automatic failover to backup shard (requires infrastructure)

**Current Status (Demo):** All shards on single server; failure affects all. In production, deploy each shard separately.

### Availability Trade-off:
- **Without sharding:** 100% availability or 0% (all-or-nothing)
- **With sharding (3 shards):** 2/3 availability if one shard fails

---

## 8. Partition Tolerance Analysis

### Network Partition Scenario:
If a shard becomes unreachable:
- **Shard 0 unreachable:** Queries for users with user_id % 3 == 0 timeout
- **Application behavior:** 
  - Return 503 Service Unavailable for affected users
  - Unaffected users continue normally
  - Data on unreachable shard is not corrupted

### Implementation Strategy:
```python
def handle_shard_failure(shard_id):
    try:
        query_shard(shard_id)
    except ConnectionError:
        log_shard_unavailable(shard_id)
        return {"status": "partial_service", "affected_users": calculate_affected_range(shard_id)}
```

---

## 9. Data Migration Plan

### Step 1: Create Shard Tables
- Run sharding SQL migration script
- Create empty sharded tables with same schema as originals

### Step 2: Populate Shards
- For each user in original Users table:
  - Calculate shard_id = user_id % 3
  - INSERT into shard_{shard_id}_users
  - CASCADE related records (logs, students, alumni, etc.)

### Step 3: Verification
- Count records in each shard
- Verify no records lost: sum(shard_0 + shard_1 + shard_2) = original_count
- Validate hash distribution

### Step 4: Cutover
- Update application to use sharding logic
- Route all new queries to appropriate shards

---

## 10. Observability & Monitoring

**Metrics to Track:**
1. **Data Distribution:** Records per shard
2. **Query Latency:** By shard
3. **Shard Health:** Connectivity, response time
4. **Hotspots:** Identify uneven load

---

## Conclusion

This hash-based sharding on `user_id` provides:
✅ Predictable distribution
✅ Deterministic routing
✅ Scalable architecture
✅ Acceptable consistency model for this application
⚠️ Requires careful management of cross-shard queries
⚠️ Partial availability during shard failures (mitigated with replication in production)
