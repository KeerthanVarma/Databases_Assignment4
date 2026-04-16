

# ============================================================================
# SHARDING ENDPOINTS (Assignment 4)
# ============================================================================

@app.get("/admin/sharding/status")
def get_sharding_status_endpoint(user=Depends(current_user_dependency)):
    """Get current sharding configuration and status."""
    require_admin(user, "/admin/sharding/status", "sharding_query")
    return get_sharding_status()


@app.post("/admin/sharding/initialize")
def initialize_sharding_endpoint(user=Depends(current_user_dependency)):
    """Initialize sharding tables (admin only)."""
    require_admin(user, "/admin/sharding/initialize", "sharding_management")
    try:
        initialize_sharding()
        return {
            "success": True,
            "message": "Sharding tables initialized successfully",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to initialize sharding: {str(e)}",
            "error": str(e)
        }


@app.get("/admin/sharding/routing-demo")
def demo_sharding_routing(user_id: int = 5, table_name: str = "users", user=Depends(current_user_dependency)):
    """
    Demonstrate sharding routing logic
    Example: GET /admin/sharding/routing-demo?user_id=5&table_name=users
    """
    require_admin(user, "/admin/sharding/routing-demo", "sharding_query")
    
    from .sharding_manager import get_router, ShardingException
    
    try:
        router = get_router()
        shard_id = router.get_shard_id(user_id)
        shard_table = router.get_shard_table_name(table_name, user_id)
        
        return {
            "user_id": user_id,
            "table_name": table_name,
            "shard_id": shard_id,
            "shard_table": shard_table,
            "formula": f"shard_id = {user_id} % 3 = {shard_id}",
            "explanation": f"Record with user_id={user_id} for table '{table_name}' will be routed to '{shard_table}'"
        }
    except ShardingException as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/admin/sharding/distribution")
def get_shard_distribution(user=Depends(current_user_dependency)):
    """
    Get data distribution across shards
    Shows how many records are in each shard
    """
    require_admin(user, "/admin/sharding/distribution", "sharding_query")
    
    from .sharding_manager import NUM_SHARDS
    import os
    
    sharding_enabled = os.getenv("MODULE_B_SHARDING_ENABLED", "1") == "1"
    
    if not sharding_enabled:
        return {"error": "Sharding is not enabled"}
    
    distribution = {}
    for shard_id in range(NUM_SHARDS):
        shard_table = f"shard_{shard_id}_users"
        try:
            count = fetch_one(f"SELECT COUNT(*) as count FROM {shard_table}", ())
            distribution[f"shard_{shard_id}"] = count["count"] if count else 0
        except Exception as e:
            distribution[f"shard_{shard_id}"] = f"Error: {str(e)}"
    
    total = sum(c for c in distribution.values() if isinstance(c, int))
    distribution["total"] = total
    distribution["avg_per_shard"] = total // NUM_SHARDS if NUM_SHARDS > 0 else 0
    
    return {
        "sharding_enabled": sharding_enabled,
        "num_shards": NUM_SHARDS,
        "distribution": distribution,
        "timestamp": datetime.now().isoformat()
    }


@app.post("/admin/sharding/demonstrate")
def demonstrate_query_routing(user=Depends(current_user_dependency)):
    """
    Demonstrate query routing with multiple users
    Shows how different users are routed to different shards
    """
    require_admin(user, "/admin/sharding/demonstrate", "sharding_query")
    
    from .sharding_manager import get_router
    
    router = get_router()
    
    # Demonstrate routing for various users
    demo_user_ids = [1, 2, 3, 4, 5, 6, 10, 15, 20, 30]
    
    routing_map = []
    for uid in demo_user_ids:
        shard_id = router.get_shard_id(uid)
        routing_map.append({
            "user_id": uid,
            "shard_id": shard_id,
            "users_table": f"shard_{shard_id}_users",
            "students_table": f"shard_{shard_id}_students",
            "applications_table": f"shard_{shard_id}_applications"
        })
    
    # Group by shard
    by_shard = {}
    for route in routing_map:
        shard_id = route["shard_id"]
        if shard_id not in by_shard:
            by_shard[shard_id] = []
        by_shard[shard_id].append(route["user_id"])
    
    return {
        "strategy": "hash-based: shard_id = user_id % 3",
        "routing_map": routing_map,
        "distribution_by_shard": by_shard,
        "explanation": "Each user_id is mapped to exactly one shard deterministically"
    }


@app.get("/admin/sharding/query-analysis/{user_id}")
def analyze_user_routing(user_id: int, user=Depends(current_user_dependency)):
    """
    Analyze which shard(s) a query for a specific user will be routed to
    """
    require_admin(user, f"/admin/sharding/query-analysis/{user_id}", "sharding_query")
    
    from .sharding_manager import get_router, ShardAnalyzer
    
    router = get_router()
    analyzer = ShardAnalyzer(router)
    
    sharded_tables = ["users", "students", "alumni_user", "companies", "user_logs", "resumes", "applications"]
    centralized_tables = ["job_postings", "eligibility_criteria", "roles"]
    
    analysis = {
        "user_id": user_id,
        "target_shard_id": router.get_shard_id(user_id),
        "sharded_table_routing": {},
        "centralized_table_routing": {},
    }
    
    # Analyze sharded tables
    for table in sharded_tables:
        try:
            explanation = analyzer.explain_routing(table, user_id)
            analysis["sharded_table_routing"][table] = explanation
        except Exception as e:
            analysis["sharded_table_routing"][table] = {"error": str(e)}
    
    # Analyze centralized tables
    for table in centralized_tables:
        analysis["centralized_table_routing"][table] = {
            "routing": "centralized",
            "target_table": table,
            "explanation": "No sharding - all nodes/queries access same table"
        }
    
    return analysis
