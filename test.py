import requests

r = requests.get('https://serpapi.com/search', params={
    'engine': 'google_shopping',
    'q': 'iphone 15',
    'gl': 'us',
    'hl': 'en',
    'api_key': '53f7121395daf7334e67dddec98475b4eca76bd3f16bd09932ee03c20786d41c'
}, timeout=30)

data = r.json()
results = data.get('shopping_results', [])
print('Total results:', len(results))
if results:
    print('First item:', results[0])
else:
    print('Error:', data.get('error', data))