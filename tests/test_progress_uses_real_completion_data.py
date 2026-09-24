from backend.app import app


def test_get_progress_uses_assessment_and_activity_tables(monkeypatch):
    class FakeCursor:
        def __init__(self):
            self._result = []
            self._fetchone_result = None
            self._fetchall_result = []

        def execute(self, query, params=()):
            if 'FROM assessment_attempts aa' in query and 'a.language IN (\'python\', \'java\')' in query:
                self._fetchone_result = {'completed': 2}
            elif 'FROM assessment_attempts aa' in query and 'a.language IN (\'php\', \'javascript\', \'cpp\')' in query:
                self._fetchall_result = [
                    {'language': 'php', 'completed': 2},
                    {'language': 'javascript', 'completed': 1},
                ]
            elif 'FROM activities' in query and 'student_id = %s' in query:
                self._fetchall_result = []
            else:
                self._fetchone_result = {'completed': 0}

        def fetchone(self):
            result = self._fetchone_result
            self._fetchone_result = None
            return result

        def fetchall(self):
            result = self._fetchall_result
            self._fetchall_result = []
            return result

        def close(self):
            pass

    class FakeConn:
        def __init__(self):
            self.cursor_obj = FakeCursor()

        def cursor(self, dictionary=True):
            return self.cursor_obj

        def close(self):
            pass

    monkeypatch.setattr('backend.app.get_db_connection', lambda: FakeConn())

    with app.test_client() as client:
        with client.session_transaction() as session:
            session['role'] = 'student'
            session['user_id'] = 99

        response = client.get('/get_progress')

    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert data['completed_assessments'] == 2
    assert data['completed_activities'] == 3
    assert data['completed'] == 5
    assert data['progress'] == 20


def test_get_activity_progress_includes_submitted_activity_assessments(monkeypatch):
    class FakeCursor:
        def __init__(self):
            self._fetchall_result = []

        def execute(self, query, params=()):
            if 'SELECT language, COUNT(*) AS total' in query:
                self._fetchall_result = [
                    {'language': 'python', 'total': 5},
                    {'language': 'java', 'total': 5},
                    {'language': 'php', 'total': 5},
                    {'language': 'javascript', 'total': 5},
                    {'language': 'cpp', 'total': 5},
                ]
            elif "a.language IN ('python', 'java')" in query:
                self._fetchall_result = [{'language': 'python', 'completed': 1}]
            elif "a.language IN ('php', 'javascript', 'cpp')" in query:
                self._fetchall_result = [{'language': 'php', 'completed': 2}]
            elif 'FROM activities' in query:
                self._fetchall_result = []

        def fetchall(self):
            result = self._fetchall_result
            self._fetchall_result = []
            return result

        def close(self):
            pass

    class FakeConn:
        def __init__(self):
            self.cursor_obj = FakeCursor()

        def cursor(self, dictionary=True):
            return self.cursor_obj

        def close(self):
            pass

    monkeypatch.setattr('backend.app.get_db_connection', lambda: FakeConn())

    with app.test_client() as client:
        with client.session_transaction() as session:
            session['role'] = 'student'
            session['user_id'] = 99

        response = client.get('/get_activity_progress')

    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert data['php']['completed'] == 2
    assert data['completed_assessments'] == 1
    assert data['completed_activities'] == 2
    assert data['total_completed'] == 3
    assert data['overall_percentage'] == 12
