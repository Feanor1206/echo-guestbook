import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.request import urlopen


def test_script_starts_with_legacy_windows_output_encoding(tmp_path):
    root = Path(__file__).resolve().parents[1]
    env = {
        **os.environ,
        'GUESTBOOK_DATA_DIR': str(tmp_path / 'data'),
        'PORT': '0',
        'PYTHONIOENCODING': 'cp1252',
        'PYTHONUNBUFFERED': '1',
    }
    log = tmp_path / 'server.log'
    with log.open('wb') as output:
        process = subprocess.Popen(
            [sys.executable, str(root / 'app.py')], cwd=root, env=env,
            stdout=output, stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                text = log.read_text(encoding='cp1252')
                assert process.poll() is None, text
                match = re.search(r'Uvicorn running on (http://127\.0\.0\.1:\d+)', text)
                if match:
                    with urlopen(match.group(1) + '/health', timeout=5) as response:
                        assert json.load(response)['status'] == 'ok'
                    assert 'ECHO Guestbook running: http://127.0.0.1:0' in text
                    break
                time.sleep(0.1)
            else:
                raise AssertionError('Server did not start:\n' + log.read_text(encoding='cp1252'))
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
