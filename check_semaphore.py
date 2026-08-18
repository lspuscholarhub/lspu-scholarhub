"""
After registering a sender name in Semaphore dashboard,
run this to test SMS and confirm the correct sender name.
Usage: py check_semaphore.py
"""
import urllib.request, urllib.parse, urllib.error, json, os, sys
from dotenv import load_dotenv
load_dotenv()

api_key     = os.environ.get('SEMAPHORE_API_KEY', '').strip()
sender_name = os.environ.get('SEMAPHORE_SENDER_NAME', '').strip()
number      = '09683652615'
message     = 'LSPU ScholarHub: SMS notification test. If you receive this, SMS is working!'

print(f"API Key   : {api_key[:8]}...")
print(f"Sender    : '{sender_name}'")
print(f"Sending to: {number}")

params = {'apikey': api_key, 'number': number, 'message': message}
if sender_name:
    params['sendername'] = sender_name

payload = urllib.parse.urlencode(params).encode('utf-8')
req = urllib.request.Request(
    'https://api.semaphore.co/api/v4/messages',
    data=payload, method='POST'
)
req.add_header('Content-Type', 'application/x-www-form-urlencoded')

try:
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode())
    print("\n✓ SUCCESS:", json.dumps(data, indent=2))
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f"\n✗ HTTP {e.code}: {body}")
    if 'sender' in body.lower():
        print("\n→ ACTION NEEDED: Go to semaphore.co → Sender Names → Apply for a sender name")
        print("  Suggested name: LSPU (max 11 chars, no spaces)")
except Exception as e:
    print(f"\n✗ Error: {e}")
