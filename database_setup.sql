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
    first_name VARCHAR(100),
    middle_initial VARCHAR(10),
    last_name VARCHAR(100),
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
    staff_code_hash VARCHAR(255),
    full_name VARCHAR(200),
    email VARCHAR(100),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ICT support accounts
CREATE TABLE IF NOT EXISTS ict_support (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    staff_code_hash VARCHAR(255),
    full_name VARCHAR(200) NOT NULL,
    role_type ENUM('admin', 'tech', 'helpdesk', 'coordinator') NOT NULL DEFAULT 'tech',
    email VARCHAR(100) UNIQUE,
    status ENUM('active', 'inactive', 'suspended') NOT NULL DEFAULT 'active',
    last_login DATETIME NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Assessment definitions shown in the separate Python and Java assessment pages
CREATE TABLE IF NOT EXISTS assessments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    assessment_number TINYINT NOT NULL,
    language ENUM('python', 'java', 'cpp', 'javascript', 'php') NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    duration_minutes SMALLINT UNSIGNED NOT NULL,
    points SMALLINT UNSIGNED NOT NULL,
    difficulty ENUM('Easy', 'Medium', 'Hard') NOT NULL,
    expected_output TEXT NOT NULL,
    hint TEXT NOT NULL,
    required_blocks TEXT NOT NULL,
    starter_blocks_xml TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_assessment_language_number (language, assessment_number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Activity scores are separate from assessment attempts.
CREATE TABLE IF NOT EXISTS activities (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    activity_name VARCHAR(200) NOT NULL,
    score SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    code_blocks TEXT,
    language VARCHAR(30),
    completed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_student_activity (student_id, activity_name),
    INDEX idx_activities_student (student_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Student assessment submissions and scores
CREATE TABLE IF NOT EXISTS assessment_attempts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    assessment_id INT NOT NULL,
    student_id INT NOT NULL,
    code_blocks TEXT NOT NULL,
    output TEXT,
    score SMALLINT UNSIGNED DEFAULT 0,
    status ENUM('in_progress', 'submitted') NOT NULL DEFAULT 'in_progress',
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    submitted_at DATETIME NULL,
    FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    UNIQUE KEY uq_student_assessment_attempt (assessment_id, student_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ICT support tickets
CREATE TABLE IF NOT EXISTS ict_tickets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ticket_number VARCHAR(30) UNIQUE NOT NULL,
    student_id INT NOT NULL,
    student_name VARCHAR(200),
    student_lrn VARCHAR(50),
    subject VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    priority ENUM('low', 'medium', 'high') NOT NULL DEFAULT 'medium',
    category VARCHAR(100) NOT NULL DEFAULT 'other',
    status ENUM('pending', 'in_progress', 'resolved', 'closed') NOT NULL DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    resolved_at DATETIME NULL,
    INDEX idx_ict_tickets_student (student_id),
    INDEX idx_ict_tickets_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Default teacher accounts
INSERT INTO teachers (username, password, full_name, email, created_at)
VALUES
    ('admin', '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9', 'System Administrator', 'admin@blocklearn.edu.ph', @now),
    ('teacher1', '1aec145aae00aee55d04997f34045b9e3ab42ddb25bf220f29b62f981963c1a8', 'Teacher One', 'teacher1@blocklearn.edu.ph', @now);

-- Default ICT support accounts
INSERT INTO ict_support (username, password, full_name, role_type, email)
VALUES
    ('ICT-Tech', SHA2('Tech123@', 256), 'ICT Technician', 'tech', 'ict.tech@pnhs.edu.ph');

-- Assessment content used by Python and Java assessment playgrounds
INSERT INTO assessments
    (assessment_number, language, title, description, duration_minutes, points, difficulty,
     expected_output, hint, required_blocks, starter_blocks_xml)
VALUES
    (1, 'python', 'Python Fundamentals', 'Basic Python syntax, print statements, and program output.', 10, 10, 'Easy',
     'Hello, World!', 'Use print("Hello, World!") in Python.', 'print,TEXT',
     '<xml xmlns="https://developers.google.com/blockly/xml"><block type="text_print" x="20" y="20"><value name="TEXT"><block type="text"><field name="TEXT">Hello, World!</field></block></value></block></xml>'),
    (2, 'python', 'Variables & Data Types', 'Understanding variables, strings, integers, and type conversion.', 12, 15, 'Easy',
     'Juan', 'Use name = "Juan" then print(name).', 'SET VARIABLE,PRINT,TEXT,GET VARIABLE',
     '<xml xmlns="https://developers.google.com/blockly/xml"><block type="variables_set" x="20" y="20"><field name="VAR">name</field><value name="VALUE"><block type="text"><field name="TEXT">Juan</field></block></value><next><block type="text_print"><value name="TEXT"><block type="variables_get"><field name="VAR">name</field></block></value></block></next></block></xml>'),
    (3, 'python', 'Conditional Statements', 'Master if-else, elif, and logical operators in Python programming.', 15, 20, 'Medium',
     'Positive', 'Use 10 > 5 with GT operator.', 'IF-ELSE,COMPARE,PRINT,NUMBER',
     '<xml xmlns="https://developers.google.com/blockly/xml"><block type="controls_if" x="20" y="20"><mutation else="1"></mutation><value name="IF0"><block type="logic_compare"><field name="OP">GT</field><value name="A"><block type="math_number"><field name="NUM">10</field></block></value><value name="B"><block type="math_number"><field name="NUM">5</field></block></value></block></value><statement name="DO0"><block type="text_print"><value name="TEXT"><block type="text"><field name="TEXT">Positive</field></block></value></block></statement><statement name="ELSE"><block type="text_print"><value name="TEXT"><block type="text"><field name="TEXT">Negative</field></block></value></block></statement></block></xml>'),
    (4, 'python', 'Loops & Iterations', 'Learn for loops, while loops, and iteration techniques in Python.', 18, 20, 'Medium',
     '1\n2\n3\n4\n5', 'Use for i in range(1, 6).', 'FOR LOOP,PRINT,GET VARIABLE',
     '<xml xmlns="https://developers.google.com/blockly/xml"><block type="controls_for" x="20" y="20"><field name="VAR">i</field><value name="FROM"><block type="math_number"><field name="NUM">1</field></block></value><value name="TO"><block type="math_number"><field name="NUM">5</field></block></value><value name="BY"><block type="math_number"><field name="NUM">1</field></block></value><statement name="DO"><block type="text_print"><value name="TEXT"><block type="variables_get"><field name="VAR">i</field></block></value></block></statement></block></xml>'),
    (5, 'python', 'Functions & Modules', 'Create and use functions, understand scope, and import modules.', 20, 25, 'Hard',
     'Welcome to BlockLearn!', 'Define def greet() then call greet().', 'DEFINE FUNCTION,PRINT,CALL FUNCTION,TEXT',
     '<xml xmlns="https://developers.google.com/blockly/xml"><block type="procedures_defreturn" x="20" y="20"><mutation><arg name=""></arg></mutation><field name="NAME">greet</field><statement name="STACK"><block type="text_print"><value name="TEXT"><block type="text"><field name="TEXT">Welcome to BlockLearn!</field></block></value></block></statement><next><block type="procedures_callreturn"><mutation name="greet"></mutation></block></next></block></xml>'),
    (1, 'java', 'Java Fundamentals', 'Basic Java syntax, System.out.println, and program output.', 10, 10, 'Easy',
     'Hello, World!', 'Use System.out.println("Hello, World!"); in Java.', 'System.out.println,TEXT',
     '<xml xmlns="https://developers.google.com/blockly/xml"><block type="java_print" x="20" y="20"><value name="TEXT"><block type="text"><field name="TEXT">Hello, World!</field></block></value></block></xml>'),
    (2, 'java', 'Variables & Data Types', 'Understanding int, double, String variables in Java.', 12, 15, 'Easy',
     '16', 'Use int age = 16; then System.out.println(age);', 'CREATE VARIABLE,System.out.println,GET VARIABLE,NUMBER',
     '<xml xmlns="https://developers.google.com/blockly/xml"><block type="java_variable" x="20" y="20"><field name="TYPE">int</field><field name="NAME">age</field><value name="VALUE"><block type="math_number"><field name="NUM">16</field></block></value><next><block type="java_print"><value name="TEXT"><block type="java_variable_get"><field name="NAME">age</field></block></value></block></next></block></xml>'),
    (3, 'java', 'Conditional Statements', 'Master if-else statements and comparison operators in Java.', 15, 20, 'Medium',
     'Passed', 'Use score >= 75 with GTE operator.', 'IF-ELSE,CREATE VARIABLE,System.out.println,COMPARE,NUMBER',
     '<xml xmlns="https://developers.google.com/blockly/xml"><block type="java_variable" x="20" y="20"><field name="TYPE">int</field><field name="NAME">score</field><value name="VALUE"><block type="math_number"><field name="NUM">80</field></block></value><next><block type="java_if"><value name="IF0"><block type="logic_compare"><field name="OP">GTE</field><value name="A"><block type="java_variable_get"><field name="NAME">score</field></block></value><value name="B"><block type="math_number"><field name="NUM">75</field></block></value></block></value><statement name="DO0"><block type="java_print"><value name="TEXT"><block type="text"><field name="TEXT">Passed</field></block></value></block></statement><statement name="ELSE"><block type="java_print"><value name="TEXT"><block type="text"><field name="TEXT">Failed</field></block></value></block></statement></block></next></block></xml>'),
    (4, 'java', 'Loops & Repetition', 'Learn for loops and while loops in Java programming.', 18, 20, 'Medium',
     '1\n2\n3\n4\n5', 'Use for (int i = 1; i <= 5; i++).', 'FOR LOOP,System.out.println,GET VARIABLE',
     '<xml xmlns="https://developers.google.com/blockly/xml"><block type="java_for" x="20" y="20"><field name="VAR">i</field><value name="FROM"><block type="math_number"><field name="NUM">1</field></block></value><value name="TO"><block type="math_number"><field name="NUM">5</field></block></value><statement name="DO"><block type="java_print"><value name="TEXT"><block type="java_variable_get"><field name="NAME">i</field></block></value></block></statement></block></xml>'),
    (5, 'java', 'Methods & Problem Solving', 'Create and call methods, understand reusable code in Java.', 20, 25, 'Hard',
     'Welcome to Java!', 'Create void welcome() then call welcome();', 'CREATE METHOD,System.out.println,CALL METHOD,TEXT',
     '<xml xmlns="https://developers.google.com/blockly/xml"><block type="java_method" x="20" y="20"><field name="NAME">welcome</field><statement name="STACK"><block type="java_print"><value name="TEXT"><block type="text"><field name="TEXT">Welcome to Java!</field></block></value></block></statement><next><block type="java_method_call"><field name="NAME">welcome</field></block></next></block></xml>'),
    (1, 'cpp', 'Hello C++', 'Print Hello, C++! to the console.', 5, 10, 'Easy',
     'Hello, C++!', 'Use cout << "Hello, C++!";', 'cout,TEXT', '<xml xmlns="https://developers.google.com/blockly/xml"></xml>'),
    (2, 'cpp', 'Store Age', 'Create an age variable with value 17 and print it.', 5, 10, 'Easy',
     '17', 'Use int age = 17; then cout << age;', 'int variable,cout,NUMBER,GET VARIABLE', '<xml xmlns="https://developers.google.com/blockly/xml"></xml>'),
    (3, 'cpp', 'Multiply Numbers', 'Multiply 6 by 5 and print the result.', 8, 10, 'Medium',
     '30', 'Use cout << 6 * 5;', 'cout,MULTIPLY,NUMBER', '<xml xmlns="https://developers.google.com/blockly/xml"></xml>'),
    (4, 'cpp', 'Less Than', 'Check whether 15 is less than 20 and print the message.', 10, 10, 'Medium',
     '15 is less than 20', 'Use if (15 < 20) with cout inside.', 'if,LESS THAN,cout,NUMBER,TEXT', '<xml xmlns="https://developers.google.com/blockly/xml"></xml>'),
    (5, 'cpp', 'Display Numbers', 'Display numbers 1 to 5 using a for loop.', 12, 10, 'Hard',
    '1\n2\n3\n4\n5', 'Use for (int i = 1; i <= 5; i++).', 'FOR LOOP,cout,NUMBER,GET VARIABLE', '<xml xmlns="https://developers.google.com/blockly/xml"></xml>'),
    (1, 'javascript', 'Hello, JavaScript!', 'Print Hello, JavaScript! to the console.', 5, 10, 'Easy',
     'Hello, JavaScript!', 'Use console.log("Hello, JavaScript!");', 'console.log,TEXT', '<xml xmlns="https://developers.google.com/blockly/xml"></xml>'),
    (2, 'javascript', 'Store and Display a Score', 'Create a score variable with value 90 and print it.', 5, 10, 'Easy',
     '90', 'Use var score = 90; then console.log(score);', 'var,console.log,NUMBER,variable_get', '<xml xmlns="https://developers.google.com/blockly/xml"></xml>'),
    (3, 'javascript', 'Add Two Numbers', 'Add 25 and 15 and print the result.', 8, 10, 'Medium',
     '40', 'Use console.log(25 + 15);', 'console.log,+,NUMBER', '<xml xmlns="https://developers.google.com/blockly/xml"></xml>'),
    (4, 'javascript', 'Greater Than', 'Check whether 20 is greater than 10 and print the message.', 10, 10, 'Medium',
     '20 is greater than 10', 'Use if (20 > 10) with console.log inside.', 'if,>,console.log,NUMBER,TEXT', '<xml xmlns="https://developers.google.com/blockly/xml"></xml>'),
    (5, 'javascript', 'Repeat a Message Five Times', 'Print I love programming! five times with a loop.', 12, 10, 'Hard',
     'I love programming!\nI love programming!\nI love programming!\nI love programming!\nI love programming!', 'Use a for loop that repeats 5 times.', 'for loop,console.log,NUMBER,TEXT', '<xml xmlns="https://developers.google.com/blockly/xml"></xml>');

INSERT INTO assessments
    (assessment_number, language, title, description, duration_minutes, points, difficulty,
     expected_output, hint, required_blocks, starter_blocks_xml)
VALUES
    (1, 'php', 'Hello PHP', 'Print Hello, PHP! to the console.', 5, 10, 'Easy',
     'Hello, PHP!', 'Use echo "Hello, PHP!".', 'echo,TEXT', '<xml xmlns="https://developers.google.com/blockly/xml"></xml>'),
    (2, 'php', 'Store a Name', 'Create a name variable and display it.', 5, 10, 'Easy',
     'Caryll', 'Use $name = "Caryll" then echo $name.', 'variable,echo,TEXT,GET VARIABLE', '<xml xmlns="https://developers.google.com/blockly/xml"></xml>'),
    (3, 'php', 'Subtract Numbers', 'Subtract 50 from 80 and display the result.', 8, 10, 'Medium',
     '30', 'Use echo 80 - 50.', 'echo,SUBTRACT,NUMBER', '<xml xmlns="https://developers.google.com/blockly/xml"></xml>'),
    (4, 'php', 'Greater Than', 'Check whether 25 is greater than 18.', 10, 10, 'Medium',
     '25 is greater than 18', 'Use if (25 > 18) with echo.', 'if,>,echo,NUMBER,TEXT', '<xml xmlns="https://developers.google.com/blockly/xml"></xml>'),
    (5, 'php', 'Repeat a Message', 'Display Learning PHP! three times using a loop.', 12, 10, 'Hard',
     'Learning PHP!\nLearning PHP!\nLearning PHP!', 'Use a loop that repeats three times.', 'FOR LOOP,echo,NUMBER,TEXT', '<xml xmlns="https://developers.google.com/blockly/xml"></xml>');

