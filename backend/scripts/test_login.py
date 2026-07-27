import urllib.request
import json

try:
    url = 'http://localhost:8000/api/v1/auth/login'
    payload = json.dumps({'username': 'admin', 'password': 'admin123'}).encode('utf-8')
    headers = {'Content-Type': 'application/json'}
    req = urllib.request.Request(url, data=payload, headers=headers)
    with urllib.request.urlopen(req) as resp:
        print("LOGIN TEST SUCCESS: Status", resp.status)
        data = json.loads(resp.read().decode('utf-8'))
        print("Access Token received:", data.get('access_token')[:20], "...")
except Exception as e:
    print("LOGIN TEST FAILED:", e)
