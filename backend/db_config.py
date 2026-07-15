# backend/db_config.py - Database Configuration with Submission Functions

import mysql.connector
from mysql.connector import Error
from datetime import datetime

# Database configuration
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'C@ryll025',
    'database': 'blocklypnhsproject'
}

def get_db_connection():
    """Create and return a database connection"""
    try:
        return mysql.connector.connect(**db_config)
    except mysql.connector.Error as err:
        print(f"Database connection error: {err}")
        raise Exception("Database connection failed")

def test_connection():
    """Test database connection"""
    try:
        conn = get_db_connection()
        if conn.is_connected():
            print(f"Connected to database: {db_config['database']}")
            conn.close()
            return True
    except Exception as e:
        print(f"Connection failed: {e}")
        return False

# ===== SUBMISSION FUNCTIONS =====

def save_submission(student_id, activity_name, code_blocks, language='python'):
    """
    Save student's activity submission
    
    Args:
        student_id (int): Student's user ID
        activity_name (str): Name of the activity
        code_blocks (str): The Python code/blockly XML
        language (str): Programming language
    
    Returns:
        dict: {success: bool, submission_id: int, message: str}
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Check if student already submitted this activity
        cursor.execute('''
            SELECT id, status FROM student_submissions 
            WHERE student_id = %s AND activity_name = %s
            ORDER BY submitted_at DESC LIMIT 1
        ''', (student_id, activity_name))
        
        existing = cursor.fetchone()
        
        if existing:
            # Update existing submission (resubmit)
            cursor.execute('''
                UPDATE student_submissions 
                SET code_blocks = %s, 
                    language = %s, 
                    status = 'pending_review',
                    submitted_at = CURRENT_TIMESTAMP
                WHERE id = %s
            ''', (code_blocks, language, existing['id']))
            
            submission_id = existing['id']
            is_new = False
        else:
            # Insert new submission
            cursor.execute('''
                INSERT INTO student_submissions 
                (student_id, activity_name, code_blocks, language, status, submitted_at)
                VALUES (%s, %s, %s, %s, 'pending_review', CURRENT_TIMESTAMP)
            ''', (student_id, activity_name, code_blocks, language))
            
            submission_id = cursor.lastrowid
            is_new = True
        
        conn.commit()
        conn.close()
        
        # Create notification for teachers
        if is_new:
            create_teacher_notification(student_id, activity_name, submission_id)
        
        return {
            'success': True,
            'submission_id': submission_id,
            'is_new': is_new,
            'message': 'Activity submitted successfully!'
        }
        
    except mysql.connector.Error as e:
        print(f"Error saving submission: {e}")
        return {
            'success': False,
            'message': f'Database error: {str(e)}'
        }


def get_student_submissions(student_id, activity_name=None):
    """
    Get student's submission history
    
    Returns:
        list: Submissions with status and details
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        if activity_name:
            cursor.execute('''
                SELECT id, activity_name, code_blocks, language, status, 
                       submitted_at, score, feedback
                FROM student_submissions 
                WHERE student_id = %s AND activity_name = %s
                ORDER BY submitted_at DESC
            ''', (student_id, activity_name))
        else:
            cursor.execute('''
                SELECT id, activity_name, code_blocks, language, status, 
                       submitted_at, score, feedback
                FROM student_submissions 
                WHERE student_id = %s
                ORDER BY submitted_at DESC
            ''', (student_id,))
        
        submissions = cursor.fetchall()
        conn.close()
        
        # Convert datetime objects to string
        for sub in submissions:
            if sub['submitted_at']:
                sub['submitted_at'] = sub['submitted_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        return submissions
        
    except mysql.connector.Error as e:
        print(f"Error getting submissions: {e}")
        return []


def get_activity_status(student_id, activity_name):
    """
    Get student's current status for a specific activity
    
    Returns:
        dict: {status: str, score: int, feedback: str, submitted_at: str}
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute('''
            SELECT status, score, feedback, submitted_at
            FROM student_submissions 
            WHERE student_id = %s AND activity_name = %s
            ORDER BY submitted_at DESC LIMIT 1
        ''', (student_id, activity_name))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'status': row['status'],
                'score': row['score'],
                'feedback': row['feedback'],
                'submitted_at': row['submitted_at'].strftime('%Y-%m-%d %H:%M:%S') if row['submitted_at'] else None
            }
        else:
            return {
                'status': 'not_started',
                'score': None,
                'feedback': None,
                'submitted_at': None
            }
            
    except mysql.connector.Error as e:
        print(f"Error getting activity status: {e}")
        return {'status': 'error', 'message': str(e)}


def get_pending_submissions_for_teachers():
    """
    Get all pending submissions for teacher review
    
    Returns:
        list: Pending submissions with student details
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute('''
            SELECT 
                s.id, 
                s.student_id,
                u.username,
                u.name as student_name,
                s.activity_name,
                s.code_blocks,
                s.language,
                s.submitted_at,
                s.score,
                s.feedback
            FROM student_submissions s
            JOIN users u ON s.student_id = u.id
            WHERE s.status = 'pending_review'
            ORDER BY s.submitted_at DESC
        ''')
        
        submissions = cursor.fetchall()
        conn.close()
        
        # Convert datetime to string
        for sub in submissions:
            if sub['submitted_at']:
                sub['submitted_at'] = sub['submitted_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        return submissions
        
    except mysql.connector.Error as e:
        print(f"Error getting pending submissions: {e}")
        return []


def review_submission(submission_id, score, feedback, status='approved'):
    """
    Teacher reviews a student submission
    
    Args:
        submission_id (int): Submission ID
        score (int): Score (0-100)
        feedback (str): Teacher's feedback
        status (str): 'approved' or 'rejected'
    
    Returns:
        dict: {success: bool, message: str}
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute('''
            UPDATE student_submissions 
            SET status = %s, 
                score = %s, 
                feedback = %s,
                reviewed_at = CURRENT_TIMESTAMP
            WHERE id = %s
        ''', (status, score, feedback, submission_id))
        
        conn.commit()
        
        # Get student info for notification
        cursor.execute('''
            SELECT s.student_id, s.activity_name, u.username
            FROM student_submissions s
            JOIN users u ON s.student_id = u.id
            WHERE s.id = %s
        ''', (submission_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            create_student_notification(
                row['student_id'], 
                row['activity_name'], 
                status, 
                score, 
                feedback
            )
        
        return {
            'success': True,
            'message': f'Submission {status} with score {score}'
        }
        
    except mysql.connector.Error as e:
        return {
            'success': False,
            'message': f'Error reviewing submission: {str(e)}'
        }


def get_all_student_submissions_for_teacher(teacher_id=None):
    """
    Get all student submissions for teacher's dashboard
    
    Returns:
        list: All submissions grouped by student
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute('''
            SELECT 
                s.id,
                s.student_id,
                u.username,
                u.name as student_name,
                u.grade_level,
                s.activity_name,
                s.language,
                s.status,
                s.score,
                s.feedback,
                s.submitted_at,
                s.reviewed_at
            FROM student_submissions s
            JOIN users u ON s.student_id = u.id
            WHERE u.role = 'student'
            ORDER BY s.submitted_at DESC
        ''')
        
        submissions = cursor.fetchall()
        conn.close()
        
        # Convert datetime to string
        for sub in submissions:
            if sub['submitted_at']:
                sub['submitted_at'] = sub['submitted_at'].strftime('%Y-%m-%d %H:%M:%S')
            if sub['reviewed_at']:
                sub['reviewed_at'] = sub['reviewed_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        return submissions
        
    except mysql.connector.Error as e:
        print(f"Error getting all submissions: {e}")
        return []


# ===== NOTIFICATION FUNCTIONS =====

def create_teacher_notification(student_id, activity_name, submission_id):
    """Create notification for teachers when student submits"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get student name
        cursor.execute('SELECT username, name FROM users WHERE id = %s', (student_id,))
        student = cursor.fetchone()
        student_name = student[1] if student and student[1] else student[0] if student else f"Student #{student_id}"
        
        # Insert notification
        cursor.execute('''
            INSERT INTO notifications 
            (type, title, message, target_role, related_id, created_at, is_read)
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, 0)
        ''', (
            'submission',
            ' New Activity Submission',
            f'{student_name} submitted "{activity_name}" for review.',
            'teacher',
            submission_id
        ))
        
        conn.commit()
        conn.close()
        return True
        
    except mysql.connector.Error as e:
        print(f"Error creating teacher notification: {e}")
        return False


def create_student_notification(student_id, activity_name, status, score, feedback):
    """Notify student about review result"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if status == 'approved':
            title = ' Activity Approved!'
            message = f'Your "{activity_name}" activity was approved with a score of {score}/100.'
        else:
            title = ' Activity Needs Revision'
            message = f'Your "{activity_name}" activity needs revision. Feedback: {feedback}'
        
        cursor.execute('''
            INSERT INTO notifications 
            (user_id, type, title, message, created_at, is_read)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, 0)
        ''', (student_id, 'review_result', title, message))
        
        conn.commit()
        conn.close()
        return True
        
    except mysql.connector.Error as e:
        print(f"Error creating student notification: {e}")
        return False


def get_student_notifications(student_id):
    """Get student's notifications"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute('''
            SELECT id, type, title, message, created_at, is_read
            FROM notifications 
            WHERE user_id = %s OR (user_id IS NULL AND target_role = 'student')
            ORDER BY created_at DESC
            LIMIT 30
        ''', (student_id,))
        
        notifications = cursor.fetchall()
        conn.close()
        
        # Convert datetime to string
        for notif in notifications:
            if notif['created_at']:
                notif['created_at'] = notif['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        return notifications
        
    except mysql.connector.Error as e:
        print(f"Error getting notifications: {e}")
        return []


def get_teacher_notifications(teacher_id):
    """Get teacher's notifications"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute('''
            SELECT id, type, title, message, created_at, is_read, related_id
            FROM notifications 
            WHERE target_role = 'teacher' OR user_id = %s
            ORDER BY created_at DESC
            LIMIT 30
        ''', (teacher_id,))
        
        notifications = cursor.fetchall()
        conn.close()
        
        # Convert datetime to string
        for notif in notifications:
            if notif['created_at']:
                notif['created_at'] = notif['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        return notifications
        
    except mysql.connector.Error as e:
        print(f"Error getting teacher notifications: {e}")
        return []


def get_unread_notification_count(user_id, target_role=None):
    """Get count of unread notifications for user"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if target_role:
            cursor.execute('''
                SELECT COUNT(*) 
                FROM notifications 
                WHERE (user_id = %s OR (user_id IS NULL AND target_role = %s))
                AND is_read = 0
            ''', (user_id, target_role))
        else:
            cursor.execute('''
                SELECT COUNT(*) 
                FROM notifications 
                WHERE user_id = %s
                AND is_read = 0
            ''', (user_id,))
        
        count = cursor.fetchone()[0]
        conn.close()
        return count
        
    except mysql.connector.Error as e:
        print(f"Error getting unread count: {e}")
        return 0


def mark_notification_read(notification_id):
    """Mark a notification as read"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE notifications 
            SET is_read = 1 
            WHERE id = %s
        ''', (notification_id,))
        
        conn.commit()
        conn.close()
        return True
        
    except mysql.connector.Error as e:
        print(f"Error marking notification read: {e}")
        return False


def mark_all_notifications_read(user_id):
    """Mark all notifications as read for a user"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE notifications 
            SET is_read = 1 
            WHERE user_id = %s AND is_read = 0
        ''', (user_id,))
        
        conn.commit()
        conn.close()
        return True
        
    except mysql.connector.Error as e:
        print(f"Error marking all notifications read: {e}")
        return False


# ===== DATABASE INITIALIZATION =====

def create_tables():
    """Create all necessary tables for the application"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                name VARCHAR(100),
                email VARCHAR(100),
                role VARCHAR(20) DEFAULT 'student',
                grade_level VARCHAR(10),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Student submissions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS student_submissions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                student_id INT NOT NULL,
                activity_name VARCHAR(100) NOT NULL,
                code_blocks TEXT NOT NULL,
                language VARCHAR(20) DEFAULT 'python',
                status VARCHAR(20) DEFAULT 'pending_review',
                score INT,
                feedback TEXT,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
        # Notifications table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT,
                target_role VARCHAR(20),
                type VARCHAR(50) NOT NULL,
                title VARCHAR(255) NOT NULL,
                message TEXT NOT NULL,
                related_id INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_read BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
        # Create indexes for performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_submissions_student ON student_submissions(student_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_submissions_status ON student_submissions(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_notifications_read ON notifications(is_read)')
        
        conn.commit()
        conn.close()
        print(" Database tables created successfully!")
        return True
        
    except mysql.connector.Error as e:
        print(f"Error creating tables: {e}")
        return False


# ===== DEMO DATA =====

def seed_demo_data():
    """Insert demo data for testing"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Demo student
        cursor.execute('''
            INSERT IGNORE INTO users (username, password, name, email, role, grade_level)
            VALUES ('student1', 'password123', 'Juan Dela Cruz', 'juan@example.com', 'student', 'Grade 11')
        ''')
        
        # Demo teacher
        cursor.execute('''
            INSERT IGNORE INTO users (username, password, name, email, role)
            VALUES ('teacher1', 'password123', 'Maria Santos', 'maria@example.com', 'teacher')
        ''')
        
        conn.commit()
        conn.close()
        print(" Demo data seeded!")
        return True
        
    except mysql.connector.Error as e:
        print(f"Error seeding demo data: {e}")
        return False


# Export for use in other files
__all__ = [
    'db_config',
    'get_db_connection', 
    'test_connection',
    'save_submission',
    'get_student_submissions',
    'get_activity_status',
    'get_pending_submissions_for_teachers',
    'get_all_student_submissions_for_teacher',
    'review_submission',
    'create_teacher_notification',
    'create_student_notification',
    'get_student_notifications',
    'get_teacher_notifications',
    'get_unread_notification_count',
    'mark_notification_read',
    'mark_all_notifications_read',
    'create_tables',
    'seed_demo_data'
]

# Run initialization if executed directly
if __name__ == '__main__':
    print(" Initializing database...")
    if test_connection():
        create_tables()
        seed_demo_data()
        print(" Database setup complete!")
    else:
        print(" Database connection failed!")