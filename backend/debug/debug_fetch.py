import requests
s = requests.Session()
# login as teacher1
r = s.post('http://127.0.0.1:5000/login', json={'role':'teacher','username':'teacher1','password':'teacher123'})
print('LOGIN', r.status_code, r.text)
# get teacher data
r2 = s.get('http://127.0.0.1:5000/get_teacher_dashboard_data')
print('\nGET_TEACHER_DATA', r2.status_code)
print(r2.text[:4000])
# get role-aware data
r3 = s.get('http://127.0.0.1:5000/get_dashboard_data')
print('\nGET_DASHBOARD_DATA', r3.status_code)
print(r3.text[:4000])
# try public recent submissions
r4 = s.get('http://127.0.0.1:5000/get_recent_submissions')
print('\nGET_RECENT_SUBMISSIONS', r4.status_code)
print(r4.text[:4000])
