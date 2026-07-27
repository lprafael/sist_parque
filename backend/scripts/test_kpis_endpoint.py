import urllib.request
import json

# 1. Login to get token
login_url = "http://localhost:8000/api/v1/auth/login"
login_payload = json.dumps({"username": "admin", "password": "admin123"}).encode("utf-8")
headers = {"Content-Type": "application/json"}

req_login = urllib.request.Request(login_url, data=login_payload, headers=headers)
with urllib.request.urlopen(req_login) as resp:
    token_data = json.loads(resp.read().decode("utf-8"))
    token = token_data["access_token"]

# 2. Get KPIs
kpi_url = "http://localhost:8000/api/v1/dashboard/kpis"
kpi_headers = {"Authorization": f"Bearer {token}"}
req_kpi = urllib.request.Request(kpi_url, headers=kpi_headers)

with urllib.request.urlopen(req_kpi) as resp_kpi:
    kpi_data = json.loads(resp_kpi.read().decode("utf-8"))
    print("\n=== DASHBOARD KPIs DESDE EL ENDPOINT ===")
    print(json.dumps(kpi_data, indent=2))
