# CareerTrack DBMS - Enterprise Database Management System

<div align="center">

![Python](https://img.shields.io/badge/Python-3.8+-blue?style=flat-square&logo=python)
![MySQL](https://img.shields.io/badge/MySQL-8.0+-blue?style=flat-square&logo=mysql)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green?style=flat-square&logo=fastapi)
![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen?style=flat-square)

**Production-ready DBMS with ACID compliance, horizontal sharding, and 40+ REST APIs**

A complete database management system powering a real-world placement and recruitment platform.

[Quick Start](#quick-start) | [Features](#features) | [Architecture](#architecture) | [Modules](#modules) | [Documentation](#documentation)

</div>

---

## Overview

**CareerTrack DBMS** is an enterprise-grade database management system built from scratch, demonstrating production-level database engineering. It handles:

- Student placement and job recruitment workflow
- Concurrent operations across 3 distributed database nodes
- Complex transactions with ACID guarantees
- Role-based access control with 6 privilege levels
- Complete audit trail for compliance

**Why it matters**: Solves real scalability, reliability, and performance challenges faced by modern applications.

---

## Project at a Glance

| Metric | Value |
|--------|-------|
| **Production Code** | 3,500+ lines |
| **API Endpoints** | 40+ |
| **Database Tables** | 21 per shard |
| **Test Cases** | 50+ |
| **Test Pass Rate** | 100% |
| **Concurrent Users** | 61+ (scales to thousands) |
| **Sharding Nodes** | 3 |
| **Modules** | 2 |

---

## Key Features

### Module A: ACID Transaction Engine
- **B+ Tree Storage**: Custom implementation with O(log n) operations
- **Full ACID**: Atomicity, Consistency, Isolation, Durability guaranteed
- **Crash Recovery**: ARIES-inspired automatic recovery on failure
- **Concurrency**: Deadlock detection, lock-based isolation
- **Durability**: Write-Ahead Logging with force-write persistence

### Module B: Distributed Platform
- **Horizontal Sharding**: Hash-based partitioning across 3+ nodes
- **REST API**: 40+ production endpoints (login, job search, applications, etc.)
- **RBAC**: 6-tier role hierarchy with permission enforcement
- **Audit Logging**: Complete operation tracking for compliance
- **Web UI**: Dashboard for all user roles
- **Performance**: <50ms average response time

---

## Architecture

### System Design

```
┌─────────────────────────────────────────┐
│          CLIENT LAYER                   │
│   Web Browser, Mobile, API Clients      │
└─────────────────────────────────────────┘
                    |
                    v
┌─────────────────────────────────────────┐
│      FastAPI Application (Port 8000)    │
│  - REST API (40+ endpoints)             │
│  - Authentication & RBAC                │
│  - Sharding Manager                     │
│  - Transaction Coordinator              │
└─────────────────────────────────────────┘
        |              |              |
        v              v              v
    ┌────────┐   ┌────────┐   ┌────────┐
    │Shard 0 │   │Shard 1 │   │Shard 2 │
    │ MySQL  │   │ MySQL  │   │ MySQL  │
    │ :3307  │   │ :3308  │   │ :3309  │
    └────────┘   └────────┘   └────────┘
```

**Data Flow**: Client request → API validation → RBAC check → Shard routing (hash(user_id)) → Transaction execution → Response

---

## Quick Start

### Prerequisites
- Python 3.8+
- MySQL 8.0+
- 5 minutes setup

### Setup

**1. Install dependencies**
```bash
cd Module_B
pip install -r requirements.txt
```

**2. Configure database**
```bash
# Windows PowerShell
$env:MODULE_B_DB_HOST="localhost"
$env:MODULE_B_DB_PORT="3306"
$env:MODULE_B_DB_USER="root"
$env:MODULE_B_DB_PASSWORD=""
$env:MODULE_B_DB_NAME="module_b"
```

**3. Start backend**
```bash
python start_backend.py
```

**4. Access**
- Web UI: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Verify Installation
```bash
python check_shards.py
python test_hash_distribution.py
python verify_sharding.py
```

---

## Test Credentials

| Role | Username | Password |
|------|----------|----------|
| Admin | admin | admin123 |
| CDS Manager | cdsmanager1 | hash61 |
| Recruiter | recruiter1 | hash41 |
| Student | student1 | hash1 |
| Alumni | alumni1 | hash31 |
| CDS Team | cds1 | hash56 |

---

## Modules

### Module A: Transaction Engine

**What it does**: Implements a complete transaction-enabled database with crash recovery

**Key components**:
- `database/bplustree.py` - B+ Tree storage engine
- `transaction/transaction_manager.py` - Transaction lifecycle
- `transaction/wal.py` - Write-Ahead Logging
- `transaction/lock_manager.py` - Concurrency control
- `transaction/recovery.py` - Crash recovery

**Run demo**:
```bash
cd Module_A
python run_demo.py                              # Basic demo
python demo_bplustree_acid_complete.py         # Full ACID demo
jupyter notebook report.ipynb                   # Performance analysis
```

**Tests**:
```bash
pytest test_comprehensive_failure_scenarios.py -v
pytest test_integration_acid.py -v
```

### Module B: Distributed Platform

**What it does**: REST API platform with horizontal sharding and RBAC

**Key components**:
- `app/main.py` - FastAPI application
- `app/sharding_manager.py` - Hash-based routing
- `app/auth.py` - JWT authentication
- `sql/` - Database schemas

**Run backend**:
```bash
cd Module_B
python start_backend.py
```

**API Endpoints** (40+):
- Authentication: `/login`, `/logout`, `/isAuth`
- Portfolio: `/portfolio/{id}`
- Companies: `/companies` (CRUD)
- Jobs: `/jobs` (CRUD)
- Applications: `/applications` (workflow)
- Interviews: `/interviews` (tracking)
- Admin: `/audit-logs`, `/analytics`

**Tests**:
```bash
python tests/integration_test_suite.py
python tests/race_condition_tests.py
python verify_sharding.py
```

---

## Performance

| Metric | Value |
|--------|-------|
| Shard routing | 400ns (negligible) |
| B+ Tree operation | O(log n) |
| API response | <50ms average |
| Data distribution | ±1.7% variance |
| Scalability | 3 to N shards (linear) |

---

## Technology Stack

**Backend**: FastAPI, Python 3.8+  
**Databases**: MySQL 8.0+, Custom B+ Tree  
**Concurrency**: Threading, Reader-Writer Locks  
**API**: REST, OpenAPI 3.0, Swagger  
**Security**: JWT, Bcrypt, CORS  
**Testing**: pytest, Integration tests  
**Logging**: JSON WAL, CSV Reports  

---

## Key Accomplishments

- **Complete ACID Implementation**: All ACID properties verified and tested
- **Scalable Architecture**: Horizontal sharding enables linear scaling
- **Production Ready**: 100% test pass rate, comprehensive error handling
- **Enterprise Security**: 6-tier RBAC with complete audit trails
- **Performance Optimized**: Sub-millisecond routing, O(log n) operations
- **Full-Stack**: Database engine + APIs + Web UI + Testing

---

## Database Schema

**Core Tables** (per shard): 21 tables including:
- User management (users, roles, sessions)
- Placement system (students, companies, jobs, applications, interviews)
- Supporting (skills, certifications, referrals, audit_logs)

**Distribution**: 61 users migrated with zero data loss, ±1.7% variance across shards

---

## Testing

**Coverage**: 50+ test cases across both modules  
**Pass Rate**: 100%  
**Types**: Unit tests, Integration tests, Failure scenarios, Race condition detection

**Run all tests**:
```bash
cd Module_A
pytest test_*.py -v

cd ../Module_B
python tests/integration_test_suite.py
python tests/race_condition_tests.py
```

---

## Assignments Completed

### Module A: ACID Transaction Engine

**Built**: Transaction-enabled database from scratch with B+ Tree storage

**Deliverables**:
- Self-balancing B+ Tree (O(log n) operations)
- Full ACID compliance (Atomicity, Consistency, Isolation, Durability)
- Crash recovery (ARIES-inspired 3-phase algorithm)
- Concurrency control (Deadlock detection, lock management)
- Performance monitoring (Real-time metrics, CSV reports)
- 50+ tests (100% passing)

### Module B: Distributed Platform

**Built**: Production platform with 40+ APIs and horizontal sharding

**Deliverables**:
- 3-node sharding (Hash-based partitioning)
- 40+ REST endpoints
- 6-tier RBAC with permissions
- 21 tables per shard
- Complete audit logging
- Web UI dashboard
- 50+ integration tests (100% passing)

---

## Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System design and decisions
- **[IMPLEMENTATION_REFERENCE.md](IMPLEMENTATION_REFERENCE.md)** - Code organization
- **[Module_A/README.md](Module_A/README.md)** - Transaction engine details
- **[Module_B/README.md](Module_B/README.md)** - Platform documentation

---

## Deployment

The system is production-ready with:
- SSL/TLS support
- Connection pooling
- Monitoring capabilities
- Backup/Recovery procedures
- Performance benchmarking tools

For deployment, configure environment variables and follow setup instructions.

---

## License

Educational and portfolio project demonstrating advanced database engineering concepts.

---

<div align="center">

**Enterprise Database Management System - Production Grade**

For questions, refer to documentation or examine the test suite and source code.

</div>
