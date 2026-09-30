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
            self._fetchone_result = None

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
                self._fetchall_result = [{'language': 'python', 'completed': 1, 'passed': 1}]
            elif "a.language IN ('php', 'javascript', 'cpp')" in query:
                self._fetchall_result = [{'language': 'php', 'completed': 2, 'passed': 2}]
            elif 'AS score_count' in query:
                self._fetchone_result = {'score_count': 0, 'average_score': 0}

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

        response = client.get('/get_activity_progress')

    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert data['php']['completed'] == 2
    assert data['completed_assessments'] == 1
    assert data['completed_activities'] == 2
    assert data['total_completed'] == 3
    assert data['overall_percentage'] == 12


def test_student_progress_results_prefer_teacher_reviewed_score(monkeypatch):
    executed_queries = []

    class FakeCursor:
        def execute(self, query, params=()):
            executed_queries.append(query)

        def fetchall(self):
            return []

        def close(self):
            pass

    class FakeConn:
        def cursor(self, dictionary=True):
            return FakeCursor()

        def close(self):
            pass

    monkeypatch.setattr('backend.app.get_db_connection', lambda: FakeConn())

    with app.test_client() as client:
        with client.session_transaction() as session:
            session['role'] = 'student'
            session['user_id'] = 99

        response = client.get('/get_progress_results')

    assert response.status_code == 200
    assert response.get_json() == {'success': True, 'results': []}
    assert 'ROUND(aa.teacher_score / 10, 1)' in executed_queries[0]
    assert "WHERE d.language IN ('python', 'java')" in executed_queries[0]
    assert "WHERE d.language IN ('javascript', 'cpp', 'php')" in executed_queries[1]
    assert 'WHEN aa.teacher_score IS NOT NULL THEN' in executed_queries[1]
    assert 'WHEN aa.auto_score IS NOT NULL THEN' in executed_queries[1]
    assert 'ROUND(aa.score / 10, 1)' in executed_queries[1]


def test_student_progress_renders_catalog_counts_and_student_completions(monkeypatch):
    class FakeCursor:
        def execute(self, query, params=()):
            assert params == (99,)
            assert 'COUNT(DISTINCT a.id) AS total' in query
            assert "aa.status IN ('submitted', 'completed', 'pending_review')" in query

        def fetchall(self):
            return [
                {'language': 'php', 'total': 5, 'completed': 2},
                {'language': 'javascript', 'total': 5, 'completed': 1},
                {'language': 'cpp', 'total': 5, 'completed': 3},
                {'language': 'python', 'total': 4, 'completed': 3},
                {'language': 'java', 'total': 5, 'completed': 1},
            ]

        def close(self):
            pass

    class FakeConn:
        def cursor(self, dictionary=True):
            return FakeCursor()

        def close(self):
            pass

    monkeypatch.setattr('backend.app.get_db_connection', lambda: FakeConn())

    with app.test_client() as client:
        with client.session_transaction() as session:
            session['role'] = 'student'
            session['user_id'] = 99

        response = client.get('/student_progress')

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert '10 of 24 activities and assessments completed.' in page
    assert 'Activities Completed' in page
    assert '6<span class="stat-unit">/15</span>' in page
    assert 'Assessments Completed' in page
    assert '4<span class="stat-unit">/9</span>' in page
    assert 'class="detail-group-heading">Activities</li>' in page
    assert 'class="detail-group-heading detail-group-heading--separated">Assessments</li>' in page
    assert 'Activities completed</small>' not in page
    assert '12 / 18 modules' not in page
    assert 'Average Score' not in page
    assert '+4% this month' not in page
