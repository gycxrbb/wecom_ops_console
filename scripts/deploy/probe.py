"""Runs inside the application container; never prints application data or secrets."""
import json
import os
import urllib.request

base = 'http://127.0.0.1:' + os.environ.get('PORT', '8000')
with urllib.request.urlopen(base + '/api/v1/health', timeout=15) as response:
    data = json.load(response)
if data.get('status') != 'ok' or data.get('db') is not True:
    raise RuntimeError('Database health check failed')
with urllib.request.urlopen(base + '/', timeout=15) as response:
    if response.status != 200:
        raise RuntimeError('Frontend check failed')
print('API_DB_OK FRONTEND_OK')
