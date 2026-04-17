# Module B - Local API, RBAC, and SQL Optimization

## Features Implemented
- Local DB with Assignment 1-aligned core tables: `roles`, `users`, `sessions`, `groups`, `user_groups`, and `audit_logs`.
- Project tables aligned to Assignment 1: `students`, `companies`, `job_postings`, `applications`.
- Session-validated API endpoints with role enforcement (`CDS Manager` as admin-equivalent and `Student` as regular user).
- Student portfolio access control (`private`, `group`, `public`).
- CRUD APIs for companies and jobs.
- Audit logging for every write operation to both `logs/audit.log` and `audit_logs` table, including denied admin-only access attempts.
- SQL index strategy in `sql/indexes.sql` targeting query predicates and joins.
- Performance benchmark script and EXPLAIN plan capture in `scripts/benchmark_indexing.py`.

## Run locally

### MySQL backend startup (Windows PowerShell)

```powershell
pip install -r requirements.txt
$env:MODULE_B_DB_HOST="localhost"
$env:MODULE_B_DB_PORT="3306"
$env:MODULE_B_DB_USER="root"
$env:MODULE_B_DB_PASSWORD=""
$env:MODULE_B_DB_NAME="module_b"
python start_backend.py
```

`start_backend.py` will initialize sharding and run FastAPI on port `8000` by default.
To use a different port:

```powershell
$env:MODULE_B_PORT="8001"
python start_backend.py
```

### Remote shard notes
- Shard routing for distributed data uses the configured shard manager (ports `3307`, `3308`, `3309`).
- If shard hosts are unreachable, central MySQL-backed APIs still initialize where applicable and warnings are logged.

## Web UI
- Open `http://127.0.0.1:8000/` for the local frontend (login, portfolio, company/job CRUD views).
- Swagger remains available at `http://127.0.0.1:8000/docs`.

## Seed credentials
- Admin-equivalent (`CDS Manager`): `admin` / `admin123`
- Students: `student1` to `student30` with passwords `hash1` to `hash30`
- Alumni: `alumni1` to `alumni10` with passwords `hash31` to `hash40`
- Recruiters: `recruiter1` to `recruiter15` with passwords `hash41` to `hash55`
- CDS Team: `cds1` to `cds5` with passwords `hash56` to `hash60`
- CDS Manager: `cdsmanager1` / `hash61`

## Key endpoints
- `POST /login`
- `GET /isAuth`
- `GET /portfolio/{member_id}`
- `PATCH /portfolio/{member_id}`
- `POST/GET/PATCH/DELETE /companies`
- `POST/GET/PATCH/DELETE /jobs`
- `POST/GET/PATCH/DELETE /applications`
- `GET /audit-logs` (CDS Manager / admin-equivalent only)

## Benchmark
```bash
python scripts/benchmark_indexing.py
```
This writes `benchmark_results.txt` with:
- API response times before/after indexing
- SQL query times before/after indexing
- EXPLAIN QUERY PLAN snapshots before/after indexing
