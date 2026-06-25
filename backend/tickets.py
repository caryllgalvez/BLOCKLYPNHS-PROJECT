# backend/tickets.py - Ticket Management System

from backend.db_config import get_db_connection
from datetime import datetime

class TicketManager:
    """Handles all ticket-related database operations"""
    
    @staticmethod
    def create_ticket(student_id, student_name, subject, message, priority='medium'):
        """Create a new support ticket"""
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO tickets (student_id, student_name, subject, message, priority, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (student_id, student_name, subject, message, priority, datetime.now()))
            
            ticket_id = cursor.lastrowid
            conn.commit()
            
            return {'success': True, 'ticket_id': ticket_id, 'message': 'Ticket created successfully'}
            
        except Exception as e:
            print(f"Error creating ticket: {e}")
            return {'success': False, 'message': str(e)}
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    @staticmethod
    def get_student_tickets(student_id):
        """Get all tickets for a specific student"""
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            cursor.execute("""
                SELECT id, subject, message, status, priority, 
                      teacher_approval,
                       DATE_FORMAT(created_at, '%Y-%m-%d %H:%i') as created_at,
                        DATE_FORMAT(updated_at, '%Y-%m-%d %H:%i') as updated_at
                FROM tickets 
                WHERE student_id = %s 
                ORDER BY 
                    CASE status 
                        WHEN 'pending' THEN 1 
                        WHEN 'in_progress' THEN 2 
                        WHEN 'resolved' THEN 3 
                        WHEN 'closed' THEN 4 
                    END,
                    created_at DESC
            """, (student_id,))
            
            tickets = cursor.fetchall()
            return {'success': True, 'tickets': tickets}
            
        except Exception as e:
            print(f"Error getting student tickets: {e}")
            return {'success': False, 'message': str(e)}
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    @staticmethod
    def get_all_tickets(status_filter=None):
        """Get all tickets (for teachers) with optional status filter"""
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            if status_filter:
                cursor.execute("""
                    SELECT t.id, t.student_id, t.student_name, t.subject, t.message, t.status, t.priority, t.teacher_approval,
                           DATE_FORMAT(t.created_at, '%Y-%m-%d %H:%i') as created_at,
                           DATE_FORMAT(t.updated_at, '%Y-%m-%d %H:%i') as updated_at,
                           s.lrn as student_lrn,
                           s.grade_level as student_grade
                    FROM tickets t
                    LEFT JOIN students s ON t.student_id = s.id
                    WHERE t.status = %s
                    ORDER BY 
                        CASE t.priority 
                            WHEN 'high' THEN 1 
                            WHEN 'medium' THEN 2 
                            WHEN 'low' THEN 3 
                        END,
                        t.created_at DESC
                """, (status_filter,))
            else:
                cursor.execute("""
                    SELECT t.id, t.student_id, t.student_name, t.subject, t.message, t.status, t.priority, t.teacher_approval,
                           DATE_FORMAT(t.created_at, '%Y-%m-%d %H:%i') as created_at,
                           DATE_FORMAT(t.updated_at, '%Y-%m-%d %H:%i') as updated_at,
                           s.lrn as student_lrn,
                           s.grade_level as student_grade
                    FROM tickets t
                    LEFT JOIN students s ON t.student_id = s.id
                    ORDER BY 
                        CASE t.status 
                            WHEN 'pending' THEN 1 
                            WHEN 'in_progress' THEN 2 
                            WHEN 'resolved' THEN 3 
                            WHEN 'closed' THEN 4 
                        END,
                        CASE t.priority 
                            WHEN 'high' THEN 1 
                            WHEN 'medium' THEN 2 
                            WHEN 'low' THEN 3 
                        END,
                        t.created_at DESC
                """)
            
            tickets = cursor.fetchall()
            return {'success': True, 'tickets': tickets}
            
        except Exception as e:
            print(f"Error getting all tickets: {e}")
            return {'success': False, 'message': str(e)}
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    @staticmethod
    def get_ticket_by_id(ticket_id):
        """Get a single ticket by ID"""
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            cursor.execute("""
                SELECT t.id, t.student_id, t.student_name, t.subject, t.message, t.status, t.priority, t.teacher_approval,
                       DATE_FORMAT(t.created_at, '%Y-%m-%d %H:%i') as created_at,
                       DATE_FORMAT(t.updated_at, '%Y-%m-%d %H:%i') as updated_at,
                       s.lrn as student_lrn,
                       s.grade_level as student_grade,
                       s.email as student_email,
                       s.username as student_username
                FROM tickets t
                LEFT JOIN students s ON t.student_id = s.id
                WHERE t.id = %s
            """, (ticket_id,))
            
            ticket = cursor.fetchone()
            return {'success': True, 'ticket': ticket}
            
        except Exception as e:
            print(f"Error getting ticket: {e}")
            return {'success': False, 'message': str(e)}
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    @staticmethod
    def update_ticket_status(ticket_id, status, teacher_approval=None):
        """Update ticket status and optionally set teacher_approval"""
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            update_fields = []
            params = []
            
            if status:
                update_fields.append("status = %s")
                params.append(status)
                if status in ['resolved', 'closed']:
                    update_fields.append("resolved_at = %s")
                    params.append(datetime.now())
            
            if teacher_approval is not None:
                update_fields.append("teacher_approval = %s")
                params.append(teacher_approval)
            
            if not update_fields:
                return {'success': False, 'message': 'No updates provided'}
            
            # Add updated_at
            update_fields.append("updated_at = %s")
            params.append(datetime.now())
            
            params.append(ticket_id)
            query = f"UPDATE tickets SET {', '.join(update_fields)} WHERE id = %s"
            cursor.execute(query, params)
            conn.commit()
            
            return {'success': True, 'message': 'Ticket updated successfully'}
            
        except Exception as e:
            print(f"Error updating ticket: {e}")
            return {'success': False, 'message': str(e)}
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    @staticmethod
    def get_ticket_counts():
        """Get ticket statistics for teacher dashboard"""
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) as in_progress,
                    SUM(CASE WHEN status = 'resolved' THEN 1 ELSE 0 END) as resolved,
                    SUM(CASE WHEN status = 'closed' THEN 1 ELSE 0 END) as closed,
                    SUM(CASE WHEN priority = 'high' THEN 1 ELSE 0 END) as high_priority
                FROM tickets
            """)
            
            counts = cursor.fetchone()
            return {
                'success': True,
                'total': counts['total'] or 0,
                'pending': counts['pending'] or 0,
                'in_progress': counts['in_progress'] or 0,
                'resolved': counts['resolved'] or 0,
                'closed': counts['closed'] or 0,
                'high_priority': counts['high_priority'] or 0
            }
            
        except Exception as e:
            print(f"Error getting ticket counts: {e}")
            return {'success': False, 'message': str(e)}
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()


# Simple function-based interface (easier to use in app.py)
def create_ticket(student_id, student_name, subject, message, priority='medium'):
    return TicketManager.create_ticket(student_id, student_name, subject, message, priority)

def get_student_tickets(student_id):
    return TicketManager.get_student_tickets(student_id)

def get_all_tickets(status_filter=None):
    return TicketManager.get_all_tickets(status_filter)

def get_ticket_by_id(ticket_id):
    return TicketManager.get_ticket_by_id(ticket_id)

def update_ticket_status(ticket_id, status, teacher_approval=None):
    return TicketManager.update_ticket_status(ticket_id, status, teacher_approval)

def get_ticket_counts():
    return TicketManager.get_ticket_counts()