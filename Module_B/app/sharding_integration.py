"""
Website-Shard Integration Layer
Bridges existing website code to use sharded MySQL backend
Maintains backward compatibility while enabling transparent sharding
"""

from typing import Dict, List, Optional, Any, Tuple
import logging
from app.sharded_db import get_db_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ShardingRouter:
    """Routes database operations to appropriate shards"""
    
    def __init__(self):
        self.db_manager = get_db_manager()
    
    # ========== USER OPERATIONS ==========
    
    def create_user(self, user_id: int, username: str, email: str, password_hash: str,
                   role_id: int, full_name: str, contact_number: str) -> bool:
        """Create new user"""
        return self.db_manager.insert_user(
            user_id=user_id,
            username=username,
            email=email,
            password_hash=password_hash,
            role_id=role_id,
            is_verified=True,
            full_name=full_name,
            contact_number=contact_number,
            status="ACTIVE"
        )
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Get user by ID"""
        return self.db_manager.get_user_by_id(user_id)
    
    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Get user by username"""
        return self.db_manager.get_user_by_username(username)
    
    def find_user_by_email(self, email: str) -> Optional[Dict]:
        """Find user by email"""
        users = self.db_manager.get_all_users_by_role(1)  # Get all users
        for user in users:
            if user.get('email') == email:
                return user
        return None
    
    def update_user(self, user_id: int, updates: Dict[str, Any]) -> bool:
        """Update user"""
        return self.db_manager.update_user(user_id, updates)
    
    def authenticate_user(self, username: str, password_hash: str) -> Optional[Dict]:
        """Authenticate user"""
        user = self.get_user_by_username(username)
        if user and user.get('password_hash') == password_hash:
            return user
        return None
    
    # ========== STUDENT OPERATIONS ==========
    
    def create_student(self, student_id: int, user_id: int, **kwargs) -> bool:
        """Create student record"""
        return self.db_manager.insert_student(
            student_id=student_id,
            user_id=user_id,
            cpi=kwargs.get('cpi', 0.0),
            program=kwargs.get('program', ''),
            discipline=kwargs.get('discipline', ''),
            graduating_year=kwargs.get('graduating_year', 2026),
            backlogs=kwargs.get('backlogs', 0),
            gender=kwargs.get('gender', 'Unknown')
        )
    
    def get_student_by_user(self, user_id: int) -> Optional[Dict]:
        """Get student by user_id"""
        return self.db_manager.get_student_by_user_id(user_id)
    
    def get_all_students(self) -> List[Dict]:
        """Get all students"""
        return self.db_manager.get_all_students()
    
    def update_student(self, student_id: int, user_id: int, updates: Dict) -> bool:
        """Update student record"""
        shard_id = self.db_manager.get_shard_id(user_id)
        table_name = self.db_manager.get_table_name("students", shard_id)
        
        # Build SET clause
        set_clauses = []
        values = []
        for key, value in updates.items():
            set_clauses.append(f"{key} = %s")
            values.append(value)
        
        values.append(student_id)
        query = f"""
        UPDATE {table_name}
        SET {', '.join(set_clauses)}
        WHERE student_id = %s
        """
        
        return self.db_manager.execute_on_shard(shard_id, query, tuple(values))
    
    # ========== COMPANY OPERATIONS ==========
    
    def create_company(self, company_id: int, user_id: int, company_name: str,
                      industry_sector: str = None, org_type: str = None) -> bool:
        """Create company record"""
        return self.db_manager.insert_company(
            company_id=company_id,
            user_id=user_id,
            company_name=company_name,
            industry_sector=industry_sector or '',
            org_type=org_type or ''
        )
    
    def get_company_by_user(self, user_id: int) -> Optional[Dict]:
        """Get company by recruiter user_id"""
        return self.db_manager.get_company_by_user_id(user_id)
    
    def get_all_companies(self) -> List[Dict]:
        """Get all companies"""
        return self.db_manager.get_all_companies()
    
    def update_company(self, company_id: int, user_id: int, updates: Dict) -> bool:
        """Update company record"""
        shard_id = self.db_manager.get_shard_id(user_id)
        table_name = self.db_manager.get_table_name("companies", shard_id)
        
        # Build SET clause
        set_clauses = []
        values = []
        for key, value in updates.items():
            set_clauses.append(f"{key} = %s")
            values.append(value)
        
        values.append(company_id)
        query = f"""
        UPDATE {table_name}
        SET {', '.join(set_clauses)}
        WHERE company_id = %s
        """
        
        return self.db_manager.execute_on_shard(shard_id, query, tuple(values))
    
    # ========== ALUMNI OPERATIONS ==========
    
    def get_alumni_by_user(self, user_id: int) -> Optional[Dict]:
        """Get alumni by user_id"""
        return self.db_manager.get_alumni_by_user_id(user_id)
    
    def get_all_alumni(self) -> List[Dict]:
        """Get all alumni"""
        return self.db_manager.get_all_alumni()
    
    # ========== SYSTEM QUERIES ==========
    
    def get_shard_stats(self) -> Dict:
        """Get statistics for all shards"""
        return self.db_manager.get_shard_statistics()
    
    def health_check(self) -> Dict[str, Any]:
        """Check sharding system health"""
        try:
            stats = self.get_shard_stats()
            return {
                "status": "healthy",
                "shards": stats
            }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }


# Global router instance
_router = None


def get_router() -> ShardingRouter:
    """Get or create global sharding router"""
    global _router
    if _router is None:
        _router = ShardingRouter()
    return _router


def initialize_router():
    """Initialize sharding router"""
    global _router
    _router = ShardingRouter()
    logger.info("[ROUTER] Sharding router initialized")
    return _router
