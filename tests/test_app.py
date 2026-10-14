import json
import sqlite3
import sys
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app


def client(tmp_path):
    app = create_app(tmp_path)
    return TestClient(app, follow_redirects=False)


def token(client):
    page = client.get('/add')
    assert page.status_code == 200
    return BeautifulSoup(page.text, 'html.parser').select_one('input[name="csrf"]')['value']


def test_main_pages_and_empty_stats(tmp_path):
    with client(tmp_path) as web:
        assert 'Những dấu ấn' in web.get('/').text
        assert 'Gửi lời nhắn' in web.get('/add').text
        assert web.get('/stats').status_code == 200
        assert web.get('/charts/stats.png').headers['content-type'] == 'image/png'
        assert web.get('/charts/activity.png').status_code == 200
        assert web.get('/api/stats').json()['total'] == 0
        assert web.get('/health').json()['status'] == 'ok'
        assert web.get('/unknown-url').status_code == 404


def test_add_validate_delete_persist(tmp_path):
    with client(tmp_path) as web:
        csrf = token(web)
        assert web.post('/add', data={'csrf': csrf, 'name': '', 'message': ''}).status_code == 422
        assert web.post('/add', data={'csrf': csrf, 'name': 'abc', 'message': ''}).status_code == 422
        assert web.post('/add', data={'csrf': 'invalid', 'name': 'abc', 'message': 'Hello'}).status_code == 403
        res = web.post('/add', data={'csrf': csrf, 'name': 'An', 'message': 'Xin chào mọi người!'})
        assert res.status_code == 303 and '/?new=1' in res.headers['location']
        assert 'Xin chào mọi người!' in web.get('/').text
        assert web.get('/api/stats').json()['total'] == 1
        assert web.get('/api/stats').json()['leaders'][0]['name'] == 'An'
        assert web.get('/export').status_code == 200
        assert len(json.loads((tmp_path/'data.json').read_text(encoding='utf-8'))['entries']) == 1
        with sqlite3.connect(tmp_path/'guestbook.db') as db:
            assert db.execute('SELECT COUNT(*) FROM entries').fetchone()[0] == 1
        assert web.get('/delete/1').status_code == 405
        assert web.post('/delete/1', data={'csrf': csrf}).status_code == 303
        assert web.get('/api/stats').json()['total'] == 0
        assert json.loads((tmp_path/'data.json').read_text(encoding='utf-8'))['entries'] == []
        with sqlite3.connect(tmp_path/'guestbook.db') as db:
            assert db.execute('SELECT COUNT(*) FROM entries').fetchone()[0] == 0


def test_restart_and_xss(tmp_path):
    with client(tmp_path) as web:
        csrf = token(web)
        assert web.post('/add', data={'csrf': csrf, 'name': '<img src=x>', 'message': '<script>alert(1)</script>'}).status_code == 303
    with client(tmp_path) as web:
        page = web.get('/')
        assert '&lt;script&gt;' in page.text
        assert '<script>alert(1)</script>' not in page.text
        assert web.get('/api/entries').json()['entries'][0]['id'] == 1


@pytest.mark.parametrize('name,message', [
    ('   ', 'Xin chào'),
    ('An', '   '),
    ('A' * 41, 'Xin chào'),
    ('An', 'a' * 601),
])
def test_invalid_input_does_not_write_data(tmp_path, name, message):
    with client(tmp_path) as web:
        response = web.post('/add', data={'csrf': token(web), 'name': name, 'message': message})
        assert response.status_code == 422
        assert web.get('/api/entries').json()['total'] == 0
        assert json.loads((tmp_path / 'data.json').read_text(encoding='utf-8'))['entries'] == []


def test_unicode_at_limits_and_whitespace_trim(tmp_path):
    with client(tmp_path) as web:
        name, message = 'Đ' * 40, '💜' * 600
        response = web.post('/add', data={
            'csrf': token(web), 'name': f' {name} ', 'message': f' {message} ',
        })
        assert response.status_code == 303
        entry = web.get('/api/entries').json()['entries'][0]
        assert entry['name'] == name
        assert entry['message'] == message


def test_csrf_is_required_and_bound_to_session(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app) as first, TestClient(app) as second:
        csrf = token(first)
        token(second)
        payload = {'name': 'An', 'message': 'Xin chào'}
        assert first.post('/add', data=payload).status_code == 403
        assert second.post('/add', data={**payload, 'csrf': csrf}).status_code == 403
        assert first.post('/add', data={**payload, 'csrf': csrf}).status_code == 200
        assert first.post('/delete/1', data={}).status_code == 403
        assert second.post('/delete/1', data={'csrf': csrf}).status_code == 403
        assert first.get('/api/entries').json()['total'] == 1


def test_export_headers_and_missing_entry(tmp_path):
    with client(tmp_path) as web:
        csrf = token(web)
        response = web.get('/export')
        assert response.json()['entries'] == []
        assert 'attachment;' in response.headers['content-disposition']
        assert response.headers['x-content-type-options'] == 'nosniff'
        assert response.headers['x-frame-options'] == 'DENY'
        assert web.post('/delete/999', data={'csrf': csrf}).status_code == 303
        assert web.get('/api/entries').json()['total'] == 0
