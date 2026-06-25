# app.py - Main Flask Application for Blockly Learning Platform
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
from flask_cors import CORS
import mysql.connector
import hashlib
from datetime import datetime
import os
import re

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'frontend')
STATIC_DIR = os.path.join(BASE_DIR, 'static')

app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
app.secret_key = 'your-secret-key-change-this-in-production-2024'
CORS(app)


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
        
        # Insert default lessons if none exist
        cursor.execute("SELECT COUNT(*) AS lesson_count FROM lessons")
        lesson_count = cursor.fetchone().get('lesson_count', 0)
        if lesson_count == 0:
            default_lessons = [
                (1, "📢 Activity 1: Say Hello!", "Learn to print 'Hello World' using Blockly", "Print statement basics", "Beginner", 1),
                (2, "👤 Activity 2: Print Your Name", "Print your own name using variables", "Variables and strings", "Beginner", 2),
                (3, "➕ Activity 3: Simple Math", "Perform addition and print the result", "Math operations", "Beginner", 3),
                (4, "🔄 Activity 4: Using Loops", "Repeat actions using loops", "Loop structures", "Intermediate", 4)
            ]
            cursor.executemany(
                "INSERT INTO lessons (id, title, description, content, difficulty, order_num) VALUES (%s, %s, %s, %s, %s, %s)",
                default_lessons
            )
        
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
            teacher1_password = hash_password("teacher123")
            cursor.execute("""
                INSERT INTO teachers (username, password, full_name, email, created_at) 
                VALUES (%s, %s, %s, %s, %s)
            """, ("teacher1", teacher1_password, "Teacher One", "teacher1@blocklearn.edu.ph", datetime.now()))
            print("✅ Teacher account created: username='teacher1', password='teacher123'")
        else:
            teacher1_password = hash_password("teacher123")
            if teacher1_row['username'] != 'teacher1':
                cursor.execute("UPDATE teachers SET username = %s WHERE id = %s", ("teacher1", teacher1_row['id']))
                print("ℹ️ Normalized existing teacher1 username to lowercase")
            if teacher1_row['password'] != teacher1_password:
                cursor.execute("UPDATE teachers SET password = %s WHERE id = %s", (teacher1_password, teacher1_row['id']))
                print("ℹ️ Updated teacher1 password to the provided default")
            print("ℹ️ Teacher1 account already exists")
        
        conn.commit()
        print("✅ Database initialized successfully!")
        
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
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

@app.route('/registeracc')
def registeracc():
    return render_template('registeracc.html')

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

@app.route('/student_activities')
def student_activities():
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
    return render_template('teacher_students.html', 
                          username=session.get('username'),
                          full_name=session.get('full_name'))

@app.route('/teacher_scores')
def teacher_scores():
    if session.get('role') != 'teacher':
        return redirect('/')
    return render_template('teacher_scores.html', 
                          username=session.get('username'))

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
    return render_template('teacher_reports_analytics.html', 
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
                   DATE_FORMAT(created_at, '%B %d, %Y') as created_at
            FROM teachers 
            WHERE id = %s
        """, (session.get('user_id'),))
        teacher = cursor.fetchone()
        
        cursor.execute("SELECT COUNT(*) as total FROM students")
        total_students = cursor.fetchone()['total']
        
        cursor.execute("""
            SELECT COUNT(*) as total, IFNULL(AVG(score), 0) as avg_score 
            FROM activities
        """)
        stats = cursor.fetchone()
        total_activities = stats['total'] if stats['total'] else 0
        average_score = round(stats['avg_score']) if stats['avg_score'] else 0
        
        return render_template('teacher_profile.html', 
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
    return render_template('teacher_settings.html', 
                          username=session.get('username'))

@app.route('/teacher_tickets')
def teacher_tickets():
    if session.get('role') != 'teacher':
        return redirect('/')
    return render_template('teacher_tickets.html', 
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
            'email': teacher['email'] if teacher else 'admin@blocklearn.edu.ph',
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
            cursor.execute("SELECT COUNT(*) as total FROM lessons")
            total_result = cursor.fetchone()
            total_lessons = total_result['total'] if total_result else 4
            
            cursor.execute("""
                SELECT COUNT(DISTINCT activity_name) as completed
                FROM activities
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
            SELECT activity_name, score, 
                   DATE_FORMAT(completed_at, '%Y-%m-%d %H:%i') as completed_at
            FROM activities 
            WHERE student_id = %s 
            ORDER BY completed_at DESC 
            LIMIT 5
        """, (student_id,))
        recent = cursor.fetchall()
        
        cursor.execute("""
            SELECT IFNULL(AVG(score), 0) as avg_score, COUNT(*) as total
            FROM activities 
            WHERE student_id = %s
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
            {'id': 1, 'title': '📢 Activity 1: Say Hello!', 'description': 'Learn basic print statements', 'content': 'Print "Hello World"', 'difficulty': 'Beginner'},
            {'id': 2, 'title': '👤 Activity 2: Print Your Name', 'description': 'Print your own name', 'content': 'Variables and strings', 'difficulty': 'Beginner'},
            {'id': 3, 'title': '➕ Activity 3: Simple Math', 'description': 'Perform calculations', 'content': 'Math operations', 'difficulty': 'Beginner'},
            {'id': 4, 'title': '🔄 Activity 4: Using Loops', 'description': 'Repeat actions', 'content': 'Loop structures', 'difficulty': 'Intermediate'}
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
            SELECT activity_name, score, completed_at 
            FROM activities 
            WHERE student_id = %s
        """, (student_id,))
        completed = cursor.fetchall()
        
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
        ]
        
        completed_names = [c['activity_name'] for c in completed]
        for activity in all_activities:
            activity['completed'] = activity['name'] in completed_names
            if activity['completed']:
                comp = next((c for c in completed if c['activity_name'] == activity['name']), None)
                if comp:
                    activity['score'] = comp['score']
        
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
        
        cursor.execute("SELECT COUNT(*) as total FROM activities WHERE student_id = %s", (student_id,))
        completed_count = cursor.fetchone()['total']
        
        cursor.execute("SELECT IFNULL(AVG(score), 0) as avg FROM activities WHERE student_id = %s", (student_id,))
        avg_score = cursor.fetchone()['avg']
        
        cursor.execute("""
            SELECT COUNT(*) as total FROM activities 
            WHERE student_id = %s AND language = 'python'
        """, (student_id,))
        python_count = cursor.fetchone()['total']
        
        cursor.execute("""
            SELECT COUNT(*) as total FROM activities 
            WHERE student_id = %s AND language = 'javascript'
        """, (student_id,))
        js_count = cursor.fetchone()['total']
        
        cursor.execute("""
            SELECT COUNT(*) as total FROM activities 
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
        return jsonify({'success': False})
    
    try:
        student_id = session.get('user_id')
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT language, COUNT(*) as completed
            FROM activities 
            WHERE student_id = %s
            GROUP BY language
        """, (student_id,))
        lang_stats = cursor.fetchall()
        
        python_count = 0
        js_count = 0
        html_count = 0
        
        for stat in lang_stats:
            if stat['language'] == 'python':
                python_count = stat['completed']
            elif stat['language'] == 'javascript':
                js_count = stat['completed']
            elif stat['language'] == 'html':
                html_count = stat['completed']
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'python': {'completed': python_count, 'total': 6},
            'javascript': {'completed': js_count, 'total': 3},
            'html': {'completed': html_count, 'total': 2}
        })
        
    except Exception as e:
        print(f"Get activity progress error: {e}")
        return jsonify({'success': False})

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
        
        if not subject or not message:
            return jsonify({'success': False, 'message': 'Subject and message are required'})
        
        student_id = session.get('user_id')
        student_name = session.get('username')
        
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
                    s.email,
                    DATE_FORMAT(s.created_at, '%Y-%m-%d') as created_at,
                    (SELECT COUNT(*) FROM activities WHERE student_id = s.id) as activity_count,
                    (SELECT COUNT(*) > 0 FROM activities WHERE student_id = s.id) as has_activities
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
            
            print(f"📊 Retrieved {len(scores)} scores")
            
            return jsonify({'success': True, 'scores': scores})
        finally:
            cursor.close()
            conn.close()
    except Exception as e:
        print(f"❌ Get scores error: {e}")
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
                SELECT s.lrn as student_name, s.grade_level,
                       COUNT(a.id) as total_activities,
                       IFNULL(ROUND(AVG(a.score), 1), 0) as average_score,
                       SUM(CASE WHEN a.score < 50 THEN 1 ELSE 0 END) as low_scores
                FROM students s
                LEFT JOIN activities a ON s.id = a.student_id
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