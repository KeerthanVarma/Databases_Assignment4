-- =====================================================
-- SHARDING MIGRATION SCRIPT
-- Module B: Hash-Based Sharding by user_id
-- Strategy: user_id % 3 (3 shards)
-- =====================================================

-- =====================================================
-- PART 1: CREATE SHARD TABLES
-- =====================================================

-- SHARD 0 TABLES
-- =====================================================

-- shard_0_users
CREATE TABLE IF NOT EXISTS shard_0_users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role_id INT NOT NULL,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    full_name VARCHAR(150) NOT NULL,
    contact_number VARCHAR(20),
    status VARCHAR(50) DEFAULT 'ACTIVE',
    shard_id INT DEFAULT 0,

    CONSTRAINT fk_role_shard_0
        FOREIGN KEY (role_id)
        REFERENCES Roles(role_id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,

    CHECK (email ~* '^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$'),
    CHECK (contact_number ~ '^\+?[1-9]\d{1,14}$' OR contact_number IS NULL),
    CHECK (shard_id = 0)
);

-- shard_0_user_logs
CREATE TABLE IF NOT EXISTS shard_0_user_logs (
    log_id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    action TEXT NOT NULL,
    ip_address VARCHAR(45),
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    device_info TEXT,
    shard_id INT DEFAULT 0,

    FOREIGN KEY (user_id)
        REFERENCES shard_0_users(user_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CHECK (end_time IS NULL OR end_time > start_time),
    CHECK (shard_id = 0)
);

-- shard_0_students
CREATE TABLE IF NOT EXISTS shard_0_students (
    student_id BIGSERIAL PRIMARY KEY,
    user_id INT UNIQUE NOT NULL,
    latest_cpi NUMERIC(3,2),
    program VARCHAR(100),
    discipline VARCHAR(100),
    graduating_year INT,
    active_backlogs INT DEFAULT 0,
    gender VARCHAR(10),
    tenth_percent NUMERIC(5,2),
    tenth_passout_year INT,
    twelfth_percent NUMERIC(5,2),
    twelfth_passout_year INT,
    shard_id INT DEFAULT 0,

    FOREIGN KEY (user_id)
        REFERENCES shard_0_users(user_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CHECK (latest_cpi BETWEEN 0 AND 10 OR latest_cpi IS NULL),
    CHECK (active_backlogs >= 0),
    CHECK (gender IN ('Male','Female','Other') OR gender IS NULL),
    CHECK (shard_id = 0)
);

-- shard_0_alumni_user
CREATE TABLE IF NOT EXISTS shard_0_alumni_user (
    alumni_id SERIAL PRIMARY KEY,
    user_id INT UNIQUE NOT NULL,
    grad_year INT NOT NULL,
    current_company VARCHAR(150),
    placement_history TEXT,
    designation VARCHAR(150),
    shard_id INT DEFAULT 0,

    FOREIGN KEY (user_id)
        REFERENCES shard_0_users(user_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CHECK (shard_id = 0)
);

-- shard_0_companies
CREATE TABLE IF NOT EXISTS shard_0_companies (
    company_id SERIAL PRIMARY KEY,
    user_id INT UNIQUE NOT NULL,
    company_name VARCHAR(200) NOT NULL,
    industry_sector VARCHAR(150),
    type_of_organization VARCHAR(100),
    hiring_history TEXT,
    company_description TEXT,
    website_url TEXT,
    shard_id INT DEFAULT 0,

    FOREIGN KEY (user_id)
        REFERENCES shard_0_users(user_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CHECK (company_name <> ''),
    CHECK (shard_id = 0)
);

-- shard_0_resumes
CREATE TABLE IF NOT EXISTS shard_0_resumes (
    resume_id SERIAL PRIMARY KEY,
    student_id BIGINT NOT NULL,
    user_id INT NOT NULL,
    resume_label VARCHAR(100) NOT NULL,
    file_url TEXT NOT NULL,
    ats_score NUMERIC(5,2),
    is_verified BOOLEAN DEFAULT FALSE,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    shard_id INT DEFAULT 0,

    FOREIGN KEY (student_id)
        REFERENCES shard_0_students(student_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    FOREIGN KEY (user_id)
        REFERENCES shard_0_users(user_id)
        ON DELETE CASCADE,

    CHECK (ats_score BETWEEN 0 AND 100 OR ats_score IS NULL),
    CHECK (resume_label <> ''),
    CHECK (shard_id = 0)
);

-- shard_0_applications
CREATE TABLE IF NOT EXISTS shard_0_applications (
    application_id SERIAL PRIMARY KEY,
    job_id INT NOT NULL,
    student_id BIGINT NOT NULL,
    user_id INT NOT NULL,
    applied_at DATE,
    status VARCHAR(50),
    shard_id INT DEFAULT 0,

    FOREIGN KEY (student_id)
        REFERENCES shard_0_students(student_id)
        ON DELETE CASCADE,

    FOREIGN KEY (user_id)
        REFERENCES shard_0_users(user_id),

    CHECK (shard_id = 0)
);

CREATE INDEX IF NOT EXISTS idx_shard_0_applications_user_id ON shard_0_applications(user_id);


-- =====================================================
-- SHARD 1 TABLES
-- =====================================================

-- shard_1_users
CREATE TABLE IF NOT EXISTS shard_1_users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role_id INT NOT NULL,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    full_name VARCHAR(150) NOT NULL,
    contact_number VARCHAR(20),
    status VARCHAR(50) DEFAULT 'ACTIVE',
    shard_id INT DEFAULT 1,

    CONSTRAINT fk_role_shard_1
        FOREIGN KEY (role_id)
        REFERENCES Roles(role_id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,

    CHECK (email ~* '^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$'),
    CHECK (contact_number ~ '^\+?[1-9]\d{1,14}$' OR contact_number IS NULL),
    CHECK (shard_id = 1)
);

-- shard_1_user_logs
CREATE TABLE IF NOT EXISTS shard_1_user_logs (
    log_id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    action TEXT NOT NULL,
    ip_address VARCHAR(45),
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    device_info TEXT,
    shard_id INT DEFAULT 1,

    FOREIGN KEY (user_id)
        REFERENCES shard_1_users(user_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CHECK (end_time IS NULL OR end_time > start_time),
    CHECK (shard_id = 1)
);

-- shard_1_students
CREATE TABLE IF NOT EXISTS shard_1_students (
    student_id BIGSERIAL PRIMARY KEY,
    user_id INT UNIQUE NOT NULL,
    latest_cpi NUMERIC(3,2),
    program VARCHAR(100),
    discipline VARCHAR(100),
    graduating_year INT,
    active_backlogs INT DEFAULT 0,
    gender VARCHAR(10),
    tenth_percent NUMERIC(5,2),
    tenth_passout_year INT,
    twelfth_percent NUMERIC(5,2),
    twelfth_passout_year INT,
    shard_id INT DEFAULT 1,

    FOREIGN KEY (user_id)
        REFERENCES shard_1_users(user_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CHECK (latest_cpi BETWEEN 0 AND 10 OR latest_cpi IS NULL),
    CHECK (active_backlogs >= 0),
    CHECK (gender IN ('Male','Female','Other') OR gender IS NULL),
    CHECK (shard_id = 1)
);

-- shard_1_alumni_user
CREATE TABLE IF NOT EXISTS shard_1_alumni_user (
    alumni_id SERIAL PRIMARY KEY,
    user_id INT UNIQUE NOT NULL,
    grad_year INT NOT NULL,
    current_company VARCHAR(150),
    placement_history TEXT,
    designation VARCHAR(150),
    shard_id INT DEFAULT 1,

    FOREIGN KEY (user_id)
        REFERENCES shard_1_users(user_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CHECK (shard_id = 1)
);

-- shard_1_companies
CREATE TABLE IF NOT EXISTS shard_1_companies (
    company_id SERIAL PRIMARY KEY,
    user_id INT UNIQUE NOT NULL,
    company_name VARCHAR(200) NOT NULL,
    industry_sector VARCHAR(150),
    type_of_organization VARCHAR(100),
    hiring_history TEXT,
    company_description TEXT,
    website_url TEXT,
    shard_id INT DEFAULT 1,

    FOREIGN KEY (user_id)
        REFERENCES shard_1_users(user_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CHECK (company_name <> ''),
    CHECK (shard_id = 1)
);

-- shard_1_resumes
CREATE TABLE IF NOT EXISTS shard_1_resumes (
    resume_id SERIAL PRIMARY KEY,
    student_id BIGINT NOT NULL,
    user_id INT NOT NULL,
    resume_label VARCHAR(100) NOT NULL,
    file_url TEXT NOT NULL,
    ats_score NUMERIC(5,2),
    is_verified BOOLEAN DEFAULT FALSE,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    shard_id INT DEFAULT 1,

    FOREIGN KEY (student_id)
        REFERENCES shard_1_students(student_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    FOREIGN KEY (user_id)
        REFERENCES shard_1_users(user_id)
        ON DELETE CASCADE,

    CHECK (ats_score BETWEEN 0 AND 100 OR ats_score IS NULL),
    CHECK (resume_label <> ''),
    CHECK (shard_id = 1)
);

-- shard_1_applications
CREATE TABLE IF NOT EXISTS shard_1_applications (
    application_id SERIAL PRIMARY KEY,
    job_id INT NOT NULL,
    student_id BIGINT NOT NULL,
    user_id INT NOT NULL,
    applied_at DATE,
    status VARCHAR(50),
    shard_id INT DEFAULT 1,

    FOREIGN KEY (student_id)
        REFERENCES shard_1_students(student_id)
        ON DELETE CASCADE,

    FOREIGN KEY (user_id)
        REFERENCES shard_1_users(user_id),

    CHECK (shard_id = 1)
);

CREATE INDEX IF NOT EXISTS idx_shard_1_applications_user_id ON shard_1_applications(user_id);


-- =====================================================
-- SHARD 2 TABLES
-- =====================================================

-- shard_2_users
CREATE TABLE IF NOT EXISTS shard_2_users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role_id INT NOT NULL,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    full_name VARCHAR(150) NOT NULL,
    contact_number VARCHAR(20),
    status VARCHAR(50) DEFAULT 'ACTIVE',
    shard_id INT DEFAULT 2,

    CONSTRAINT fk_role_shard_2
        FOREIGN KEY (role_id)
        REFERENCES Roles(role_id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,

    CHECK (email ~* '^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$'),
    CHECK (contact_number ~ '^\+?[1-9]\d{1,14}$' OR contact_number IS NULL),
    CHECK (shard_id = 2)
);

-- shard_2_user_logs
CREATE TABLE IF NOT EXISTS shard_2_user_logs (
    log_id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    action TEXT NOT NULL,
    ip_address VARCHAR(45),
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    device_info TEXT,
    shard_id INT DEFAULT 2,

    FOREIGN KEY (user_id)
        REFERENCES shard_2_users(user_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CHECK (end_time IS NULL OR end_time > start_time),
    CHECK (shard_id = 2)
);

-- shard_2_students
CREATE TABLE IF NOT EXISTS shard_2_students (
    student_id BIGSERIAL PRIMARY KEY,
    user_id INT UNIQUE NOT NULL,
    latest_cpi NUMERIC(3,2),
    program VARCHAR(100),
    discipline VARCHAR(100),
    graduating_year INT,
    active_backlogs INT DEFAULT 0,
    gender VARCHAR(10),
    tenth_percent NUMERIC(5,2),
    tenth_passout_year INT,
    twelfth_percent NUMERIC(5,2),
    twelfth_passout_year INT,
    shard_id INT DEFAULT 2,

    FOREIGN KEY (user_id)
        REFERENCES shard_2_users(user_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CHECK (latest_cpi BETWEEN 0 AND 10 OR latest_cpi IS NULL),
    CHECK (active_backlogs >= 0),
    CHECK (gender IN ('Male','Female','Other') OR gender IS NULL),
    CHECK (shard_id = 2)
);

-- shard_2_alumni_user
CREATE TABLE IF NOT EXISTS shard_2_alumni_user (
    alumni_id SERIAL PRIMARY KEY,
    user_id INT UNIQUE NOT NULL,
    grad_year INT NOT NULL,
    current_company VARCHAR(150),
    placement_history TEXT,
    designation VARCHAR(150),
    shard_id INT DEFAULT 2,

    FOREIGN KEY (user_id)
        REFERENCES shard_2_users(user_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CHECK (shard_id = 2)
);

-- shard_2_companies
CREATE TABLE IF NOT EXISTS shard_2_companies (
    company_id SERIAL PRIMARY KEY,
    user_id INT UNIQUE NOT NULL,
    company_name VARCHAR(200) NOT NULL,
    industry_sector VARCHAR(150),
    type_of_organization VARCHAR(100),
    hiring_history TEXT,
    company_description TEXT,
    website_url TEXT,
    shard_id INT DEFAULT 2,

    FOREIGN KEY (user_id)
        REFERENCES shard_2_users(user_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CHECK (company_name <> ''),
    CHECK (shard_id = 2)
);

-- shard_2_resumes
CREATE TABLE IF NOT EXISTS shard_2_resumes (
    resume_id SERIAL PRIMARY KEY,
    student_id BIGINT NOT NULL,
    user_id INT NOT NULL,
    resume_label VARCHAR(100) NOT NULL,
    file_url TEXT NOT NULL,
    ats_score NUMERIC(5,2),
    is_verified BOOLEAN DEFAULT FALSE,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    shard_id INT DEFAULT 2,

    FOREIGN KEY (student_id)
        REFERENCES shard_2_students(student_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    FOREIGN KEY (user_id)
        REFERENCES shard_2_users(user_id)
        ON DELETE CASCADE,

    CHECK (ats_score BETWEEN 0 AND 100 OR ats_score IS NULL),
    CHECK (resume_label <> ''),
    CHECK (shard_id = 2)
);

-- shard_2_applications
CREATE TABLE IF NOT EXISTS shard_2_applications (
    application_id SERIAL PRIMARY KEY,
    job_id INT NOT NULL,
    student_id BIGINT NOT NULL,
    user_id INT NOT NULL,
    applied_at DATE,
    status VARCHAR(50),
    shard_id INT DEFAULT 2,

    FOREIGN KEY (student_id)
        REFERENCES shard_2_students(student_id)
        ON DELETE CASCADE,

    FOREIGN KEY (user_id)
        REFERENCES shard_2_users(user_id),

    CHECK (shard_id = 2)
);

CREATE INDEX IF NOT EXISTS idx_shard_2_applications_user_id ON shard_2_applications(user_id);


-- =====================================================
-- PART 2: CREATE SHARDING METADATA TABLE
-- =====================================================

CREATE TABLE IF NOT EXISTS sharding_metadata (
    metadata_id SERIAL PRIMARY KEY,
    num_shards INT NOT NULL DEFAULT 3,
    shard_key VARCHAR(50) NOT NULL DEFAULT 'user_id',
    partitioning_strategy VARCHAR(50) NOT NULL DEFAULT 'hash-based',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO sharding_metadata (num_shards, shard_key, partitioning_strategy)
SELECT 3, 'user_id', 'hash-based'
WHERE NOT EXISTS (SELECT 1 FROM sharding_metadata);

-- =====================================================
-- PART 3: MIGRATION FUNCTIONS
-- =====================================================

-- Function to get shard number based on user_id
CREATE OR REPLACE FUNCTION get_shard_number(p_user_id INT)
RETURNS INT AS $$
BEGIN
    RETURN p_user_id % 3;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function to get shard table name
CREATE OR REPLACE FUNCTION get_shard_table_name(p_table_name VARCHAR, p_user_id INT)
RETURNS VARCHAR AS $$
DECLARE
    v_shard_id INT;
BEGIN
    v_shard_id := get_shard_number(p_user_id);
    RETURN 'shard_' || v_shard_id || '_' || p_table_name;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- =====================================================
-- PART 4: DATA MIGRATION
-- Team: Machine_minds
-- Strategy: Hash-based (user_id % 3)
-- =====================================================

-- =====================================================
-- SECTION 4A: MIGRATE USERS
-- =====================================================
INSERT INTO shard_0_users 
SELECT user_id, username, email, password_hash, role_id, is_verified, created_at, full_name, contact_number, status, 0
FROM users WHERE user_id % 3 = 0
ON CONFLICT DO NOTHING;

INSERT INTO shard_1_users 
SELECT user_id, username, email, password_hash, role_id, is_verified, created_at, full_name, contact_number, status, 1
FROM users WHERE user_id % 3 = 1
ON CONFLICT DO NOTHING;

INSERT INTO shard_2_users 
SELECT user_id, username, email, password_hash, role_id, is_verified, created_at, full_name, contact_number, status, 2
FROM users WHERE user_id % 3 = 2
ON CONFLICT DO NOTHING;

-- =====================================================
-- SECTION 4B: MIGRATE USER_LOGS
-- =====================================================
INSERT INTO shard_0_user_logs
SELECT log_id, user_id, action, ip_address, start_time, end_time, device_info, 0
FROM user_logs WHERE user_id % 3 = 0
ON CONFLICT DO NOTHING;

INSERT INTO shard_1_user_logs
SELECT log_id, user_id, action, ip_address, start_time, end_time, device_info, 1
FROM user_logs WHERE user_id % 3 = 1
ON CONFLICT DO NOTHING;

INSERT INTO shard_2_user_logs
SELECT log_id, user_id, action, ip_address, start_time, end_time, device_info, 2
FROM user_logs WHERE user_id % 3 = 2
ON CONFLICT DO NOTHING;

-- =====================================================
-- SECTION 4C: MIGRATE STUDENTS
-- =====================================================
INSERT INTO shard_0_students
SELECT student_id, user_id, latest_cpi, program, discipline, graduating_year, active_backlogs, gender, 
       tenth_percent, tenth_passout_year, twelfth_percent, twelfth_passout_year, 0
FROM students WHERE user_id % 3 = 0
ON CONFLICT DO NOTHING;

INSERT INTO shard_1_students
SELECT student_id, user_id, latest_cpi, program, discipline, graduating_year, active_backlogs, gender, 
       tenth_percent, tenth_passout_year, twelfth_percent, twelfth_passout_year, 1
FROM students WHERE user_id % 3 = 1
ON CONFLICT DO NOTHING;

INSERT INTO shard_2_students
SELECT student_id, user_id, latest_cpi, program, discipline, graduating_year, active_backlogs, gender, 
       tenth_percent, tenth_passout_year, twelfth_percent, twelfth_passout_year, 2
FROM students WHERE user_id % 3 = 2
ON CONFLICT DO NOTHING;

-- =====================================================
-- SECTION 4D: MIGRATE ALUMNI_USER
-- =====================================================
INSERT INTO shard_0_alumni_user
SELECT alumni_id, user_id, grad_year, current_company, placement_history, designation, 0
FROM alumni_user WHERE user_id % 3 = 0
ON CONFLICT DO NOTHING;

INSERT INTO shard_1_alumni_user
SELECT alumni_id, user_id, grad_year, current_company, placement_history, designation, 1
FROM alumni_user WHERE user_id % 3 = 1
ON CONFLICT DO NOTHING;

INSERT INTO shard_2_alumni_user
SELECT alumni_id, user_id, grad_year, current_company, placement_history, designation, 2
FROM alumni_user WHERE user_id % 3 = 2
ON CONFLICT DO NOTHING;

-- =====================================================
-- SECTION 4E: MIGRATE COMPANIES
-- =====================================================
INSERT INTO shard_0_companies
SELECT company_id, user_id, company_name, industry_sector, type_of_organization, hiring_history, company_description, website_url, 0
FROM companies WHERE user_id % 3 = 0
ON CONFLICT DO NOTHING;

INSERT INTO shard_1_companies
SELECT company_id, user_id, company_name, industry_sector, type_of_organization, hiring_history, company_description, website_url, 1
FROM companies WHERE user_id % 3 = 1
ON CONFLICT DO NOTHING;

INSERT INTO shard_2_companies
SELECT company_id, user_id, company_name, industry_sector, type_of_organization, hiring_history, company_description, website_url, 2
FROM companies WHERE user_id % 3 = 2
ON CONFLICT DO NOTHING;

-- =====================================================
-- SECTION 4F: MIGRATE RESUMES
-- =====================================================
INSERT INTO shard_0_resumes
SELECT r.resume_id, r.student_id, s.user_id, r.resume_label, r.file_url, r.ats_score, r.is_verified, r.uploaded_at, 0
FROM resumes r
JOIN students s ON r.student_id = s.student_id
WHERE s.user_id % 3 = 0
ON CONFLICT DO NOTHING;

INSERT INTO shard_1_resumes
SELECT r.resume_id, r.student_id, s.user_id, r.resume_label, r.file_url, r.ats_score, r.is_verified, r.uploaded_at, 1
FROM resumes r
JOIN students s ON r.student_id = s.student_id
WHERE s.user_id % 3 = 1
ON CONFLICT DO NOTHING;

INSERT INTO shard_2_resumes
SELECT r.resume_id, r.student_id, s.user_id, r.resume_label, r.file_url, r.ats_score, r.is_verified, r.uploaded_at, 2
FROM resumes r
JOIN students s ON r.student_id = s.student_id
WHERE s.user_id % 3 = 2
ON CONFLICT DO NOTHING;

-- =====================================================
-- SECTION 4G: MIGRATE APPLICATIONS
-- =====================================================
INSERT INTO shard_0_applications
SELECT a.application_id, a.job_id, a.student_id, s.user_id, a.applied_at, a.status, 0
FROM applications a
JOIN students s ON a.student_id = s.student_id
WHERE s.user_id % 3 = 0
ON CONFLICT DO NOTHING;

INSERT INTO shard_1_applications
SELECT a.application_id, a.job_id, a.student_id, s.user_id, a.applied_at, a.status, 1
FROM applications a
JOIN students s ON a.student_id = s.student_id
WHERE s.user_id % 3 = 1
ON CONFLICT DO NOTHING;

INSERT INTO shard_2_applications
SELECT a.application_id, a.job_id, a.student_id, s.user_id, a.applied_at, a.status, 2
FROM applications a
JOIN students s ON a.student_id = s.student_id
WHERE s.user_id % 3 = 2
ON CONFLICT DO NOTHING;

-- =====================================================
-- PART 5: VERIFICATION QUERIES
-- =====================================================

-- Verify shard table existence and data count
SELECT 'VERIFICATION REPORT - Machine_minds Sharding' as report_title;
SELECT '================================================' as separator;

-- Count original data
SELECT 'ORIGINAL DATA COUNTS' as section;
SELECT COUNT(*) as total_users FROM users;
SELECT COUNT(*) as total_students FROM students;
SELECT COUNT(*) as total_alumni FROM alumni_user;
SELECT COUNT(*) as total_companies FROM companies;
SELECT COUNT(*) as total_user_logs FROM user_logs;
SELECT COUNT(*) as total_resumes FROM resumes;
SELECT COUNT(*) as total_applications FROM applications;

-- Verify sharded data
SELECT 'SHARDED DATA DISTRIBUTION' as section;
SELECT 
    'shard_0_users' as shard_table, 
    COUNT(*) as record_count 
FROM shard_0_users
UNION ALL
SELECT 'shard_1_users', COUNT(*) FROM shard_1_users
UNION ALL
SELECT 'shard_2_users', COUNT(*) FROM shard_2_users
UNION ALL
SELECT 'shard_0_students', COUNT(*) FROM shard_0_students
UNION ALL
SELECT 'shard_1_students', COUNT(*) FROM shard_1_students
UNION ALL
SELECT 'shard_2_students', COUNT(*) FROM shard_2_students
UNION ALL
SELECT 'shard_0_alumni_user', COUNT(*) FROM shard_0_alumni_user
UNION ALL
SELECT 'shard_1_alumni_user', COUNT(*) FROM shard_1_alumni_user
UNION ALL
SELECT 'shard_2_alumni_user', COUNT(*) FROM shard_2_alumni_user
UNION ALL
SELECT 'shard_0_companies', COUNT(*) FROM shard_0_companies
UNION ALL
SELECT 'shard_1_companies', COUNT(*) FROM shard_1_companies
UNION ALL
SELECT 'shard_2_companies', COUNT(*) FROM shard_2_companies
UNION ALL
SELECT 'shard_0_user_logs', COUNT(*) FROM shard_0_user_logs
UNION ALL
SELECT 'shard_1_user_logs', COUNT(*) FROM shard_1_user_logs
UNION ALL
SELECT 'shard_2_user_logs', COUNT(*) FROM shard_2_user_logs
UNION ALL
SELECT 'shard_0_resumes', COUNT(*) FROM shard_0_resumes
UNION ALL
SELECT 'shard_1_resumes', COUNT(*) FROM shard_1_resumes
UNION ALL
SELECT 'shard_2_resumes', COUNT(*) FROM shard_2_resumes
UNION ALL
SELECT 'shard_0_applications', COUNT(*) FROM shard_0_applications
UNION ALL
SELECT 'shard_1_applications', COUNT(*) FROM shard_1_applications
UNION ALL
SELECT 'shard_2_applications', COUNT(*) FROM shard_2_applications
ORDER BY shard_table;

-- Summary statistics
SELECT 'DATA INTEGRITY CHECKS' as section;
SELECT 
    (SELECT COUNT(*) FROM shard_0_users) +
    (SELECT COUNT(*) FROM shard_1_users) +
    (SELECT COUNT(*) FROM shard_2_users) as total_sharded_users,
    (SELECT COUNT(*) FROM users) as original_users,
    CASE 
        WHEN (SELECT COUNT(*) FROM shard_0_users) + (SELECT COUNT(*) FROM shard_1_users) + (SELECT COUNT(*) FROM shard_2_users) = 
             (SELECT COUNT(*) FROM users)
        THEN 'VERIFIED - No data loss'
        ELSE 'WARNING - Data mismatch'
    END as verification_status;ERE s.user_id % 3 = 1
ON CONFLICT DO NOTHING;

INSERT INTO shard_2_resumes
SELECT r.resume_id, r.student_id, s.user_id, r.resume_label, r.file_url, r.ats_score, r.is_verified, r.uploaded_at, 2
FROM resumes r
JOIN students s ON r.student_id = s.student_id
WHERE s.user_id % 3 = 2
ON CONFLICT DO NOTHING;

-- =====================================================
-- SECTION 4G: MIGRATE APPLICATIONS
-- =====================================================
INSERT INTO shard_0_applications
SELECT a.application_id, a.job_id, a.student_id, s.user_id, a.applied_at, a.status, 0
FROM applications a
JOIN students s ON a.student_id = s.student_id
WHERE s.user_id % 3 = 0
ON CONFLICT DO NOTHING;

INSERT INTO shard_1_applications
SELECT a.application_id, a.job_id, a.student_id, s.user_id, a.applied_at, a.status, 1
FROM applications a
JOIN students s ON a.student_id = s.student_id
WHERE s.user_id % 3 = 1
ON CONFLICT DO NOTHING;

INSERT INTO shard_2_applications
SELECT a.application_id, a.job_id, a.student_id, s.user_id, a.applied_at, a.status, 2
FROM applications a
JOIN students s ON a.student_id = s.student_id
WHERE s.user_id % 3 = 2
ON CONFLICT DO NOTHING;

-- =====================================================
-- PART 5: VERIFICATION QUERIES
-- =====================================================

-- Verify shard table existence and data count
SELECT 'VERIFICATION REPORT - Machine_minds Sharding' as report_title;
SELECT '================================================' as separator;

-- Count original data
SELECT 'ORIGINAL DATA COUNTS' as section;
SELECT COUNT(*) as total_users FROM users;
SELECT COUNT(*) as total_students FROM students;
SELECT COUNT(*) as total_alumni FROM alumni_user;
SELECT COUNT(*) as total_companies FROM companies;
SELECT COUNT(*) as total_user_logs FROM user_logs;
SELECT COUNT(*) as total_resumes FROM resumes;
SELECT COUNT(*) as total_applications FROM applications;

-- Verify sharded data
SELECT 'SHARDED DATA DISTRIBUTION' as section;
SELECT 
    'shard_0_users' as shard_table, 
    COUNT(*) as record_count 
FROM shard_0_users
UNION ALL
SELECT 'shard_1_users', COUNT(*) FROM shard_1_users
UNION ALL
SELECT 'shard_2_users', COUNT(*) FROM shard_2_users
UNION ALL
SELECT 'shard_0_students', COUNT(*) FROM shard_0_students
UNION ALL
SELECT 'shard_1_students', COUNT(*) FROM shard_1_students
UNION ALL
SELECT 'shard_2_students', COUNT(*) FROM shard_2_students
UNION ALL
SELECT 'shard_0_alumni_user', COUNT(*) FROM shard_0_alumni_user
UNION ALL
SELECT 'shard_1_alumni_user', COUNT(*) FROM shard_1_alumni_user
UNION ALL
SELECT 'shard_2_alumni_user', COUNT(*) FROM shard_2_alumni_user
UNION ALL
SELECT 'shard_0_companies', COUNT(*) FROM shard_0_companies
UNION ALL
SELECT 'shard_1_companies', COUNT(*) FROM shard_1_companies
UNION ALL
SELECT 'shard_2_companies', COUNT(*) FROM shard_2_companies
UNION ALL
SELECT 'shard_0_user_logs', COUNT(*) FROM shard_0_user_logs
UNION ALL
SELECT 'shard_1_user_logs', COUNT(*) FROM shard_1_user_logs
UNION ALL
SELECT 'shard_2_user_logs', COUNT(*) FROM shard_2_user_logs
UNION ALL
SELECT 'shard_0_resumes', COUNT(*) FROM shard_0_resumes
UNION ALL
SELECT 'shard_1_resumes', COUNT(*) FROM shard_1_resumes
UNION ALL
SELECT 'shard_2_resumes', COUNT(*) FROM shard_2_resumes
UNION ALL
SELECT 'shard_0_applications', COUNT(*) FROM shard_0_applications
UNION ALL
SELECT 'shard_1_applications', COUNT(*) FROM shard_1_applications
UNION ALL
SELECT 'shard_2_applications', COUNT(*) FROM shard_2_applications
ORDER BY shard_table;

-- Summary statistics
SELECT 'DATA INTEGRITY CHECKS' as section;
SELECT 
    (SELECT COUNT(*) FROM shard_0_users) +
    (SELECT COUNT(*) FROM shard_1_users) +
    (SELECT COUNT(*) FROM shard_2_users) as total_sharded_users,
    (SELECT COUNT(*) FROM users) as original_users,
    CASE 
        WHEN (SELECT COUNT(*) FROM shard_0_users) + (SELECT COUNT(*) FROM shard_1_users) + (SELECT COUNT(*) FROM shard_2_users) = 
             (SELECT COUNT(*) FROM users)
        THEN 'VERIFIED - No data loss'
        ELSE 'WARNING - Data mismatch'
    END as verification_status;
