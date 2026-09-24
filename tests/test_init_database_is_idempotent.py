from backend.app import init_database


def test_init_database_removes_duplicate_assessment_rows_before_seed(monkeypatch):
    query_log = []

    class FakeCursor:
        def __init__(self):
            self._fetchone_result = None

        def executemany(self, query, params=()):
            self.execute(query, params)

        def execute(self, query, params=()):
            nonlocal query_log
            query_log.append(query)
            if 'SHOW COLUMNS FROM students LIKE' in query or 'SHOW COLUMNS FROM teachers LIKE' in query:
                self._fetchone_result = {'Field': 'dummy'}
                return

            if "SELECT COUNT(*) AS total FROM assessments" in query:
                self._fetchone_result = {'total': 0}
                return

            if "SELECT id, password, status FROM ict_support" in query:
                self._fetchone_result = None
                return

            if "SELECT id FROM teachers WHERE username = 'admin'" in query:
                self._fetchone_result = None
                return

            if "SELECT id, username, password FROM teachers WHERE LOWER(username) = 'teacher1'" in query:
                self._fetchone_result = None
                return

            if 'DELETE FROM ict_support' in query:
                self._fetchone_result = None
                return

            self._fetchone_result = None

        def fetchone(self):
            result = self._fetchone_result
            self._fetchone_result = None
            return result

        def fetchall(self):
            return []

        def close(self):
            pass

    class FakeConn:
        def __init__(self):
            self.cursor_obj = FakeCursor()

        def cursor(self, dictionary=True):
            return self.cursor_obj

        def commit(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr('backend.app.get_db_connection', lambda: FakeConn())

    init_database()

    assert any('DELETE t1' in query and 'assessment_number = t2.assessment_number' in query for query in query_log)


def test_init_database_does_not_reinsert_assessments_when_records_exist(monkeypatch):
    insert_calls = []

    class FakeCursor:
        def __init__(self):
            self._fetchone_result = None

        def execute(self, query, params=()):
            nonlocal insert_calls
            if 'INSERT INTO assessments' in query:
                insert_calls.append(query)
                if 'ON DUPLICATE KEY UPDATE' not in query:
                    raise AssertionError('Assessment seed insert was not idempotent')
                self._fetchone_result = None
                return

            if "SELECT COUNT(*) AS total FROM assessments" in query:
                self._fetchone_result = {'total': 1}
                return

            if "SELECT id, password, status FROM ict_support" in query:
                self._fetchone_result = {'id': 1, 'password': 'abc', 'status': 'active'}
                return

            if "SELECT id FROM teachers WHERE username = 'admin'" in query:
                self._fetchone_result = {'id': 1}
                return

            if "SELECT id, username, password FROM teachers WHERE LOWER(username) = 'teacher1'" in query:
                self._fetchone_result = {'id': 1, 'username': 'teacher1', 'password': 'abc'}
                return

            if 'SHOW COLUMNS FROM students LIKE' in query or 'SHOW COLUMNS FROM teachers LIKE' in query:
                self._fetchone_result = {'Field': 'dummy'}
                return

            if 'DELETE FROM ict_support' in query:
                self._fetchone_result = None
                return

            self._fetchone_result = None

        def fetchone(self):
            result = self._fetchone_result
            self._fetchone_result = None
            return result

        def fetchall(self):
            return []

        def close(self):
            pass

    class FakeConn:
        def __init__(self):
            self.cursor_obj = FakeCursor()

        def cursor(self, dictionary=True):
            return self.cursor_obj

        def commit(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr('backend.app.get_db_connection', lambda: FakeConn())

    init_database()

    assert insert_calls == []
