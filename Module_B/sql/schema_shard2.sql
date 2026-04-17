-- ======================================================================
-- Shard 2 Schema (Port 3309)
-- Create all shard_2_* tables for data where user_id % 3 = 2
-- ======================================================================

SET FOREIGN_KEY_CHECKS=0;

CREATE TABLE IF NOT EXISTS shard_2_users (
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
    shard_id INT DEFAULT 2,
    INDEX idx_username (username),
    INDEX idx_email (email),
    INDEX idx_created_at (created_at)
);

CREATE TABLE IF NOT EXISTS shard_2_students (
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
    shard_id INT DEFAULT 2,
    FOREIGN KEY (user_id) REFERENCES shard_2_users(user_id),
    INDEX idx_user_id (user_id),
    INDEX idx_cpi (latest_cpi)
);

CREATE TABLE IF NOT EXISTS shard_2_alumni_user (
    alumni_id INT PRIMARY KEY,
    user_id INT NOT NULL,
    grad_year INT,
    current_company VARCHAR(255),
    placement_history TEXT,
    designation VARCHAR(255),
    shard_id INT DEFAULT 2,
    FOREIGN KEY (user_id) REFERENCES shard_2_users(user_id),
    INDEX idx_user_id (user_id)
);

CREATE TABLE IF NOT EXISTS shard_2_companies (
    company_id INT PRIMARY KEY,
    user_id INT NOT NULL,
    company_name VARCHAR(255) NOT NULL,
    industry_sector VARCHAR(100),
    type_of_organization VARCHAR(100),
    hiring_history TEXT,
    company_description TEXT,
    website_url VARCHAR(255),
    shard_id INT DEFAULT 2,
    FOREIGN KEY (user_id) REFERENCES shard_2_users(user_id),
    INDEX idx_user_id (user_id),
    INDEX idx_company_name (company_name)
);

CREATE TABLE IF NOT EXISTS shard_2_user_logs (
    log_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    action VARCHAR(255),
    ip_address VARCHAR(45),
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    device_info TEXT,
    shard_id INT DEFAULT 2,
    FOREIGN KEY (user_id) REFERENCES shard_2_users(user_id),
    INDEX idx_user_id (user_id),
    INDEX idx_start_time (start_time),
    INDEX idx_action (action)
);

CREATE TABLE IF NOT EXISTS shard_2_resumes (
    resume_id INT PRIMARY KEY,
    student_id INT NOT NULL,
    user_id INT NOT NULL,
    resume_label VARCHAR(255),
    file_url VARCHAR(255),
    ats_score DECIMAL(5,2),
    is_verified BOOLEAN DEFAULT FALSE,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    shard_id INT DEFAULT 2,
    FOREIGN KEY (user_id) REFERENCES shard_2_users(user_id),
    FOREIGN KEY (student_id) REFERENCES shard_2_students(student_id),
    INDEX idx_user_id (user_id),
    INDEX idx_student_id (student_id),
    INDEX idx_uploaded_at (uploaded_at)
);

CREATE TABLE IF NOT EXISTS shard_2_applications (
    application_id INT PRIMARY KEY,
    job_id INT,
    student_id INT NOT NULL,
    user_id INT NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'pending',
    shard_id INT DEFAULT 2,
    FOREIGN KEY (user_id) REFERENCES shard_2_users(user_id),
    FOREIGN KEY (student_id) REFERENCES shard_2_students(student_id),
    INDEX idx_user_id (user_id),
    INDEX idx_student_id (student_id),
    INDEX idx_job_id (job_id),
    INDEX idx_applied_at (applied_at),
    INDEX idx_status (status)
);

SET FOREIGN_KEY_CHECKS=1;
