from backend import app
with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['role'] = 'student'
        sess['user_id'] = 1
        sess['username'] = 'test'
    response = client.post('/submit_activity', json={
        'activity_name': 'Print Statement',
        'code_blocks': 'print("Hello World")',
        'language': 'python'
    })
    print(response.status_code)
    print(response.get_data(as_text=True))
