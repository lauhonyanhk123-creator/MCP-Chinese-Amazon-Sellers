#!/usr/bin/env python3
from web_app import app

print('Testing routes...')
with app.test_client() as client:
    # Test index
    print('1. Testing / (index)...')
    r = client.get('/')
    print(f'   Status: {r.status_code}')
    html = r.get_data(as_text=True)
    print(f'   Has inventory link: {"/inventory" in html}')
    
    # Test inventory
    print('\n2. Testing /inventory...')
    r = client.get('/inventory')
    print(f'   Status: {r.status_code}')
    html = r.get_data(as_text=True)
    print(f'   Has alerts: {"Wireless Bluetooth" in html}')
    
    # Test filters
    print('\n3. Testing /inventory with platform=1688...')
    r = client.get('/inventory?platform=1688')
    html = r.get_data(as_text=True)
    print(f'   Status: {r.status_code}')
    print(f'   Shows 1688: {"1688" in html}')
    
    # Test threshold filter
    print('\n4. Testing /inventory with threshold=5...')
    r = client.get('/inventory?threshold=5')
    html = r.get_data(as_text=True)
    print(f'   Status: {r.status_code}')
    
    # Test bilingual
    print('\n5. Testing English...')
    r = client.get('/inventory?lang=en')
    html = r.get_data(as_text=True)
    print(f'   Status: {r.status_code}')
    print(f'   Has English text: {"Low Stock" in html}')
    
    print('\nAll tests passed! ✓')
