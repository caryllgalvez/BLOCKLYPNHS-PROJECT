# app.py - Main Flask Application for Blockly Learning Platform
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
from flask_cors import CORS
import mysql.connector
import hashlib
from datetime import datetime
import os
import re
import jinja2

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'frontend', 'public')
STATIC_DIR = os.path.join(BASE_DIR, 'static')

app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
app.secret_key = 'your-secret-key-change-this-in-production-2024'
CORS(app)

# Configure Jinja loader to search common frontend subfolders so templates
# like 'student_dashboard.html' are discovered when stored under
# frontend/student, frontend/teacher, frontend/activities, etc.
frontend_dirs = [
    TEMPLATE_DIR,
    os.path.join(BASE_DIR, 'frontend'),
    os.path.join(BASE_DIR, 'frontend', 'student'),
    os.path.join(BASE_DIR, 'frontend', 'teacher'),
    os.path.join(BASE_DIR, 'frontend', 'activities'),
    os.path.join(BASE_DIR, 'frontend', 'playground'),
    os.path.join(BASE_DIR, 'frontend', 'auth'),
    os.path.join(BASE_DIR, 'frontend', 'analytics')
]
app.jinja_loader = jinja2.FileSystemLoader(frontend_dirs)


# Serve favicon to avoid 404 from browsers requesting /favicon.ico
@app.route('/favicon.ico')
def favicon():
    ico_path = os.path.join(app.static_folder, 'favicon.ico')
    svg_path = os.path.join(app.static_folder, 'favicon.svg')
    if os.path.exists(ico_path):
        return send_from_directory(app.static_folder, 'favicon.ico')
    if os.path.exists(svg_path):
        return send_from_directory(app.static_folder, 'favicon.svg')
    return ('', 204)

# Database configuration
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'C@ryll025',
    'database': 'blocklypnhsproject'
}

# Store last update timestamp for real-time tracking
last_update_timestamp = None

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


def get_all_activities():
    return [
        {'id': 1, 'name': 'Print Statement', 'language': 'python', 'difficulty': 'easy'},
        {'id': 2, 'name': 'Variables and Print', 'language': 'python', 'difficulty': 'easy'},
        {'id': 3, 'name': 'If-Else Condition', 'language': 'python', 'difficulty': 'easy'},
        {'id': 4, 'name': 'Age Checker', 'language': 'python', 'difficulty': 'medium'},
        {'id': 5, 'name': 'Number Guessing Game', 'language': 'python', 'difficulty': 'hard'},
        {'id': 6, 'name': 'Hello World', 'language': 'javascript', 'difficulty': 'easy'},
        {'id': 7, 'name': 'Variable Greeting', 'language': 'javascript', 'difficulty': 'easy'},
        {'id': 8, 'name': 'Add Numbers', 'language': 'javascript', 'difficulty': 'medium'},
        {'id': 9, 'name': 'Temperature Converter', 'language': 'javascript', 'difficulty': 'hard'},
        {'id': 10, 'name': 'Create Heading', 'language': 'html', 'difficulty': 'easy'},
        {'id': 11, 'name': 'Create Paragraph', 'language': 'html', 'difficulty': 'easy'},
        {'id': 12, 'name': 'Heading with Style', 'language': 'html', 'difficulty': 'medium'},
        {'id': 13, 'name': 'HTML Page', 'language': 'html', 'difficulty': 'hard'},
    ]


def get_max_score(activity_name):
    if not activity_name:
        return 10
    name = activity_name.lower()
    if 'print' in name or 'variable' in name or 'if-else' in name or 'hello world' in name or 'greeting' in name:
        return 10
    if 'age' in name or 'checker' in name or 'style' in name or 'list' in name or 'unordered' in name:
        return 15
    if 'guess' in name or 'guessing' in name or 'game' in name or 'temperature' in name or 'web page' in name or 'html page' in name or 'add numbers' in name:
        return 20
    return 10


def create_index_if_not_exists(cursor, table_name, index_name, columns):
    try:
        cursor.execute(f"SHOW INDEX FROM `{table_name}`")
        indexes = cursor.fetchall()
        if any(index.get('Key_name') == index_name for index in indexes):
            return
        cursor.execute(f"CREATE INDEX `{index_name}` ON `{table_name}` ({columns})")
    except Exception as exc:
        print(f" Could not create index {index_name}: {exc}")


def column_exists(cursor, table_name, column_name):
    try:
        cursor.execute(f"SHOW COLUMNS FROM `{table_name}`")
        columns = cursor.fetchall()
        return any(col.get('Field') == column_name for col in columns)
    except Exception:
        return False


def add_column_if_not_exists(cursor, table_name, column_definition, column_name):
    if column_exists(cursor, table_name, column_name):
        return
    try:
        cursor.execute(f"ALTER TABLE `{table_name}` ADD COLUMN {column_definition}")
        print(f" Added column {column_name} to {table_name}")
    except Exception as exc:
        print(f" Could not add column {column_name} to {table_name}: {exc}")

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
            print(" Added full_name column to students table")
        
        # Create teachers table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS teachers (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                full_name VARCHAR(200),
                email VARCHAR(100),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create activities table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activities (
                id INT AUTO_INCREMENT PRIMARY KEY,
                student_id INT NOT NULL,
                activity_name VARCHAR(200) NOT NULL,
                score INT DEFAULT 0,
                code_blocks TEXT,
                language VARCHAR(50) DEFAULT 'python',
                completed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
            )
        """)
        
        # ===== STUDENT SUBMISSIONS TABLE =====
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS student_submissions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                student_id INT NOT NULL,
                activity_name VARCHAR(200) NOT NULL,
                code_blocks TEXT NOT NULL,
                language VARCHAR(50) DEFAULT 'python',
                status VARCHAR(50) DEFAULT 'pending_review',
                score INT,
                feedback TEXT,
                submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                reviewed_at DATETIME,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
            )
        """)
        
        # ===== NOTIFICATIONS TABLE =====
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT,
                target_role VARCHAR(20),
                type VARCHAR(50) NOT NULL,
                title VARCHAR(255) NOT NULL,
                message TEXT NOT NULL,
                related_id INT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_read BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (user_id) REFERENCES students(id) ON DELETE CASCADE
            )
        """)
        add_column_if_not_exists(cursor, 'notifications', 'user_id INT NULL AFTER id', 'user_id')
        add_column_if_not_exists(cursor, 'notifications', 'target_role VARCHAR(20) NULL AFTER user_id', 'target_role')
        add_column_if_not_exists(cursor, 'notifications', 'related_id INT NULL AFTER message', 'related_id')
        add_column_if_not_exists(cursor, 'notifications', 'is_read BOOLEAN DEFAULT FALSE AFTER created_at', 'is_read')
        
        # Create lessons table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lessons (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                description TEXT,
                content TEXT,
                difficulty VARCHAR(50),
                order_num INT DEFAULT 0
            )
        """)
        
        # Create tickets table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id INT AUTO_INCREMENT PRIMARY KEY,
                student_id INT NOT NULL,
                student_name VARCHAR(100),
                subject VARCHAR(200) NOT NULL,
                message TEXT NOT NULL,
                status ENUM('pending', 'in_progress', 'resolved', 'closed') DEFAULT 'pending',
                priority ENUM('low', 'medium', 'high') DEFAULT 'medium',
                teacher_approval ENUM('pending','approved','denied') DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                resolved_at DATETIME NULL,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
            )
        """)
        add_column_if_not_exists(cursor, 'tickets', 'student_name VARCHAR(100) NULL AFTER student_id', 'student_name')
        add_column_if_not_exists(cursor, 'tickets', 'teacher_approval ENUM(\'pending\',\'approved\',\'denied\') DEFAULT \'pending\' AFTER priority', 'teacher_approval')
        add_column_if_not_exists(cursor, 'tickets', 'resolved_at DATETIME NULL AFTER updated_at', 'resolved_at')
        
        # Create indexes for performance in a MySQL-compatible way
        create_index_if_not_exists(cursor, 'student_submissions', 'idx_submissions_student', 'student_id')
        create_index_if_not_exists(cursor, 'student_submissions', 'idx_submissions_status', 'status')
        create_index_if_not_exists(cursor, 'notifications', 'idx_notifications_user', 'user_id')
        create_index_if_not_exists(cursor, 'notifications', 'idx_notifications_read', 'is_read')
        
        # Insert default lessons if none exist
        cursor.execute("SELECT COUNT(*) AS lesson_count FROM lessons")
        lesson_count = cursor.fetchone().get('lesson_count', 0)
        if lesson_count == 0:
            default_lessons = [
                (1, " Activity 1: Say Hello!", "Learn to print 'Hello World' using Blockly", "Print statement basics", "Beginner", 1),
                (2, " Activity 2: Print Your Name", "Print your own name using variables", "Variables and strings", "Beginner", 2),
                (3, " Activity 3: Simple Math", "Perform addition and print the result", "Math operations", "Beginner", 3),
                (4, " Activity 4: Using Loops", "Repeat actions using loops", "Loop structures", "Intermediate", 4)
            ]
            cursor.executemany(
                "INSERT INTO lessons (id, title, description, content, difficulty, order_num) VALUES (%s, %s, %s, %s, %s, %s)",
                default_lessons
            )
        
        # CREATE DEFAULT TEACHER ACCOUNT
        cursor.execute("SELECT id, username, password FROM teachers WHERE LOWER(username) = 'teacher1'")
        teacher1_row = cursor.fetchone()
        if not teacher1_row:
            teacher1_password = hash_password("teacher123")
            cursor.execute("""
                INSERT INTO teachers (username, password, full_name, email, created_at) 
                VALUES (%s, %s, %s, %s, %s)
            """, ("teacher1", teacher1_password, "Teacher One", "teacher1@blocklearn.edu.ph", datetime.now()))
            print(" Teacher account created: username='teacher1', password='teacher123'")
        else:
            teacher1_password = hash_password("teacher123")
            if teacher1_row['username'] != 'teacher1':
                cursor.execute("UPDATE teachers SET username = %s WHERE id = %s", ("teacher1", teacher1_row['id']))
                print("ℹ Normalized existing teacher1 username to lowercase")
            if teacher1_row['password'] != teacher1_password:
                cursor.execute("UPDATE teachers SET password = %s WHERE id = %s", (teacher1_password, teacher1_row['id']))
                print("ℹ Updated teacher1 password to the provided default")
            print("ℹ Teacher1 account already exists")
        
        conn.commit()
        print(" Database initialized successfully!")
        
    except Exception as e:
        print(f" Database initialization error: {e}")
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
    return render_template('homepage.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/registeracc')
def registeracc():
    return render_template('register.html')

# ===== STUDENT ROUTES =====
@app.route('/student_dashboard')
def student_dashboard():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('student_dashboard.html', 
                          lrn=session.get('lrn'),
                          grade_level=session.get('grade_level'),
                          username=session.get('username'),
                          full_name=session.get('full_name'))

# ===== PYTHON ROUTES =====
@app.route('/student_playground')
def student_playground():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('student_playground.html', 
                          username=session.get('username'),
                          grade_level=session.get('grade_level'))

@app.route('/student_playground_python')
def student_playground_python():
    """Python Blockly Playground - with activity parameter support"""
    if session.get('role') != 'student':
        return redirect('/')
    
    # Get the activity from URL parameter (default: print-statement)
    activity = request.args.get('activity', 'print-statement')
    
    # Pass the activity to the template
    return render_template('student_playground.html', 
                          username=session.get('username'),
                          grade_level=session.get('grade_level'),
                          lrn=session.get('lrn'),
                          activity=activity)

@app.route('/student_activities')
def student_activities():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('student_activities.html', 
                          username=session.get('username'),
                          lrn=session.get('lrn'))

@app.route('/student_activities_python')
def student_activities_python():
    """Python Activities Page (alias for student_activities)"""
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('student_activities.html', 
                          username=session.get('username'),
                          lrn=session.get('lrn'))

# ===== JAVASCRIPT ROUTES =====
@app.route('/student_playground_javascript')
def student_playground_javascript():
    """JavaScript Blockly Playground"""
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('student_playground_javascript.html', 
                          username=session.get('username'),
                          grade_level=session.get('grade_level'),
                          lrn=session.get('lrn'))

@app.route('/student_activities_javascript')
def student_activities_javascript():
    """JavaScript Activities Page"""
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('student_activities_javascript.html', 
                          username=session.get('username'),
                          lrn=session.get('lrn'))

# ===== HTML/CSS ROUTES =====
@app.route('/student_playground_html')
def student_playground_html():
    """HTML/CSS Blockly Playground"""
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('student_playground_html.html', 
                          username=session.get('username'),
                          grade_level=session.get('grade_level'),
                          lrn=session.get('lrn'))

@app.route('/student_activities_html')
def student_activities_html():
    """HTML/CSS Activities Page"""
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('student_activities_html.html', 
                          username=session.get('username'),
                          lrn=session.get('lrn'))

# ===== OTHER STUDENT ROUTES =====
@app.route('/student_progress')
def student_progress():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('student_progress.html', 
                          username=session.get('username'))

@app.route('/student_achievements')
def student_achievements():
    if session.get('role') != 'student':
        return redirect('/')
    return render_template('student_achievements.html', 
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
                   DATE_FORMAT(created_at, '%B %d, %Y') as created_at,
                   (SELECT COUNT(*) FROM activities WHERE student_id = students.id) as total_activities,
                   (SELECT IFNULL(AVG(score), 0) FROM activities WHERE student_id = students.id) as average_score
            FROM students 
            WHERE id = %s
        """, (session.get('user_id'),))
        student = cursor.fetchone()
        
        return render_template('student_profile.html', 
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
    return render_template('student_settings.html', 
                          username=session.get('username'))

# ===== TEACHER ROUTES =====
@app.route('/teacher_dashboard')
def teacher_dashboard():
    if session.get('role') != 'teacher':
        return redirect('/')
    return render_template('teacher_dashboard.html', 
                          username=session.get('username'),
                          full_name=session.get('full_name'))

@app.route('/teacher_students')
def teacher_students():
    if session.get('role') != 'teacher':
        return redirect('/')
    return render_template('teacher_student_list.html', 
                          username=session.get('username'),
                          full_name=session.get('full_name'))

@app.route('/teacher_scores')
def teacher_scores():
    if session.get('role') != 'teacher':
        return redirect('/')
    return render_template('teacher_studentscores.html', 
                          username=session.get('username'),
                          full_name=session.get('full_name'))

@app.route('/teacher_reports')
def teacher_reports():
    if session.get('role') != 'teacher':
        return redirect('/')
    return redirect('/teacher_reports_analytics')

@app.route('/teacher_reports_analytics')
def teacher_reports_analytics():
    """Combined Reports and Analytics page"""
    if session.get('role') != 'teacher':
        return redirect('/')
    return render_template('reports_analytics.html', 
                          username=session.get('username'),
                          full_name=session.get('full_name'))


# ===== UPDATED GET_TEACHER_DASHBOARD_DATA =====
@app.route('/get_teacher_dashboard_data')
def get_teacher_dashboard_data():
    """Return aggregated data for teacher dashboard: recent submissions,
    score distribution, completion overview, totals, tickets, and notifications."""
    if session.get('role') != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'})

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Recent submissions (limit 6)
        cursor.execute("""
            SELECT s.id, s.student_id, u.username as student_username, u.full_name as student_name,
                   s.activity_name, s.status, s.score,
                   DATE_FORMAT(s.submitted_at, '%Y-%m-%d %H:%i:%s') as submitted_at
            FROM student_submissions s
            JOIN students u ON s.student_id = u.id
            ORDER BY s.submitted_at DESC
            LIMIT 6
        """)
        recent_subs = cursor.fetchall()

        # Score distribution
        cursor.execute("""
            SELECT
                SUM(CASE WHEN s.score BETWEEN 0 AND 59 THEN 1 ELSE 0 END) as b0,
                SUM(CASE WHEN s.score BETWEEN 60 AND 69 THEN 1 ELSE 0 END) as b60,
                SUM(CASE WHEN s.score BETWEEN 70 AND 79 THEN 1 ELSE 0 END) as b70,
                SUM(CASE WHEN s.score BETWEEN 80 AND 89 THEN 1 ELSE 0 END) as b80,
                SUM(CASE WHEN s.score BETWEEN 90 AND 100 THEN 1 ELSE 0 END) as b90
            FROM (
                SELECT score FROM student_submissions WHERE status = 'checked' AND score IS NOT NULL
                UNION ALL
                SELECT score FROM activities WHERE score IS NOT NULL
            ) s
        """)
        dist = cursor.fetchone() or {}
        score_distribution = {
            'labels': ['0-59','60-69','70-79','80-89','90-100'],
            'data': [dist.get('b0') or 0, dist.get('b60') or 0, dist.get('b70') or 0, dist.get('b80') or 0, dist.get('b90') or 0]
        }

        # Completion overview
        cursor.execute("SELECT COUNT(*) as total_students FROM students")
        total_students = cursor.fetchone().get('total_students') or 0

        try:
            activity_count = len(get_all_activities())
        except Exception:
            cursor.execute("SELECT COUNT(*) as total_activities FROM activities")
            activity_count = cursor.fetchone().get('total_activities') or 0

        cursor.execute("SELECT SUM(CASE WHEN status = 'checked' THEN 1 ELSE 0 END) as checked, SUM(CASE WHEN status = 'pending_review' THEN 1 ELSE 0 END) as pending FROM student_submissions")
        comp = cursor.fetchone() or {}
        checked = comp.get('checked') or 0
        pending = comp.get('pending') or 0
        total_expected = total_students * activity_count if total_students and activity_count else 0
        not_submitted = max(total_expected - (checked + pending), 0)

        completion_overview = {
            'labels': ['Completed','Pending','Not Started'],
            'data': [checked, pending, not_submitted]
        }

        # Totals and averages
        cursor.execute("SELECT IFNULL(ROUND(AVG(score),1), 0) as average_score FROM activities")
        avg_row = cursor.fetchone() or {}
        average_score = avg_row.get('average_score') or 0

        cursor.execute("SELECT COUNT(*) as total_activities FROM activities")
        ta_row = cursor.fetchone() or {}
        total_activities = ta_row.get('total_activities') or 0

        cursor.execute("SELECT COUNT(*) as total_students FROM students")
        ts_row = cursor.fetchone() or {}
        total_students = ts_row.get('total_students') or 0

        # ===== PENDING TICKETS =====
        cursor.execute("SELECT COUNT(*) as pending FROM tickets WHERE status = 'pending'")
        pending_tickets_row = cursor.fetchone() or {}
        pending_tickets = pending_tickets_row.get('pending') or 0

        # ===== PENDING SUBMISSIONS =====
        cursor.execute("SELECT COUNT(*) as pending_submissions FROM student_submissions WHERE status = 'pending_review'")
        pending_submissions_row = cursor.fetchone() or {}
        pending_submissions = pending_submissions_row.get('pending_submissions') or 0

        # ===== NOTIFICATIONS =====
        cursor.execute("""
            SELECT id, type, title, message, 
                   DATE_FORMAT(created_at, '%Y-%m-%d %H:%i') as time_ago,
                   is_read
            FROM notifications 
            WHERE target_role = 'teacher'
            ORDER BY created_at DESC 
            LIMIT 8
        """)
        notifications = cursor.fetchall()

        # Convert notifications to format expected by frontend
        notif_list = []
        for n in notifications:
            notif_list.append({
                'id': n['id'],
                'title': n['title'],
                'message': n['message'],
                'time_ago': n['time_ago'],
                'read': n['is_read'] == 1,
                'type': n['type']
            })

        # ===== RECENT TICKETS =====
        cursor.execute("""
            SELECT t.id, t.subject, t.status, t.priority,
                   DATE_FORMAT(t.created_at, '%Y-%m-%d %H:%i') as created_at,
                   u.full_name as student_full_name,
                   u.username as student_username
            FROM tickets t
            LEFT JOIN students u ON t.student_id = u.id
            ORDER BY t.created_at DESC
            LIMIT 5
        """)
        recent_tickets = cursor.fetchall()

        conn.close()

        return jsonify({
            'success': True,
            'recent_submissions': recent_subs,
            'score_distribution': score_distribution,
            'completion_overview': completion_overview,
            'total_students': total_students,
            'average_score': average_score,
            'total_activities': total_activities,
            'pending_tickets': pending_tickets,
            'pending_submissions': pending_submissions,
            'notifications': notif_list,
            'recent_tickets': recent_tickets
        })

    except Exception as e:
        print(f"Error getting teacher dashboard data: {e}")
        return jsonify({'success': False, 'message': str(e)})


# ===== CHECK TEACHER UPDATES (REAL-TIME POLLING) =====
@app.route('/check_teacher_updates')
def check_teacher_updates():
    """Check for new teacher notifications and ticket updates"""
    if session.get('role') != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get latest notification timestamp
        cursor.execute("""
            SELECT MAX(created_at) as last_update
            FROM notifications 
            WHERE target_role = 'teacher'
        """)
        notif_result = cursor.fetchone()
        
        # Get latest ticket timestamp
        cursor.execute("""
            SELECT MAX(created_at) as last_update
            FROM tickets
        """)
        ticket_result = cursor.fetchone()

        # Get latest student submission timestamp
        cursor.execute("""
            SELECT MAX(submitted_at) as last_update
            FROM student_submissions
        """)
        submission_result = cursor.fetchone()
        
        # Get pending ticket count
        cursor.execute("SELECT COUNT(*) as pending FROM tickets WHERE status = 'pending'")
        pending_result = cursor.fetchone()

        # Get pending submission count for teacher review
        cursor.execute("SELECT COUNT(*) as pending_submissions FROM student_submissions WHERE status = 'pending_review'")
        pending_submissions_result = cursor.fetchone()
        
        conn.close()
        
        # Get client's last known timestamp
        client_timestamp = request.args.get('last_update')
        
        latest_timestamp = None
        if notif_result and notif_result['last_update']:
            latest_timestamp = notif_result['last_update']
        if ticket_result and ticket_result['last_update']:
            if not latest_timestamp or ticket_result['last_update'] > latest_timestamp:
                latest_timestamp = ticket_result['last_update']
        if submission_result and submission_result['last_update']:
            if not latest_timestamp or submission_result['last_update'] > latest_timestamp:
                latest_timestamp = submission_result['last_update']
        
        has_updates = False
        if client_timestamp and latest_timestamp:
            client_time_str = client_timestamp.replace('T', ' ').replace('Z', '')
            server_time_str = str(latest_timestamp)[:19]
            has_updates = server_time_str > client_time_str
        
        return jsonify({
            'success': True,
            'has_updates': has_updates,
            'pending_tickets': pending_result.get('pending') or 0,
            'pending_submissions': pending_submissions_result.get('pending_submissions') or 0,
            'last_update': str(latest_timestamp) if latest_timestamp else None
        })
        
    except Exception as e:
        print(f"Error checking updates: {e}")
        return jsonify({'success': False, 'message': str(e)})


@app.route('/get_dashboard_data')
def get_dashboard_data():
    """Role-aware dashboard data for shared sidebar and dashboards"""
    role = session.get('role')
    user_id = session.get('user_id')

    try:
        if role == 'teacher':
            # Reuse teacher dashboard logic
            return get_teacher_dashboard_data()

        if role == 'student':
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)

            # Recent submissions for this student
            cursor.execute("""
                SELECT s.id, s.activity_name, s.status, s.score,
                       DATE_FORMAT(s.submitted_at, '%Y-%m-%d %H:%i:%s') as submitted_at
                FROM student_submissions s
                WHERE s.student_id = %s
                ORDER BY s.submitted_at DESC
                LIMIT 6
            """, (user_id,))
            recent_subs = cursor.fetchall()

            # Student activity stats
            cursor.execute("SELECT COUNT(*) as total_activities, IFNULL(ROUND(AVG(score),1),0) as avg_score FROM activities WHERE student_id = %s", (user_id,))
            acts = cursor.fetchone() or {}
            total_activities = acts.get('total_activities') or 0
            average_score = acts.get('avg_score') or 0

            # Ticket counts for this student
            cursor.execute("SELECT SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending, COUNT(*) as total FROM tickets WHERE student_id = %s", (user_id,))
            tcounts = cursor.fetchone() or {}
            pending_tickets = tcounts.get('pending') or 0
            total_tickets = tcounts.get('total') or 0

            # Recent notifications for student
            cursor.execute("SELECT id, title, message, is_read, DATE_FORMAT(created_at, '%Y-%m-%d %H:%i:%s') as created_at FROM notifications WHERE user_id = %s ORDER BY created_at DESC LIMIT 8", (user_id,))
            notes = cursor.fetchall()

            conn.close()

            return jsonify({
                'success': True,
                'recent_submissions': recent_subs,
                'total_activities': total_activities,
                'average_score': average_score,
                'pending_tickets': pending_tickets,
                'total_tickets': total_tickets,
                'notifications': notes
            })

        # Unauthenticated or unknown role
        return jsonify({'success': False, 'message': 'Unauthorized'})

    except Exception as e:
        print(f"Error getting dashboard data: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/teacher_profile', methods=['GET'])
@app.route('/teacher_profile/', methods=['GET'])
@app.route('/teacher/profile', methods=['GET'])
def teacher_profile():
    if session.get('role') != 'teacher':
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT id, username, full_name, email,
                   DATE_FORMAT(created_at, '%B %d, %Y') as created_at
            FROM teachers 
            WHERE id = %s
        """, (session.get('user_id'),))
        teacher = cursor.fetchone() or {}

        cursor.execute("SELECT COUNT(*) as total FROM students")
        ts = cursor.fetchone() or {'total': 0}
        total_students = ts.get('total', 0)

        cursor.execute("""
            SELECT COUNT(*) as total, IFNULL(AVG(score), 0) as avg_score 
            FROM activities
        """)
        stats = cursor.fetchone() or {'total': 0, 'avg_score': 0}
        total_activities = stats.get('total', 0) or 0
        average_score = int(round(stats.get('avg_score', 0) or 0))

        profile_data = {
            'full_name': teacher.get('full_name', ''),
            'username': teacher.get('username', ''),
            'email': teacher.get('email', ''),
            'created_at': teacher.get('created_at', ''),
            'total_students': total_students,
            'total_activities': total_activities,
            'average_score': average_score
        }

        return render_template('teacher_profile.html',
                              teacher=teacher,
                              profile_data=profile_data,
                              total_students=total_students,
                              total_activities=total_activities,
                              average_score=average_score,
                              username=session.get('username'))
    except Exception as e:
        print(f"Teacher profile error: {e}")
        return redirect('/teacher_dashboard')
    finally:
        cursor.close()
        conn.close()

@app.route('/teacher_settings')
def teacher_settings():
    if session.get('role') != 'teacher':
        return redirect('/')
    return render_template('teacher_settings.html', 
                          username=session.get('username'))

@app.route('/teacher_tickets')
@app.route('/teacher_ticktes')
def teacher_tickets():
    if session.get('role') != 'teacher':
        return redirect('/')
    return render_template('teacher_tickets.html', 
                          username=session.get('username'),
                          full_name=session.get('full_name'))

@app.route('/teacher_submissions')
def teacher_submissions_page():
    """Teacher Submissions page for reviewing student work"""
    if session.get('role') != 'teacher':
        return redirect('/')
    return render_template('teacher_submissions.html', 
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
            SELECT lrn, full_name, grade_level, email,
                   DATE_FORMAT(created_at, '%B %d, %Y') as created_at
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
                   DATE_FORMAT(created_at, '%B %d, %Y') as created_at
            FROM teachers WHERE id = %s
        """, (session.get('user_id'),))
        teacher = cursor.fetchone()
        
        cursor.execute("SELECT COUNT(*) as total_students FROM students")
        total_students = cursor.fetchone()['total_students']
        
        cursor.execute("""
            SELECT COUNT(*) as total_activities, IFNULL(ROUND(AVG(score), 0), 0) as avg_score 
            FROM activities
        """)
        stats = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'username': teacher['username'] if teacher else '',
            'full_name': teacher['full_name'] if teacher else '',
            'email': teacher['email'] if teacher else 'teacher@blocklearn.edu.ph',
            'created_at': teacher['created_at'] if teacher else '',
            'total_students': total_students,
            'total_activities': stats['total_activities'] or 0,
            'average_score': stats['avg_score'] or 0
        })
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'success': False, 'message': str(e)})

# ==================== AUTHENTICATION ROUTES ====================

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
                    
            else:  # teacher
                username = data.get('username')
                if not username:
                    return jsonify({'success': False, 'message': 'Username is required for teachers'})
                    
                cursor.execute("SELECT * FROM teachers WHERE LOWER(username) = LOWER(%s)", (username,))
                user = cursor.fetchone()
                
                if user and hash_password(password) == user['password']:
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
            print(f" [SUCCESS] Account created for LRN: {lrn} - Name: {full_name}")
            return jsonify({'success': True, 'message': 'Account created successfully! You can now login.'})
            
        except mysql.connector.IntegrityError as err:
            if err.errno == 1062:
                return jsonify({'success': False, 'message': 'LRN or username already exists'})
            else:
                print(f" [ERROR] IntegrityError: {err}")
                return jsonify({'success': False, 'message': f'Database error: {str(err)}'})
        except mysql.connector.Error as err:
            print(f" [ERROR] MySQL Error: {err}")
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
        print(f" [ERROR] Create account error: {e}")
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
        
        if not all([student_id, activity_name, score is not None]):
            return jsonify({'success': False, 'message': 'Missing required fields'})
        
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
                    SET score = %s, code_blocks = %s, completed_at = %s
                    WHERE student_id = %s AND activity_name = %s
                """, (score, code_blocks, datetime.now(), student_id, activity_name))
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

# ==================== SUBMISSION API ROUTES ====================

@app.route('/submit_activity', methods=['POST'])
def submit_activity():
    """Student submits activity for review"""
    if session.get('role') != 'student':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'message': 'Invalid submission data'}), 400

    student_id = session.get('user_id')
    activity_name = (data.get('activity_name') or '').strip()
    code_blocks = (data.get('code_blocks') or '').strip()
    language = (data.get('language') or 'python').strip() or 'python'

    if not student_id or not activity_name or not code_blocks:
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT id FROM students WHERE id = %s", (student_id,))
        if cursor.fetchone() is None:
            return jsonify({'success': False, 'message': 'Student account not found. Please log in again.'}), 401

        cursor.execute("""
            SELECT id FROM student_submissions 
            WHERE student_id = %s AND activity_name = %s
            ORDER BY submitted_at DESC LIMIT 1
        """, (student_id, activity_name))
        existing = cursor.fetchone()

        if existing:
            cursor.execute("""
                UPDATE student_submissions 
                SET code_blocks = %s, 
                    language = %s, 
                    status = 'pending_review',
                    submitted_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (code_blocks, language, existing['id']))
            submission_id = existing['id']
            is_new = False
        else:
            cursor.execute("""
                INSERT INTO student_submissions 
                (student_id, activity_name, code_blocks, language, status, submitted_at)
                VALUES (%s, %s, %s, %s, 'pending_review', CURRENT_TIMESTAMP)
            """, (student_id, activity_name, code_blocks, language))
            submission_id = cursor.lastrowid
            is_new = True

        conn.commit()

        if is_new:
            cursor.execute("SELECT username, full_name FROM students WHERE id = %s", (student_id,))
            student = cursor.fetchone()
            student_name = student['full_name'] if student and student['full_name'] else student['username'] if student else f"Student #{student_id}"

            cursor.execute("""
                INSERT INTO notifications 
                (target_role, type, title, message, related_id, created_at, is_read)
                VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, 0)
            """, (
                'teacher',
                'submission',
                'New Activity Submission',
                f'{student_name} submitted "{activity_name}" for review.',
                submission_id
            ))
            conn.commit()

        return jsonify({
            'success': True,
            'submission_id': submission_id,
            'is_new': is_new,
            'message': 'Activity submitted for review!'
        })

    except mysql.connector.Error as e:
        print(f"Submit activity DB error: {e}")
        return jsonify({'success': False, 'message': f'Database error: {str(e)}'}), 500
    except Exception as e:
        print(f"Submit activity error: {e}")
        return jsonify({'success': False, 'message': 'Failed to submit activity. Please try again.'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/get_activity_status', methods=['GET'])
def get_activity_status():
    """Get status for a specific activity"""
    if session.get('role') != 'student':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        student_id = session.get('user_id')
        activity_name = request.args.get('activity')
        
        if not activity_name:
            return jsonify({'success': False, 'message': 'Activity name required'})
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            cursor.execute("""
                SELECT status, score, feedback,
                       DATE_FORMAT(submitted_at, '%Y-%m-%d %H:%i') as submitted_at,
                       DATE_FORMAT(reviewed_at, '%Y-%m-%d %H:%i') as reviewed_at
                FROM student_submissions 
                WHERE student_id = %s AND activity_name = %s
                ORDER BY submitted_at DESC LIMIT 1
            """, (student_id, activity_name))
            
            submission = cursor.fetchone()
            
            if submission:
                return jsonify({'success': True, 'status': submission})
            else:
                return jsonify({
                    'success': True, 
                    'status': {
                        'status': 'not_started', 
                        'score': None, 
                        'feedback': None, 
                        'submitted_at': None,
                        'reviewed_at': None
                    }
                })
            
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        print(f"Get activity status error: {e}")
        return jsonify({'success': False, 'message': str(e)})

# ==================== TEACHER SUBMISSION ROUTES ====================

@app.route('/teacher/submissions', methods=['GET'])
def teacher_submissions():
    """Teacher gets all submissions (pending and checked)"""
    if session.get('role') != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # Get pending submissions
            cursor.execute("""
                SELECT 
                    s.id, 
                    s.student_id,
                    u.username,
                    u.full_name as student_name,
                    u.lrn,
                    s.activity_name,
                    s.code_blocks,
                    s.language,
                    DATE_FORMAT(s.submitted_at, '%Y-%m-%d %H:%i') as submitted_at,
                    s.score,
                    s.feedback,
                    s.status
                FROM student_submissions s
                JOIN students u ON s.student_id = u.id
                WHERE s.status = 'pending_review'
                ORDER BY s.submitted_at DESC
            """)
            pending = cursor.fetchall()
            
            # Get checked submissions
            cursor.execute("""
                SELECT 
                    s.id, 
                    s.student_id,
                    u.username,
                    u.full_name as student_name,
                    u.lrn,
                    s.activity_name,
                    s.code_blocks,
                    s.language,
                    DATE_FORMAT(s.submitted_at, '%Y-%m-%d %H:%i') as submitted_at,
                    DATE_FORMAT(s.reviewed_at, '%Y-%m-%d %H:%i') as reviewed_at,
                    s.score,
                    s.feedback,
                    s.status
                FROM student_submissions s
                JOIN students u ON s.student_id = u.id
                WHERE s.status IN ('approved', 'needs_revision')
                ORDER BY s.reviewed_at DESC
            """)
            checked = cursor.fetchall()
            
            # Get counts by status
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM student_submissions
                GROUP BY status
            """)
            counts_data = cursor.fetchall()
            counts = {'pending': 0, 'approved': 0, 'needs_revision': 0, 'total': 0}
            for row in counts_data:
                counts[row['status']] = row['count']
                counts['total'] += row['count']
            
            return jsonify({
                'success': True,
                'pending': pending,
                'checked': checked,
                'total': counts['total'],
                'counts': counts
            })
            
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        print(f"Get teacher submissions error: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/teacher/submission/<int:submission_id>', methods=['GET'])
def teacher_get_submission(submission_id):
    """Teacher gets a specific submission"""
    if session.get('role') != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            cursor.execute("""
                SELECT 
                    s.id, 
                    s.student_id,
                    u.username,
                    u.full_name as student_name,
                    u.lrn,
                    s.activity_name,
                    s.code_blocks,
                    s.language,
                    DATE_FORMAT(s.submitted_at, '%Y-%m-%d %H:%i') as submitted_at,
                    DATE_FORMAT(s.reviewed_at, '%Y-%m-%d %H:%i') as reviewed_at,
                    s.score,
                    s.feedback,
                    s.status
                FROM student_submissions s
                JOIN students u ON s.student_id = u.id
                WHERE s.id = %s
            """, (submission_id,))
            
            submission = cursor.fetchone()
            
            if submission:
                return jsonify({'success': True, 'submission': submission})
            else:
                return jsonify({'success': False, 'message': 'Submission not found'})
            
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        print(f"Get submission error: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/teacher/review_submission', methods=['POST'])
def teacher_review_submission():
    """Teacher reviews a submission"""
    if session.get('role') != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        data = request.json
        submission_id = data.get('submission_id')
        score = data.get('score')
        feedback = data.get('feedback', '')
        status = data.get('status', 'approved')
        
        if not submission_id or score is None:
            return jsonify({'success': False, 'message': 'Missing required fields'})
        
        # Validate score
        try:
            score = int(score)
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid score format'})
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # Get submission info before updating
            cursor.execute("""
                SELECT s.student_id, s.activity_name, u.username, u.full_name
                FROM student_submissions s
                JOIN students u ON s.student_id = u.id
                WHERE s.id = %s
            """, (submission_id,))
            
            submission = cursor.fetchone()
            
            if not submission:
                return jsonify({'success': False, 'message': 'Submission not found'})
            
            activity_name = submission['activity_name']
            max_score = get_max_score(activity_name)
            if score < 0 or score > max_score:
                return jsonify({'success': False, 'message': f'Score must be between 0 and {max_score}'})
            
            # Update submission
            cursor.execute("""
                UPDATE student_submissions 
                SET status = %s, score = %s, feedback = %s, reviewed_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (status, score, feedback, submission_id))
            
            conn.commit()
            
            # Create notification for student
            student_id = submission['student_id']
            if status == 'approved':
                title = 'Activity Approved!'
                message = f'Your "{activity_name}" activity was approved with a score of {score}/{max_score}.'
            else:
                title = 'Activity Needs Revision'
                message = f'Your "{activity_name}" activity needs revision. Feedback: {feedback}'
            
            cursor.execute("""
                INSERT INTO notifications 
                (user_id, type, title, message, created_at, is_read)
                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, 0)
            """, (student_id, 'review_result', title, message))
            
            conn.commit()
            
            return jsonify({
                'success': True,
                'message': f'Submission {status} with score {score}/{max_score}'
            })
            
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        print(f"Review submission error: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/teacher/submissions/pending', methods=['GET'])
def teacher_pending_submissions():
    """Teacher gets pending submissions only"""
    if session.get('role') != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            cursor.execute("""
                SELECT 
                    s.id, 
                    s.student_id,
                    u.username,
                    u.full_name as student_name,
                    u.lrn,
                    s.activity_name,
                    s.code_blocks,
                    s.language,
                    DATE_FORMAT(s.submitted_at, '%Y-%m-%d %H:%i') as submitted_at,
                    s.score,
                    s.feedback
                FROM student_submissions s
                JOIN students u ON s.student_id = u.id
                WHERE s.status = 'pending_review'
                ORDER BY s.submitted_at DESC
            """)
            
            submissions = cursor.fetchall()
            return jsonify({'success': True, 'submissions': submissions})
            
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        print(f"Get pending submissions error: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/teacher/submissions/checked', methods=['GET'])
def teacher_checked_submissions():
    """Teacher gets checked submissions only"""
    if session.get('role') != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            cursor.execute("""
                SELECT 
                    s.id, 
                    s.student_id,
                    u.username,
                    u.full_name as student_name,
                    u.lrn,
                    s.activity_name,
                    s.code_blocks,
                    s.language,
                    DATE_FORMAT(s.submitted_at, '%Y-%m-%d %H:%i') as submitted_at,
                    DATE_FORMAT(s.reviewed_at, '%Y-%m-%d %H:%i') as reviewed_at,
                    s.score,
                    s.feedback,
                    s.status
                FROM student_submissions s
                JOIN students u ON s.student_id = u.id
                WHERE s.status IN ('approved', 'needs_revision')
                ORDER BY s.reviewed_at DESC
            """)
            
            submissions = cursor.fetchall()
            return jsonify({'success': True, 'submissions': submissions})
            
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        print(f"Get checked submissions error: {e}")
        return jsonify({'success': False, 'message': str(e)})

# ==================== NOTIFICATION ROUTES ====================

@app.route('/get_notifications', methods=['GET'])
def get_notifications():
    """Get user notifications"""
    user_id = session.get('user_id')
    role = session.get('role')
    
    if not user_id:
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            if role == 'student':
                cursor.execute("""
                    SELECT id, type, title, message, 
                           DATE_FORMAT(created_at, '%Y-%m-%d %H:%i') as created_at, 
                           is_read
                    FROM notifications 
                    WHERE user_id = %s OR (user_id IS NULL AND target_role = 'student')
                    ORDER BY created_at DESC
                    LIMIT 30
                """, (user_id,))
            else:  # teacher
                cursor.execute("""
                    SELECT id, type, title, message, 
                           DATE_FORMAT(created_at, '%Y-%m-%d %H:%i') as created_at, 
                           is_read
                    FROM notifications 
                    WHERE target_role = 'teacher' OR user_id = %s
                    ORDER BY created_at DESC
                    LIMIT 30
                """, (user_id,))
            
            notifications = cursor.fetchall()
            return jsonify({'success': True, 'notifications': notifications})
            
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        print(f"Get notifications error: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/get_unread_count', methods=['GET'])
def get_unread_count():
    """Get unread notification count"""
    user_id = session.get('user_id')
    role = session.get('role')
    
    if not user_id:
        return jsonify({'success': False, 'count': 0})
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            if role == 'student':
                cursor.execute("""
                    SELECT COUNT(*) FROM notifications 
                    WHERE (user_id = %s OR (user_id IS NULL AND target_role = 'student'))
                    AND is_read = 0
                """, (user_id,))
            else:  # teacher
                cursor.execute("""
                    SELECT COUNT(*) FROM notifications 
                    WHERE (target_role = 'teacher' OR user_id = %s)
                    AND is_read = 0
                """, (user_id,))
            
            count = cursor.fetchone()[0]
            return jsonify({'success': True, 'count': count})
            
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        print(f"Get unread count error: {e}")
        return jsonify({'success': False, 'count': 0})

@app.route('/mark_notification_read', methods=['POST'])
def mark_notification_read():
    """Mark notification as read"""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        data = request.json
        notification_id = data.get('notification_id')
        
        if not notification_id:
            return jsonify({'success': False, 'message': 'Notification ID required'})
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE notifications 
                SET is_read = 1 
                WHERE id = %s
            """, (notification_id,))
            
            conn.commit()
            return jsonify({'success': True, 'message': 'Notification marked as read'})
            
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        print(f"Mark notification read error: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/mark_all_notifications_read', methods=['POST'])
def mark_all_notifications_read():
    """Mark all notifications as read"""
    user_id = session.get('user_id')
    role = session.get('role')
    
    if not user_id:
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            if role == 'student':
                cursor.execute("""
                    UPDATE notifications 
                    SET is_read = 1 
                    WHERE (user_id = %s OR (user_id IS NULL AND target_role = 'student'))
                    AND is_read = 0
                """, (user_id,))
            else:  # teacher
                cursor.execute("""
                    UPDATE notifications 
                    SET is_read = 1 
                    WHERE (target_role = 'teacher' OR user_id = %s)
                    AND is_read = 0
                """, (user_id,))
            
            conn.commit()
            return jsonify({'success': True, 'message': 'All notifications marked as read'})
            
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        print(f"Mark all notifications read error: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/get_recent_submissions', methods=['GET'])
def get_recent_submissions_route():
    """Get recent submissions for dashboard"""
    if session.get('role') != 'student':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        student_id = session.get('user_id')
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            cursor.execute("""
                SELECT id, activity_name, status, score, feedback,
                       DATE_FORMAT(submitted_at, '%Y-%m-%d %H:%i') as submitted_at
                FROM student_submissions 
                WHERE student_id = %s
                ORDER BY submitted_at DESC
                LIMIT 5
            """, (student_id,))
            
            submissions = cursor.fetchall()
            return jsonify({'success': True, 'submissions': submissions})
            
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        print(f"Get recent submissions error: {e}")
        return jsonify({'success': False, 'message': str(e)})

# ==================== GET_PROGRESS ====================

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
            all_activities = get_all_activities()
            total_lessons = len(all_activities)
            
            cursor.execute("""
                SELECT COUNT(DISTINCT activity_name) as completed
                FROM student_submissions
                WHERE student_id = %s
            """, (student_id,))
            completed_result = cursor.fetchone()
            completed = completed_result['completed'] if completed_result else 0
            
            progress = (completed / total_lessons * 100) if total_lessons > 0 else 0
            return jsonify({'success': True, 'progress': progress, 'completed': completed, 'total': total_lessons})
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
            SELECT activity_name, score, status,
                   IFNULL(DATE_FORMAT(reviewed_at, '%Y-%m-%d %H:%i'), DATE_FORMAT(submitted_at, '%Y-%m-%d %H:%i')) as completed_at
            FROM student_submissions 
            WHERE student_id = %s 
            ORDER BY submitted_at DESC 
            LIMIT 5
        """, (student_id,))
        recent = cursor.fetchall() or []
        
        cursor.execute("""
            SELECT COUNT(DISTINCT activity_name) as total,
                   IFNULL(ROUND(AVG(score), 0), 0) as avg_score
            FROM student_submissions 
            WHERE student_id = %s AND score IS NOT NULL
        """, (student_id,))
        stats = cursor.fetchone() or {'avg_score': 0, 'total': 0}
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True, 
            'recent_activities': recent,
            'average_score': round(stats['avg_score'] or 0),
            'total_activities': stats['total'] or 0
        })
    except Exception as e:
        print(f"Error in get_student_stats: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/get_lessons')
def get_lessons():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            cursor.execute("SELECT * FROM lessons ORDER BY order_num, id")
            lessons = cursor.fetchall()
            return jsonify({'success': True, 'lessons': lessons})
        finally:
            cursor.close()
            conn.close()
    except Exception as e:
        print(f"Get lessons error: {e}")
        return jsonify({'success': True, 'lessons': [
            {'id': 1, 'title': ' Activity 1: Say Hello!', 'description': 'Learn basic print statements', 'content': 'Print "Hello World"', 'difficulty': 'Beginner'},
            {'id': 2, 'title': ' Activity 2: Print Your Name', 'description': 'Print your own name', 'content': 'Variables and strings', 'difficulty': 'Beginner'},
            {'id': 3, 'title': ' Activity 3: Simple Math', 'description': 'Perform calculations', 'content': 'Math operations', 'difficulty': 'Beginner'},
            {'id': 4, 'title': ' Activity 4: Using Loops', 'description': 'Repeat actions', 'content': 'Loop structures', 'difficulty': 'Intermediate'}
        ]})

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

@app.route('/complete_lesson', methods=['POST'])
def complete_lesson():
    if session.get('role') != 'student':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        data = request.json
        lesson_title = data.get('lesson_title')
        score = data.get('score', 100)
        
        student_id = session.get('user_id')
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id FROM activities 
            WHERE student_id = %s AND activity_name = %s
        """, (student_id, lesson_title))
        
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO activities (student_id, activity_name, score, completed_at, language)
                VALUES (%s, %s, %s, %s, %s)
            """, (student_id, lesson_title, score, datetime.now(), 'python'))
            conn.commit()
        
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Lesson completed!'})
    except Exception as e:
        print(f"Error in complete_lesson: {e}")
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
            SELECT activity_name, score, language, status, submitted_at
            FROM student_submissions 
            WHERE student_id = %s
            ORDER BY submitted_at DESC
        """, (student_id,))
        completed_rows = cursor.fetchall() or []
        
        latest_submissions = {}
        for row in completed_rows:
            name = row.get('activity_name')
            if not name or name in latest_submissions:
                continue
            latest_submissions[name] = row
        
        all_activities = get_all_activities()
        for activity in all_activities:
            submission = latest_submissions.get(activity['name'])
            activity['completed'] = bool(submission)
            if submission:
                activity['score'] = submission.get('score')
                activity['status'] = submission.get('status')
        
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'activities': all_activities})
        
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
        
        cursor.execute("SELECT COUNT(DISTINCT activity_name) as total FROM student_submissions WHERE student_id = %s AND status = 'approved'", (student_id,))
        completed_count = cursor.fetchone()['total']
        
        cursor.execute("SELECT IFNULL(ROUND(AVG(score), 0), 0) as avg FROM student_submissions WHERE student_id = %s AND score IS NOT NULL AND status = 'approved'", (student_id,))
        avg_score = cursor.fetchone()['avg']
        
        cursor.execute("""
            SELECT COUNT(DISTINCT activity_name) as total FROM student_submissions 
            WHERE student_id = %s AND language = 'python'
        """, (student_id,))
        python_count = cursor.fetchone()['total']
        
        cursor.execute("""
            SELECT COUNT(DISTINCT activity_name) as total FROM student_submissions 
            WHERE student_id = %s AND language = 'javascript'
        """, (student_id,))
        js_count = cursor.fetchone()['total']
        
        cursor.execute("""
            SELECT COUNT(DISTINCT activity_name) as total FROM student_submissions 
            WHERE student_id = %s AND language = 'html'
        """, (student_id,))
        html_count = cursor.fetchone()['total']
        
        achievements = [
            {'id': 1, 'name': 'First Code', 'icon': 'fa-code', 'description': 'Complete your first activity', 'unlocked': completed_count >= 1},
            {'id': 2, 'name': 'Blockly Beginner', 'icon': 'fa-rocket', 'description': 'Complete 3 activities', 'unlocked': completed_count >= 3},
            {'id': 3, 'name': 'Bronze Coder', 'icon': 'fa-medal', 'description': 'Complete 5 activities', 'unlocked': completed_count >= 5},
            {'id': 4, 'name': 'Silver Coder', 'icon': 'fa-medal', 'description': 'Complete 10 activities', 'unlocked': completed_count >= 10},
            {'id': 5, 'name': 'Gold Coder', 'icon': 'fa-crown', 'description': 'Complete 15 activities', 'unlocked': completed_count >= 15},
            {'id': 6, 'name': 'High Achiever', 'icon': 'fa-star', 'description': 'Average score 80% or higher', 'unlocked': avg_score >= 80},
            {'id': 7, 'name': 'Python Master', 'icon': 'fa-python', 'description': 'Complete all Python activities (5)', 'unlocked': python_count >= 5},
            {'id': 8, 'name': 'JS Ninja', 'icon': 'fa-js', 'description': 'Complete all JavaScript activities (4)', 'unlocked': js_count >= 4},
            {'id': 9, 'name': 'HTML Hero', 'icon': 'fa-html5', 'description': 'Complete all HTML activities (4)', 'unlocked': html_count >= 4},
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
            SELECT COUNT(DISTINCT DATE(submitted_at)) as days,
                   COUNT(DISTINCT activity_name) as total_activities,
                   IFNULL(ROUND(AVG(score), 0), 0) as average_score
            FROM student_submissions 
            WHERE student_id = %s 
              AND submitted_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        """, (student_id,))
        stats = cursor.fetchone() or {'days': 0, 'total_activities': 0, 'average_score': 0}
        streak = min(stats['days'] or 0, 7)
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'streak': streak,
            'recent_activity_count': stats['total_activities'] or 0,
            'recent_average_score': stats['average_score'] or 0
        })
        
    except Exception as e:
        print(f"Get dashboard stats error: {e}")
        return jsonify({'success': False, 'streak': 0, 'recent_activity_count': 0, 'recent_average_score': 0})

@app.route('/get_recent_activity')
def get_recent_activity():
    if session.get('role') != 'student':
        return jsonify({'success': False, 'message': 'Unauthorized'})

    try:
        student_id = session.get('user_id')
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT activity_name, status, score, submitted_at
            FROM student_submissions
            WHERE student_id = %s
            ORDER BY submitted_at DESC
            LIMIT 5
        """, (student_id,))
        rows = cursor.fetchall() or []

        activities = []
        now = datetime.now()
        for row in rows:
            submitted_at = row.get('submitted_at')
            time_ago = 'Just now'
            if submitted_at and isinstance(submitted_at, datetime):
                delta = now - submitted_at
                seconds = int(delta.total_seconds())
                if seconds < 60:
                    time_ago = 'Just now'
                elif seconds < 3600:
                    time_ago = f"{seconds // 60}m ago"
                elif seconds < 86400:
                    time_ago = f"{seconds // 3600}h ago"
                elif seconds < 604800:
                    time_ago = f"{seconds // 86400}d ago"
                else:
                    time_ago = submitted_at.strftime('%b %d')

            activities.append({
                'title': row.get('activity_name') or 'Activity',
                'score': row.get('score'),
                'status': row.get('status'),
                'time_ago': time_ago
            })

        cursor.close()
        conn.close()
        return jsonify({'success': True, 'activities': activities})
    except Exception as e:
        print(f"Get recent activity error: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/get_activity_progress')
def get_activity_progress():
    if session.get('role') != 'student':
        return jsonify({'success': False})
    
    try:
        student_id = session.get('user_id')
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        all_activities = get_all_activities()
        language_totals = {
            'python': 6,
            'javascript': 4,
            'html': 4,
        }
        activity_language_map = {
            activity['name']: activity.get('language')
            for activity in all_activities
            if activity.get('language') in language_totals
        }

        cursor.execute("""
            SELECT DISTINCT activity_name, language
            FROM student_submissions 
            WHERE student_id = %s
        """, (student_id,))
        completed_rows = cursor.fetchall() or []
        
        completed_counts = {lang: 0 for lang in language_totals}
        seen_activity_names = set()

        for row in completed_rows:
            activity_name = row.get('activity_name')
            if not activity_name or activity_name in seen_activity_names:
                continue

            lang = row.get('language')
            if lang not in language_totals:
                lang = activity_language_map.get(activity_name)

            if lang in language_totals:
                completed_counts[lang] += 1
                seen_activity_names.add(activity_name)
        
        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'python': {'completed': completed_counts['python'], 'total': language_totals['python']},
            'javascript': {'completed': completed_counts['javascript'], 'total': language_totals['javascript']},
            'html': {'completed': completed_counts['html'], 'total': language_totals['html']}
        })
        
    except Exception as e:
        print(f"Get activity progress error: {e}")
        return jsonify({'success': False})

# ==================== TICKET API ROUTES ====================

# Import ticket functions (if they exist in backend)
try:
    from backend.tickets import (
        create_ticket, get_student_tickets, get_all_tickets,
        get_ticket_by_id, update_ticket_status, get_ticket_counts,
        create_ticket_notification
    )
except ImportError:
    # Fallback implementations if backend.tickets doesn't exist
    def create_ticket(student_id, student_name, subject, message, priority):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO tickets (student_id, student_name, subject, message, priority, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (student_id, student_name, subject, message, priority, datetime.now()))
            conn.commit()
            return {'success': True, 'message': 'Ticket created successfully'}
        except Exception as e:
            print(f"Create ticket error: {e}")
            return {'success': False, 'message': str(e)}
        finally:
            cursor.close()
            conn.close()
    
    def get_student_tickets(student_id):
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT id, subject, message, status, priority,
                       DATE_FORMAT(created_at, '%Y-%m-%d %H:%i') as created_at
                FROM tickets
                WHERE student_id = %s
                ORDER BY created_at DESC
            """, (student_id,))
            tickets = cursor.fetchall()
            return {'success': True, 'tickets': tickets}
        except Exception as e:
            return {'success': False, 'message': str(e)}
        finally:
            cursor.close()
            conn.close()
    
    def get_all_tickets(status_filter=None):
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            if status_filter:
                cursor.execute("""
                    SELECT t.*, 
                           DATE_FORMAT(t.created_at, '%Y-%m-%d %H:%i') as created_at
                    FROM tickets t
                    WHERE t.status = %s
                    ORDER BY t.created_at DESC
                """, (status_filter,))
            else:
                cursor.execute("""
                    SELECT t.*, 
                           DATE_FORMAT(t.created_at, '%Y-%m-%d %H:%i') as created_at
                    FROM tickets t
                    ORDER BY t.created_at DESC
                """)
            tickets = cursor.fetchall()
            return {'success': True, 'tickets': tickets}
        except Exception as e:
            return {'success': False, 'message': str(e)}
        finally:
            cursor.close()
            conn.close()
    
    def update_ticket_status(ticket_id, status):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE tickets 
                SET status = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (status, ticket_id))
            conn.commit()
            return {'success': True, 'message': 'Ticket updated successfully'}
        except Exception as e:
            return {'success': False, 'message': str(e)}
        finally:
            cursor.close()
            conn.close()
    
    def get_ticket_counts():
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM tickets
                GROUP BY status
            """)
            counts = cursor.fetchall()
            result = {'pending': 0, 'in_progress': 0, 'resolved': 0, 'closed': 0}
            for row in counts:
                result[row['status']] = row['count']
            return {'success': True, 'counts': result}
        except Exception as e:
            return {'success': False, 'message': str(e)}
        finally:
            cursor.close()
            conn.close()

    def create_ticket_notification(ticket_id, student_id, subject, status, student_name=None):
        if not ticket_id or not student_id:
            return {'success': False, 'message': 'Missing ticket or student'}
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            status_label = {
                'pending': 'pending',
                'in_progress': 'in progress',
                'resolved': 'resolved',
                'closed': 'closed'
            }.get(status, status or 'updated')
            message = f"Your ticket '{subject or 'ticket'}' is now {status_label}."
            if student_name:
                message = f"Hi {student_name}, your ticket '{subject or 'ticket'}' is now {status_label}."
            cursor.execute("""
                INSERT INTO notifications (user_id, target_role, type, title, message, related_id, is_read, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (student_id, 'student', 'ticket_update', 'Ticket status updated', message, ticket_id, 0, datetime.now()))
            conn.commit()
            return {'success': True, 'message': 'Notification created'}
        except Exception as e:
            print(f"Create ticket notification error: {e}")
            return {'success': False, 'message': str(e)}
        finally:
            cursor.close()
            conn.close()

@app.route('/submit_ticket', methods=['POST'])
def submit_ticket():
    if session.get('role') != 'student':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        data = request.json
        subject = data.get('subject')
        message = data.get('message')
        priority = data.get('priority', 'medium')
        
        if not subject or not message:
            return jsonify({'success': False, 'message': 'Subject and message are required'})
        
        student_id = session.get('user_id')
        student_name = session.get('full_name') or session.get('username')
        
        result = create_ticket(student_id, student_name, subject, message, priority)
        return jsonify(result)
        
    except Exception as e:
        print(f"Error submitting ticket: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/get_tickets')
def get_tickets():
    if session.get('role') not in ['student', 'teacher']:
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        if session.get('role') == 'student':
            student_id = session.get('user_id')
            result = get_student_tickets(student_id)
        else:
            status_filter = request.args.get('status')
            result = get_all_tickets(status_filter)
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Error getting tickets: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/update_ticket', methods=['POST'])
def update_ticket():
    if session.get('role') != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        data = request.json
        ticket_id = data.get('ticket_id')
        status = data.get('status')
        
        if not ticket_id:
            return jsonify({'success': False, 'message': 'Ticket ID required'})
        
        result = update_ticket_status(ticket_id, status)
        if result.get('success'):
            ticket_result = get_ticket_by_id(ticket_id)
            if ticket_result.get('success') and ticket_result.get('ticket'):
                ticket = ticket_result['ticket']
                student_id = ticket.get('student_id')
                subject = ticket.get('subject') or 'ticket'
                student_name = ticket.get('student_name') or ticket.get('student_full_name') or ticket.get('student_username') or ''
                if student_id:
                    create_ticket_notification(ticket_id, student_id, subject, status, student_name)
        return jsonify(result)
        
    except Exception as e:
        print(f"Error updating ticket: {e}")
        return jsonify({'success': False, 'message': str(e)})


# ==================== UPDATED GET_TICKET_COUNT ====================
@app.route('/get_ticket_count')
def get_ticket_count():
    if session.get('role') != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get counts by status
        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM tickets
            GROUP BY status
        """)
        counts_data = cursor.fetchall()
        
        # Initialize with zeros
        result = {
            'pending': 0,
            'in_progress': 0,
            'resolved': 0,
            'closed': 0,
            'total': 0
        }
        
        for row in counts_data:
            status = row['status']
            count = row['count']
            if status in result:
                result[status] = count
            result['total'] += count
        
        cursor.close()
        conn.close()
        
        # Return both formats for compatibility
        return jsonify({
            'success': True,
            'pending': result['pending'],
            'in_progress': result['in_progress'],
            'resolved': result['resolved'],
            'closed': result['closed'],
            'total': result['total'],
            'counts': result  # For backward compatibility
        })
        
    except Exception as e:
        print(f"Error getting ticket count: {e}")
        return jsonify({
            'success': False,
            'message': str(e),
            'pending': 0,
            'resolved': 0,
            'total': 0,
            'counts': {'pending': 0, 'resolved': 0, 'total': 0}
        })


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
                    s.email,
                    DATE_FORMAT(s.created_at, '%Y-%m-%d') as created_at,
                    (SELECT COUNT(*) FROM student_submissions WHERE student_id = s.id) as activity_count,
                    (SELECT COUNT(*) > 0 FROM student_submissions WHERE student_id = s.id) as has_activities
                FROM students s
                ORDER BY s.created_at DESC
            """)
            students = cursor.fetchall()
            
            for student in students:
                student['has_activities'] = student['activity_count'] > 0
            
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
                    a.activity_name, 
                    a.score, 
                    a.language,
                    DATE_FORMAT(a.completed_at, '%Y-%m-%d %H:%i') as completed_at
                FROM activities a
                JOIN students s ON a.student_id = s.id
                ORDER BY a.completed_at DESC
                LIMIT 100
            """)
            scores = cursor.fetchall()
            
            print(f" Retrieved {len(scores)} scores")
            
            return jsonify({'success': True, 'scores': scores})
        finally:
            cursor.close()
            conn.close()
    except Exception as e:
        print(f" Get scores error: {e}")
        return jsonify({'success': False, 'message': 'Failed to retrieve scores'})

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
                SELECT s.full_name as student_name,
                       s.lrn,
                       s.grade_level,
                       COUNT(ss.id) as total_activities,
                       IFNULL(ROUND(AVG(CASE WHEN ss.status = 'approved' AND ss.score IS NOT NULL THEN ss.score END), 1), 0) as average_score,
                       SUM(CASE WHEN ss.status = 'approved' AND ss.score IS NOT NULL AND ss.score < 50 THEN 1 ELSE 0 END) as low_scores,
                       GROUP_CONCAT(CASE WHEN ss.status = 'approved' AND ss.score IS NOT NULL THEN ss.score END ORDER BY ss.submitted_at DESC SEPARATOR ', ') as scores
                FROM students s
                LEFT JOIN student_submissions ss 
                    ON s.id = ss.student_id
                GROUP BY s.id
                ORDER BY average_score DESC
            """)
            reports = cursor.fetchall()

            cursor.execute("""
                SELECT
                    COUNT(*) as total_submissions,
                    IFNULL(ROUND(AVG(score), 1), 0) as class_average,
                    SUM(CASE WHEN score >= 70 THEN 1 ELSE 0 END) as passing_count,
                    SUM(CASE WHEN score IS NOT NULL THEN 1 ELSE 0 END) as scored_count
                FROM student_submissions
            """)
            summary = cursor.fetchone() or {}
            total_submissions = summary.get('total_submissions') or 0
            class_average = summary.get('class_average') or 0
            scored_count = summary.get('scored_count') or 0
            passing_count = summary.get('passing_count') or 0
            passing_rate = round((passing_count / scored_count) * 100) if scored_count > 0 else 0

            cursor.execute("SELECT COUNT(*) as total_students FROM students")
            total_students = cursor.fetchone().get('total_students') or 0

            return jsonify({
                'success': True,
                'reports': reports,
                'total_students': total_students,
                'total_submissions': total_submissions,
                'class_average': class_average,
                'passing_rate': passing_rate
            })
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
                   DATE_FORMAT(created_at, '%B %d, %Y') as joined_date
            FROM students WHERE lrn = %s
        """, (lrn,))
        student = cursor.fetchone()
        
        if not student:
            return jsonify({'success': False, 'message': 'Student not found'})
        
        cursor.execute("""
            SELECT activity_name, score, language,
                   DATE_FORMAT(completed_at, '%Y-%m-%d %H:%i') as completed_at
            FROM activities WHERE student_id = %s
            ORDER BY completed_at DESC
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
            SELECT s.lrn as student_name,
                   COUNT(a.id) as activities_completed,
                   IFNULL(ROUND(AVG(a.score)), 0) as average_score
            FROM students s
            LEFT JOIN activities a ON s.id = a.student_id
            GROUP BY s.id
            HAVING activities_completed > 0
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

# ==================== REAL-TIME STATUS UPDATE ENDPOINT ====================

@app.route('/check_student_updates', methods=['GET'])
def check_student_updates():
    """Check if there are any updates to student data (for real-time polling)"""
    if session.get('role') != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        # Get the last activity timestamp from the database
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT MAX(completed_at) as last_activity
            FROM activities
        """)
        result = cursor.fetchone()
        last_activity = result['last_activity'] if result else None
        
        cursor.close()
        conn.close()
        
        # Get the client's last known timestamp from query parameter
        client_timestamp = request.args.get('last_update')
        
        has_updates = False
        if client_timestamp and last_activity:
            # Convert to string for comparison
            client_time_str = client_timestamp.replace('T', ' ').replace('Z', '')
            server_time_str = str(last_activity)[:19]
            
            # Compare timestamps
            has_updates = server_time_str > client_time_str
        
        return jsonify({
            'success': True,
            'has_updates': has_updates,
            'last_activity': str(last_activity) if last_activity else None
        })
        
    except Exception as e:
        print(f"Check student updates error: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/get_students_with_status', methods=['GET'])
def get_students_with_status():
    """Get students with their activity status (for real-time updates)"""
    if session.get('role') != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                s.id,
                s.lrn,
                s.full_name,
                s.grade_level,
                s.email,
                DATE_FORMAT(s.created_at, '%Y-%m-%d') as created_at,
                (SELECT COUNT(*) FROM activities WHERE student_id = s.id) as activity_count,
                (SELECT COUNT(*) > 0 FROM activities WHERE student_id = s.id) as has_activities,
                (SELECT MAX(completed_at) FROM activities WHERE student_id = s.id) as last_activity
            FROM students s
            ORDER BY s.created_at DESC
        """)
        students = cursor.fetchall()
        
        for student in students:
            student['has_activities'] = student['activity_count'] > 0
            if student['last_activity']:
                student['last_activity'] = str(student['last_activity'])[:19]
        
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'students': students})
        
    except Exception as e:
        print(f"Get students with status error: {e}")
        return jsonify({'success': False, 'message': 'Failed to retrieve students'})

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
    print('Run the app and open http://127.0.0.1:5000')
    print('=' * 60)
    
    # Run without the interactive debugger to avoid debugger resource requests/log noise
    app.run(debug=False, host='127.0.0.1', port=5000)