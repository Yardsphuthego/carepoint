"""CI-only browser check against the local Docker profile; never print passwords."""
import os
import subprocess
from playwright.sync_api import sync_playwright

compose = ['docker', 'compose', '-f', 'compose.local.yml']
if os.environ.get('CAREPOINT_NATIVE_SMOKE'):
    from pathlib import Path
    text = Path('.local-native/local-logins.txt').read_text()
else:
    text = subprocess.check_output(compose + ['exec', '-T', 'web', 'cat', '/data/local-logins.txt'], text=True)
lines = text.splitlines()
accounts = {line: lines[index + 1].removeprefix('Password: ') for index, line in enumerate(lines) if line.startswith('carepoint.')}
front_port = os.environ.get('CAREPOINT_FRONTEND_PORT', '3100')
web_port = os.environ.get('CAREPOINT_WEB_PORT', '8100')
with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    for username, path in [('carepoint.patient', '/appointments/'), ('carepoint.admin', '/admin/')]:
        context = browser.new_context()
        page = context.new_page()
        page.goto(f'http://localhost:{front_port}')
        page.get_by_role('button', name='Patient sign in', exact=True).first.click()
        form = page.frame_locator('iframe')
        form.get_by_label('Username', exact=True).fill(username)
        form.get_by_label('Password', exact=True).fill(accounts[username])
        form.get_by_role('button', name='Sign in', exact=True).click()
        page.wait_for_url(f'http://localhost:{web_port}{path}', timeout=30000)
        page.locator('.cp-workspace').wait_for()
        print(f'{username}: login and dashboard passed')
        context.close()
    browser.close()
