from backend.app import app


def test_get_activity_scores_uses_assessment_attempts_fallback(monkeypatch):
    class FakeCursor:
        def __init__(self):
            self._result = []
            self._execute_calls = []

        def execute(self, query, params=()):
            self._execute_calls.append((query, params))
            if 'FROM activities' in query and 'student_id = %s' in query:
                self._result = []
            elif 'FROM assessment_attempts aa' in query:
                self._result = [{
                    'lrn': '123456789012',
                    'activity_name': 'Hello C++',
                    'language': 'cpp',
                    'score': 90,
                    'completed_at': '2026-09-10 09:00'
                }]
            else:
                self._result = []

        def fetchall(self):
            return list(self._result)

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
            session['role'] = 'teacher'

        response = client.get('/get_activity_scores')

    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert data['scores'][0]['lrn'] == '123456789012'
    assert data['scores'][0]['activity_name'] == 'Hello C++'
    assert data['scores'][0]['score'] == 90


def test_leaderboard_uses_activity_and_assessment_scores(monkeypatch):
    class FakeCursor:
        def __init__(self):
            self.result = []
            self.query = ''

        def execute(self, query, params=()):
            self.query = query
            self.result = [{
                'student_name': 'Student One',
                'lrn': '123456789012',
                'activities_completed': 2,
                'average_score': 95,
            }]

        def fetchall(self):
            return self.result

        def close(self):
            pass

    class FakeConn:
        def __init__(self):
            self.cursor_obj = FakeCursor()

        def cursor(self, dictionary=True):
            return self.cursor_obj

        def close(self):
            pass

    conn = FakeConn()
    monkeypatch.setattr('backend.app.get_db_connection', lambda: conn)

    with app.test_client() as client:
        with client.session_transaction() as session:
            session['role'] = 'student'

        response = client.get('/leaderboard')

    assert response.status_code == 200
    data = response.get_json()
    assert data['leaderboard'][0]['average_score'] == 95
    assert 'FROM activities' in conn.cursor_obj.query
    assert 'FROM assessment_attempts' in conn.cursor_obj.query
