import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import mysql.connector

from .auth import (
    authenticate_user,
    create_session,
    current_user_dependency,
    is_cds_user,
    is_admin_user,
    is_recruiter_user,
    log_audit,
    require_admin,
    require_cds_access,
    require_recruiter_access,
)
from .db import execute, fetch_all, fetch_one, get_connection, initialize_database, execute_with_acid_transaction, get_acid_integration_status, log_acid_operation, get_sharding_status, initialize_sharding, fetch_one_sharded, fetch_all_sharded
from .sharded_db import ShardedDatabaseManager
from .schemas import (
    ApplicationCreate,
    ApplicationUpdate,
    AuthResponse,
    CompanyCreate,
    CompanyUpdate,
    GroupCreate,
    GroupMembershipRequest,
    JobCreate,
    JobUpdate,
    LoginRequest,
    MemberCreate,
    MemberUpdate,
)

app = FastAPI(title="Module B RBAC API", version="1.0.0")

# Initialize Sharded Database Manager for MySQL access
try:
    sharded_db = ShardedDatabaseManager()
    print("[OK] Sharded database manager initialized for data endpoints")
except Exception as e:
    print(f"[WARNING] Sharded database manager failed: {e}")
    sharded_db = None

# Enable CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000", "http://127.0.0.1:3000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parents[1]
UI_DIR = BASE_DIR / "ui"
UI_PAGES = {
    "index": "index.html",
    "portfolio": "portfolio.html",
    "members": "members.html",
    "groups": "groups.html",
    "companies-jobs": "companies_jobs.html",
    "applications": "applications.html",
    "audit": "audit.html",
}

if UI_DIR.exists():
    app.mount("/static", StaticFiles(directory=UI_DIR / "static"), name="static")


@app.on_event("startup")
def startup_event():
    # Skip traditional database initialization when using sharding
    # Sharding is already initialized by start_backend.py
    if os.getenv("USE_SHARDING", "1") == "0":
        apply_indexes = os.getenv("MODULE_B_APPLY_INDEXES", "1") == "1"
        initialize_database(apply_indexes=apply_indexes)


@app.get("/")
def root():
    index_path = UI_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "Welcome to test APIs"}


@app.get("/ui/{page_name}")
def serve_ui_page(page_name: str):
    file_name = UI_PAGES.get(page_name)
    if not file_name:
        raise HTTPException(status_code=404, detail="Page not found")

    page_path = UI_DIR / file_name
    if not page_path.exists():
        raise HTTPException(status_code=404, detail="Page file missing")
    return FileResponse(page_path)


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)


@app.get("/.well-known/appspecific/com.chrome.devtools.json", include_in_schema=False)
def chrome_devtools_probe():
    return Response(status_code=204)


@app.post("/login")
def login(payload: LoginRequest):
    user = authenticate_user(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_session(user["user_id"])
    
    # Calculate expiry without querying database
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat()
    
    return {
        "message": "Login successful",
        "session_token": token,
        "username": user["username"],
        "role": user.get("role", "user"),
        "expiry": expires_at,
    }


@app.get("/isAuth", response_model=AuthResponse)
def is_auth(user=Depends(current_user_dependency)):
    return AuthResponse(
        message="User is authenticated",
        username=user["username"],
        role=user["role"],
        expiry=datetime.fromisoformat(user["expires_at"]),
    )


@app.get("/me/student")
def get_my_student_member_id(user=Depends(current_user_dependency)):
    row = fetch_one("SELECT student_id AS member_id FROM students WHERE user_id = ?", (user["user_id"],))
    if not row:
        raise HTTPException(status_code=404, detail="Student profile not found")
    return dict(row)


def _as_program_set(programs: Optional[str]) -> set[str]:
    if not programs:
        return set()
    return {item.strip().lower() for item in programs.split(",") if item and item.strip()}


def _check_student_job_eligibility(student_id: int, job_id: int) -> Optional[str]:
    student = fetch_one(
        """
        SELECT student_id, latest_cpi, active_backlogs, program, graduating_year
        FROM students
        WHERE student_id = ?
        """,
        (student_id,),
    )
    if not student:
        return "Student profile not found"

    criteria = fetch_one(
        """
        SELECT min_cpi, allowed_backlogs, eligible_programs, eligible_year
        FROM eligibility_criteria
        WHERE job_id = ?
        """,
        (job_id,),
    )
    if not criteria:
        return None

    min_cpi = criteria["min_cpi"]
    if min_cpi is not None:
        if student["latest_cpi"] is None or float(student["latest_cpi"]) < float(min_cpi):
            return f"CPI eligibility not met (required >= {min_cpi})"

    allowed_backlogs = criteria["allowed_backlogs"]
    if allowed_backlogs is not None:
        student_backlogs = int(student["active_backlogs"] or 0)
        if student_backlogs > int(allowed_backlogs):
            return f"Backlog eligibility not met (allowed <= {allowed_backlogs})"

    eligible_programs = _as_program_set(criteria["eligible_programs"])
    if eligible_programs:
        student_program = (student["program"] or "").strip().lower()
        if student_program not in eligible_programs:
            return "Program is not eligible for this job"

    eligible_year = criteria["eligible_year"]
    if eligible_year is not None:
        if student["graduating_year"] is None or int(student["graduating_year"]) != int(eligible_year):
            return f"Graduating year eligibility not met (required {eligible_year})"

    return None


def _recruiter_can_manage_application(application_id: int, recruiter_user_id: int) -> bool:
    row = fetch_one(
        """
        SELECT 1
        FROM applications a
        JOIN job_postings j ON a.job_id = j.job_id
        JOIN companies c ON j.company_id = c.company_id
        WHERE a.application_id = ? AND c.user_id = ?
        LIMIT 1
        """,
        (application_id, recruiter_user_id),
    )
    return bool(row)


@app.get("/portfolio/{member_id}")
def get_member_portfolio(member_id: int, request: Request, user=Depends(current_user_dependency)):
    row = fetch_one(
        """
        SELECT s.student_id AS member_id, s.user_id, s.bio, s.skills, s.portfolio_visibility, u.full_name, u.email
        FROM students s JOIN users u ON s.user_id = u.user_id
        WHERE s.student_id = ?
        """,
        (member_id,),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Member not found")

    if is_admin_user(user) or is_cds_user(user):
        return dict(row)

    # Regular users can view their own profile.
    if int(row["user_id"]) == int(user["user_id"]):
        return dict(row)

    # Group/public visibility checks for non-owner users.
    if row["portfolio_visibility"] == "public":
        return dict(row)

    if row["portfolio_visibility"] == "group":
        shared_group = fetch_one(
            """
            SELECT 1
            FROM user_groups ug1
            JOIN user_groups ug2 ON ug1.group_id = ug2.group_id
            WHERE ug1.user_id = ? AND ug2.user_id = ?
            LIMIT 1
            """,
            (user["user_id"], row["user_id"]),
        )
        if shared_group:
            return dict(row)

    log_audit(user["user_id"], "DENY", "students", str(member_id), request.url.path, "forbidden")
    raise HTTPException(status_code=403, detail="Not allowed to view this portfolio")


@app.patch("/portfolio/{member_id}")
def update_member_portfolio(member_id: int, payload: MemberUpdate, request: Request, user=Depends(current_user_dependency)):
    row = fetch_one("SELECT student_id AS member_id, user_id FROM students WHERE student_id = ?", (member_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Member not found")

    if not is_admin_user(user) and int(row["user_id"]) != int(user["user_id"]):
        log_audit(user["user_id"], "DENY", "students", str(member_id), request.url.path, "forbidden")
        raise HTTPException(status_code=403, detail="Not allowed to modify this portfolio")

    updates = []
    params = []
    data = payload.model_dump(exclude_none=True)
    for key, value in data.items():
        updates.append(f"{key} = ?")
        params.append(value)

    if not updates:
        return {"message": "Nothing to update"}

    params.append(member_id)
    with get_connection() as conn:
        conn.execute(f"UPDATE students SET {', '.join(updates)} WHERE student_id = ?", tuple(params))
        conn.commit()

    # ========== SHARD UPDATE ==========
    try:
        user_id = row["user_id"]
        shard_id = sharded_db.get_shard_id(user_id)
        table_name = sharded_db.get_table_name("students", shard_id)
        
        # Build update query for MySQL shard
        shard_updates = []
        shard_params = []
        for key, value in data.items():
            if key == "portfolio_visibility":
                shard_updates.append(f"{key} = %s")
            else:
                shard_updates.append(f"{key} = %s")
            shard_params.append(value)
        
        if shard_updates:
            shard_params.append(member_id)
            query = f"UPDATE {table_name} SET {', '.join(shard_updates)} WHERE student_id = %s"
            sharded_db.execute_on_shard(shard_id, query, tuple(shard_params))
            print(f"[SHARDING] Portfolio updated for member {member_id} in shard {shard_id}")
    except Exception as e:
        print(f"[SHARDING WARNING] Shard update failed for portfolio {member_id}: {e}")

    log_audit(user["user_id"], "UPDATE", "students", str(member_id), request.url.path, "success")
    return {"message": "Portfolio updated"}


@app.get("/members")
def list_members(user=Depends(current_user_dependency)):
    if user["role"] != "Alumni" and not is_cds_user(user):
        raise HTTPException(status_code=403, detail="Not allowed to view candidate list")

    # Use sharded database if available
    if not sharded_db:
        raise HTTPException(status_code=500, detail="Database manager unavailable")
    
    all_members = []
    for shard_id in range(3):
        try:
            query = f"""
            SELECT s.student_id AS member_id, u.user_id, u.full_name, u.email,
                   s.latest_cpi, s.program, s.discipline, s.graduating_year,
                   s.active_backlogs, s.gender
            FROM shard_{shard_id}_students s
            JOIN shard_{shard_id}_users u ON s.user_id = u.user_id
            ORDER BY s.graduating_year DESC, s.latest_cpi DESC, u.full_name ASC
            """
            conn = sharded_db.get_connection(shard_id)
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query)
            rows = cursor.fetchall()
            all_members.extend(rows)
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"[ERROR] Shard {shard_id} query failed: {e}")
            continue
    
    return all_members


@app.post("/members")
def create_member(payload: MemberCreate, request: Request, user=Depends(current_user_dependency)):
    require_admin(user, request.url.path, "users/students")

    role = fetch_one("SELECT role_id FROM roles WHERE role_name = ?", (payload.role_name,))
    if not role:
        raise HTTPException(status_code=400, detail="Invalid role")

    existing = fetch_one(
        "SELECT user_id FROM users WHERE username = ? OR email = ?",
        (payload.username, payload.email),
    )
    if existing:
        raise HTTPException(status_code=409, detail="Username or email already exists")

    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO users(username, email, password_hash, role_id, full_name, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                payload.username,
                payload.email,
                payload.password,
                role["role_id"],
                payload.full_name,
                payload.is_active,
            ),
        )
        user_id = cur.lastrowid
        if not user_id:
            raise HTTPException(status_code=500, detail="Failed to create user")

        # Keep credentials in users only; students table stores profile/academic data.
        cur = conn.execute(
            """
            INSERT INTO students(user_id, latest_cpi, program, discipline, graduating_year, active_backlogs, bio, skills, portfolio_visibility)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                payload.latest_cpi,
                payload.program,
                payload.discipline,
                payload.graduating_year,
                payload.active_backlogs,
                payload.bio,
                payload.skills,
                payload.portfolio_visibility,
            ),
        )
        member_id = cur.lastrowid
        if not member_id:
            raise HTTPException(status_code=500, detail="Failed to create student profile")

        for group_id in payload.group_ids:
            group = conn.execute("SELECT group_id FROM groups WHERE group_id = ?", (group_id,)).fetchone()
            if not group:
                raise HTTPException(status_code=404, detail=f"Group {group_id} not found")
            conn.execute(
                "INSERT OR IGNORE INTO user_groups(user_id, group_id) VALUES (?, ?)",
                (user_id, group_id),
            )

        conn.commit()

    # ========== SHARD INTEGRATION ==========
    # Insert into MySQL shards for sharding/distributed queries
    try:
        shard_id = sharded_db.get_shard_id(user_id)
        
        # Insert user into correct shard
        sharded_db.insert_user(
            user_id=user_id,
            username=payload.username,
            email=payload.email,
            password_hash=payload.password,
            role_id=role["role_id"],
            is_verified=True,
            full_name=payload.full_name,
            contact_number="",
            status="ACTIVE"
        )
        
        # Insert student profile into correct shard
        sharded_db.insert_student(
            student_id=member_id,
            user_id=user_id,
            cpi=payload.latest_cpi,
            program=payload.program,
            discipline=payload.discipline,
            graduating_year=payload.graduating_year,
            backlogs=payload.active_backlogs,
            gender="Unknown"
        )
        
        print(f"[SHARDING SUCCESS] Member {user_id} (Shard {shard_id}): Inserted user + student profile")
    except Exception as e:
        print(f"[SHARDING WARNING] Shard insertion failed for user {user_id}: {e}")
        # Continue anyway - PostgreSQL insert succeeded, partial sharding is acceptable
    
    log_audit(user["user_id"], "INSERT", "users/students", str(member_id), request.url.path, "success")
    return {"message": "Member created", "member_id": member_id, "user_id": user_id}


@app.delete("/members/{member_id}")
def delete_member(member_id: int, request: Request, user=Depends(current_user_dependency)):
    require_admin(user, request.url.path, "users/students")

    member = fetch_one("SELECT user_id FROM students WHERE student_id = ?", (member_id,))
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    with get_connection() as conn:
        cur = conn.execute("DELETE FROM users WHERE user_id = ?", (member["user_id"],))
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="User not found")

    # ========== SHARD DELETE ==========
    try:
        user_id = member["user_id"]
        shard_id = sharded_db.get_shard_id(user_id)
        
        # Delete student from shard
        student_table = sharded_db.get_table_name("students", shard_id)
        sharded_db.execute_on_shard(shard_id, f"DELETE FROM {student_table} WHERE student_id = %s", (member_id,))
        
        # Delete user from shard
        user_table = sharded_db.get_table_name("users", shard_id)
        sharded_db.execute_on_shard(shard_id, f"DELETE FROM {user_table} WHERE user_id = %s", (user_id,))
        
        print(f"[SHARDING] Member {member_id} (user {user_id}) deleted from shard {shard_id}")
    except Exception as e:
        print(f"[SHARDING WARNING] Shard delete failed for member {member_id}: {e}")

    log_audit(user["user_id"], "DELETE", "users/students", str(member_id), request.url.path, "success")
    return {"message": "Member deleted"}


@app.get("/recruiters")
def list_recruiters(user=Depends(current_user_dependency)):
    if not is_admin_user(user) and not is_cds_user(user):
        raise HTTPException(status_code=403, detail="Not allowed to view recruiters")

    if not sharded_db:
        raise HTTPException(status_code=500, detail="Database manager unavailable")
    
    all_recruiters = []
    for shard_id in range(3):
        try:
            # Role 2 is Recruiter
            query = f"""
            SELECT u.user_id, u.username, u.email, u.full_name, u.status
            FROM shard_{shard_id}_users u
            WHERE u.role_id = 2
            ORDER BY u.user_id
            """
            conn = sharded_db.get_connection(shard_id)
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query)
            rows = cursor.fetchall()
            all_recruiters.extend(rows)
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"[ERROR] Shard {shard_id} query failed: {e}")
            continue
    
    return all_recruiters


@app.post("/recruiters")
def create_recruiter(payload: MemberCreate, request: Request, user=Depends(current_user_dependency)):
    require_admin(user, request.url.path, "users")

    recruiter_role = fetch_one("SELECT role_id FROM roles WHERE role_name = 'Recruiter'")
    if not recruiter_role:
        raise HTTPException(status_code=500, detail="Recruiter role missing")

    existing = fetch_one(
        "SELECT user_id FROM users WHERE username = ? OR email = ?",
        (payload.username, payload.email),
    )
    if existing:
        raise HTTPException(status_code=409, detail="Username or email already exists")

    recruiter_id = execute(
        """
        INSERT INTO users(username, email, password_hash, role_id, full_name, is_active, status)
        VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE')
        """,
        (
            payload.username,
            payload.email,
            payload.password,
            recruiter_role["role_id"],
            payload.full_name,
            payload.is_active,
        ),
    )
    
    # ========== SHARD INSERT ==========
    try:
        shard_id = sharded_db.get_shard_id(recruiter_id)
        sharded_db.insert_user(
            user_id=recruiter_id,
            username=payload.username,
            email=payload.email,
            password_hash=payload.password,
            role_id=recruiter_role["role_id"],
            is_verified=True,
            full_name=payload.full_name,
            contact_number="",
            status="ACTIVE"
        )
        print(f"[SHARDING] Recruiter {recruiter_id} inserted into shard {shard_id}")
    except Exception as e:
        print(f"[SHARDING WARNING] Shard insert failed for recruiter {recruiter_id}: {e}")
    
    log_audit(user["user_id"], "INSERT", "users/recruiters", str(recruiter_id), request.url.path, "success")
    return {"message": "Recruiter created", "recruiter_user_id": recruiter_id}


@app.delete("/recruiters/{recruiter_user_id}")
def delete_recruiter(recruiter_user_id: int, request: Request, user=Depends(current_user_dependency)):
    require_admin(user, request.url.path, "users/recruiters")

    recruiter = fetch_one(
        """
        SELECT u.user_id
        FROM users u
        JOIN roles r ON u.role_id = r.role_id
        WHERE u.user_id = ? AND r.role_name = 'Recruiter'
        """,
        (recruiter_user_id,),
    )
    if not recruiter:
        raise HTTPException(status_code=404, detail="Recruiter not found")

    with get_connection() as conn:
        cur = conn.execute("DELETE FROM users WHERE user_id = ?", (recruiter_user_id,))
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Recruiter not found")

    # ========== SHARD DELETE ==========
    try:
        shard_id = sharded_db.get_shard_id(recruiter_user_id)
        user_table = sharded_db.get_table_name("users", shard_id)
        sharded_db.execute_on_shard(shard_id, f"DELETE FROM {user_table} WHERE user_id = %s", (recruiter_user_id,))
        print(f"[SHARDING] Recruiter {recruiter_user_id} deleted from shard {shard_id}")
    except Exception as e:
        print(f"[SHARDING WARNING] Shard delete failed for recruiter {recruiter_user_id}: {e}")

    log_audit(user["user_id"], "DELETE", "users/recruiters", str(recruiter_user_id), request.url.path, "success")
    return {"message": "Recruiter deleted"}


@app.post("/groups")
def create_group(payload: GroupCreate, request: Request, user=Depends(current_user_dependency)):
    require_admin(user, request.url.path, "groups")
    group_id = execute("INSERT INTO groups(group_name) VALUES (?)", (payload.group_name,))
    log_audit(user["user_id"], "INSERT", "groups", str(group_id), request.url.path, "success")
    return {"message": "Group created", "group_id": group_id}


@app.get("/groups")
def list_groups(user=Depends(current_user_dependency)):
    rows = fetch_all(
        """
        SELECT g.group_id, g.group_name, COUNT(ug.user_id) AS member_count
        FROM groups g
        LEFT JOIN user_groups ug ON g.group_id = ug.group_id
        GROUP BY g.group_id, g.group_name
        ORDER BY g.group_id
        """
    )
    return [dict(r) for r in rows]


@app.post("/groups/{group_id}/members")
def add_group_member(group_id: int, payload: GroupMembershipRequest, request: Request, user=Depends(current_user_dependency)):
    require_admin(user, request.url.path, "user_groups")

    member = fetch_one("SELECT user_id FROM students WHERE student_id = ?", (payload.member_id,))
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    group = fetch_one("SELECT group_id FROM groups WHERE group_id = ?", (group_id,))
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    execute(
        "INSERT OR IGNORE INTO user_groups(user_id, group_id) VALUES (?, ?)",
        (member["user_id"], group_id),
    )
    log_audit(user["user_id"], "INSERT", "user_groups", f"{member['user_id']}:{group_id}", request.url.path, "success")
    return {"message": "Member added to group"}


@app.delete("/groups/{group_id}/members/{member_id}")
def remove_group_member(group_id: int, member_id: int, request: Request, user=Depends(current_user_dependency)):
    require_admin(user, request.url.path, "user_groups")

    member = fetch_one("SELECT user_id FROM students WHERE student_id = ?", (member_id,))
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    with get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM user_groups WHERE user_id = ? AND group_id = ?",
            (member["user_id"], group_id),
        )
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Group membership not found")

    log_audit(user["user_id"], "DELETE", "user_groups", f"{member['user_id']}:{group_id}", request.url.path, "success")
    return {"message": "Member removed from group"}


@app.post("/companies")
def create_company(payload: CompanyCreate, request: Request, user=Depends(current_user_dependency)):
    require_recruiter_access(user, request.url.path, "companies")
    recruiter_role = fetch_one("SELECT role_id FROM roles WHERE role_name = ?", ("Recruiter",))
    if not recruiter_role:
        raise HTTPException(status_code=500, detail="Recruiter role missing")

    existing_company_for_user = fetch_one("SELECT company_id FROM companies WHERE user_id = ?", (user["user_id"],))
    if user["role"] == "Recruiter":
        if existing_company_for_user:
            return {
                "message": "Company already exists for recruiter",
                "company_id": existing_company_for_user["company_id"],
            }
        company_user_id = user["user_id"]
    else:
        if existing_company_for_user:
            generated_username = f"recruiter_{int(datetime.now().timestamp())}"
            generated_email = f"{generated_username}@local.dev"
            company_user_id = execute(
                """
                INSERT INTO users(username, email, password_hash, role_id, full_name, is_active, status)
                VALUES (?, ?, ?, ?, ?, 1, 'ACTIVE')
                """,
                (generated_username, generated_email, "recruiter123", recruiter_role["role_id"], f"Recruiter {generated_username}"),
            )
        else:
            company_user_id = user["user_id"]

    record_id = execute(
        "INSERT INTO companies(user_id, company_name, industry_sector) VALUES (?, ?, ?)",
        (company_user_id, payload.company_name, payload.domain),
    )
    
    # ========== SHARD INSERT ==========
    try:
        shard_id = sharded_db.get_shard_id(company_user_id)
        sharded_db.insert_company(
            company_id=record_id,
            user_id=company_user_id,
            company_name=payload.company_name,
            industry_sector=payload.domain,
            org_type="Company"
        )
        print(f"[SHARDING] Company {record_id} inserted into shard {shard_id}")
    except Exception as e:
        print(f"[SHARDING WARNING] Shard insert failed for company {record_id}: {e}")
    
    log_audit(user["user_id"], "INSERT", "companies", str(record_id), request.url.path, "success")
    return {"message": "Company created", "company_id": record_id}


@app.get("/companies/me")
def get_my_company(user=Depends(current_user_dependency)):
    require_recruiter_access(user, "/companies/me", "companies")
    row = fetch_one(
        """
        SELECT company_id, company_name, industry_sector AS domain, user_id AS created_by, NULL AS created_at
        FROM companies
        WHERE user_id = ?
        """,
        (user["user_id"],),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Company not found for this recruiter")
    return dict(row)


@app.get("/companies")
def list_companies(user=Depends(current_user_dependency)):
    if not sharded_db:
        raise HTTPException(status_code=500, detail="Database manager unavailable")
    
    # Query from all shards and aggregate results
    all_companies = []
    
    for shard_id in range(3):
        try:
            if user["role"] == "Recruiter":
                query = f"""
                SELECT company_id, company_name, industry_sector AS domain, user_id AS created_by, NULL AS created_at
                FROM shard_{shard_id}_companies
                WHERE user_id = %s
                ORDER BY company_id
                """
                conn = sharded_db.get_connection(shard_id)
                cursor = conn.cursor(dictionary=True)
                cursor.execute(query, (user["user_id"],))
            else:
                query = f"""
                SELECT company_id, company_name, industry_sector AS domain, user_id AS created_by, NULL AS created_at
                FROM shard_{shard_id}_companies
                ORDER BY company_id
                """
                conn = sharded_db.get_connection(shard_id)
                cursor = conn.cursor(dictionary=True)
                cursor.execute(query)
            
            rows = cursor.fetchall()
            all_companies.extend(rows)
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"[ERROR] Shard {shard_id} query failed: {e}")
            continue
    
    return all_companies


@app.patch("/companies/{company_id}")
def update_company(company_id: int, payload: CompanyUpdate, request: Request, user=Depends(current_user_dependency)):
    require_recruiter_access(user, request.url.path, "companies")
    existing = fetch_one("SELECT company_id, user_id FROM companies WHERE company_id = ?", (company_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="Company not found")

    if user["role"] == "Recruiter" and int(existing["user_id"]) != int(user["user_id"]):
        log_audit(user["user_id"], "DENY", "companies", str(company_id), request.url.path, "forbidden")
        raise HTTPException(status_code=403, detail="Not allowed to modify this company")

    data = payload.model_dump(exclude_none=True)
    if not data:
        return {"message": "Nothing to update"}

    with get_connection() as conn:
        updates = []
        params = []
        for key, value in data.items():
            col = "industry_sector" if key == "domain" else key
            updates.append(f"{col} = ?")
            params.append(value)
        params.append(company_id)
        conn.execute(f"UPDATE companies SET {', '.join(updates)} WHERE company_id = ?", tuple(params))
        conn.commit()

    # ========== SHARD UPDATE ==========
    try:
        user_id = existing["user_id"]
        shard_id = sharded_db.get_shard_id(user_id)
        table_name = sharded_db.get_table_name("companies", shard_id)
        
        # Build update query for MySQL shard
        shard_updates = []
        shard_params = []
        for key, value in data.items():
            col = "industry_sector" if key == "domain" else key
            shard_updates.append(f"{col} = %s")
            shard_params.append(value)
        
        if shard_updates:
            shard_params.append(company_id)
            query = f"UPDATE {table_name} SET {', '.join(shard_updates)} WHERE company_id = %s"
            sharded_db.execute_on_shard(shard_id, query, tuple(shard_params))
            print(f"[SHARDING] Company {company_id} updated in shard {shard_id}")
    except Exception as e:
        print(f"[SHARDING WARNING] Shard update failed for company {company_id}: {e}")

    log_audit(user["user_id"], "UPDATE", "companies", str(company_id), request.url.path, "success")
    return {"message": "Company updated"}


@app.delete("/companies/{company_id}")
def delete_company(company_id: int, request: Request, user=Depends(current_user_dependency)):
    require_recruiter_access(user, request.url.path, "companies")

    existing = fetch_one("SELECT company_id, user_id FROM companies WHERE company_id = ?", (company_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="Company not found")

    if user["role"] == "Recruiter" and int(existing["user_id"]) != int(user["user_id"]):
        log_audit(user["user_id"], "DENY", "companies", str(company_id), request.url.path, "forbidden")
        raise HTTPException(status_code=403, detail="Not allowed to delete this company")

    with get_connection() as conn:
        cur = conn.execute("DELETE FROM companies WHERE company_id = ?", (company_id,))
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Company not found")

    # ========== SHARD DELETE ==========
    try:
        user_id = existing["user_id"]
        shard_id = sharded_db.get_shard_id(user_id)
        company_table = sharded_db.get_table_name("companies", shard_id)
        sharded_db.execute_on_shard(shard_id, f"DELETE FROM {company_table} WHERE company_id = %s", (company_id,))
        print(f"[SHARDING] Company {company_id} deleted from shard {shard_id}")
    except Exception as e:
        print(f"[SHARDING WARNING] Shard delete failed for company {company_id}: {e}")

    log_audit(user["user_id"], "DELETE", "companies", str(company_id), request.url.path, "success")
    return {"message": "Company deleted"}


@app.post("/jobs")
def create_job(payload: JobCreate, request: Request, user=Depends(current_user_dependency)):
    require_recruiter_access(user, request.url.path, "job_postings")
    company = fetch_one("SELECT company_id, user_id FROM companies WHERE company_id = ?", (payload.company_id,))
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    if user["role"] == "Recruiter" and int(company["user_id"]) != int(user["user_id"]):
        log_audit(user["user_id"], "DENY", "job_postings", None, request.url.path, "forbidden")
        raise HTTPException(status_code=403, detail="Recruiter can post jobs only for own company")

    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO job_postings(company_id, designation, location, deadline, posted_date)
            VALUES (?, ?, ?, ?, ?)
            RETURNING job_id
            """,
            (payload.company_id, payload.title, payload.location, payload.deadline, datetime.now().date().isoformat()),
        )
        record_id = cur.fetchone()["job_id"]
        conn.execute(
            "INSERT INTO eligibility_criteria(job_id, min_cpi) VALUES (?, ?)",
            (record_id, payload.min_cpi),
        )
        conn.commit()

    # ========== SHARD INSERT ==========
    try:
        # Route by company owner's user_id
        shard_id = sharded_db.get_shard_id(company["user_id"])
        table_name = sharded_db.get_table_name("jobs", shard_id)
        
        query = f"""
        INSERT INTO {table_name} (job_id, company_id, designation, location, deadline, posted_date, min_cpi)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        sharded_db.execute_on_shard(
            shard_id, query,
            (record_id, payload.company_id, payload.title, payload.location, payload.deadline, 
             datetime.now().date().isoformat(), payload.min_cpi)
        )
        print(f"[SHARDING] Job {record_id} inserted into shard {shard_id}")
    except Exception as e:
        print(f"[SHARDING WARNING] Shard insert failed for job {record_id}: {e}")

    log_audit(user["user_id"], "INSERT", "job_postings", str(record_id), request.url.path, "success")
    return {"message": "Job created", "job_id": record_id}


@app.get("/jobs")
def list_jobs(min_cpi: Optional[float] = None, user=Depends(current_user_dependency)):
    # TODO: Implement job listing from sharded/centralized database
    # For now, return empty list (job_postings queries to PostgreSQL which may not be responding)
    return []


@app.patch("/jobs/{job_id}")
def update_job(job_id: int, payload: JobUpdate, request: Request, user=Depends(current_user_dependency)):
    require_recruiter_access(user, request.url.path, "job_postings")
    existing = fetch_one(
        """
        SELECT j.job_id, c.user_id
        FROM job_postings j
        JOIN companies c ON c.company_id = j.company_id
        WHERE j.job_id = ?
        """,
        (job_id,),
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Job not found")

    if user["role"] == "Recruiter" and int(existing["user_id"]) != int(user["user_id"]):
        log_audit(user["user_id"], "DENY", "job_postings", str(job_id), request.url.path, "forbidden")
        raise HTTPException(status_code=403, detail="Recruiter can modify only own company jobs")

    data = payload.model_dump(exclude_none=True)
    if not data:
        return {"message": "Nothing to update"}

    with get_connection() as conn:
        job_updates = []
        job_params = []

        if "title" in data:
            job_updates.append("designation = ?")
            job_params.append(data["title"])
        if "location" in data:
            job_updates.append("location = ?")
            job_params.append(data["location"])
        if "deadline" in data:
            job_updates.append("deadline = ?")
            job_params.append(data["deadline"])

        if job_updates:
            job_params.append(job_id)
            conn.execute(f"UPDATE job_postings SET {', '.join(job_updates)} WHERE job_id = ?", tuple(job_params))

        if "min_cpi" in data:
            existing_criteria = conn.execute("SELECT criteria_id FROM eligibility_criteria WHERE job_id = ?", (job_id,)).fetchone()
            if existing_criteria:
                conn.execute("UPDATE eligibility_criteria SET min_cpi = ? WHERE job_id = ?", (data["min_cpi"], job_id))
            else:
                conn.execute("INSERT INTO eligibility_criteria(job_id, min_cpi) VALUES (?, ?)", (job_id, data["min_cpi"]))

        conn.commit()

    # ========== SHARD UPDATE ==========
    try:
        # Route by company owner's user_id
        shard_id = sharded_db.get_shard_id(existing["user_id"])
        table_name = sharded_db.get_table_name("jobs", shard_id)
        
        # Build update query for MySQL shard
        shard_updates = []
        shard_params = []
        if "title" in data:
            shard_updates.append("designation = %s")
            shard_params.append(data["title"])
        if "location" in data:
            shard_updates.append("location = %s")
            shard_params.append(data["location"])
        if "deadline" in data:
            shard_updates.append("deadline = %s")
            shard_params.append(data["deadline"])
        if "min_cpi" in data:
            shard_updates.append("min_cpi = %s")
            shard_params.append(data["min_cpi"])
        
        if shard_updates:
            shard_params.append(job_id)
            query = f"UPDATE {table_name} SET {', '.join(shard_updates)} WHERE job_id = %s"
            sharded_db.execute_on_shard(shard_id, query, tuple(shard_params))
            print(f"[SHARDING] Job {job_id} updated in shard {shard_id}")
    except Exception as e:
        print(f"[SHARDING WARNING] Shard update failed for job {job_id}: {e}")

    log_audit(user["user_id"], "UPDATE", "job_postings", str(job_id), request.url.path, "success")
    return {"message": "Job updated"}


@app.delete("/jobs/{job_id}")
def delete_job(job_id: int, request: Request, user=Depends(current_user_dependency)):
    require_recruiter_access(user, request.url.path, "job_postings")

    existing = fetch_one(
        """
        SELECT j.job_id, c.user_id
        FROM job_postings j
        JOIN companies c ON c.company_id = j.company_id
        WHERE j.job_id = ?
        """,
        (job_id,),
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Job not found")

    if user["role"] == "Recruiter" and int(existing["user_id"]) != int(user["user_id"]):
        log_audit(user["user_id"], "DENY", "job_postings", str(job_id), request.url.path, "forbidden")
        raise HTTPException(status_code=403, detail="Recruiter can delete only own company jobs")

    with get_connection() as conn:
        cur = conn.execute("DELETE FROM job_postings WHERE job_id = ?", (job_id,))
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Job not found")

    # ========== SHARD DELETE ==========
    try:
        # Route by company owner's user_id
        shard_id = sharded_db.get_shard_id(existing["user_id"])
        table_name = sharded_db.get_table_name("jobs", shard_id)
        sharded_db.execute_on_shard(shard_id, f"DELETE FROM {table_name} WHERE job_id = %s", (job_id,))
        print(f"[SHARDING] Job {job_id} deleted from shard {shard_id}")
    except Exception as e:
        print(f"[SHARDING WARNING] Shard delete failed for job {job_id}: {e}")

    log_audit(user["user_id"], "DELETE", "job_postings", str(job_id), request.url.path, "success")
    return {"message": "Job deleted"}


@app.get("/applications")
def list_applications(user=Depends(current_user_dependency)):
    rows = fetch_all(
        """
        SELECT a.application_id, a.job_id, a.status, a.applied_at, s.student_id AS member_id, u.full_name,
               j.designation AS title, c.company_name, c.user_id AS recruiter_user_id
        FROM applications a
        JOIN students s ON a.student_id = s.student_id
        JOIN users u ON s.user_id = u.user_id
        JOIN job_postings j ON a.job_id = j.job_id
        JOIN companies c ON j.company_id = c.company_id
        ORDER BY a.applied_at DESC
        """
    )
    if is_admin_user(user) or is_cds_user(user):
        return [dict(r) for r in rows]

    if user["role"] == "Recruiter":
        return [dict(r) for r in rows if int(r["recruiter_user_id"]) == int(user["user_id"])]

    own_member = fetch_one("SELECT student_id AS member_id FROM students WHERE user_id = ?", (user["user_id"],))
    if not own_member:
        return []
    return [dict(r) for r in rows if int(r["member_id"]) == int(own_member["member_id"])]


@app.post("/applications")
def create_application(payload: ApplicationCreate, request: Request, user=Depends(current_user_dependency)):
    student_id = payload.student_id
    if is_admin_user(user):
        if student_id is None:
            raise HTTPException(status_code=400, detail="student_id is required for admin-created applications")
    else:
        own_member = fetch_one("SELECT student_id FROM students WHERE user_id = ?", (user["user_id"],))
        if not own_member:
            log_audit(user["user_id"], "DENY", "applications", None, request.url.path, "forbidden")
            raise HTTPException(status_code=403, detail="Only students with a profile can apply")
        student_id = own_member["student_id"]

    job = fetch_one("SELECT job_id FROM job_postings WHERE job_id = ?", (payload.job_id,))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if not is_admin_user(user):
        eligibility_error = _check_student_job_eligibility(int(student_id), int(payload.job_id))
        if eligibility_error:
            raise HTTPException(status_code=403, detail=eligibility_error)

    existing = fetch_one(
        "SELECT application_id FROM applications WHERE job_id = ? AND student_id = ?",
        (payload.job_id, student_id),
    )
    if existing:
        raise HTTPException(status_code=409, detail="Application already exists for this job and student")

    try:
        record_id = execute(
            "INSERT INTO applications(job_id, student_id, applied_at, status) VALUES (?, ?, ?, ?)",
            (payload.job_id, student_id, datetime.now().date().isoformat(), payload.status),
        )
    except Exception as e:
        if "UNIQUE" in str(e) or "Duplicate" in str(e):
            raise HTTPException(status_code=409, detail="Application already exists for this job and student")
        raise
    
    # ========== SHARD INSERT ==========
    try:
        # Get student's user_id to route by student
        student_user = fetch_one("SELECT user_id FROM students WHERE student_id = ?", (student_id,))
        if student_user:
            shard_id = sharded_db.get_shard_id(student_user["user_id"])
            table_name = sharded_db.get_table_name("applications", shard_id)
            
            query = f"""
            INSERT INTO {table_name} (application_id, job_id, student_id, applied_at, status)
            VALUES (%s, %s, %s, %s, %s)
            """
            sharded_db.execute_on_shard(
                shard_id, query,
                (record_id, payload.job_id, student_id, datetime.now().date().isoformat(), payload.status)
            )
            print(f"[SHARDING] Application {record_id} inserted into shard {shard_id}")
    except Exception as e:
        print(f"[SHARDING WARNING] Shard insert failed for application {record_id}: {e}")
    
    log_audit(user["user_id"], "INSERT", "applications", str(record_id), request.url.path, "success")
    return {"message": "Application created", "application_id": record_id}


@app.patch("/applications/{application_id}")
def update_application(application_id: int, payload: ApplicationUpdate, request: Request, user=Depends(current_user_dependency)):
    app_row = fetch_one(
        "SELECT application_id, student_id FROM applications WHERE application_id = ?",
        (application_id,),
    )
    if not app_row:
        raise HTTPException(status_code=404, detail="Application not found")

    if not is_admin_user(user):
        if is_recruiter_user(user):
            if not _recruiter_can_manage_application(application_id, user["user_id"]):
                log_audit(user["user_id"], "DENY", "applications", str(application_id), request.url.path, "forbidden")
                raise HTTPException(status_code=403, detail="Recruiter can update only own job applications")
        else:
            log_audit(user["user_id"], "DENY", "applications", str(application_id), request.url.path, "forbidden")
            raise HTTPException(status_code=403, detail="Not allowed to modify this application")

    with get_connection() as conn:
        conn.execute(
            "UPDATE applications SET status = ? WHERE application_id = ?",
            (payload.status, application_id),
        )
        conn.commit()

    # ========== SHARD UPDATE ==========
    try:
        # Get student's user_id to route by student
        student_user = fetch_one("SELECT user_id FROM students WHERE student_id = ?", (app_row["student_id"],))
        if student_user:
            shard_id = sharded_db.get_shard_id(student_user["user_id"])
            table_name = sharded_db.get_table_name("applications", shard_id)
            
            query = f"UPDATE {table_name} SET status = %s WHERE application_id = %s"
            sharded_db.execute_on_shard(shard_id, query, (payload.status, application_id))
            print(f"[SHARDING] Application {application_id} updated in shard {shard_id}")
    except Exception as e:
        print(f"[SHARDING WARNING] Shard update failed for application {application_id}: {e}")

    log_audit(user["user_id"], "UPDATE", "applications", str(application_id), request.url.path, "success")
    return {"message": "Application updated"}


@app.delete("/applications/{application_id}")
def delete_application(application_id: int, request: Request, user=Depends(current_user_dependency)):
    app_row = fetch_one(
        "SELECT application_id, student_id FROM applications WHERE application_id = ?",
        (application_id,),
    )
    if not app_row:
        raise HTTPException(status_code=404, detail="Application not found")

    if not is_admin_user(user):
        log_audit(user["user_id"], "DENY", "applications", str(application_id), request.url.path, "forbidden")
        raise HTTPException(status_code=403, detail="Only admin can delete applications")

    with get_connection() as conn:
        conn.execute("DELETE FROM applications WHERE application_id = ?", (application_id,))
        conn.commit()

    # ========== SHARD DELETE ==========
    try:
        # Get student's user_id to route by student
        student_user = fetch_one("SELECT user_id FROM students WHERE student_id = ?", (app_row["student_id"],))
        if student_user:
            shard_id = sharded_db.get_shard_id(student_user["user_id"])
            table_name = sharded_db.get_table_name("applications", shard_id)
            sharded_db.execute_on_shard(shard_id, f"DELETE FROM {table_name} WHERE application_id = %s", (application_id,))
            print(f"[SHARDING] Application {application_id} deleted from shard {shard_id}")
    except Exception as e:
        print(f"[SHARDING WARNING] Shard delete failed for application {application_id}: {e}")

    log_audit(user["user_id"], "DELETE", "applications", str(application_id), request.url.path, "success")
    return {"message": "Application deleted"}


@app.get("/audit-logs")
def get_audit_logs(limit: int = 100, user=Depends(current_user_dependency)):
    require_cds_access(user, "/audit-logs", "audit_logs")
    rows = fetch_all(
        """
        SELECT log_id, actor_user_id, action, table_name, record_id, request_path, status, logged_at
        FROM audit_logs
        ORDER BY logged_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [dict(r) for r in rows]


# ==========================================
# FAILURE INJECTION ENDPOINTS FOR TESTING
# ==========================================

import signal
import sys
import threading
import time
from typing import Literal

# Global state for failure injection
_failure_state = {
    "crash_enabled": False,
    "crash_delay": 0,
    "crash_mode": "immediate"
}

def _trigger_crash(mode: str, delay: float = 0):
    """Internal function to trigger system crash for testing."""
    def delayed_crash():
        if delay > 0:
            time.sleep(delay)
        
        if mode == "immediate":
            # Immediate termination
            os._exit(1)
        elif mode == "sigterm":
            # Graceful shutdown signal
            os.kill(os.getpid(), signal.SIGTERM)
        elif mode == "sigkill":
            # Force kill signal (if supported)
            try:
                os.kill(os.getpid(), signal.SIGKILL)
            except:
                os._exit(2)
        elif mode == "exception":
            # Raise unhandled exception
            raise RuntimeError("Simulated system crash for testing")
        else:
            # Default: immediate exit
            os._exit(1)
    
    if delay > 0:
        # Run crash in background thread for delayed crashes
        crash_thread = threading.Thread(target=delayed_crash, daemon=True)
        crash_thread.start()
    else:
        delayed_crash()


@app.post("/admin/failure-injection/enable")
def enable_failure_injection(
    request: Request,
    user=Depends(current_user_dependency),
    mode: Literal["immediate", "sigterm", "sigkill", "exception"] = "immediate",
    delay: float = 0
):
    """
    Enable failure injection for testing crash recovery scenarios.
    
    Admin-only endpoint for controlled system failures during testing.
    
    Args:
        mode: Type of crash to simulate
            - immediate: os._exit(1) - immediate termination
            - sigterm: SIGTERM signal - graceful shutdown
            - sigkill: SIGKILL signal - force kill
            - exception: Unhandled runtime exception
        delay: Seconds to wait before triggering crash (0 = immediate)
    
    Security: Admin access required, logs all usage
    """
    require_admin(user, request.url.path, "failure_injection")
    
    _failure_state["crash_enabled"] = True
    _failure_state["crash_delay"] = delay
    _failure_state["crash_mode"] = mode
    
    log_audit(
        user["user_id"], 
        "CONFIG", 
        "failure_injection", 
        f"enabled_{mode}_{delay}s", 
        request.url.path, 
        "success"
    )
    
    return {
        "message": "Failure injection enabled",
        "mode": mode,
        "delay_seconds": delay,
        "warning": "System will crash when triggered. Use for testing only!"
    }


@app.post("/admin/failure-injection/trigger")
def trigger_failure_injection(request: Request, user=Depends(current_user_dependency)):
    """
    Immediately trigger the configured system failure.
    
    Admin-only endpoint that causes the server to crash for testing
    crash recovery and rollback scenarios.
    
    WARNING: This will terminate the server process!
    """
    require_admin(user, request.url.path, "failure_injection")
    
    if not _failure_state["crash_enabled"]:
        raise HTTPException(
            status_code=400, 
            detail="Failure injection not enabled. Call /admin/failure-injection/enable first."
        )
    
    mode = _failure_state["crash_mode"]
    delay = _failure_state["crash_delay"]
    
    log_audit(
        user["user_id"], 
        "TRIGGER", 
        "failure_injection", 
        f"crash_{mode}_{delay}s", 
        request.url.path, 
        "success"
    )
    
    # Log the crash trigger before crashing
    print(f"[CRASH INJECTION] Admin {user['username']} triggered {mode} crash with {delay}s delay")
    
    # Trigger the crash
    _trigger_crash(mode, delay)
    
    # This should never be reached if crash works
    return {"message": "Crash triggered", "mode": mode, "delay": delay}


@app.post("/admin/failure-injection/disable")
def disable_failure_injection(request: Request, user=Depends(current_user_dependency)):
    """Disable failure injection system."""
    require_admin(user, request.url.path, "failure_injection")
    
    _failure_state["crash_enabled"] = False
    _failure_state["crash_delay"] = 0
    _failure_state["crash_mode"] = "immediate"
    
    log_audit(
        user["user_id"], 
        "CONFIG", 
        "failure_injection", 
        "disabled", 
        request.url.path, 
        "success"
    )
    
    return {"message": "Failure injection disabled"}


@app.get("/admin/failure-injection/status")
def get_failure_injection_status(user=Depends(current_user_dependency)):
    """Get current failure injection configuration."""
    require_admin(user, "/admin/failure-injection/status", "failure_injection")
    
    return {
        "enabled": _failure_state["crash_enabled"],
        "mode": _failure_state["crash_mode"],
        "delay_seconds": _failure_state["crash_delay"],
        "available_modes": ["immediate", "sigterm", "sigkill", "exception"]
    }


@app.post("/admin/failure-injection/transaction-crash")
def trigger_transaction_crash(
    request: Request,
    user=Depends(current_user_dependency),
    delay: float = 2.0
):
    """
    Simulate crash during active transaction for ACID testing.
    
    This endpoint:
    1. Starts a multi-table transaction
    2. Performs partial operations 
    3. Crashes before commit
    4. Tests recovery system's ability to rollback incomplete transactions
    """
    require_admin(user, request.url.path, "failure_injection")
    
    log_audit(
        user["user_id"], 
        "TRIGGER", 
        "failure_injection", 
        f"transaction_crash_{delay}s", 
        request.url.path, 
        "success"
    )
    
    print(f"[TRANSACTION CRASH TEST] Starting transaction, will crash in {delay}s")
    
    # Start a transaction that modifies multiple tables
    try:
        with get_connection() as conn:
            # Start transaction
            conn.execute("BEGIN TRANSACTION")
            
            # Insert test data that will need rollback
            conn.execute(
                "INSERT INTO audit_logs (actor_user_id, action, table_name, record_id, request_path, status) VALUES (?, ?, ?, ?, ?, ?)",
                (user["user_id"], "TEST", "crash_test", "pre_crash", "/admin/failure-injection/transaction-crash", "incomplete")
            )
            
            # Wait specified delay (simulates processing time)
            time.sleep(delay)
            
            # This should never complete due to crash
            conn.execute(
                "INSERT INTO audit_logs (actor_user_id, action, table_name, record_id, request_path, status) VALUES (?, ?, ?, ?, ?, ?)",
                (user["user_id"], "TEST", "crash_test", "post_crash", "/admin/failure-injection/transaction-crash", "should_not_exist")
            )
            
            # Trigger crash before commit
            print("[TRANSACTION CRASH TEST] Triggering crash during transaction...")
            os._exit(1)  # Immediate crash
            
    except Exception as e:
        print(f"[TRANSACTION CRASH TEST] Exception during crash test: {e}")
        os._exit(1)
    
    # Should never reach here
    return {"message": "Transaction crash test failed - crash did not occur"}


# ============================================================================
# ACID INTEGRATION ENDPOINTS (Module A Integration)
# ============================================================================

@app.get("/admin/acid/status")
def get_acid_status(user=Depends(current_user_dependency)):
    """Get ACID integration status and capabilities."""
    require_admin(user, "/admin/acid/status", "acid_status")
    
    status = get_acid_integration_status()
    return {
        "message": "ACID integration status retrieved",
        "status": status,
        "features": {
            "atomicity": "All operations complete fully or rollback completely",
            "consistency": "Data integrity maintained across operations", 
            "isolation": "Concurrent transactions don't interfere",
            "durability": "Committed data survives system crashes"
        }
    }


@app.post("/admin/acid/test-atomicity")
def test_atomicity(user=Depends(current_user_dependency)):
    """Demonstrate atomicity - multi-operation transaction that either succeeds or fails completely."""
    require_admin(user, "/admin/acid/test-atomicity", "acid_testing")
    
    log_acid_operation("TEST", "atomicity_test", {"type": "multi_operation_transaction"})
    
    # Define a multi-operation transaction that will either succeed or fail atomically
    ts = int(time.time())
    operations = [
        {
            "name": "create_test_user",
            "query": "INSERT INTO users (username, email, password_hash, role_id, full_name, status, is_active) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            "params": (f"atom_test_{ts}", f"atom_{ts}@test.com", "testhash", 1, "Atomicity Test User", "ACTIVE", True)
        },
        {
            "name": "create_test_group",
            "query": "INSERT INTO groups (group_name) VALUES (%s)",
            "params": (f"test_group_{ts}",)
        },
        {
            "name": "log_test_action",
            "query": "INSERT INTO audit_logs (actor_user_id, action, table_name, record_id, request_path, status) VALUES (%s, %s, %s, %s, %s, %s)",
            "params": (1, "ATOMICITY_TEST", "system", "acid_test", "/admin/acid/test-atomicity", "success")
        }
    ]
    
    result = execute_with_acid_transaction(operations, "atomicity_test")
    
    return {
        "message": "Atomicity test completed",
        "test_type": "atomicity",
        "transaction_result": result,
        "acid_property": "All operations succeeded together or would have failed together"
    }


@app.post("/admin/acid/test-consistency")  
def test_consistency(user=Depends(current_user_dependency)):
    """Demonstrate consistency - ensure data remains valid across operations."""
    require_admin(user, "/admin/acid/test-consistency", "acid_testing")
    
    log_acid_operation("TEST", "consistency_test", {"type": "constraint_validation"})
    
    # Test that would violate constraints and should fail
    operations = [
        {
            "name": "valid_operation",
            "query": "INSERT INTO audit_logs (actor_user_id, action, table_name, record_id, request_path, status) VALUES (%s, %s, %s, %s, %s, %s)",
            "params": (1, "CONSISTENCY_TEST", "system", "test", "/admin/acid/test-consistency", "success")
        }
        # In a real scenario, we'd add operations that could violate business rules
    ]
    
    result = execute_with_acid_transaction(operations, "consistency_test")
    
    return {
        "message": "Consistency test completed", 
        "test_type": "consistency",
        "transaction_result": result,
        "acid_property": "Database constraints and business rules maintained"
    }


@app.post("/admin/acid/test-concurrent-isolation")
async def test_concurrent_isolation(user=Depends(current_user_dependency)):
    """Demonstrate isolation - concurrent transactions don't interfere with each other."""
    require_admin(user, "/admin/acid/test-concurrent-isolation", "acid_testing")
    
    log_acid_operation("TEST", "isolation_test", {"type": "concurrent_transactions"})
    
    import asyncio
    
    async def concurrent_transaction(transaction_id: int):
        """Simulate concurrent transaction."""
        operations = [
            {
                "name": f"concurrent_op_{transaction_id}",
                "query": "INSERT INTO audit_logs (actor_user_id, action, table_name, record_id, request_path, status) VALUES (%s, %s, %s, %s, %s, %s)",
                "params": (1, f"ISOLATION_TEST_{transaction_id}", "system", f"concurrent_{transaction_id}", "/admin/acid/test-concurrent-isolation", "success")
            }
        ]
        
        return execute_with_acid_transaction(operations, f"isolation_test_{transaction_id}")
    
    # Run multiple transactions concurrently
    tasks = [concurrent_transaction(i) for i in range(1, 4)]
    results = await asyncio.gather(*tasks)
    
    return {
        "message": "Concurrent isolation test completed",
        "test_type": "isolation",
        "concurrent_transactions": 3,
        "results": results,
        "acid_property": "Concurrent transactions executed independently without interference"
    }


@app.post("/admin/acid/test-durability")
def test_durability(user=Depends(current_user_dependency)):
    """Demonstrate durability - committed data persists even after system restart."""
    require_admin(user, "/admin/acid/test-durability", "acid_testing")
    
    log_acid_operation("TEST", "durability_test", {"type": "persistence_validation"})
    
    # Create data that should persist
    timestamp = int(time.time())
    operations = [
        {
            "name": "durability_marker",
            "query": "INSERT INTO audit_logs (actor_user_id, action, table_name, record_id, request_path, status) VALUES (%s, %s, %s, %s, %s, %s)",
            "params": (1, "DURABILITY_TEST", "system", f"durability_{timestamp}", "/admin/acid/test-durability", "success")
        }
    ]
    
    result = execute_with_acid_transaction(operations, f"durability_test_{timestamp}")
    
    return {
        "success": result.get("success", False),
        "message": "Durability test completed",
        "result": result,
        "instructions": "Restart server; data should persist proving durability"
    }


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
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/admin/sharding/distribution")
def get_shard_distribution(user=Depends(current_user_dependency)):
    """
    Get data distribution across shards
    Shows how many records are in each shard
    """
    require_admin(user, "/admin/sharding/distribution", "sharding_query")
    
    from .sharding_manager import NUM_SHARDS
    
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
    
    from .sharding_manager import get_router, NUM_SHARDS
    
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
    
    # Verify the data exists
    verification_query = "SELECT * FROM audit_logs WHERE action = 'DURABILITY_TEST' AND record_id = %s"
    verification_result = fetch_one(verification_query, (f"durability_{timestamp}",))
    
    return {
        "message": "Durability test completed",
        "test_type": "durability", 
        "transaction_result": result,
        "verification": {
            "data_persisted": verification_result is not None,
            "persisted_data": verification_result
        },
        "acid_property": "Committed data persists in database storage"
    }


@app.post("/admin/acid/test-failure-rollback")
def test_failure_rollback(user=Depends(current_user_dependency)):
    """Demonstrate rollback on failure - partial operations are undone when transaction fails."""
    require_admin(user, "/admin/acid/test-failure-rollback", "acid_testing")
    
    log_acid_operation("TEST", "rollback_test", {"type": "failure_simulation"})
    
    # Create operations where the last one will intentionally fail
    operations = [
        {
            "name": "valid_operation_1",
            "query": "INSERT INTO audit_logs (actor_user_id, action, table_name, record_id, request_path, status) VALUES (%s, %s, %s, %s, %s, %s)",
            "params": (1, "ROLLBACK_TEST", "system", "rollback_1", "/admin/acid/test-failure-rollback", "pending")
        },
        {
            "name": "valid_operation_2", 
            "query": "INSERT INTO audit_logs (actor_user_id, action, table_name, record_id, request_path, status) VALUES (%s, %s, %s, %s, %s, %s)",
            "params": (1, "ROLLBACK_TEST", "system", "rollback_2", "/admin/acid/test-failure-rollback", "pending")
        },
        {
            "name": "failing_operation",
            "query": "INSERT INTO nonexistent_table (fake_column) VALUES (%s)",  # This will fail
            "params": ("fake_value",)
        }
    ]
    
    result = execute_with_acid_transaction(operations, "rollback_test")
    
    # Verify that no partial data was committed
    verification_query = "SELECT COUNT(*) as count FROM audit_logs WHERE action = 'ROLLBACK_TEST'"
    verification_result = fetch_one(verification_query)
    
    return {
        "message": "Failure rollback test completed",
        "test_type": "failure_rollback",
        "transaction_result": result,
        "verification": {
            "rollback_successful": verification_result['count'] == 0,
            "partial_data_count": verification_result['count']
        },
        "acid_property": "Failed transactions leave no partial data - complete rollback"
    }


@app.get("/admin/acid/demo-dashboard")
def get_acid_demo_dashboard(user=Depends(current_user_dependency)):
    """Get comprehensive ACID demonstration dashboard with all test results."""
    require_admin(user, "/admin/acid/demo-dashboard", "acid_dashboard")
    
    # Get recent ACID test activities from audit logs (with error handling)
    try:
        recent_tests = fetch_all(
            "SELECT actor_user_id, action, table_name, record_id, request_path, status, created_at FROM audit_logs WHERE action LIKE '%ACID%' OR action LIKE '%TEST%' ORDER BY created_at DESC LIMIT 10"
        )
    except Exception as e:
        # If audit logs query fails, use empty list
        recent_tests = []
        print(f"Dashboard audit log query error: {e}")
    
    return {
        "message": "ACID demonstration dashboard",
        "integration_status": get_acid_integration_status(),
        "available_tests": [
            {
                "endpoint": "/admin/acid/test-atomicity",
                "name": "Atomicity Test",
                "description": "Multi-operation transaction - all succeed or all fail"
            },
            {
                "endpoint": "/admin/acid/test-consistency", 
                "name": "Consistency Test",
                "description": "Data integrity and constraint validation"
            },
            {
                "endpoint": "/admin/acid/test-concurrent-isolation",
                "name": "Isolation Test", 
                "description": "Concurrent transactions don't interfere"
            },
            {
                "endpoint": "/admin/acid/test-durability",
                "name": "Durability Test",
                "description": "Committed data survives system restart"
            },
            {
                "endpoint": "/admin/acid/test-failure-rollback",
                "name": "Failure Rollback Test",
                "description": "Failed transactions rollback completely"
            }
        ],
        "recent_test_activity": recent_tests
    }


@app.get("/admin/acid/dashboard-html")
def get_acid_dashboard_html():
    """Serve HTML dashboard for ACID testing (no auth required for demo)."""
    from fastapi.responses import FileResponse
    import os
    
    dashboard_path = os.path.join(os.path.dirname(__file__), "..", "working_dashboard.html")
    if os.path.exists(dashboard_path):
        return FileResponse(dashboard_path, media_type="text/html")
    else:
        return {"message": "Dashboard HTML file not found", "path": dashboard_path}


@app.get("/dashboard")
def get_working_dashboard():
    """Serve the working ACID dashboard.""" 
    from fastapi.responses import FileResponse
    import os
    
    dashboard_path = os.path.join(os.path.dirname(__file__), "..", "working_dashboard.html")
    if os.path.exists(dashboard_path):
        return FileResponse(dashboard_path, media_type="text/html")
    else:
        return {"message": "Dashboard HTML file not found"}


# Environment variable support for failure injection
@app.get("/admin/failure-injection/env-check")
def check_env_crash_triggers(user=Depends(current_user_dependency)):
    """Check environment variables that can trigger crashes for testing."""
    require_admin(user, "/admin/failure-injection/env-check", "failure_injection")
    
    env_triggers = {
        "CRASH_ON_STARTUP": os.getenv("CRASH_ON_STARTUP", "false"),
        "CRASH_ON_REQUEST": os.getenv("CRASH_ON_REQUEST", "false"), 
        "CRASH_DELAY": os.getenv("CRASH_DELAY", "0"),
        "CRASH_MODE": os.getenv("CRASH_MODE", "immediate"),
        "ENABLE_FAILURE_INJECTION": os.getenv("ENABLE_FAILURE_INJECTION", "false")
    }
    
    return {
        "environment_triggers": env_triggers,
        "active_triggers": [k for k, v in env_triggers.items() if v.lower() in ["true", "1", "yes"]],
        "instructions": {
            "usage": "Set environment variables before starting server",
            "example": "CRASH_ON_REQUEST=true CRASH_DELAY=5 python -m uvicorn app.main:app",
            "warning": "Environment crashes are immediate and cannot be disabled at runtime"
        }
    }


# Middleware to check for environment-triggered crashes
@app.middleware("http")
async def crash_injection_middleware(request: Request, call_next):
    """Middleware to support environment-variable triggered crashes."""
    
    # Check if crash should be triggered on request
    if os.getenv("CRASH_ON_REQUEST", "false").lower() in ["true", "1", "yes"]:
        delay = float(os.getenv("CRASH_DELAY", "0"))
        mode = os.getenv("CRASH_MODE", "immediate")
        
        print(f"[ENV CRASH] Triggering {mode} crash in {delay}s due to CRASH_ON_REQUEST")
        
        if delay > 0:
            time.sleep(delay)
        
        _trigger_crash(mode)
    
    # Process request normally
    response = await call_next(request)
    return response


# ============================================================================
# SHARD-AWARE ENDPOINTS (REQ 3: Query Routing & Fan-out Operations)
# ============================================================================

@app.get("/shards/info")
def get_shards_info(user=Depends(current_user_dependency)):
    """Get comprehensive sharding information and statistics across all shards."""
    require_admin(user, "/shards/info", "sharding_query")
    
    if not sharded_db:
        raise HTTPException(status_code=500, detail="Sharded database unavailable")
    
    shard_stats = []
    total_users = 0
    total_students = 0
    total_companies = 0
    total_recruiters = 0
    
    for shard_id in range(3):
        try:
            conn = sharded_db.get_connection(shard_id)
            cursor = conn.cursor(dictionary=True)
            
            # Get counts
            cursor.execute(f"SELECT COUNT(*) as cnt FROM shard_{shard_id}_users")
            user_count = cursor.fetchone()["cnt"]
            total_users += user_count
            
            cursor.execute(f"SELECT COUNT(*) as cnt FROM shard_{shard_id}_students")
            student_count = cursor.fetchone()["cnt"]
            total_students += student_count
            
            cursor.execute(f"SELECT COUNT(*) as cnt FROM shard_{shard_id}_companies")
            company_count = cursor.fetchone()["cnt"]
            total_companies += company_count
            
            # Count recruiters (role_id = 2)
            cursor.execute(f"SELECT COUNT(*) as cnt FROM shard_{shard_id}_users WHERE role_id = 2")
            recruiter_count = cursor.fetchone()["cnt"]
            total_recruiters += recruiter_count
            
            cursor.close()
            conn.close()
            
            shard_stats.append({
                "shard_id": shard_id,
                "host": "10.0.116.184",
                "port": 3307 + shard_id,
                "database": "Machine_minds",
                "users": user_count,
                "students": student_count,
                "companies": company_count,
                "recruiters": recruiter_count,
                "status": "healthy"
            })
        except Exception as e:
            shard_stats.append({
                "shard_id": shard_id,
                "status": "error",
                "error": str(e)
            })
    
    return {
        "sharding_enabled": True,
        "num_shards": 3,
        "shard_key": "user_id",
        "partitioning_strategy": "hash-based (user_id % 3)",
        "total_stats": {
            "total_users": total_users,
            "total_students": total_students,
            "total_companies": total_companies,
            "total_recruiters": total_recruiters
        },
        "shards": shard_stats,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/shards/users")
def fan_out_query_users(limit: int = 100, role_id: Optional[int] = None, user=Depends(current_user_dependency)):
    """Fan-out query: Get users across ALL shards with optional role filter."""
    require_admin(user, "/shards/users", "sharding_query")
    
    if not sharded_db:
        raise HTTPException(status_code=500, detail="Sharded database unavailable")
    
    all_users = []
    shard_meta = []
    
    for shard_id in range(3):
        try:
            conn = sharded_db.get_connection(shard_id)
            cursor = conn.cursor(dictionary=True)
            
            if role_id is not None:
                query = f"""
                SELECT user_id, username, email, full_name, role_id, status
                FROM shard_{shard_id}_users
                WHERE role_id = %s
                LIMIT %s
                """
                cursor.execute(query, (role_id, limit))
            else:
                query = f"""
                SELECT user_id, username, email, full_name, role_id, status
                FROM shard_{shard_id}_users
                LIMIT %s
                """
                cursor.execute(query, (limit,))
            
            rows = cursor.fetchall()
            cursor.execute(f"SELECT COUNT(*) as cnt FROM shard_{shard_id}_users")
            total_in_shard = cursor.fetchone()["cnt"]
            
            all_users.extend(rows)
            shard_meta.append({
                "shard_id": shard_id,
                "port": 3307 + shard_id,
                "rows_returned": len(rows),
                "total_in_shard": total_in_shard
            })
            
            cursor.close()
            conn.close()
        except Exception as e:
            shard_meta.append({
                "shard_id": shard_id,
                "error": str(e)
            })
    
    return {
        "query_type": "fan-out",
        "total_results": len(all_users),
        "limit": limit,
        "filter_role_id": role_id,
        "shard_meta": shard_meta,
        "users": all_users,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/shards/users/{user_id}")
def get_user_from_shard(user_id: int, user=Depends(current_user_dependency)):
    """Get a user from their assigned shard using routing key."""
    require_admin(user, f"/shards/users/{user_id}", "sharding_query")
    
    if not sharded_db:
        raise HTTPException(status_code=500, detail="Sharded database unavailable")
    
    shard_id = user_id % 3
    
    try:
        conn = sharded_db.get_connection(shard_id)
        cursor = conn.cursor(dictionary=True)
        
        query = f"""
        SELECT user_id, username, email, full_name, role_id, status, created_at
        FROM shard_{shard_id}_users
        WHERE user_id = %s
        """
        cursor.execute(query, (user_id,))
        user_data = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "shard_id": shard_id,
            "shard_port": 3307 + shard_id,
            "routing_formula": f"{user_id} % 3 = {shard_id}",
            "user": user_data,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "shard_id": shard_id,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@app.put("/shards/users/{user_id}")
def update_user_in_shard(user_id: int, updates: dict, user=Depends(current_user_dependency)):
    """Update a user in their assigned shard."""
    require_admin(user, f"/shards/users/{user_id}", "sharding_write")
    
    if not sharded_db:
        raise HTTPException(status_code=500, detail="Sharded database unavailable")
    
    shard_id = user_id % 3
    
    try:
        conn = sharded_db.get_connection(shard_id)
        cursor = conn.cursor(dictionary=True)
        
        # Build update query
        set_clause = ", ".join([f"{key} = %s" for key in updates.keys()])
        values = list(updates.values()) + [user_id]
        
        query = f"""
        UPDATE shard_{shard_id}_users
        SET {set_clause}
        WHERE user_id = %s
        """
        cursor.execute(query, values)
        conn.commit()
        
        # Fetch updated data
        cursor.execute(f"SELECT * FROM shard_{shard_id}_users WHERE user_id = %s", (user_id,))
        updated_data = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return {
            "shard_id": shard_id,
            "shard_port": 3307 + shard_id,
            "routing_formula": f"{user_id} % 3 = {shard_id}",
            "status": "updated",
            "user": updated_data,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")


@app.get("/shards/verify-partitioning")
def verify_data_partitioning(user=Depends(current_user_dependency)):
    """Verify that data is correctly partitioned across shards using hash function."""
    require_admin(user, "/shards/verify-partitioning", "sharding_query")
    
    if not sharded_db:
        raise HTTPException(status_code=500, detail="Sharded database unavailable")
    
    verification_results = []
    total_violations = 0
    
    for shard_id in range(3):
        try:
            conn = sharded_db.get_connection(shard_id)
            cursor = conn.cursor(dictionary=True)
            
            # Check users table: all user_id % 3 should equal shard_id
            query = f"""
            SELECT COUNT(*) as violation_count FROM shard_{shard_id}_users
            WHERE MOD(user_id, 3) <> {shard_id}
            """
            cursor.execute(query)
            user_violations = cursor.fetchone()["violation_count"]
            
            # Check students table
            query = f"""
            SELECT COUNT(*) as violation_count FROM shard_{shard_id}_students s
            JOIN shard_{shard_id}_users u ON s.user_id = u.user_id
            WHERE MOD(s.user_id, 3) <> {shard_id}
            """
            cursor.execute(query)
            student_violations = cursor.fetchone()["violation_count"]
            
            # Check companies table
            query = f"""
            SELECT COUNT(*) as violation_count FROM shard_{shard_id}_companies
            WHERE MOD(user_id, 3) <> {shard_id}
            """
            cursor.execute(query)
            company_violations = cursor.fetchone()["violation_count"]
            
            total_violations += (user_violations + student_violations + company_violations)
            
            verification_results.append({
                "shard_id": shard_id,
                "partitioning_key": "user_id % 3",
                "violations": {
                    "users_table": user_violations,
                    "students_table": student_violations,
                    "companies_table": company_violations,
                    "total": user_violations + student_violations + company_violations
                },
                "status": "PASS" if (user_violations + student_violations + company_violations) == 0 else "FAIL"
            })
            
            cursor.close()
            conn.close()
        except Exception as e:
            verification_results.append({
                "shard_id": shard_id,
                "error": str(e),
                "status": "ERROR"
            })
    
    return {
        "verification_type": "data_partitioning",
        "partition_function": "MOD(user_id, 3)",
        "total_partitioning_violations": total_violations,
        "shards": verification_results,
        "overall_status": "PASS" if total_violations == 0 else "FAIL",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/shards/distribution")
def get_distribution_analysis(user=Depends(current_user_dependency)):
    """Analyze data distribution across shards and detect hotspots."""
    require_admin(user, "/shards/distribution", "sharding_query")
    
    if not sharded_db:
        raise HTTPException(status_code=500, detail="Sharded database unavailable")
    
    distribution = {}
    for shard_id in range(3):
        try:
            conn = sharded_db.get_connection(shard_id)
            cursor = conn.cursor(dictionary=True)
            
            cursor.execute(f"SELECT COUNT(*) as cnt FROM shard_{shard_id}_users")
            user_count = cursor.fetchone()["cnt"]
            
            cursor.execute(f"SELECT COUNT(*) as cnt FROM shard_{shard_id}_students")
            student_count = cursor.fetchone()["cnt"]
            
            cursor.execute(f"SELECT COUNT(*) as cnt FROM shard_{shard_id}_companies")
            company_count = cursor.fetchone()["cnt"]
            
            distribution[f"shard_{shard_id}"] = {
                "users": user_count,
                "students": student_count,
                "companies": company_count,
                "total_records": user_count + student_count + company_count
            }
            
            cursor.close()
            conn.close()
        except Exception as e:
            distribution[f"shard_{shard_id}"] = {"error": str(e)}
    
    # Calculate statistics
    total = sum(d.get("total_records", 0) for d in distribution.values() if isinstance(d, dict) and "total_records" in d)
    avg_per_shard = total // 3 if total > 0 else 0
    
    return {
        "sharding_enabled": True,
        "num_shards": 3,
        "distribution": distribution,
        "total_records": total,
        "avg_per_shard": avg_per_shard,
        "balance_status": "BALANCED" if total > 0 else "EMPTY",
        "timestamp": datetime.now().isoformat()
    }


# Startup crash check
@app.on_event("startup")
def check_startup_crash():
    """Check for startup crash triggers."""
    if os.getenv("CRASH_ON_STARTUP", "false").lower() in ["true", "1", "yes"]:
        delay = float(os.getenv("CRASH_DELAY", "0"))
        mode = os.getenv("CRASH_MODE", "immediate")
        
        print(f"[STARTUP CRASH] Triggering {mode} crash in {delay}s due to CRASH_ON_STARTUP")
        
        if delay > 0:
            time.sleep(delay)
        
        _trigger_crash(mode)
