"""
Sharding Manager Module
Provides routing logic for hash-based sharding by user_id
Strategy: user_id % num_shards (3 shards)
"""

from typing import List, Dict, Any, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)

# Sharding configuration
NUM_SHARDS = 3
SHARD_KEY = "user_id"
PARTITIONING_STRATEGY = "hash-based"

# Tables that are sharded by user_id
SHARDED_TABLES = {
    "users",
    "user_logs",
    "students",
    "alumni_user",
    "companies",
    "resumes",
    "applications",
}

# Tables that are NOT sharded (centralized)
CENTRALIZED_TABLES = {
    "roles",
    "job_postings",
    "job_events",
    "eligibility_criteria",
    "interviews",
    "venue_booking",
    "question_bank",
    "prep_pages",
    "placement_stats",
    "penalties",
    "cds_training_sessions",
    "alumni_training_map",
    "audit_logs",
    "groups",
    "group_members",
}


class ShardingException(Exception):
    """Exception raised for sharding-related errors"""
    pass


class QueryType(Enum):
    """Types of queries for routing"""
    LOOKUP = "lookup"  # Single key lookup
    INSERT = "insert"  # Insert new record
    UPDATE = "update"  # Update existing record
    DELETE = "delete"  # Delete record
    RANGE = "range"  # Range/multi-shard query
    CROSS_SHARD = "cross_shard"  # Join across shards


class ShardRouter:
    """
    Routes queries to appropriate shards based on user_id
    Implements hash-based partitioning: shard_id = user_id % num_shards
    """

    def __init__(self, num_shards: int = NUM_SHARDS):
        """
        Initialize router with number of shards
        
        Args:
            num_shards: Number of shards (default: 3)
        """
        self.num_shards = num_shards
        self.shard_key = SHARD_KEY

    def get_shard_id(self, user_id: int) -> int:
        """
        Calculate shard ID for a given user_id using hash-based partitioning
        
        Args:
            user_id: User ID to route
            
        Returns:
            Shard ID (0 to num_shards-1)
            
        Raises:
            ShardingException: If user_id is invalid
        """
        if user_id is None or not isinstance(user_id, int):
            raise ShardingException(f"Invalid user_id: {user_id}")
        if user_id < 0:
            raise ShardingException(f"user_id must be positive: {user_id}")
        
        shard_id = user_id % self.num_shards
        logger.debug(f"Routed user_id={user_id} to shard={shard_id}")
        return shard_id

    def get_shard_table_name(self, table_name: str, user_id: int) -> str:
        """
        Get the sharded table name for a given table and user_id
        
        Args:
            table_name: Base table name (without shard prefix)
            user_id: User ID to determine shard
            
        Returns:
            Sharded table name (e.g., "shard_0_users")
            
        Raises:
            ShardingException: If table is not sharded or user_id is invalid
        """
        if table_name.lower() not in SHARDED_TABLES:
            raise ShardingException(f"Table '{table_name}' is not sharded. Use centralized tables instead.")
        
        shard_id = self.get_shard_id(user_id)
        sharded_name = f"shard_{shard_id}_{table_name}"
        logger.debug(f"Sharded table: {table_name} -> {sharded_name}")
        return sharded_name

    def get_all_shard_tables(self, table_name: str) -> List[str]:
        """
        Get all shard table names for a given base table
        Used for range queries that span multiple shards
        
        Args:
            table_name: Base table name
            
        Returns:
            List of all shard table names for this table
        """
        if table_name.lower() not in SHARDED_TABLES:
            raise ShardingException(f"Table '{table_name}' is not sharded.")
        
        tables = [f"shard_{i}_{table_name}" for i in range(self.num_shards)]
        logger.debug(f"All shard tables for {table_name}: {tables}")
        return tables

    def is_sharded_table(self, table_name: str) -> bool:
        """Check if a table is sharded"""
        return table_name.lower() in SHARDED_TABLES

    def is_centralized_table(self, table_name: str) -> bool:
        """Check if a table is centralized (not sharded)"""
        return table_name.lower() in CENTRALIZED_TABLES

    def extract_user_id_from_query(self, query: str) -> Optional[int]:
        """
        Extract user_id from a query string
        Looks for patterns like "WHERE user_id = X" or "user_id = X"
        
        Args:
            query: SQL query string
            
        Returns:
            user_id if found, None otherwise
        """
        import re
        
        # Try to find user_id = <number>
        patterns = [
            r'WHERE\s+user_id\s*=\s*(\d+)',
            r'user_id\s*=\s*(\d+)',
            r'WHERE\s+u\.user_id\s*=\s*(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                return int(match.group(1))
        
        return None

    def route_select_query(self, table_name: str, user_id: Optional[int]) -> List[str]:
        """
        Route a SELECT query to appropriate shard(s)
        
        Args:
            table_name: Table to query
            user_id: User ID (None for range queries spanning all shards)
            
        Returns:
            List of shard table names to query
        """
        if self.is_centralized_table(table_name):
            # Centralized tables - query directly (no sharding)
            return [table_name]
        
        if not self.is_sharded_table(table_name):
            raise ShardingException(f"Unknown table: {table_name}")
        
        if user_id is None:
            # Range query - need to query all shards
            logger.warning(f"Range query on {table_name}: querying all shards")
            return self.get_all_shard_tables(table_name)
        else:
            # Single-shard lookup
            return [self.get_shard_table_name(table_name, user_id)]

    def route_insert_query(self, table_name: str, user_id: int) -> str:
        """
        Route an INSERT query to appropriate shard
        
        Args:
            table_name: Table to insert into
            user_id: User ID of record to insert
            
        Returns:
            Shard table name
        """
        if self.is_centralized_table(table_name):
            return table_name
        
        if not self.is_sharded_table(table_name):
            raise ShardingException(f"Unknown table: {table_name}")
        
        return self.get_shard_table_name(table_name, user_id)

    def route_update_query(self, table_name: str, user_id: int) -> str:
        """
        Route an UPDATE query to appropriate shard
        
        Args:
            table_name: Table to update
            user_id: User ID of record to update
            
        Returns:
            Shard table name
        """
        if self.is_centralized_table(table_name):
            return table_name
        
        if not self.is_sharded_table(table_name):
            raise ShardingException(f"Unknown table: {table_name}")
        
        return self.get_shard_table_name(table_name, user_id)

    def route_delete_query(self, table_name: str, user_id: int) -> str:
        """
        Route a DELETE query to appropriate shard
        
        Args:
            table_name: Table to delete from
            user_id: User ID of record to delete
            
        Returns:
            Shard table name
        """
        if self.is_centralized_table(table_name):
            return table_name
        
        if not self.is_sharded_table(table_name):
            raise ShardingException(f"Unknown table: {table_name}")
        
        return self.get_shard_table_name(table_name, user_id)


class ShardAnalyzer:
    """Analyzes sharding distribution and provides statistics"""
    
    def __init__(self, router: ShardRouter):
        self.router = router
    
    def get_distribution_summary(self) -> Dict[str, int]:
        """
        Get expected distribution of users across shards
        (Requires database connection - simplified version shown)
        
        Returns:
            Dict with shard IDs and user counts
        """
        return {
            f"shard_{i}": f"~total_users / {self.router.num_shards}"
            for i in range(self.router.num_shards)
        }
    
    def explain_routing(self, table_name: str, user_id: int) -> Dict[str, Any]:
        """
        Explain routing decision for a query
        
        Args:
            table_name: Table being queried
            user_id: User ID being queried
            
        Returns:
            Dict with routing explanation
        """
        if self.router.is_centralized_table(table_name):
            return {
                "table": table_name,
                "type": "centralized",
                "routing": "no_sharding",
                "reason": "Table is centralized and not sharded"
            }
        
        shard_id = self.router.get_shard_id(user_id)
        shard_table = self.router.get_shard_table_name(table_name, user_id)
        
        return {
            "table": table_name,
            "type": "sharded",
            "shard_key": "user_id",
            "shard_key_value": user_id,
            "shard_id": shard_id,
            "formula": f"shard_id = {user_id} % {self.router.num_shards} = {shard_id}",
            "target_table": shard_table,
            "reason": "Hash-based partitioning by user_id"
        }


# Global router instance
_router: Optional[ShardRouter] = None


def get_router() -> ShardRouter:
    """Get or create global router instance"""
    global _router
    if _router is None:
        _router = ShardRouter(NUM_SHARDS)
    return _router


def route_query(table_name: str, query_type: str, user_id: Optional[int] = None) -> List[str]:
    """
    Convenience function to route a query
    
    Args:
        table_name: Table name
        query_type: Type of query (select, insert, update, delete)
        user_id: User ID (required for non-range queries)
        
    Returns:
        List of shard table names to query
    """
    router = get_router()
    
    if query_type.lower() == "select":
        return router.route_select_query(table_name, user_id)
    elif query_type.lower() == "insert":
        if user_id is None:
            raise ShardingException("user_id required for INSERT queries")
        return [router.route_insert_query(table_name, user_id)]
    elif query_type.lower() == "update":
        if user_id is None:
            raise ShardingException("user_id required for UPDATE queries")
        return [router.route_update_query(table_name, user_id)]
    elif query_type.lower() == "delete":
        if user_id is None:
            raise ShardingException("user_id required for DELETE queries")
        return [router.route_delete_query(table_name, user_id)]
    else:
        raise ShardingException(f"Unknown query type: {query_type}")


def get_distribution_stats() -> Dict[str, Any]:
    """
    Get sharding distribution statistics
    
    Returns:
        Dict with sharding configuration and stats
    """
    return {
        "num_shards": NUM_SHARDS,
        "shard_key": SHARD_KEY,
        "strategy": PARTITIONING_STRATEGY,
        "sharded_tables": sorted(SHARDED_TABLES),
        "centralized_tables": sorted(CENTRALIZED_TABLES),
        "expected_distribution": "Hash-based (uniform across shards)"
    }
