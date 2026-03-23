"""Quick test to diagnose login issues."""
import re
from app import create_app

app = create_app()
client = app.test_client()

# Get login page
resp = client.get('/login')
print(f'GET /login status: {resp.status_code}')

html = resp.data.decode()

# Extract CSRF token
m = re.search(r'name="csrf_token".*?value="([^"]+)"', html)
if not m:
    m = re.search(r'id="csrf_token".*?value="([^"]+)"', html)
token = m.group(1) if m else 'NOT_FOUND'
print(f'CSRF token found: {token[:20] if token != "NOT_FOUND" else token}')

# Try login
resp2 = client.post('/login', data={
    'username': 'admin',
    'password': 'admin123',
    'csrf_token': token,
    'submit': 'Sign In'
}, follow_redirects=False)
print(f'POST /login status: {resp2.status_code}')
print(f'Location: {resp2.headers.get("Location", "none")}')

if resp2.status_code == 200:
    body = resp2.data.decode()
    # Check for flash messages / errors
    flashes = re.findall(r'class="alert[^"]*"[^>]*>(.*?)</div>', body, re.DOTALL)
    for f in flashes:
        print(f'Flash: {f.strip()[:200]}')
    if 'Invalid' in body:
        print('Found "Invalid" in response body')
    if 'csrf' in body.lower():
        print('Found CSRF-related text in response body')

# Test with follow_redirects to see final page
resp3 = client.post('/login', data={
    'username': 'admin',
    'password': 'admin123',
    'csrf_token': token,
    'submit': 'Sign In'
}, follow_redirects=True)
print(f'\nWith follow_redirects: status={resp3.status_code}')
body3 = resp3.data.decode()
if 'Dashboard' in body3 or 'dashboard' in body3:
    print('SUCCESS: Reached dashboard after login')
elif 'Sign In' in body3 or 'login' in body3.lower():
    print('FAILED: Still on login page')
    # Check for error messages
    if 'Invalid' in body3:
        print('  -> "Invalid username or password" shown')
    if 'CSRF' in body3 or 'csrf' in body3:
        print('  -> CSRF error shown')
