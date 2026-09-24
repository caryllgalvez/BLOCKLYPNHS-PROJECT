# app.py - Main Flask Application for Blockly Learning Platform
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
from flask_cors import CORS
import mysql.connector
import hashlib
import secrets
from datetime import datetime, timedelta
import os
import re
import traceback
from backend.notification_service import (
    notify_new_assessment_submission,
    notify_assessment_checked,
    notify_new_support_ticket,
    notify_ticket_updated,
    get_notifications_for_user,
    mark_all_notifications_read,
)
from backend.staff_auth import initialize_staff_code_hashes, verify_staff_code

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'frontend')
STATIC_DIR = os.path.join(BASE_DIR, 'static')

app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
app.secret_key = 'your-secret-key-change-this-in-production-2024'
CORS(app)


# Serve the BL logo as the browser favicon to replace the default/blank icon.
@app.route('/favicon.ico')
def favicon():
    logo_path = os.path.join(app.static_folder, 'BL-LOGO.png')
    if os.path.exists(logo_path):
        return send_from_directory(app.static_folder, 'BL-LOGO.png', mimetype='image/png')
    return ('', 204)

@app.route('/module-assets/<path:filename>')
def module_assets(filename):
    """Serve CSS and JavaScript assets used by module lesson pages."""
    modules_dir = os.path.join(BASE_DIR, 'frontend', 'modules_activities')
    return send_from_directory(modules_dir, filename)

# Database configuration
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'C@ryll025',
    'database': 'blocklypnhsproject'
}

def get_db_connection():
    try:
        return mysql.connector.connect(**db_config)
    except mysql.connector.Error as err:
        print(f"Database connection error: {err}")
        raise Exception("Database connection failed")

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def validate_lrn(lrn):
    return lrn and re.match(r'^\d{12}$', str(lrn))

# ==================== DATABASE INITIALIZATION ====================

def init_database():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Create students table with full_name
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                full_name VARCHAR(200),
                password VARCHAR(255) NOT NULL,
                lrn VARCHAR(50) UNIQUE NOT NULL,
                grade_level VARCHAR(20) NOT NULL,
                email VARCHAR(100),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Add full_name column if it doesn't exist
        cursor.execute("SHOW COLUMNS FROM students LIKE 'full_name'")
        if cursor.fetchone() is None:
            cursor.execute("ALTER TABLE students ADD COLUMN full_name VARCHAR(200) AFTER username")
            print("✅ Added full_name column to students table")

        for column_name, column_definition in (
            ('reset_token', 'VARCHAR(128) NULL'),
            ('reset_token_expires', 'DATETIME NULL'),
        ):
            cursor.execute(f"SHOW COLUMNS FROM students LIKE '{column_name}'")
            if cursor.fetchone() is None:
                cursor.execute(f"ALTER TABLE students ADD COLUMN {column_name} {column_definition}")
        
        # Create teachers table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS teachers (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                staff_code_hash VARCHAR(255),
                full_name VARCHAR(200),
                email VARCHAR(100),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
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
            )
        """)

        for table in ('teachers', 'ict_support'):
            cursor.execute(f"SHOW COLUMNS FROM {table} LIKE 'staff_code_hash'")
            if cursor.fetchone() is None:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN staff_code_hash VARCHAR(255) NULL")

        # Keep ICT access limited to the single technician account.
        cursor.execute("DELETE FROM ict_support WHERE LOWER(username) <> 'ict-tech'")

        ict_password = hash_password('Tech123@')
        cursor.execute("SELECT id, password, status FROM ict_support WHERE LOWER(username) = LOWER(%s)", ('ICT-Tech',))
        ict_user = cursor.fetchone()
        if not ict_user:
            cursor.execute("""
                INSERT INTO ict_support (username, password, full_name, role_type, email)
                VALUES (%s, %s, %s, %s, %s)
            """, ('ICT-Tech', ict_password, 'ICT Technician', 'tech', 'ict.tech@pnhs.edu.ph'))
            print("✅ ICT account created: username='ICT-Tech'")
        elif ict_user['password'] != ict_password or ict_user['status'] != 'active':
            cursor.execute("""
                UPDATE ict_support
                SET password = %s, status = 'active'
                WHERE id = %s
            """, (ict_password, ict_user['id']))
            print("ℹ️ ICT-Tech account credentials/status refreshed")
        
        # Keep activity scores separate from assessment attempts.
        cursor.execute("""
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
            )
        """)
        cursor.execute("DROP TABLE IF EXISTS tickets")

        cursor.execute("""
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
            )
        """)

        # Store the assessment definitions used by the separate language pages.
        cursor.execute("""
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
            )
        """)

        # Older databases can contain duplicate assessment rows from prior bootstraps.
        # Remove them before the seed inserts so the unique index is always clean.
        cursor.execute("""
            DELETE t1
            FROM assessments t1
            INNER JOIN assessments t2
                ON t1.id < t2.id
               AND t1.language = t2.language
               AND t1.assessment_number = t2.assessment_number
        """)

        cursor.execute("SELECT COUNT(*) AS total FROM assessments")
        if cursor.fetchone()['total'] == 0:
            default_assessments = [
                ('python', 1, 'Python Fundamentals', 'Basic Python syntax, print statements, and program output.', 10, 10, 'Easy', 'Hello, World!', 'Use print("Hello, World!") in Python.', 'print,TEXT'),
                ('python', 2, 'Variables & Data Types', 'Understanding variables, strings, integers, and type conversion.', 12, 15, 'Easy', 'Juan', 'Use name = "Juan" then print(name).', 'SET VARIABLE,PRINT,TEXT,GET VARIABLE'),
                ('python', 3, 'Conditional Statements', 'Master if-else, elif, and logical operators in Python programming.', 15, 20, 'Medium', 'Positive', 'Use 10 > 5 with GT operator.', 'IF-ELSE,COMPARE,PRINT,NUMBER'),
                ('python', 4, 'Loops & Iterations', 'Learn for loops, while loops, and iteration techniques in Python.', 18, 20, 'Medium', '1\n2\n3\n4\n5', 'Use for i in range(1, 6).', 'FOR LOOP,PRINT,GET VARIABLE'),
                ('python', 5, 'Functions & Modules', 'Create and use functions, understand scope, and import modules.', 20, 25, 'Hard', 'Welcome to BlockLearn!', 'Define def greet() then call greet().', 'DEFINE FUNCTION,PRINT,CALL FUNCTION,TEXT'),
                ('java', 1, 'Java Fundamentals', 'Basic Java syntax, System.out.println, and program output.', 10, 10, 'Easy', 'Hello, World!', 'Use System.out.println("Hello, World!"); in Java.', 'System.out.println,TEXT'),
                ('java', 2, 'Variables & Data Types', 'Understanding int, double, String variables in Java.', 12, 15, 'Easy', '16', 'Use int age = 16; then System.out.println(age);', 'CREATE VARIABLE,System.out.println,GET VARIABLE,NUMBER'),
                ('java', 3, 'Conditional Statements', 'Master if-else statements and comparison operators in Java.', 15, 20, 'Medium', 'Passed', 'Use score >= 75 with GTE operator.', 'IF-ELSE,CREATE VARIABLE,System.out.println,COMPARE,NUMBER'),
                ('java', 4, 'Loops & Repetition', 'Learn for loops and while loops in Java programming.', 18, 20, 'Medium', '1\n2\n3\n4\n5', 'Use for (int i = 1; i <= 5; i++).', 'FOR LOOP,System.out.println,GET VARIABLE'),
                ('java', 5, 'Methods & Problem Solving', 'Create and call methods, understand reusable code in Java.', 20, 25, 'Hard', 'Welcome to Java!', 'Create void welcome() then call welcome();', 'CREATE METHOD,System.out.println,CALL METHOD,TEXT')
            ]
            cursor.executemany("""
                INSERT INTO assessments
                    (language, assessment_number, title, description, duration_minutes, points,
                     difficulty, expected_output, hint, required_blocks, starter_blocks_xml)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    title = VALUES(title),
                    description = VALUES(description),
                    duration_minutes = VALUES(duration_minutes),
                    points = VALUES(points),
                    difficulty = VALUES(difficulty),
                    expected_output = VALUES(expected_output),
                    hint = VALUES(hint),
                    required_blocks = VALUES(required_blocks),
                    starter_blocks_xml = VALUES(starter_blocks_xml)
            """, [assessment + ('<xml xmlns="https://developers.google.com/blockly/xml"></xml>',) for assessment in default_assessments])

        # Normalize legacy language labels before restoring the strict ENUM.
        # Older databases used display names such as "C++" and "JavaScript".
        cursor.execute("ALTER TABLE assessments MODIFY language VARCHAR(20) NOT NULL")
        cursor.execute("""
            DELETE FROM assessments
            WHERE LOWER(TRIM(language)) NOT IN
                ('python', 'java', 'cpp', 'c++', 'c plus plus', 'js', 'javascript', 'php')
        """)
        cursor.execute("""
            UPDATE assessments
            SET language = CASE LOWER(TRIM(language))
                WHEN 'c++' THEN 'cpp'
                WHEN 'c plus plus' THEN 'cpp'
                WHEN 'js' THEN 'javascript'
                ELSE language
            END
            WHERE LOWER(TRIM(language)) IN ('c++', 'c plus plus', 'js')
        """)
        cursor.execute("""
            DELETE t1
            FROM assessments t1
            INNER JOIN assessments t2
                ON t1.id < t2.id
               AND t1.language = t2.language
               AND t1.assessment_number = t2.assessment_number
        """)
        cursor.execute("ALTER TABLE assessments MODIFY language ENUM('python', 'java', 'cpp', 'javascript', 'php') NOT NULL")
        cpp_assessments = [
            (1, 'Hello C++', 'Print Hello, C++! to the console.', 5, 10, 'Easy', 'Hello, C++!', 'Use cout << "Hello, C++!";', 'cout,TEXT'),
            (2, 'Store Age', 'Create an age variable with value 17 and print it.', 5, 10, 'Easy', '17', 'Use int age = 17; then cout << age;', 'int variable,cout,NUMBER,GET VARIABLE'),
            (3, 'Multiply Numbers', 'Multiply 6 by 5 and print the result.', 8, 10, 'Medium', '30', 'Use cout << 6 * 5;', 'cout,MULTIPLY,NUMBER'),
            (4, 'Less Than', 'Check whether 15 is less than 20 and print the message.', 10, 10, 'Medium', '15 is less than 20', 'Use if (15 < 20) with cout inside.', 'if,LESS THAN,cout,NUMBER,TEXT'),
            (5, 'Display Numbers', 'Display numbers 1 to 5 using a for loop.', 12, 10, 'Hard', '1\n2\n3\n4\n5', 'Use for (int i = 1; i <= 5; i++).', 'FOR LOOP,cout,NUMBER,GET VARIABLE')
        ]
        cursor.executemany("""
            INSERT INTO assessments
                (assessment_number, language, title, description, duration_minutes, points,
                 difficulty, expected_output, hint, required_blocks, starter_blocks_xml)
            VALUES (%s, 'cpp', %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                title = VALUES(title), description = VALUES(description),
                duration_minutes = VALUES(duration_minutes), points = VALUES(points),
                difficulty = VALUES(difficulty), expected_output = VALUES(expected_output),
                hint = VALUES(hint), required_blocks = VALUES(required_blocks)
        """, [assessment + ('<xml xmlns="https://developers.google.com/blockly/xml"></xml>',) for assessment in cpp_assessments])

        javascript_assessments = [
            (1, 'Hello, JavaScript!', 'Print Hello, JavaScript! to the console.', 5, 10, 'Easy', 'Hello, JavaScript!', 'Use console.log("Hello, JavaScript!");', 'console.log,TEXT'),
            (2, 'Store and Display a Score', 'Create a score variable with value 90 and print it.', 5, 10, 'Easy', '90', 'Use var score = 90; then console.log(score);', 'var,console.log,NUMBER,variable_get'),
            (3, 'Add Two Numbers', 'Add 25 and 15 and print the result.', 8, 10, 'Medium', '40', 'Use console.log(25 + 15);', 'console.log,+,NUMBER'),
            (4, 'Greater Than', 'Check whether 20 is greater than 10 and print the message.', 10, 10, 'Medium', '20 is greater than 10', 'Use if (20 > 10) with console.log inside.', 'if,>,console.log,NUMBER,TEXT'),
            (5, 'Repeat a Message Five Times', 'Print I love programming! five times with a loop.', 12, 10, 'Hard', 'I love programming!\nI love programming!\nI love programming!\nI love programming!\nI love programming!', 'Use a for loop that repeats 5 times.', 'for loop,console.log,NUMBER,TEXT')
        ]
        cursor.executemany("""
            INSERT INTO assessments
                (assessment_number, language, title, description, duration_minutes, points,
                 difficulty, expected_output, hint, required_blocks, starter_blocks_xml)
            VALUES (%s, 'javascript', %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                title = VALUES(title), description = VALUES(description),
                duration_minutes = VALUES(duration_minutes), points = VALUES(points),
                difficulty = VALUES(difficulty), expected_output = VALUES(expected_output),
                hint = VALUES(hint), required_blocks = VALUES(required_blocks)
        """, [assessment + ('<xml xmlns="https://developers.google.com/blockly/xml"></xml>',) for assessment in javascript_assessments])

        php_assessments = [
            (1, 'Hello PHP', 'Print Hello, PHP! to the console.', 5, 10, 'Easy', 'Hello, PHP!', 'Use echo "Hello, PHP!".', 'echo,TEXT'),
            (2, 'Store a Name', 'Create a name variable and display it.', 5, 10, 'Easy', 'Caryll', 'Use $name = "Caryll" then echo $name.', 'variable,echo,TEXT,GET VARIABLE'),
            (3, 'Subtract Numbers', 'Subtract 50 from 80 and display the result.', 8, 10, 'Medium', '30', 'Use echo 80 - 50.', 'echo,SUBTRACT,NUMBER'),
            (4, 'Greater Than', 'Check whether 25 is greater than 18.', 10, 10, 'Medium', '25 is greater than 18', 'Use if (25 > 18) with echo.', 'if,>,echo,NUMBER,TEXT'),
            (5, 'Repeat a Message', 'Display Learning PHP! three times using a loop.', 12, 10, 'Hard', 'Learning PHP!\nLearning PHP!\nLearning PHP!', 'Use a loop that repeats three times.', 'FOR LOOP,echo,NUMBER,TEXT')
        ]
        cursor.executemany("""
            INSERT INTO assessments
                (assessment_number, language, title, description, duration_minutes, points,
                 difficulty, expected_output, hint, required_blocks, starter_blocks_xml)
            VALUES (%s, 'php', %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                title = VALUES(title), description = VALUES(description),
                duration_minutes = VALUES(duration_minutes), points = VALUES(points),
                difficulty = VALUES(difficulty), expected_output = VALUES(expected_output),
                hint = VALUES(hint), required_blocks = VALUES(required_blocks)
        """, [assessment + ('<xml xmlns="https://developers.google.com/blockly/xml"></xml>',) for assessment in php_assessments])

        # Keep the database definition aligned with the Python Fundamentals playground.
        cursor.execute("""
            UPDATE assessments
            SET title = %s,
                description = %s,
                duration_minutes = %s,
                points = %s,
                difficulty = %s,
                expected_output = %s,
                hint = %s,
                required_blocks = %s,
                starter_blocks_xml = %s
            WHERE language = 'python' AND assessment_number = 1
        """, (
            'Python Fundamentals',
            'Basic Python syntax, print statements, and program output.',
            10,
            10,
            'Easy',
            'Hello, World!',
            'Use print("Hello, World!") in Python.',
            'print,TEXT',
            '<xml xmlns="https://developers.google.com/blockly/xml"><block type="text_print" x="20" y="20"><value name="TEXT"><block type="text"><field name="TEXT">Hello, World!</field></block></value></block></xml>'
        ))

        # Keep one saved attempt per student and assessment.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS assessment_attempts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                assessment_id INT NOT NULL,
                student_id INT NOT NULL,
                code_blocks TEXT NOT NULL,
                generated_code TEXT,
                output TEXT,
                score SMALLINT UNSIGNED DEFAULT 0,
                auto_score SMALLINT UNSIGNED DEFAULT 0,
                teacher_score SMALLINT UNSIGNED NULL,
                teacher_feedback TEXT,
                reviewed_by INT NULL,
                reviewed_at DATETIME NULL,
                status ENUM('in_progress', 'submitted') NOT NULL DEFAULT 'in_progress',
                started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                submitted_at DATETIME NULL,
                completed_at DATETIME NULL,
                FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                UNIQUE KEY uq_student_assessment_attempt (assessment_id, student_id)
            )
        """)

        attempt_columns = {
            'generated_code': 'TEXT NULL',
            'auto_score': 'SMALLINT UNSIGNED NOT NULL DEFAULT 0',
            'teacher_score': 'SMALLINT UNSIGNED NULL',
            'teacher_feedback': 'TEXT NULL',
            'reviewed_by': 'INT NULL',
            'reviewed_at': 'DATETIME NULL',
            'completed_at': 'DATETIME NULL',
        }
        for column_name, column_definition in attempt_columns.items():
            try:
                cursor.execute(f"ALTER TABLE assessment_attempts ADD COLUMN {column_name} {column_definition}")
            except mysql.connector.Error as alter_error:
                if getattr(alter_error, 'errno', None) != 1060:
                    raise
        
        # Remove the retired lessons table from databases created by older versions.
        cursor.execute("DROP TABLE IF EXISTS lessons")
        
        # CREATE ADMIN/TEACHER ACCOUNT
        cursor.execute("SELECT id FROM teachers WHERE username = 'admin'")
        if not cursor.fetchone():
            admin_password = hash_password("admin123")
            cursor.execute("""
                INSERT INTO teachers (username, password, full_name, email, created_at) 
                VALUES (%s, %s, %s, %s, %s)
            """, ("admin", admin_password, "System Administrator", "admin@blocklearn.edu.ph", datetime.now()))
            print("✅ Admin account created: username='admin', password='admin123'")
        else:
            print("ℹ️ Admin account already exists")

        cursor.execute("SELECT id, username, password FROM teachers WHERE LOWER(username) = 'teacher1'")
        teacher1_row = cursor.fetchone()
        if not teacher1_row:
            teacher1_password = hash_password("Teacher123@")
            cursor.execute("""
                INSERT INTO teachers (username, password, full_name, email, created_at) 
                VALUES (%s, %s, %s, %s, %s)
            """, ("teacher1", teacher1_password, "Teacher One", "teacher1@blocklearn.edu.ph", datetime.now()))
            print("✅ Teacher account created: username='teacher1'")
        else:
            teacher1_password = hash_password("Teacher123@")
            if teacher1_row['username'] != 'teacher1':
                cursor.execute("UPDATE teachers SET username = %s WHERE id = %s", ("teacher1", teacher1_row['id']))
                print("ℹ️ Normalized existing teacher1 username to lowercase")
            if teacher1_row['password'] != teacher1_password:
                cursor.execute("UPDATE teachers SET password = %s WHERE id = %s", (teacher1_password, teacher1_row['id']))
                print("ℹ️ Updated teacher1 password to the provided default")
            print("ℹ️ Teacher1 account already exists")
        
        initialize_staff_code_hashes(cursor)
        conn.commit()
        print("✅ Database initialized successfully!")
        
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        traceback.print_exc()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# Initialize database on startup
init_database()

# ==================== PAGE ROUTES ====================

@app.route('/')
def index():
    if session.get('role') == 'student':
        return redirect('/student_dashboard')
    elif session.get('role') == 'teacher':
        return redirect('/teacher_dashboard')
    elif session.get('role') == 'ict':
        return redirect('/ict_support_dashboard')
    return render_template('public/homepage.html')

@app.route('/about')
def about():
    return render_template('public/about.html')

@app.route('/registeracc')
def registeracc():
    return render_template('auth/register.html')

@app.route('/forgot-password', methods=['GET'])
def forgot_password_page():
    return render_template('auth/forgot.password.html')

@app.route('/reset-password', methods=['GET'])
def reset_password_page():
    return render_template('auth/Reset_Password.html')

# ===== STUDENT ROUTES =====
@app.route('/student_dashboard')
def student_dashboard():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('student/student_dashboard.html', 
                          lrn=session.get('lrn'),
                          grade_level=session.get('grade_level'),
                          username=session.get('username'),
                          full_name=session.get('full_name'))

@app.route('/student_modules')
def student_modules():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('modules_activities/ass&act_library.html',
                          username=session.get('username'),
                          full_name=session.get('full_name'),
                          library_mode='modules')

@app.route('/student_modules/cpp')
def student_modules_cpp():
    if session.get('role') != 'student':
        return redirect('/')
    return redirect('/student_modules/cpp/1')

@app.route('/student_modules/java')
def student_modules_java():
    if session.get('role') != 'student':
        return redirect('/')
    return redirect('/student_modules/java/1')

@app.route('/student_modules/<language>/<int:module_number>')
def student_module(language, module_number):
    if session.get('role') != 'student':
        return redirect('/')

    module_templates = {
        ('python', 1): 'modules_activities/modules_assessments/python_01_bascis.html',
        ('python', 2): 'modules_activities/modules_assessments/python_02_loops.html',
        ('php', 1): 'modules_activities/php_modules_01_variables.html',
        ('php', 2): 'modules_activities/php_modules_02_condition.html',
        ('javascript', 1): 'modules_activities/javascript_01_variables.html',
        ('javascript', 2): 'modules_activities/javascript_02_functions.html',
        ('cpp', 1): 'modules_activities/cpp_module_01_basics.html',
        ('cpp', 2): 'modules_activities/cpp_module_02_loops.html',
        ('java', 1): 'modules_activities/modules_assessments/java01_basics.html',
        ('java', 2): 'modules_activities/modules_assessments/java_02_loops.html',
    }
    template = module_templates.get((language.lower(), module_number))
    if not template:
        return redirect('/student_modules')

    return render_template(template,
                          username=session.get('username'),
                          grade_level=session.get('grade_level'),
                          full_name=session.get('full_name'))

@app.route('/student_playground')
def student_playground():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('public/student_playground.html',
                          username=session.get('username'),
                          grade_level=session.get('grade_level'),
                          full_name=session.get('full_name'))

@app.route('/student_playground_python')
def student_playground_python():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('playground/python_playground.html',
                          username=session.get('username'),
                          grade_level=session.get('grade_level'),
                          full_name=session.get('full_name'))

@app.route('/playground_javascript')
@app.route('/student_playground_javascript')
def student_playground_javascript():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('playground/javascript_playground.html',
                          username=session.get('username'),
                          grade_level=session.get('grade_level'),
                          full_name=session.get('full_name'))

@app.route('/student_playground_html')
def student_playground_html():
    if session.get('role') != 'student':
        return redirect('/')
    return redirect('/student_playground_python')

@app.route('/playground_php')
@app.route('/student_playground_php')
def student_playground_php():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('playground/php_playground.html',
                          username=session.get('username'),
                          grade_level=session.get('grade_level'),
                          full_name=session.get('full_name'))

@app.route('/playground_cpp')
@app.route('/student_playground_cpp')
def student_playground_cpp():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('playground/cpp_playground.html',
                          username=session.get('username'),
                          grade_level=session.get('grade_level'),
                          full_name=session.get('full_name'))

@app.route('/student_activities')
def student_activities():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('activities/php_activities.html',
                          username=session.get('username'),
                          lrn=session.get('lrn'))

@app.route('/student_activities_php')
def student_activities_php():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('activities/php_activities.html',
                          username=session.get('username'),
                          lrn=session.get('lrn'))

@app.route('/student_activities_javascript')
def student_activities_javascript():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('public/student_activities_javascript.html', 
                          username=session.get('username'),
                          lrn=session.get('lrn'))

@app.route('/student_activities_java')
def student_activities_java():
    if session.get('role') != 'student':
        return redirect('/')
    return redirect('/student_modules/java/1')

@app.route('/student_activities_html')
def student_activities_html():
    if session.get('role') != 'student':
        return redirect('/')
    return redirect('/student_activities_cpp')

@app.route('/student_activities_cpp')
def student_activities_cpp():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('public/student_activities_cpp.html',
                          username=session.get('username'),
                          lrn=session.get('lrn'))

@app.route('/student_progress')
def student_progress():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('student/student_progress.html', 
                          username=session.get('username'))

@app.route('/student_profile')
def student_profile():
    if session.get('role') != 'student':
        return redirect('/')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT id, username, full_name, lrn, grade_level, email,
                   DATE_FORMAT(created_at, '%M %d, %Y') as created_at,
                   (SELECT COUNT(*) FROM assessment_attempts
                    WHERE student_id = students.id AND status = 'submitted') as total_activities,
                   (SELECT IFNULL(AVG(score), 0) FROM assessment_attempts
                    WHERE student_id = students.id AND status = 'submitted') as average_score
            FROM students 
            WHERE id = %s
        """, (session.get('user_id'),))
        student = cursor.fetchone()
        
        return render_template('student/student_profile.html', 
                                  student=student,
                                  lrn=session.get('lrn'),
                                  username=session.get('username'),
                                  full_name=session.get('full_name'))
    finally:
        cursor.close()
        conn.close()

@app.route('/student_settings')
def student_settings():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('student/student_settings.html', 
                          username=session.get('username'))

@app.route('/student_help')
def student_help():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('student/HELP_FAQ.html', 
                          username=session.get('username'),
                          full_name=session.get('full_name'))

@app.route('/assessments')
def assessments_overview():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('modules_activities/ass&act_library.html',
                          username=session.get('username'),
                          full_name=session.get('full_name'),
                          library_mode='assessment')

@app.route('/assessment')
def assessment_overview_alias():
    return redirect('/assessments')

@app.route('/module_assessments')
def module_assessments():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('modules_activities/ass&act_library.html',
                          username=session.get('username'),
                          full_name=session.get('full_name'),
                          library_mode='assessment')

@app.route('/assessments_python')
def assessments_python():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('assessments/python_assessments.html',
                          username=session.get('username'),
                          full_name=session.get('full_name'))

@app.route('/assessments_java')
def assessments_java():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('assessments/java_assessments.html',
                          username=session.get('username'),
                          full_name=session.get('full_name'))

@app.route('/get_assessment_statuses')
def get_assessment_statuses():
    if session.get('role') != 'student':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    language = request.args.get('language', 'java')
    if language not in ('python', 'java', 'cpp', 'javascript', 'php'):
        return jsonify({'success': False, 'message': 'Invalid language'}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT a.assessment_number, aa.status, aa.score
            FROM assessments a
            LEFT JOIN assessment_attempts aa
                ON aa.assessment_id = a.id AND aa.student_id = %s
            WHERE a.language = %s
            ORDER BY a.assessment_number
        """, (session['user_id'], language))
        rows = cursor.fetchall()
        statuses = []
        for row in rows:
            attempt_status = row['status']
            score = row['score']
            if attempt_status == 'submitted':
                status = 'passed' if (score or 0) >= 75 else 'done'
            elif attempt_status == 'in_progress':
                status = 'in_progress'
            else:
                status = 'not_started'
            statuses.append({
                'assessment_number': row['assessment_number'],
                'status': status,
                'score': score
            })
        submitted_scores = [
            row['score'] for row in rows
            if row['status'] == 'submitted' and row['score'] is not None
        ]
        return jsonify({
            'success': True,
            'statuses': statuses,
            'total': len(statuses),
            'completed': sum(1 for item in statuses if item['status'] in ('passed', 'done')),
            'in_progress': sum(1 for item in statuses if item['status'] == 'in_progress'),
            'average_score': round(sum(submitted_scores) / len(submitted_scores)) if submitted_scores else 0
        })
    except Exception as e:
        print(f"Get assessment statuses error: {e}")
        return jsonify({'success': False, 'message': 'Failed to load assessment statuses'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/assessment_python_activity')
def assessment_python_activity():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('assessments/playground_python.html',
                          username=session.get('username'),
                          full_name=session.get('full_name'),
                          assessment_id=request.args.get('id', '1'))

@app.route('/assessment_java_activity')
def assessment_java_activity():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('assessments/playground_java.html',
                          username=session.get('username'),
                          full_name=session.get('full_name'),
                          assessment_id=request.args.get('id', '1'))

@app.route('/notifications')
def notifications_page():
    role = session.get('role')
    templates = {
        'student': 'student/student_notifications.html',
        'teacher': 'teacher/teacher_notifications.html',
        'ict': 'ict-support/ict_notifications.html',
    }
    if role not in templates:
        return redirect('/')
    return render_template(templates[role])

@app.route('/get_notifications')
def get_notifications():
    role = session.get('role')
    if role not in ('student', 'teacher', 'ict'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    notifications = get_notifications_for_user(session.get('user_id'), role)
    return jsonify({
        'success': True,
        'notifications': notifications,
        'unread_count': sum(1 for item in notifications if not item['is_read']),
    })

@app.route('/mark_notifications_read', methods=['POST'])
def mark_notifications_read():
    role = session.get('role')
    if role not in ('student', 'teacher', 'ict'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    return jsonify({'success': mark_all_notifications_read(session.get('user_id'), role)})

@app.route('/submit_assessment', methods=['POST'])
def submit_assessment():
    if session.get('role') != 'student':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    data = request.get_json(silent=True) or {}
    language = data.get('language')
    assessment_number = data.get('assessment_number')
    code_blocks = data.get('code_blocks')
    generated_code = str(data.get('generated_code', ''))
    output = str(data.get('output', '')).strip()

    if language not in ('python', 'java', 'cpp', 'javascript', 'php') or not isinstance(assessment_number, int) or not code_blocks:
        return jsonify({'success': False, 'message': 'Invalid assessment submission'}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, expected_output, points
            FROM assessments
            WHERE language = %s AND assessment_number = %s
        """, (language, assessment_number))
        assessment = cursor.fetchone()
        if not assessment:
            return jsonify({'success': False, 'message': 'Assessment not found'}), 404

        expected_output = assessment['expected_output'].strip()
        earned_points = 10 if output == expected_output else (5 if output else 0)
        score = earned_points * 10
        submitted_at = datetime.now()
        cursor.execute("""
            INSERT INTO assessment_attempts
                (assessment_id, student_id, code_blocks, generated_code, output, score,
                 auto_score, teacher_score, status, submitted_at, completed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NULL, 'submitted', %s, %s)
            ON DUPLICATE KEY UPDATE
                code_blocks = VALUES(code_blocks),
                generated_code = VALUES(generated_code),
                output = VALUES(output),
                score = VALUES(score),
                auto_score = VALUES(auto_score),
                teacher_score = NULL,
                teacher_feedback = NULL,
                reviewed_by = NULL,
                reviewed_at = NULL,
                status = 'submitted',
                submitted_at = VALUES(submitted_at),
                completed_at = VALUES(completed_at)
        """, (assessment['id'], session['user_id'], code_blocks, generated_code, output,
               score, earned_points, submitted_at, submitted_at))
        conn.commit()

        notify_new_assessment_submission(
            session.get('full_name') or session.get('username') or 'Student',
            f'{language.title()} Assessment #{assessment_number}',
            assessment['id'],
        )

        return jsonify({
            'success': True,
            'score': score,
            'points': earned_points,
            'max_points': 10,
            'status': 'completed',
            'activity_number': assessment_number,
            'expected_output': expected_output,
            'message': 'Activity completed successfully' if earned_points == 10 else ('Activity submitted for review' if earned_points == 5 else 'Activity submitted with no score')
        })
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Submit assessment error: {e}")
        return jsonify({'success': False, 'message': 'Failed to save assessment score'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/save_assessment_blocks', methods=['POST'])
def save_assessment_blocks():
    if session.get('role') != 'student':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    data = request.get_json(silent=True) or {}
    language = data.get('language')
    assessment_number = data.get('assessment_number')
    code_blocks = data.get('code_blocks')

    if language not in ('python', 'java', 'cpp', 'javascript', 'php') or not isinstance(assessment_number, int) or not code_blocks:
        return jsonify({'success': False, 'message': 'Invalid workspace data'}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id FROM assessments
            WHERE language = %s AND assessment_number = %s
        """, (language, assessment_number))
        assessment = cursor.fetchone()
        if not assessment:
            return jsonify({'success': False, 'message': 'Assessment not found'}), 404

        cursor.execute("""
            INSERT INTO assessment_attempts
                (assessment_id, student_id, code_blocks, status)
            VALUES (%s, %s, %s, 'in_progress')
            ON DUPLICATE KEY UPDATE
                code_blocks = VALUES(code_blocks)
        """, (assessment['id'], session['user_id'], code_blocks))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Save assessment blocks error: {e}")
        return jsonify({'success': False, 'message': 'Failed to save workspace'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/assessments/activity')
def assessment_activity():
    if session.get('role') != 'student':
        return redirect('/')
    return redirect('/assessments_python')

# ===== TEACHER ROUTES =====
@app.route('/teacher_dashboard')
def teacher_dashboard():
    if session.get('role') != 'teacher':
        return redirect('/')
    return render_template('teacher/teacher_home_dashboard.html', 
                          username=session.get('username'),
                          full_name=session.get('full_name'))

@app.route('/get_teacher_dashboard_data')
def get_teacher_dashboard_data():
    if session.get('role') != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT COUNT(*) AS total_students FROM students")
        total_students = cursor.fetchone()['total_students']
        cursor.execute("""
            SELECT COUNT(*) AS total_submissions, IFNULL(ROUND(AVG(score), 0), 0) AS average_score
            FROM assessment_attempts
            WHERE status = 'submitted'
        """)
        stats = cursor.fetchone()
        cursor.execute("""
            SELECT s.full_name AS student_name, s.lrn, d.title, d.language,
                   a.score, DATE_FORMAT(a.submitted_at, '%Y-%m-%d %H:%i') AS submitted_at
            FROM assessment_attempts a
            JOIN assessments d ON d.id = a.assessment_id
            JOIN students s ON s.id = a.student_id
            WHERE a.status = 'submitted'
            ORDER BY a.submitted_at DESC
            LIMIT 5
        """)
        recent = cursor.fetchall()
        return jsonify({
            'success': True,
            'total_students': total_students,
            'average_score': stats['average_score'] or 0,
            'total_activities': stats['total_submissions'] or 0,
            'pending_submissions': 0,
            'recent_submissions': recent
        })
    except Exception as e:
        print(f"Get teacher dashboard data error: {e}")
        return jsonify({'success': False, 'message': 'Failed to retrieve dashboard data'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/teacher_students')
def teacher_students():
    if session.get('role') != 'teacher':
        return redirect('/')
    return render_template('teacher/teacher_students_list.html', 
                          username=session.get('username'),
                          full_name=session.get('full_name'))

@app.route('/teacher_score_results')
def teacher_score_results():
    if session.get('role') != 'teacher':
        return redirect('/')
    return render_template('teacher/teacher_score_results.html', 
                          username=session.get('username'))

@app.route('/teacher_scores')
def teacher_scores():
    if session.get('role') != 'teacher':
        return redirect('/')
    return redirect('/teacher_score_results')

@app.route('/teacher_passed_assessments')
def teacher_passed_assessments():
    if session.get('role') != 'teacher':
        return redirect('/')
    return redirect('/assessments_result')

@app.route('/assessments_result')
def assessments_result():
    if session.get('role') != 'teacher':
        return redirect('/')
    return render_template('teacher/assessments_result.html',
                          username=session.get('username'),
                          full_name=session.get('full_name'))

@app.route('/assessment_results')
@app.route('/teacher_assessments')
def assessment_results_alias():
    return redirect('/assessments_result')

@app.route('/teacher_reports')
def teacher_reports():
    if session.get('role') != 'teacher':
        return redirect('/')
    return redirect('/teacher_reports_analytics')

# ===== NEW ROUTE: Combined Reports & Analytics =====
@app.route('/teacher_reports_analytics')
def teacher_reports_analytics():
    """Combined Reports and Analytics page"""
    if session.get('role') != 'teacher':
        return redirect('/')
    return render_template('analytics/reports_analytics.html', 
                          username=session.get('username'),
                          full_name=session.get('full_name'))

@app.route('/teacher_profile')
def teacher_profile():
    if session.get('role') != 'teacher':
        return redirect('/')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT id, username, full_name, email,
                   DATE_FORMAT(created_at, '%M %d, %Y') as created_at
            FROM teachers 
            WHERE id = %s
        """, (session.get('user_id'),))
        teacher = cursor.fetchone()
        
        cursor.execute("SELECT COUNT(*) as total FROM students")
        total_students = cursor.fetchone()['total']
        
        cursor.execute("""
            SELECT COUNT(*) as total, IFNULL(AVG(score), 0) as avg_score
            FROM assessment_attempts
            WHERE status = 'submitted'
        """)
        stats = cursor.fetchone()
        total_activities = stats['total'] if stats['total'] else 0
        average_score = round(stats['avg_score']) if stats['avg_score'] else 0
        
        return render_template('teacher/teacher_profile.html', 
                              teacher=teacher,
                              total_students=total_students,
                              total_activities=total_activities,
                              average_score=average_score,
                              username=session.get('username'))
    finally:
        cursor.close()
        conn.close()

@app.route('/teacher_settings')
def teacher_settings():
    if session.get('role') != 'teacher':
        return redirect('/')
    return render_template('teacher/teacher_settings.html', 
                          username=session.get('username'))

@app.route('/teacher_tickets')
def teacher_tickets():
    if session.get('role') not in ['teacher', 'student']:
        return redirect('/')
    return render_template('ict-support/tickets.html', 
                          username=session.get('username'),
                          full_name=session.get('full_name'))

@app.route('/student_tickets')
def student_tickets():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('student/tickets.html',
                          username=session.get('username'),
                          full_name=session.get('full_name'))

# ==================== ICT SUPPORT ROUTES ====================

@app.route('/ict_support_dashboard')
def ict_support_dashboard():
    if session.get('role') not in ['teacher', 'ict']:
        return redirect('/')
    return render_template('ict-support/ict-dasboard.html',
                          username=session.get('username'),
                          full_name=session.get('full_name'),
                          role=session.get('role'))

@app.route('/ict_support_reports')
def ict_support_reports():
    if session.get('role') not in ['teacher', 'ict']:
        return redirect('/')
    return render_template('ict-support/reports.html',
                          username=session.get('username'),
                          full_name=session.get('full_name'))

@app.route('/ict_support_settings')
def ict_support_settings():
    if session.get('role') not in ['teacher', 'ict']:
        return redirect('/')
    return render_template('ict-support/settings.html',
                          username=session.get('username'),
                          full_name=session.get('full_name'))

@app.route('/ict_support_students')
def ict_support_students():
    if session.get('role') not in ['teacher', 'ict']:
        return redirect('/')
    return render_template('ict-support/students.html',
                          username=session.get('username'),
                          full_name=session.get('full_name'))

@app.route('/ict_support_tickets')
@app.route('/ict_tickets')
@app.route('/ict-support/tickets')
def ict_support_tickets():
    if session.get('role') not in ['teacher', 'ict']:
        return redirect('/')
    return render_template('ict-support/tickets.html',
                          username=session.get('username'),
                          full_name=session.get('full_name'))

# ==================== PROFILE DATA API ROUTES ====================

@app.route('/student_profile_data')
def student_profile_data():
    if session.get('role') != 'student':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
                 SELECT username, lrn, full_name, grade_level, email,
                   DATE_FORMAT(created_at, '%M %d, %Y') as created_at
            FROM students WHERE id = %s
        """, (session.get('user_id'),))
        student = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if student:
            return jsonify({'success': True, **student})
        return jsonify({'success': False, 'message': 'Student not found'})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/teacher_profile_data')
def teacher_profile_data():
    if session.get('role') != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT username, full_name, email,
                   DATE_FORMAT(created_at, '%M %d, %Y') as created_at
            FROM teachers WHERE id = %s
        """, (session.get('user_id'),))
        teacher = cursor.fetchone()
        
        cursor.execute("SELECT COUNT(*) as total_students FROM students")
        total_students = cursor.fetchone()['total_students']
        
        cursor.execute("""
            SELECT COUNT(*) as total_activities, IFNULL(ROUND(AVG(score), 0), 0) as avg_score
            FROM assessment_attempts
            WHERE status = 'submitted'
        """)
        stats = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'username': teacher['username'] if teacher else '',
            'full_name': teacher['full_name'] if teacher else '',
            'email': teacher['email'] if teacher else 'admin@blocklearn.edu.ph',
            'created_at': teacher['created_at'] if teacher else '',
            'total_students': total_students,
            'total_activities': stats['total_activities'] or 0,
            'average_score': stats['avg_score'] or 0
        })
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/get_ict_dashboard_data')
def get_ict_dashboard_data():
    if session.get('role') not in ['teacher', 'ict']:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT COUNT(*) AS total_students FROM students")
        total_students = cursor.fetchone()['total_students'] or 0

        cursor.execute("""
            SELECT COUNT(*) AS registered_today
            FROM students
            WHERE DATE(created_at) = CURDATE()
        """)
        registered_today = cursor.fetchone()['registered_today'] or 0

        cursor.execute("""
            SELECT id, username, full_name, lrn, created_at
            FROM students
            ORDER BY created_at DESC, id DESC
            LIMIT 5
        """)
        students = cursor.fetchall()

        cursor.execute("SELECT COUNT(*) AS total_tickets FROM ict_tickets")
        total_tickets = cursor.fetchone()['total_tickets'] or 0
        cursor.execute("""
            SELECT COUNT(*) AS pending_tickets
            FROM ict_tickets
            WHERE status IN ('pending', 'in_progress')
        """)
        pending_tickets = cursor.fetchone()['pending_tickets'] or 0

        return jsonify({
            'success': True,
            'total_students': total_students,
            'registered_today': registered_today,
            'total_tickets': total_tickets,
            'pending_tickets': pending_tickets,
            'students': students
        })
    except Exception as e:
        print(f"Error getting ICT dashboard data: {e}")
        return jsonify({'success': False, 'message': 'Failed to retrieve dashboard data'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# ==================== AUTHENTICATION ROUTES ====================

@app.route('/forgot-password', methods=['POST'])
def forgot_password():
    data = request.get_json(silent=True) or {}
    identifier = str(data.get('identifier', '')).strip()
    if not identifier:
        return jsonify({'success': False, 'message': 'LRN or username is required'}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id
            FROM students
            WHERE lrn = %s OR LOWER(username) = LOWER(%s)
            LIMIT 1
        """, (identifier, identifier))
        student = cursor.fetchone()
        if not student:
            return jsonify({'success': False, 'message': 'No student account matches that LRN or username'}), 404

        token = secrets.token_urlsafe(48)
        expires = datetime.now() + timedelta(minutes=30)
        cursor.execute("""
            UPDATE students
            SET reset_token = %s, reset_token_expires = %s
            WHERE id = %s
        """, (token, expires, student['id']))
        conn.commit()

        reset_url = f"{request.host_url.rstrip('/')}/reset-password?token={token}"
        return jsonify({
            'success': True,
            'message': 'Reset link created. Use it within 30 minutes.',
            'reset_url': reset_url,
        })
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Forgot password error: {e}")
        return jsonify({'success': False, 'message': 'Unable to create a reset link'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/reset-password', methods=['POST'])
def reset_password():
    data = request.get_json(silent=True) or {}
    token = str(data.get('token', '')).strip()
    password = str(data.get('password', ''))
    confirm_password = str(data.get('confirm_password', ''))

    if not token or len(password) < 6 or password != confirm_password:
        return jsonify({'success': False, 'message': 'Provide a valid token and matching password of at least 6 characters'}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id
            FROM students
            WHERE reset_token = %s AND reset_token_expires > NOW()
            LIMIT 1
        """, (token,))
        student = cursor.fetchone()
        if not student:
            return jsonify({'success': False, 'message': 'This reset link is invalid or expired'}), 400

        cursor.execute("""
            UPDATE students
            SET password = %s, reset_token = NULL, reset_token_expires = NULL
            WHERE id = %s
        """, (hash_password(password), student['id']))
        conn.commit()
        return jsonify({'success': True, 'message': 'Password reset successfully. You can now log in.'})
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Reset password error: {e}")
        return jsonify({'success': False, 'message': 'Unable to reset password'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/change_password', methods=['POST'])
def change_password():
    """Change the password for the currently signed-in ICT support user."""
    if session.get('role') != 'ict':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    data = request.get_json(silent=True) or {}
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    if not current_password or not new_password:
        return jsonify({'success': False, 'message': 'Current and new passwords are required'}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT password FROM ict_support WHERE id = %s AND status = 'active'",
            (session.get('user_id'),),
        )
        user = cursor.fetchone()
        if not user or hash_password(current_password) != user['password']:
            return jsonify({'success': False, 'message': 'Current password is incorrect'}), 400

        cursor.execute(
            "UPDATE ict_support SET password = %s WHERE id = %s AND status = 'active'",
            (hash_password(new_password), session.get('user_id')),
        )
        conn.commit()
        return jsonify({'success': True, 'message': 'Password updated successfully!'})
    except Exception as exc:
        if conn:
            conn.rollback()
        print(f"ICT password update error: {exc}")
        return jsonify({'success': False, 'message': 'Unable to update password'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/login', methods=['POST'])
def login_post():
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'})

        role = data.get('role')
        password = data.get('password')

        if not password or not role:
            return jsonify({'success': False, 'message': 'Missing required fields'})

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        try:
            if role == 'student':
                lrn = data.get('lrn')
                if not lrn:
                    return jsonify({'success': False, 'message': 'LRN is required for students'})
                
                if not validate_lrn(lrn):
                    return jsonify({'success': False, 'message': 'LRN must be exactly 12 digits'})
                
                cursor.execute("SELECT * FROM students WHERE lrn = %s OR username = %s", (lrn, lrn))
                user = cursor.fetchone()
                
                if user and hash_password(password) == user['password']:
                    session['user_id'] = user['id']
                    session['username'] = user['username']
                    session['full_name'] = user.get('full_name', user['username'])
                    session['lrn'] = user['lrn']
                    session['grade_level'] = user['grade_level']
                    session['role'] = 'student'
                    return jsonify({'success': True, 'role': 'student', 'redirect': '/student_dashboard'})
                else:
                    return jsonify({'success': False, 'message': 'Invalid LRN or password'})
                    
            elif role == 'ict_support':
                username = data.get('username') or data.get('employee_id')
                validation_code = data.get('validation_code')
                if not username:
                    return jsonify({'success': False, 'message': 'ICT support username is required'})
                if not validation_code:
                    return jsonify({'success': False, 'message': 'ICT support validation code is required'})

                cursor.execute("""
                    SELECT * FROM ict_support
                    WHERE LOWER(username) = LOWER(%s) AND status = 'active'
                """, (username,))
                user = cursor.fetchone()

                if user and hash_password(password) == user['password'] and verify_staff_code(user.get('staff_code_hash'), validation_code):
                    cursor.execute("UPDATE ict_support SET last_login = CURRENT_TIMESTAMP WHERE id = %s", (user['id'],))
                    conn.commit()
                    session['user_id'] = user['id']
                    session['username'] = user['username']
                    session['full_name'] = user['full_name']
                    session['role'] = 'ict'
                    return jsonify({'success': True, 'role': 'ict_support', 'redirect': '/ict_support_dashboard'})
                else:
                    return jsonify({'success': False, 'message': 'Invalid ICT support username or password'})

            else:  # teacher
                username = data.get('username')
                validation_code = data.get('validation_code')
                if not username:
                    return jsonify({'success': False, 'message': 'Username is required for teachers'})
                if not validation_code:
                    return jsonify({'success': False, 'message': 'Teacher validation code is required'})
                    
                cursor.execute("SELECT * FROM teachers WHERE LOWER(username) = LOWER(%s)", (username,))
                user = cursor.fetchone()
                
                if user and hash_password(password) == user['password'] and verify_staff_code(user.get('staff_code_hash'), validation_code):
                    session['user_id'] = user['id']
                    session['username'] = user['username']
                    session['full_name'] = user.get('full_name', user['username'])
                    session['role'] = 'teacher'
                    return jsonify({'success': True, 'role': 'teacher', 'redirect': '/teacher_dashboard'})
                else:
                    return jsonify({'success': False, 'message': 'Invalid username or password'})

        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({'success': False, 'message': 'Login failed. Please try again.'})

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ==================== CREATE ACCOUNT ROUTE ====================

@app.route('/create_account', methods=['POST'])
def create_account():
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'})

        lrn = data.get('lrn')
        full_name = data.get('full_name', '')
        password = data.get('password')
        grade_level = data.get('grade_level')
        email = data.get('email')

        if not lrn:
            return jsonify({'success': False, 'message': 'LRN is required'})
        if not full_name or not str(full_name).strip():
            return jsonify({'success': False, 'message': 'Full name is required'})
        if not password:
            return jsonify({'success': False, 'message': 'Password is required'})
        if not grade_level:
            return jsonify({'success': False, 'message': 'Grade level is required'})

        if str(grade_level).strip().lower() != 'grade 11':
            return jsonify({'success': False, 'message': 'Registration is open only for Grade 11 students.'})

        if not validate_lrn(lrn):
            return jsonify({'success': False, 'message': 'LRN must be exactly 12 digits'})

        if len(password) < 6:
            return jsonify({'success': False, 'message': 'Password must be at least 6 characters'})

        if email and not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
            return jsonify({'success': False, 'message': 'Please enter a valid email address'})

        hashed_password = hash_password(password)
        username = str(lrn)

        if not email:
            email = f"{lrn}@student.blocklearn.edu.ph"

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT id FROM students WHERE lrn = %s", (lrn,))
            if cursor.fetchone():
                return jsonify({'success': False, 'message': 'LRN already exists. Please use a different LRN.'})

            cursor.execute("SELECT id FROM students WHERE username = %s", (username,))
            if cursor.fetchone():
                return jsonify({'success': False, 'message': 'Username already exists.'})

            cursor.execute("""
                INSERT INTO students (username, full_name, password, lrn, grade_level, email, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (username, full_name, hashed_password, lrn, grade_level, email, datetime.now()))
            
            conn.commit()
            print(f"✅ [SUCCESS] Account created for LRN: {lrn} - Name: {full_name}")
            return jsonify({'success': True, 'message': 'Account created successfully! You can now login.'})
            
        except mysql.connector.IntegrityError as err:
            if err.errno == 1062:
                return jsonify({'success': False, 'message': 'LRN or username already exists'})
            else:
                print(f"❌ [ERROR] IntegrityError: {err}")
                return jsonify({'success': False, 'message': f'Database error: {str(err)}'})
        except mysql.connector.Error as err:
            print(f"❌ [ERROR] MySQL Error: {err}")
            if "Unknown column 'email'" in str(err):
                cursor.execute("""
                    INSERT INTO students (username, full_name, password, lrn, grade_level, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (username, full_name, hashed_password, lrn, grade_level, datetime.now()))
                conn.commit()
                return jsonify({'success': True, 'message': 'Account created successfully!'})
            return jsonify({'success': False, 'message': f'Database error: {str(err)}'})
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        print(f"❌ [ERROR] Create account error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Account creation failed: {str(e)}'})

# ==================== STUDENT API ROUTES ====================

@app.route('/save_activity', methods=['POST'])
def save_activity():
    if session.get('role') != 'student':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'})
        
        student_id = session.get('user_id')
        activity_name = data.get('activity_name')
        score = data.get('score')
        code_blocks = data.get('code_blocks')
        language = data.get('language')
        
        if not all([student_id, activity_name, score is not None]) or language not in ('php', 'javascript', 'cpp'):
            return jsonify({'success': False, 'message': 'Invalid activity completion data'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT id FROM activities 
                WHERE student_id = %s AND activity_name = %s
            """, (student_id, activity_name))
            
            existing = cursor.fetchone()
            
            if existing:
                cursor.execute("""
                    UPDATE activities 
                    SET score = %s, code_blocks = %s, language = %s, completed_at = %s
                    WHERE student_id = %s AND activity_name = %s
                """, (score, code_blocks, language, datetime.now(), student_id, activity_name))
            else:
                cursor.execute("""
                    INSERT INTO activities (student_id, activity_name, score, code_blocks, language, completed_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (student_id, activity_name, score, code_blocks, language, datetime.now()))
            
            conn.commit()
            return jsonify({'success': True, 'message': 'Activity saved successfully!'})
        finally:
            cursor.close()
            conn.close()
    except Exception as e:
        print(f"Save activity error: {e}")
        return jsonify({'success': False, 'message': f'Failed to save activity: {str(e)}'})

@app.route('/get_progress')
def get_progress():
    if session.get('role') != 'student':
        return jsonify({'success': False, 'message': 'Unauthorized'})

    try:
        student_id = session.get('user_id')
        if not student_id:
            return jsonify({'success': False, 'message': 'User not authenticated'})

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT COUNT(DISTINCT aa.assessment_id) AS completed
                FROM assessment_attempts aa
                JOIN assessments a ON a.id = aa.assessment_id
                WHERE aa.student_id = %s
                  AND aa.status = 'submitted'
                  AND a.language IN ('python', 'java')
            """, (student_id,))
            assessment_result = cursor.fetchone()

            cursor.execute("""
                SELECT a.language, COUNT(DISTINCT aa.assessment_id) AS completed
                FROM assessment_attempts aa
                JOIN assessments a ON a.id = aa.assessment_id
                WHERE aa.student_id = %s
                  AND aa.status = 'submitted'
                  AND a.language IN ('php', 'javascript', 'cpp')
                GROUP BY a.language
            """, (student_id,))
            submitted_activity_stats = {
                row['language']: min(row['completed'], 5)
                for row in cursor.fetchall()
            }

            cursor.execute("""
                SELECT language, COUNT(DISTINCT activity_name) AS completed
                FROM activities
                WHERE student_id = %s
                  AND language IN ('php', 'javascript', 'cpp')
                GROUP BY language
            """, (student_id,))
            saved_activity_stats = {
                row['language']: min(row['completed'], 5)
                for row in cursor.fetchall()
            }

            completed_assessments = min(assessment_result['completed'] if assessment_result else 0, 10)
            completed_activities = sum(
                max(
                    submitted_activity_stats.get(language, 0),
                    saved_activity_stats.get(language, 0),
                )
                for language in ('php', 'javascript', 'cpp')
            )
            total_completed = completed_assessments + completed_activities
            progress = round(total_completed / 25 * 100)
            return jsonify({
                'success': True,
                'progress': progress,
                'completed': total_completed,
                'completed_assessments': completed_assessments,
                'completed_activities': completed_activities,
                'total': 25,
                'total_assessments': 10,
                'total_activities': 15,
            })
        finally:
            cursor.close()
            conn.close()
    except Exception as e:
        print(f"Get progress error: {e}")
        return jsonify({'success': False, 'message': 'Failed to retrieve progress'})

@app.route('/get_student_stats')
def get_student_stats():
    if session.get('role') != 'student':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        student_id = session.get('user_id')
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT a.title AS activity_name, aa.score,
                   DATE_FORMAT(aa.submitted_at, '%Y-%m-%d %H:%i') as completed_at
            FROM assessment_attempts aa
            JOIN assessments a ON a.id = aa.assessment_id
            WHERE aa.student_id = %s AND aa.status = 'submitted'
            ORDER BY aa.submitted_at DESC
            LIMIT 5
        """, (student_id,))
        recent = cursor.fetchall()
        
        cursor.execute("""
            SELECT IFNULL(AVG(score), 0) as avg_score, COUNT(*) as total
            FROM assessment_attempts
            WHERE student_id = %s AND status = 'submitted'
        """, (student_id,))
        stats = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True, 
            'recent_activities': recent,
            'average_score': round(stats['avg_score']) if stats['avg_score'] else 0,
            'total_activities': stats['total'] or 0
        })
    except Exception as e:
        print(f"Error in get_student_stats: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/update_profile', methods=['POST'])
def update_profile():
    if session.get('role') != 'student':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        data = request.json
        grade_level = data.get('grade_level')
        email = data.get('email')
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        
        user_id = session.get('user_id')
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            if grade_level:
                cursor.execute("UPDATE students SET grade_level = %s WHERE id = %s", (grade_level, user_id))
                session['grade_level'] = grade_level
            
            if email:
                cursor.execute("UPDATE students SET email = %s WHERE id = %s", (email, user_id))
            
            if current_password and new_password:
                cursor.execute("SELECT password FROM students WHERE id = %s", (user_id,))
                user = cursor.fetchone()
                if user and hash_password(current_password) != user['password']:
                    return jsonify({'success': False, 'message': 'Current password is incorrect'})
                
                hashed_new = hash_password(new_password)
                cursor.execute("UPDATE students SET password = %s WHERE id = %s", (hashed_new, user_id))
            
            conn.commit()
            return jsonify({'success': True, 'message': 'Profile updated successfully!'})
            
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        print(f"Update profile error: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/get_activities')
def get_activities():
    if session.get('role') != 'student':
        return jsonify({'success': False})
    
    try:
        student_id = session.get('user_id')
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT activity_name, language, score, completed_at
            FROM activities
            WHERE student_id = %s
        """, (student_id,))
        saved_activity_rows = cursor.fetchall()

        cursor.execute("""
            SELECT a.language, a.assessment_number, a.title, a.points,
                   a.expected_output, aa.status, aa.score, aa.auto_score,
                   aa.teacher_score, COALESCE(aa.completed_at, aa.submitted_at) AS completed_at
            FROM assessment_attempts aa
            JOIN assessments a ON a.id = aa.assessment_id
            WHERE aa.student_id = %s
        """, (student_id,))
        assessment_attempts = cursor.fetchall()
        
        all_activities = [
            {'id': 1, 'name': 'Say Hello!', 'language': 'python', 'difficulty': 'easy'},
            {'id': 2, 'name': 'Print Your Name', 'language': 'python', 'difficulty': 'easy'},
            {'id': 3, 'name': 'Simple Math', 'language': 'python', 'difficulty': 'easy'},
            {'id': 4, 'name': 'If-Else Statement', 'language': 'python', 'difficulty': 'medium'},
            {'id': 5, 'name': 'While Loop', 'language': 'python', 'difficulty': 'medium'},
            {'id': 6, 'name': 'Conditions', 'language': 'python', 'difficulty': 'medium'},
            {'id': 7, 'name': 'Console Log', 'language': 'javascript', 'difficulty': 'easy'},
            {'id': 8, 'name': 'Alert Message', 'language': 'javascript', 'difficulty': 'easy'},
            {'id': 9, 'name': 'Simple Calculation', 'language': 'javascript', 'difficulty': 'medium'},
            {'id': 10, 'name': 'Create Heading', 'language': 'html', 'difficulty': 'easy'},
            {'id': 11, 'name': 'Create Paragraph', 'language': 'html', 'difficulty': 'easy'},
            {'id': 12, 'name': 'Hello, PHP!', 'language': 'php', 'difficulty': 'easy'},
            {'id': 13, 'name': 'Store a Name', 'language': 'php', 'difficulty': 'easy'},
            {'id': 14, 'name': 'Subtract Two Numbers', 'language': 'php', 'difficulty': 'medium'},
            {'id': 15, 'name': 'Greater Than', 'language': 'php', 'difficulty': 'medium'},
            {'id': 16, 'name': 'Repeat a Message Three Times', 'language': 'php', 'difficulty': 'hard'},
            {'id': 17, 'name': 'Hello, JavaScript!', 'language': 'javascript', 'difficulty': 'easy'},
            {'id': 18, 'name': 'Store and Display a Score', 'language': 'javascript', 'difficulty': 'easy'},
            {'id': 19, 'name': 'Add Numbers', 'language': 'javascript', 'difficulty': 'medium'},
            {'id': 20, 'name': 'Greater Than', 'language': 'javascript', 'difficulty': 'medium'},
            {'id': 21, 'name': 'Repeat a Message Five Times', 'language': 'javascript', 'difficulty': 'hard'},
            {'id': 22, 'name': 'Hello, C++!', 'language': 'cpp', 'difficulty': 'easy'},
            {'id': 23, 'name': 'Store an Age', 'language': 'cpp', 'difficulty': 'easy'},
            {'id': 24, 'name': 'Multiply Two Numbers', 'language': 'cpp', 'difficulty': 'medium'},
            {'id': 25, 'name': 'Less Than', 'language': 'cpp', 'difficulty': 'medium'},
            {'id': 26, 'name': 'Display Numbers 1 to 5', 'language': 'cpp', 'difficulty': 'hard'},
        ]
        
        completed_assessments = {
            (attempt['language'], attempt['assessment_number'])
            for attempt in assessment_attempts
            if attempt['status'] == 'submitted'
            and attempt['language'] in ('python', 'java')
        }
        activities_unlocked = len(completed_assessments) >= 10
        saved_activities = {
            (row['language'], row['activity_name']): row
            for row in saved_activity_rows
        }
        activity_languages = {'php', 'javascript', 'cpp'}

        for activity in all_activities:
            activity['completed'] = False
            activity['status'] = 'LOCKED'
            activity['activity_number'] = activity['id']
            activity['max_score'] = 10

            if activity['language'] not in activity_languages:
                continue

            saved = saved_activities.get((activity['language'], activity['name']))
            if saved:
                activity['completed'] = True
                activity['status'] = 'COMPLETED'
                activity['score'] = saved['score']
                activity['completed_at'] = saved['completed_at']
            elif activities_unlocked:
                activity['status'] = 'AVAILABLE'
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'activities': all_activities,
            'activities_unlocked': activities_unlocked,
        })
        
    except Exception as e:
        print(f"Get activities error: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/get_achievements')
def get_achievements():
    if session.get('role') != 'student':
        return jsonify({'success': False})
    
    try:
        student_id = session.get('user_id')
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT COUNT(*) as total FROM assessment_attempts
            WHERE student_id = %s AND status = 'submitted'
        """, (student_id,))
        completed_count = cursor.fetchone()['total']
        
        cursor.execute("""
            SELECT IFNULL(AVG(score), 0) as avg FROM assessment_attempts
            WHERE student_id = %s AND status = 'submitted'
        """, (student_id,))
        avg_score = cursor.fetchone()['avg']
        
        cursor.execute("""
            SELECT COUNT(*) as total
            FROM assessment_attempts aa
            JOIN assessments a ON a.id = aa.assessment_id
            WHERE aa.student_id = %s AND aa.status = 'submitted' AND a.language = 'python'
        """, (student_id,))
        python_count = cursor.fetchone()['total']
        
        cursor.execute("""
            SELECT COUNT(*) as total
            FROM assessment_attempts aa
            JOIN assessments a ON a.id = aa.assessment_id
            WHERE aa.student_id = %s AND aa.status = 'submitted' AND a.language = 'javascript'
        """, (student_id,))
        js_count = cursor.fetchone()['total']
        
        cursor.execute("""
            SELECT COUNT(*) as total
            FROM assessment_attempts aa
            JOIN assessments a ON a.id = aa.assessment_id
            WHERE aa.student_id = %s AND aa.status = 'submitted' AND a.language = 'html'
        """, (student_id,))
        html_count = cursor.fetchone()['total']
        
        achievements = [
            {'id': 1, 'name': 'First Code', 'icon': 'fa-code', 'description': 'Complete your first activity', 'unlocked': completed_count >= 1},
            {'id': 2, 'name': 'Blockly Beginner', 'icon': 'fa-rocket', 'description': 'Complete 3 activities', 'unlocked': completed_count >= 3},
            {'id': 3, 'name': 'Bronze Coder', 'icon': 'fa-medal', 'description': 'Complete 5 activities', 'unlocked': completed_count >= 5},
            {'id': 4, 'name': 'Silver Coder', 'icon': 'fa-medal', 'description': 'Complete 10 activities', 'unlocked': completed_count >= 10},
            {'id': 5, 'name': 'Gold Coder', 'icon': 'fa-crown', 'description': 'Complete 15 activities', 'unlocked': completed_count >= 15},
            {'id': 6, 'name': 'High Achiever', 'icon': 'fa-star', 'description': 'Average score 80% or higher', 'unlocked': avg_score >= 80},
            {'id': 7, 'name': 'Python Master', 'icon': 'fa-python', 'description': 'Complete all Python activities (6)', 'unlocked': python_count >= 6},
            {'id': 8, 'name': 'JS Ninja', 'icon': 'fa-js', 'description': 'Complete all JavaScript activities (3)', 'unlocked': js_count >= 3},
            {'id': 9, 'name': 'HTML Hero', 'icon': 'fa-html5', 'description': 'Complete all HTML activities (2)', 'unlocked': html_count >= 2},
            {'id': 10, 'name': 'Perfect Score', 'icon': 'fa-trophy', 'description': 'Get 100% on any activity', 'unlocked': False},
        ]
        
        cursor.close()
        conn.close()
        
        unlocked_count = sum(1 for a in achievements if a['unlocked'])
        
        return jsonify({
            'success': True, 
            'achievements': achievements, 
            'total_unlocked': unlocked_count,
            'total_achievements': len(achievements)
        })
        
    except Exception as e:
        print(f"Get achievements error: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/get_dashboard_stats')
def get_dashboard_stats():
    if session.get('role') != 'student':
        return jsonify({'success': False})
    
    try:
        student_id = session.get('user_id')
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT COUNT(DISTINCT DATE(completed_at)) as days
            FROM activities 
            WHERE student_id = %s 
            AND completed_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        """, (student_id,))
        streak_result = cursor.fetchone()
        streak = min(streak_result['days'] if streak_result else 0, 7)
        
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'streak': streak})
        
    except Exception as e:
        print(f"Get dashboard stats error: {e}")
        return jsonify({'success': False, 'streak': 0})

@app.route('/get_activity_progress')
def get_activity_progress():
    if session.get('role') != 'student':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    try:
        student_id = session.get('user_id')
        if not student_id:
            return jsonify({'success': False, 'message': 'User not authenticated'}), 401
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT language, COUNT(*) AS total
                FROM assessments
                WHERE language IN ('python', 'java', 'php', 'javascript', 'cpp')
                GROUP BY language
            """)
            language_totals = {
                row['language']: row['total']
                for row in cursor.fetchall()
            }

            cursor.execute("""
                SELECT a.language, COUNT(DISTINCT aa.assessment_id) AS completed
                FROM assessment_attempts aa
                JOIN assessments a ON a.id = aa.assessment_id
                WHERE aa.student_id = %s
                  AND aa.status = 'submitted'
                  AND a.language IN ('python', 'java')
                GROUP BY a.language
            """, (student_id,))
            assessment_stats = {
                row['language']: min(row['completed'], language_totals.get(row['language'], 0))
                for row in cursor.fetchall()
            }

            cursor.execute("""
                SELECT a.language, COUNT(DISTINCT aa.assessment_id) AS completed
                FROM assessment_attempts aa
                JOIN assessments a ON a.id = aa.assessment_id
                WHERE aa.student_id = %s
                  AND aa.status = 'submitted'
                  AND a.language IN ('php', 'javascript', 'cpp')
                GROUP BY a.language
            """, (student_id,))
            submitted_activity_stats = {
                row['language']: min(row['completed'], language_totals.get(row['language'], 0))
                for row in cursor.fetchall()
            }

            cursor.execute("""
                SELECT language, COUNT(DISTINCT activity_name) AS completed
                FROM activities
                WHERE student_id = %s
                  AND language IN ('php', 'javascript', 'cpp')
                GROUP BY language
            """, (student_id,))
            saved_activity_stats = {
                row['language']: min(row['completed'], language_totals.get(row['language'], 0))
                for row in cursor.fetchall()
            }
            activity_stats = {
                language: max(
                    submitted_activity_stats.get(language, 0),
                    saved_activity_stats.get(language, 0),
                )
                for language in ('php', 'javascript', 'cpp')
            }
        finally:
            cursor.close()
            conn.close()

        python_count = assessment_stats.get('python', 0)
        java_count = assessment_stats.get('java', 0)
        php_count = activity_stats.get('php', 0)
        js_count = activity_stats.get('javascript', 0)
        cpp_count = activity_stats.get('cpp', 0)
        completed_assessments = python_count + java_count
        completed_activities = php_count + js_count + cpp_count
        total_completed = completed_assessments + completed_activities
        python_total = language_totals.get('python', 0)
        java_total = language_totals.get('java', 0)
        php_total = language_totals.get('php', 0)
        javascript_total = language_totals.get('javascript', 0)
        cpp_total = language_totals.get('cpp', 0)
        total_assessments = python_total + java_total
        total_activities = php_total + javascript_total + cpp_total
        total_items = total_assessments + total_activities

        response = {
            'success': True,
            'python': {'completed': python_count, 'total': python_total},
            'java': {'completed': java_count, 'total': java_total},
            'php': {'completed': php_count, 'total': php_total},
            'javascript': {'completed': js_count, 'total': javascript_total},
            'cpp': {'completed': cpp_count, 'total': cpp_total},
            'completed_assessments': completed_assessments,
            'completed_activities': completed_activities,
            'total_completed': total_completed,
            'total_assessments': total_assessments,
            'total_activities': total_activities,
            'total_items': total_items,
            'overall_percentage': round(total_completed / total_items * 100) if total_items else 0,
            'activities_unlocked': completed_assessments >= total_assessments,
        }
        print(
            f"[progress] student_id={student_id} assessments="
            f"{completed_assessments}/{total_assessments} activities="
            f"{completed_activities}/{total_activities} "
            f"overall={response['overall_percentage']}%"
        )
        return jsonify(response)
    except Exception as e:
        print(f"Get activity progress error: {e}")
        return jsonify({'success': False, 'message': 'Failed to retrieve progress'}), 500

@app.route('/get_progress_results')
def get_progress_results():
    """Return database-backed assessment and activity status for the current student."""
    if session.get('role') != 'student':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    student_id = session.get('user_id')
    if not student_id:
        return jsonify({'success': False, 'message': 'User not authenticated'}), 401

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT d.language, d.assessment_number AS item_number,
                   d.title AS item_name,
                   CASE WHEN aa.status = 'submitted' THEN 'COMPLETED' ELSE 'NOT COMPLETED' END AS status,
                   CASE WHEN aa.status = 'submitted' THEN
                        COALESCE(aa.auto_score, ROUND(aa.score / 10), 0)
                        ELSE NULL END AS score,
                   10 AS max_score,
                   COALESCE(aa.completed_at, aa.submitted_at) AS completed_at,
                   'assessment' AS item_type
            FROM assessments d
            LEFT JOIN assessment_attempts aa
              ON aa.assessment_id = d.id
             AND aa.student_id = %s
            WHERE d.language IN ('python', 'java')
            ORDER BY d.language, d.assessment_number
        """, (student_id,))
        assessments = cursor.fetchall()

        cursor.execute("""
            SELECT d.language, d.assessment_number AS item_number,
                   d.title AS item_name,
                   CASE WHEN act.id IS NOT NULL OR aa.status = 'submitted'
                        THEN 'COMPLETED' ELSE 'NOT COMPLETED' END AS status,
                   CASE WHEN act.id IS NOT NULL THEN act.score
                        WHEN aa.status = 'submitted' THEN COALESCE(aa.auto_score, ROUND(aa.score / 10), 0)
                        ELSE NULL END AS score,
                   10 AS max_score,
                   COALESCE(act.completed_at, aa.completed_at, aa.submitted_at) AS completed_at,
                   'activity' AS item_type
            FROM assessments d
            LEFT JOIN activities act
              ON act.student_id = %s
             AND act.language = d.language
             AND act.activity_name = d.title
            LEFT JOIN assessment_attempts aa
              ON aa.assessment_id = d.id
             AND aa.student_id = %s
            WHERE d.language IN ('javascript', 'cpp', 'php')
            ORDER BY d.language, d.assessment_number
        """, (student_id, student_id))
        activities = cursor.fetchall()
        results = assessments + activities
        print(f"[progress-results] student_id={student_id} rows={len(results)}")
        return jsonify({'success': True, 'results': results})
    except Exception as e:
        print(f"Get progress results error for student_id={student_id}: {e}")
        return jsonify({'success': False, 'message': 'Failed to retrieve progress results'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# ==================== TICKET API ROUTES ====================

from backend.tickets import (
    create_ticket, get_student_tickets, get_all_tickets,
    get_ticket_by_id, update_ticket_status, get_ticket_counts
)

@app.route('/submit_ticket', methods=['POST'])
def submit_ticket():
    if session.get('role') != 'student':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        data = request.json
        subject = data.get('subject')
        message = data.get('message')
        priority = data.get('priority', 'medium')
        category = data.get('category', 'other')
        
        if not subject or not message:
            return jsonify({'success': False, 'message': 'Subject and message are required'})
        
        student_id = session.get('user_id')
        student_name = session.get('username')
        
        result = create_ticket(student_id, student_name, subject, message, priority, category)
        if result.get('success'):
            notify_new_support_ticket(result['ticket_number'], subject, result['ticket_id'])
        return jsonify(result)
        
    except Exception as e:
        print(f"Error submitting ticket: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/get_tickets')
def get_tickets():
    if session.get('role') not in ['student', 'teacher', 'ict']:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    try:
        if session.get('role') == 'student':
            result = get_student_tickets(session.get('user_id'))
        else:
            result = get_all_tickets(request.args.get('status'))
        return jsonify(result)
    except Exception as e:
        print(f"Error getting tickets: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/update_ticket', methods=['POST'])
def update_ticket():
    if session.get('role') not in ['teacher', 'ict']:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        data = request.json
        ticket_id = data.get('ticket_id')
        status = data.get('status')
        
        if not ticket_id:
            return jsonify({'success': False, 'message': 'Ticket ID required'})
        
        result = update_ticket_status(ticket_id, status)
        if result.get('success'):
            ticket = get_ticket_by_id(ticket_id).get('ticket') or {}
            notify_ticket_updated(
                ticket.get('student_id'),
                ticket.get('ticket_number', f'Ticket #{ticket_id}'),
                ticket.get('subject', 'Support ticket'),
                status,
                ticket_id,
            )
        return jsonify(result)
        
    except Exception as e:
        print(f"Error updating ticket: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/get_ticket_count')
def get_ticket_count():
    if session.get('role') != 'teacher':
        return jsonify({'success': False})
    
    try:
        result = get_ticket_counts()
        return jsonify(result)
        
    except Exception as e:
        print(f"Error getting ticket count: {e}")
        return jsonify({'success': False, 'message': str(e)})

# ==================== TEACHER API ROUTES ====================

@app.route('/get_students')
def get_students():
    if session.get('role') != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            cursor.execute("""
                SELECT
                    s.id,
                    s.lrn,
                    s.full_name,
                    s.grade_level,
                    DATE_FORMAT(s.created_at, '%Y-%m-%d') as created_at
                FROM students s
                ORDER BY s.created_at DESC, s.id DESC
            """)
            students = cursor.fetchall()
            
            for student in students:
                student['has_activities'] = False
            
            return jsonify({'success': True, 'students': students})
        finally:
            cursor.close()
            conn.close()
    except Exception as e:
        print(f"Get students error: {e}")
        return jsonify({'success': False, 'message': 'Failed to retrieve students'})

# ==================== IMPROVED GET_SCORES ROUTE ====================

@app.route('/get_scores')
def get_scores():
    """Get all student scores (teacher only)"""
    if session.get('role') != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            cursor.execute("""
                SELECT
                    s.lrn,
                    s.full_name as student_name,
                    d.title as activity_name,
                    a.score,
                    d.language,
                    DATE_FORMAT(a.submitted_at, '%Y-%m-%d %H:%i') as completed_at
                FROM assessment_attempts a
                JOIN assessments d ON d.id = a.assessment_id
                JOIN students s ON a.student_id = s.id
                WHERE a.status = 'submitted'
                ORDER BY a.submitted_at DESC
                LIMIT 100
            """)
            scores = cursor.fetchall()
            
            print(f"📊 Retrieved {len(scores)} scores")
            
            return jsonify({'success': True, 'scores': scores})
        finally:
            cursor.close()
            conn.close()
    except Exception as e:
        print(f"❌ Get scores error: {e}")
        return jsonify({'success': False, 'message': 'Failed to retrieve scores'})

@app.route('/get_activity_scores')
def get_activity_scores():
    if session.get('role') != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT aa.id AS submission_id,
                   s.id AS student_id,
                   s.lrn,
                   s.full_name AS student_name,
                   d.assessment_number AS activity_number,
                   d.title AS activity_name,
                   d.language,
                        CASE WHEN aa.teacher_score IS NOT NULL THEN
                               CASE WHEN aa.teacher_score > 10 THEN ROUND(aa.teacher_score / 10) ELSE aa.teacher_score END
                        WHEN aa.auto_score > 0 OR aa.score = 0 THEN aa.auto_score
                        ELSE ROUND(aa.score / 10) END AS score,
                   aa.auto_score,
                   aa.teacher_score,
                   aa.teacher_feedback,
                   aa.code_blocks,
                   aa.generated_code,
                   aa.output AS student_output,
                   d.expected_output,
                   CASE WHEN aa.score >= 75 THEN 'Passed' ELSE 'Failed' END AS result,
                   CASE WHEN aa.status = 'submitted' THEN 'COMPLETED' ELSE 'AVAILABLE' END AS status,
                   DATE_FORMAT(COALESCE(aa.completed_at, aa.submitted_at), '%Y-%m-%d %H:%i') AS completed_at
            FROM assessment_attempts aa
            JOIN assessments d ON d.id = aa.assessment_id
            JOIN students s ON s.id = aa.student_id
            WHERE d.language IN ('php', 'javascript', 'cpp')
              AND aa.status = 'submitted'
            ORDER BY COALESCE(aa.completed_at, aa.submitted_at) DESC, aa.id DESC
        """)
        scores = cursor.fetchall()

        return jsonify({'success': True, 'scores': scores})
    except Exception as e:
        print(f"Get activity scores error: {e}")
        return jsonify({'success': False, 'message': 'Failed to retrieve activity scores'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/get_passed_assessments')
def get_passed_assessments():
    if session.get('role') != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT s.full_name AS student_name, s.lrn,
                   d.title AS activity_name, d.language, d.points,
                   a.score, DATE_FORMAT(a.submitted_at, '%Y-%m-%d %H:%i') AS completed_at
            FROM assessment_attempts a
            JOIN assessments d ON d.id = a.assessment_id
            JOIN students s ON s.id = a.student_id
            WHERE a.status = 'submitted' AND a.score >= 75
            ORDER BY a.submitted_at DESC
        """)
        passed = cursor.fetchall()
        return jsonify({'success': True, 'passed': passed})
    except Exception as e:
        print(f"Get passed assessments error: {e}")
        return jsonify({'success': False, 'message': 'Failed to retrieve passed assessments'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/get_assessment_results')
def get_assessment_results():
    if session.get('role') != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT s.lrn, d.title AS assessment_name, d.language,
                   a.score, CASE WHEN a.score >= 75 THEN 'Passed' ELSE 'Needs Review' END AS result,
                   DATE_FORMAT(a.submitted_at, '%Y-%m-%d %H:%i') AS completed_at
            FROM assessment_attempts a
            JOIN assessments d ON d.id = a.assessment_id
            JOIN students s ON s.id = a.student_id
                        WHERE a.status = 'submitted'
                            AND d.language IN ('python', 'java')
            ORDER BY a.submitted_at DESC
            LIMIT 200
        """)
        return jsonify({'success': True, 'results': cursor.fetchall()})
    except Exception as e:
        print(f"Get assessment results error: {e}")
        return jsonify({'success': False, 'message': 'Failed to retrieve assessment results'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/teacher/submissions')
def teacher_submissions():
    if session.get('role') != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT a.id, s.full_name AS student_name, s.username, d.title AS activity_name,
                   d.language, d.points, ROUND(a.score * d.points / 100) AS score,
                   a.status, DATE_FORMAT(a.submitted_at, '%Y-%m-%d %H:%i') AS submitted_at
            FROM assessment_attempts a
            JOIN assessments d ON d.id = a.assessment_id
            JOIN students s ON s.id = a.student_id
            WHERE a.status = 'submitted'
            ORDER BY a.submitted_at DESC
        """)
        checked = cursor.fetchall()
        return jsonify({'success': True, 'pending': [], 'checked': checked, 'total': len(checked)})
    except Exception as e:
        print(f"Get teacher submissions error: {e}")
        return jsonify({'success': False, 'message': 'Failed to retrieve submissions'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/teacher/submission/<int:submission_id>')
def teacher_submission(submission_id):
    if session.get('role') != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
                 SELECT a.id, s.full_name AS student_name, s.username,
                     d.assessment_number AS activity_number, d.title AS activity_name,
                     d.language, d.expected_output, a.code_blocks, a.generated_code,
                       a.output AS student_output, a.score, a.auto_score,
                       CASE WHEN a.teacher_score > 10 THEN ROUND(a.teacher_score / 10) ELSE a.teacher_score END AS teacher_score,
                     a.teacher_feedback, a.status, a.submitted_at, a.completed_at
            FROM assessment_attempts a
            JOIN assessments d ON d.id = a.assessment_id
            JOIN students s ON s.id = a.student_id
            WHERE a.id = %s
        """, (submission_id,))
        submission = cursor.fetchone()
        if not submission:
            return jsonify({'success': False, 'message': 'Submission not found'}), 404
        return jsonify({'success': True, 'submission': submission})
    except Exception as e:
        print(f"Get teacher submission error: {e}")
        return jsonify({'success': False, 'message': 'Failed to retrieve submission'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/teacher/review_submission', methods=['POST'])
def review_teacher_submission():
    if session.get('role') != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    submission_id = data.get('submission_id')
    score = data.get('score')
    if not isinstance(submission_id, int) or not isinstance(score, int):
        return jsonify({'success': False, 'message': 'Invalid review data'}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT d.points, d.title, d.language, a.student_id
            FROM assessments d
            JOIN assessment_attempts a ON a.assessment_id = d.id
            WHERE a.id = %s
        """, (submission_id,))
        assessment = cursor.fetchone()
        if not assessment or score < 0 or score > 10:
            return jsonify({'success': False, 'message': 'Invalid score'}), 400
        stored_score = score * 10
        feedback = data.get('feedback', '')
        cursor.execute("""
            UPDATE assessment_attempts
            SET score = %s,
                teacher_score = %s,
                teacher_feedback = %s,
                reviewed_by = %s,
                reviewed_at = %s,
                status = 'submitted',
                completed_at = COALESCE(completed_at, submitted_at)
            WHERE id = %s
        """, (stored_score, score, feedback, session['user_id'], datetime.now(), submission_id))
        conn.commit()
        notify_assessment_checked(
            assessment['student_id'],
            assessment['title'],
            stored_score,
            feedback,
            submission_id,
        )
        return jsonify({'success': True, 'message': 'Review saved'})
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Review teacher submission error: {e}")
        return jsonify({'success': False, 'message': 'Failed to save review'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# ==================== END OF GET_SCORES ====================

@app.route('/get_performance_reports')
def get_performance_reports():
    if session.get('role') != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            cursor.execute("""
                    SELECT s.id, s.lrn, s.grade_level,
                      COUNT(a.id) as total_activities,
                      IFNULL(ROUND(AVG(a.score), 1), 0) as average_score,
                      SUM(CASE WHEN a.score < 50 THEN 1 ELSE 0 END) as low_scores
                FROM students s
                  LEFT JOIN assessment_attempts a ON s.id = a.student_id AND a.status = 'submitted'
                GROUP BY s.id
                ORDER BY average_score DESC
            """)
            reports = cursor.fetchall()
            return jsonify({'success': True, 'reports': reports})
        finally:
            cursor.close()
            conn.close()
    except Exception as e:
        print(f"Get performance reports error: {e}")
        return jsonify({'success': False, 'message': 'Failed to retrieve performance reports'})

@app.route('/get_student_detail/<lrn>')
def get_student_detail(lrn):
    if session.get('role') != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT id, lrn, full_name, grade_level, email, 
                   DATE_FORMAT(created_at, '%M %d, %Y') as joined_date
            FROM students WHERE lrn = %s
        """, (lrn,))
        student = cursor.fetchone()
        
        if not student:
            return jsonify({'success': False, 'message': 'Student not found'})
        
        cursor.execute("""
            SELECT CONCAT(d.language, ' Assessment #', d.assessment_number) AS activity_name,
                   a.score, d.language,
                   DATE_FORMAT(a.submitted_at, '%Y-%m-%d %H:%i') AS completed_at
            FROM assessment_attempts a
            JOIN assessments d ON d.id = a.assessment_id
            WHERE a.student_id = %s AND a.status = 'submitted'
            ORDER BY a.submitted_at DESC
        """, (student['id'],))
        activities = cursor.fetchall()
        
        total_activities = len(activities)
        avg_score = round(sum(a['score'] for a in activities) / total_activities) if total_activities > 0 else 0
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'student': student,
            'activities': activities,
            'total_activities': total_activities,
            'average_score': avg_score
        })
        
    except Exception as e:
        print(f"Get student detail error: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/update_teacher_profile', methods=['POST'])
def update_teacher_profile():
    if session.get('role') != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        data = request.json
        full_name = data.get('full_name')
        email = data.get('email')
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        
        user_id = session.get('user_id')
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            updates = []
            params = []
            
            if full_name:
                updates.append("full_name = %s")
                params.append(full_name)
                session['full_name'] = full_name
            
            if email:
                updates.append("email = %s")
                params.append(email)
            
            if current_password and new_password:
                cursor.execute("SELECT password FROM teachers WHERE id = %s", (user_id,))
                teacher = cursor.fetchone()
                
                if teacher and hash_password(current_password) != teacher['password']:
                    return jsonify({'success': False, 'message': 'Current password is incorrect'})
                
                updates.append("password = %s")
                params.append(hash_password(new_password))
            
            if updates:
                query = f"UPDATE teachers SET {', '.join(updates)} WHERE id = %s"
                params.append(user_id)
                cursor.execute(query, params)
                conn.commit()
            
            return jsonify({'success': True, 'message': 'Profile updated successfully!'})
            
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        print(f"Update teacher profile error: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/get_class_stats')
def get_class_stats():
    if session.get('role') != 'teacher':
        return jsonify({'success': False})
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT COUNT(*) as total FROM students")
        total_students = cursor.fetchone()['total']
        
        cursor.execute("""
            SELECT COUNT(DISTINCT student_id) as active
            FROM activities
        """)
        active_students = cursor.fetchone()['active'] or 0
        
        cursor.execute("SELECT COUNT(*) as total FROM activities")
        total_submissions = cursor.fetchone()['total'] or 0
        
        cursor.execute("SELECT IFNULL(AVG(score), 0) as avg FROM activities")
        class_avg = round(cursor.fetchone()['avg'])
        
        cursor.execute("""
            SELECT COUNT(*) as passing
            FROM activities WHERE score >= 70
        """)
        passing = cursor.fetchone()['passing'] or 0
        passing_rate = round((passing / total_submissions) * 100) if total_submissions > 0 else 0
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'total_students': total_students,
            'active_students': active_students,
            'total_submissions': total_submissions,
            'class_average': class_avg,
            'passing_rate': passing_rate
        })
        
    except Exception as e:
        print(f"Get class stats error: {e}")
        return jsonify({'success': False})

@app.route('/leaderboard')
def leaderboard():
    if session.get('role') not in ['student', 'teacher']:
        return jsonify({'success': False})
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
                 SELECT s.lrn AS student_name,
                     s.lrn,
                   COUNT(scores.student_id) AS activities_completed,
                   IFNULL(ROUND(AVG(scores.score)), 0) AS average_score
            FROM students s
            JOIN (
                SELECT student_id, score
                FROM activities
                UNION ALL
                SELECT student_id, score
                FROM assessment_attempts
                WHERE status = 'submitted'
            ) scores ON scores.student_id = s.id
            GROUP BY s.id, s.full_name, s.lrn
            ORDER BY average_score DESC, activities_completed DESC
            LIMIT 10
        """)
        top_students = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'leaderboard': top_students})
        
    except Exception as e:
        print(f"Leaderboard error: {e}")
        return jsonify({'success': False, 'message': str(e)})

# ==================== ICT SUPPORT API ROUTES ====================

@app.route('/get_monitoring_data')
def get_monitoring_data():
    if session.get('role') not in ['teacher', 'ict']:
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        monitoring = {
            'cpu_usage': 45.2,
            'memory_usage': 62.5,
            'disk_usage': 78.3,
            'network_bandwidth': 150.5,
            'uptime': '45 days, 12 hours',
            'active_users': 12,
            'services': [
                {'name': 'Web Server', 'status': 'Running', 'uptime': '15 days'},
                {'name': 'Database', 'status': 'Running', 'uptime': '45 days'},
                {'name': 'Email Service', 'status': 'Running', 'uptime': '8 days'},
                {'name': 'Backup Service', 'status': 'Stopped', 'uptime': 'N/A'}
            ]
        }
        return jsonify({'success': True, 'data': monitoring})
    except Exception as e:
        print(f"Error getting monitoring data: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/get_ict_reports')
def get_ict_reports():
    if session.get('role') not in ['teacher', 'ict']:
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        reports = {
            'system_health': 92,
            'uptime_percentage': 99.8,
            'incidents_this_month': 3,
            'resolved_tickets': 28,
            'pending_tickets': 5,
            'average_resolution_time': '4.5 hours'
        }
        return jsonify({'success': True, 'data': reports})
    except Exception as e:
        print(f"Error getting ICT reports: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/generate_report')
def generate_report():
    if session.get('role') not in ['teacher', 'ict']:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    report_type = request.args.get('type', 'ticket')
    if report_type not in ['user', 'performance']:
        return jsonify({'success': False, 'message': 'Unsupported report type'}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        if report_type == 'user':
            cursor.execute("""
                SELECT s.id, s.full_name, s.username, s.lrn, s.grade_level,
                       s.created_at AS last_active, COUNT(t.id) AS ticket_count
                FROM students s
                LEFT JOIN ict_tickets t ON t.student_id = s.id
                GROUP BY s.id, s.full_name, s.username, s.lrn, s.grade_level, s.created_at
                ORDER BY s.full_name, s.username
            """)
            users = cursor.fetchall()
            cursor.execute("SELECT COUNT(*) AS total FROM ict_tickets")
            total_tickets = cursor.fetchone()['total']
            return jsonify({
                'success': True,
                'total_users': len(users),
                'active_users': len(users),
                'inactive_users': 0,
                'total_tickets': total_tickets,
                'users': users
            })

        cursor.execute("""
            SELECT COUNT(*) AS total_tickets,
                   COALESCE(AVG(CASE WHEN status IN ('resolved', 'closed')
                       THEN TIMESTAMPDIFF(MINUTE, created_at, COALESCE(resolved_at, updated_at)) END), 0) AS avg_resolution_time,
                   COALESCE(SUM(status IN ('resolved', 'closed')) / NULLIF(COUNT(*), 0) * 100, 0) AS resolution_rate
            FROM ict_tickets
        """)
        summary = cursor.fetchone()
        cursor.execute("""
            SELECT DATE_FORMAT(created_at, '%Y-%m-%d') AS date,
                   COUNT(*) AS tickets_created,
                   SUM(status IN ('resolved', 'closed')) AS tickets_resolved,
                   COALESCE(AVG(CASE WHEN status IN ('resolved', 'closed')
                       THEN TIMESTAMPDIFF(MINUTE, created_at, COALESCE(resolved_at, updated_at)) END), 0) AS avg_resolution_time
            FROM ict_tickets
            WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            GROUP BY DATE_FORMAT(created_at, '%Y-%m-%d')
            ORDER BY DATE_FORMAT(created_at, '%Y-%m-%d') DESC
        """)
        performance_data = cursor.fetchall()
        for row in performance_data:
            row['tickets_created'] = int(row['tickets_created'] or 0)
            row['tickets_resolved'] = int(row['tickets_resolved'] or 0)
            row['avg_resolution_time'] = round(float(row['avg_resolution_time'] or 0), 1)
        return jsonify({
            'success': True,
            'avg_resolution_time': round(float(summary['avg_resolution_time'] or 0), 1),
            'resolution_rate': round(float(summary['resolution_rate'] or 0), 1),
            'total_tickets': summary['total_tickets'] or 0,
            'avg_rating': 0,
            'performance_data': performance_data
        })
    except Exception as e:
        print(f"Error generating {report_type} report: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/get_ict_students')
def get_ict_students():
    if session.get('role') not in ['teacher', 'ict']:
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT s.id, s.username, s.full_name, s.lrn, s.grade_level, s.email,
                   s.created_at, COUNT(a.id) AS activity_count,
                   COALESCE(AVG(a.score), 0) AS avg_score
            FROM students s
            LEFT JOIN assessment_attempts a
                ON s.id = a.student_id AND a.status = 'submitted'
            GROUP BY s.id, s.username, s.full_name, s.lrn, s.grade_level,
                     s.email, s.created_at
            ORDER BY s.full_name
        """)
        
        students = cursor.fetchall()
        cursor.execute("""
            SELECT id, username, full_name, role_type, email, status, last_login
            FROM ict_support
            ORDER BY full_name, username
        """)
        ict_supports = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'students': students,
            'ict_supports': ict_supports
        })
    except Exception as e:
        print(f"Error getting ICT students: {e}")
        return jsonify({'success': False, 'message': str(e)})

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'message': 'Page not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    print(f"Internal server error: {error}")
    return jsonify({'success': False, 'message': 'Internal server error'}), 500

if __name__ == '__main__':
    print('=' * 60)
    print('BLOCKLEARN - Drag-and-Drop Programming Platform')
    print('=' * 60)
    print(f"Database: {db_config['database']}")
    print(f"Host: {db_config['host']}")
    print('=' * 60)
    print('Default login credentials:')
    print('  Teacher: teacher1 / teacher123')
    print('  Admin: admin / admin123')
    print('Run the app and open http://127.0.0.1:5000')
    print('=' * 60)
    app.run(debug=True, host='127.0.0.1', port=5000)