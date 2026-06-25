# backend/db_config.py - Database Configuration

import mysql.connector
from mysql.connector import Error

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

# Export for use in other files
__all__ = ['db_config', 'get_db_connection', 'test_connection']