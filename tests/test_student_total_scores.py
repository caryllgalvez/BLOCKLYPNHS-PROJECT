from backend.scores import get_student_total_scores


def test_get_student_total_scores_aggregates_activities_and_assessments():
    class FakeCursor:
        def __init__(self):
            self._queries = []

        def execute(self, query, params=()):
            self._queries.append((query, params))

        def fetchall(self):
            query = self._queries[-1][0]
            if "a.language IN ('php', 'javascript', 'cpp')" in query:
                return [
                    {'language': 'php', 'assessment_number': 1, 'score': 100, 'auto_score': 7, 'teacher_score': None, 'status': 'submitted'},
                    {'language': 'php', 'assessment_number': 2, 'score': 80, 'auto_score': 8, 'teacher_score': None, 'status': 'submitted'},
                ]
            if "a.language IN ('python', 'java')" in query:
                return [
                    {'language': 'python', 'auto_score': 8, 'teacher_score': None},
                    {'language': 'java', 'auto_score': 7, 'teacher_score': 10},
                ]
            return []

    result = get_student_total_scores(FakeCursor(), 101)

    assert result['overall']['total'] == 33
    assert result['activities']['total'] == 15
    assert result['assessments']['total'] == 18
    assert result['activities']['by_language']['php']['total'] == 15
    php_difficulty = result['activities']['by_language']['php']['by_difficulty']
    assert php_difficulty['easy'] == {'total': 15, 'max': 20, 'percentage': 75}
    assert php_difficulty['medium']['max'] == 20
    assert php_difficulty['hard']['max'] == 10
    assert result['assessments']['by_language']['python']['total'] == 8
    assert result['assessments']['by_language']['java']['total'] == 10
