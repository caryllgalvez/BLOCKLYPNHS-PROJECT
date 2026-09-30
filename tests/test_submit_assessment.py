from backend.app import app


def test_submit_assessment_returns_max_points(monkeypatch):
    class FakeCursor:
        def __init__(self):
            self._assessment = {'id': 1, 'expected_output': 'Hello, C++!', 'points': 10}
            self._executed = []

        def execute(self, query, params):
            self._executed.append((query, params))
            if 'SELECT id, expected_output, points' in query:
                self._fetchone_result = self._assessment
            else:
                self._fetchone_result = None

        def fetchone(self):
            result = getattr(self, '_fetchone_result', None)
            self._fetchone_result = None
            return result

        def close(self):
            pass

    class FakeConn:
        def __init__(self):
            self.cursor_obj = FakeCursor()

        def cursor(self, dictionary=True):
            return self.cursor_obj

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr('backend.app.get_db_connection', lambda: FakeConn())
    monkeypatch.setattr('backend.app.notify_new_assessment_submission', lambda *args, **kwargs: None)

    with app.test_client() as client:
        with client.session_transaction() as session:
            session['role'] = 'student'
            session['user_id'] = 1
            session['full_name'] = 'Student Name'

        response = client.post(
            '/submit_assessment',
            json={
                'language': 'cpp',
                'assessment_number': 1,
                'code_blocks': '<xml></xml>',
                'output': 'Hello, C++!'
            }
        )

    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert data['points'] == 10
    assert data['max_points'] == 10


def test_submit_assessment_wrong_nonempty_output_gets_zero_and_review_status(monkeypatch):
    class FakeCursor:
        def __init__(self):
            self.insert_params = None

        def execute(self, query, params=()):
            if 'SELECT id, expected_output, points' in query:
                self.fetchone_result = {'id': 1, 'expected_output': 'Hello, World!', 'points': 10}
            elif 'INSERT INTO assessment_attempts' in query:
                self.insert_params = params
                self.fetchone_result = None

        def fetchone(self):
            return getattr(self, 'fetchone_result', None)

        def close(self):
            pass

    class FakeConnection:
        def __init__(self):
            self.cursor_instance = FakeCursor()

        def cursor(self, dictionary=True):
            return self.cursor_instance

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    connection = FakeConnection()
    monkeypatch.setattr('backend.app.get_db_connection', lambda: connection)
    monkeypatch.setattr('backend.app.notify_new_assessment_submission', lambda *args, **kwargs: None)

    with app.test_client() as client:
        with client.session_transaction() as session:
            session.update({'role': 'student', 'user_id': 1})

        response = client.post('/submit_assessment', json={
            'language': 'python',
            'assessment_number': 1,
            'code_blocks': '<xml></xml>',
            'output': '16',
        })

    result = response.get_json()
    assert response.status_code == 200
    assert result['success'] is True
    assert result['score'] == 0
    assert result['points'] == 0
    assert result['status'] == 'pending_review'
    assert connection.cursor_instance.insert_params[5:7] == (0, 0)
