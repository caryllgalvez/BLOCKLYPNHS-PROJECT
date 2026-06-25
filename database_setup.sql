-- Database setup for BlockLearn
-- Run this script in MySQL to create the database, tables, and default records.

DROP DATABASE IF EXISTS blocklypnhsproject;
CREATE DATABASE blocklypnhsproject CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE blocklypnhsproject;

SET @now = NOW();

-- Students table
CREATE TABLE IF NOT EXISTS students (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    full_name VARCHAR(200),
    password VARCHAR(255) NOT NULL,
    lrn VARCHAR(50) UNIQUE NOT NULL,
    grade_level VARCHAR(20) NOT NULL,
    email VARCHAR(100),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Teachers table
CREATE TABLE IF NOT EXISTS teachers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    full_name VARCHAR(200),
    email VARCHAR(100),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Activities table
CREATE TABLE IF NOT EXISTS activities (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    activity_name VARCHAR(200) NOT NULL,
    score INT DEFAULT 0,
    code_blocks TEXT,
    language VARCHAR(50) DEFAULT 'python',
    completed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Lessons table
CREATE TABLE IF NOT EXISTS lessons (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    content TEXT,
    difficulty VARCHAR(50),
    order_num INT DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Default teacher accounts
INSERT INTO teachers (username, password, full_name, email, created_at)
VALUES
    ('admin', '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9', 'System Administrator', 'admin@blocklearn.edu.ph', @now),
    ('teacher1', 'cde383eee8ee7a4400adf7a15f716f179a2eb97646b37e089eb8d6d04e663416', 'Teacher One', 'teacher1@blocklearn.edu.ph', @now);

-- Default lessons
INSERT INTO lessons (id, title, description, content, difficulty, order_num)
VALUES
    (1, '📢 Activity 1: Say Hello!', 'Learn to print ''Hello World'' using Blockly', 'Print statement basics', 'Beginner', 1),
    (2, '👤 Activity 2: Print Your Name', 'Print your own name using variables', 'Variables and strings', 'Beginner', 2),
    (3, '➕ Activity 3: Simple Math', 'Perform addition and print the result', 'Math operations', 'Beginner', 3),
    (4, '🔄 Activity 4: Using Loops', 'Repeat actions using loops', 'Loop structures', 'Intermediate', 4);
