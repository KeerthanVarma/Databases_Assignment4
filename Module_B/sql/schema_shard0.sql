-- ======================================================================
-- Shard 0 Schema (Port 3307)
-- Create all shard_0_* tables for data where user_id % 3 = 0
-- ======================================================================

SET FOREIGN_KEY_CHECKS=0;

-- ======================================================================
-- SHARD 0: USERS
-- ======================================================================
CREATE TABLE IF NOT EXISTS shard_0_users (
    user_id INT PRIMARY KEY,
    username VARCHAR(255) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role_id INT,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    full_name VARCHAR(255),
    contact_number VARCHAR(20),
    status VARCHAR(50) DEFAULT 'active',
    shard_id INT DEFAULT 0,
    INDEX idx_username (username),
    INDEX idx_email (email),
    INDEX idx_created_at (created_at)
);

-- ======================================================================
-- SHARD 0: STUDENTS
-- ======================================================================
CREATE TABLE IF NOT EXISTS shard_0_students (
    student_id INT PRIMARY KEY,
    user_id INT NOT NULL,
    latest_cpi DECIMAL(5,2),
    program VARCHAR(50),
    discipline VARCHAR(50),
    graduating_year INT,
    active_backlogs INT DEFAULT 0,
    gender VARCHAR(10),
    tenth_percent DECIMAL(5,2),
    tenth_passout_year INT,
    twelfth_percent DECIMAL(5,2),
    twelfth_passout_year INT,
    shard_id INT DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES shard_0_users(user_id),
    INDEX idx_user_id (user_id),
    INDEX idx_cpi (latest_cpi)
);

-- ======================================================================
-- SHARD 0: ALUMNI_USER
-- ======================================================================
CREATE TABLE IF NOT EXISTS shard_0_alumni_user (
    alumni_id INT PRIMARY KEY,
    user_id INT NOT NULL,
    grad_year INT,
    current_company VARCHAR(255),
    placement_history TEXT,
    designation VARCHAR(255),
    shard_id INT DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES shard_0_users(user_id),
    INDEX idx_user_id (user_id)
);

-- ======================================================================
-- SHARD 0: COMPANIES
-- ======================================================================
CREATE TABLE IF NOT EXISTS shard_0_companies (
    company_id INT PRIMARY KEY,
    user_id INT NOT NULL,
    company_name VARCHAR(255) NOT NULL,
    industry_sector VARCHAR(100),
    type_of_organization VARCHAR(100),
    hiring_history TEXT,
    company_description TEXT,
    website_url VARCHAR(255),
    shard_id INT DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES shard_0_users(user_id),
    INDEX idx_user_id (user_id),
    INDEX idx_company_name (company_name)
);

-- ======================================================================
-- SHARD 0: USER_LOGS
-- ======================================================================
CREATE TABLE IF NOT EXISTS shard_0_user_logs (
    log_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    action VARCHAR(255),
    ip_address VARCHAR(45),
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    device_info TEXT,
    shard_id INT DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES shard_0_users(user_id),
    INDEX idx_user_id (user_id),
    INDEX idx_start_time (start_time),
    INDEX idx_action (action)
);

-- ======================================================================
-- SHARD 0: RESUMES
-- ======================================================================
CREATE TABLE IF NOT EXISTS shard_0_resumes (
    resume_id INT PRIMARY KEY,
    student_id INT NOT NULL,
    user_id INT NOT NULL,
    resume_label VARCHAR(255),
    file_url VARCHAR(255),
    ats_score DECIMAL(5,2),
    is_verified BOOLEAN DEFAULT FALSE,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    shard_id INT DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES shard_0_users(user_id),
    FOREIGN KEY (student_id) REFERENCES shard_0_students(student_id),
    INDEX idx_user_id (user_id),
    INDEX idx_student_id (student_id),
    INDEX idx_uploaded_at (uploaded_at)
);

-- ======================================================================
-- SHARD 0: APPLICATIONS
-- ======================================================================
CREATE TABLE IF NOT EXISTS shard_0_applications (
    application_id INT PRIMARY KEY,
    job_id INT,
    student_id INT NOT NULL,
    user_id INT NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'pending',
    shard_id INT DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES shard_0_users(user_id),
    FOREIGN KEY (student_id) REFERENCES shard_0_students(student_id),
    INDEX idx_user_id (user_id),
    INDEX idx_student_id (student_id),
    INDEX idx_job_id (job_id),
    INDEX idx_applied_at (applied_at),
    INDEX idx_status (status)
);

-- ======================================================================
-- Verification Queries for Shard 0
-- ======================================================================

-- Check all tables exist
-- SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'Machine_minds' AND TABLE_NAME LIKE 'shard_0_%';

-- Check table structures
-- DESCRIBE shard_0_users;
-- DESCRIBE shard_0_students;
-- DESCRIBE shard_0_alumni_user;
-- DESCRIBE shard_0_companies;
-- DESCRIBE shard_0_user_logs;
-- DESCRIBE shard_0_resumes;
-- DESCRIBE shard_0_applications;

SET FOREIGN_KEY_CHECKS=1;

-- Verify record counts (after data migration)
-- SELECT 'shard_0_users' as table_name, COUNT(*) as count FROM shard_0_users
-- UNION ALL
-- SELECT 'shard_0_students', COUNT(*) FROM shard_0_students
-- UNION ALL
-- SELECT 'shard_0_alumni_user', COUNT(*) FROM shard_0_alumni_user
-- UNION ALL
-- SELECT 'shard_0_companies', COUNT(*) FROM shard_0_companies
-- UNION ALL
-- SELECT 'shard_0_user_logs', COUNT(*) FROM shard_0_user_logs
-- UNION ALL
-- SELECT 'shard_0_resumes', COUNT(*) FROM shard_0_resumes
-- UNION ALL
-- SELECT 'shard_0_applications', COUNT(*) FROM shard_0_applications;
