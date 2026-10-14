"""ECHO Guestbook – FastAPI + Jinja2 + SQLite + JSON + Matplotlib.

Start locally: python app.py
"""
from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from fastapi.templating import Jinja2Templates

from charts import render_charts
from storage import GuestbookStore

ROOT = Path(__file__).resolve().parent
TZ = ZoneInfo('Asia/Ho_Chi_Minh')


def _secret(data_dir: Path):
    if key := os.getenv('GUESTBOOK_SECRET_KEY'):
        return key
    path = data_dir / '.session_key'
    if path.exists():
        return path.read_text(encoding='utf-8').strip()
    # Keep sessions stable after restart without hardcoding a default key.
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(secrets.token_urlsafe(48))
    except FileExistsError:
        pass
    return path.read_text(encoding='utf-8').strip()


def create_app(data_dir: str | Path | None = None):
    folder = Path(data_dir or os.getenv('GUESTBOOK_DATA_DIR', ROOT)).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    app = FastAPI(title='ECHO — Guestbook', version='1.0', docs_url='/api/docs', redoc_url=None)
    app.add_middleware(SessionMiddleware, secret_key=_secret(folder), same_site='lax', https_only=False)
    app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')
    templates = Jinja2Templates(directory=ROOT / 'templates')
    store = GuestbookStore(folder)
    app.state.store = store
    app.state.chart_version = 1
    chart_dir = ROOT / 'static' / 'generated' if folder == ROOT else folder / 'charts'
    # Test instances share the static directory only for their fixture charts.
    if folder != ROOT:
        chart_dir = folder / 'charts'
    render_charts(store.stats(), chart_dir)
    if folder != ROOT:
        app.mount('/charts', StaticFiles(directory=chart_dir), name='charts')

    chart_base = '/static/generated' if folder == ROOT else '/charts'

    def human_date(value: str):
        date = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        return date.astimezone(TZ).strftime('%d/%m/%Y · %H:%M')

    templates.env.filters['human_date'] = human_date

    def csrf(request: Request):
        token = request.session.get('csrf_token')
        if not token:
            token = secrets.token_urlsafe(24)
            request.session['csrf_token'] = token
        return token

    def verify(request: Request, token: str):
        expected = request.session.get('csrf_token', '')
        if not token or not expected or not secrets.compare_digest(token, expected):
            raise HTTPException(status_code=403, detail='Phiên đã hết hạn. Vui lòng tải lại trang.')

    def page(request: Request, template: str, **context):
        return templates.TemplateResponse(request, template, {
            'request': request,
            'csrf': csrf(request),
            'active': request.url.path,
            'year': datetime.now(TZ).year,
            'stats': store.stats(),
            'chart_version': app.state.chart_version,
            'chart_base': chart_base,
            'flash': request.session.pop('flash', None),
            **context,
        })

    def refresh_charts():
        render_charts(store.stats(), chart_dir)
        app.state.chart_version += 1

    @app.middleware('http')
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['X-Frame-Options'] = 'DENY'
        return response

    @app.get('/', response_class=HTMLResponse)
    async def home(request: Request):
        return page(request, 'index.html', entries=store.all(), new=request.query_params.get('new', ''))

    @app.get('/add', response_class=HTMLResponse)
    async def add_page(request: Request):
        return page(request, 'add.html', values={'name': '', 'message': ''}, errors={})

    @app.post('/add', response_class=HTMLResponse)
    async def add_entry(request: Request):
        form = await request.form()
        verify(request, str(form.get('csrf', '')))
        name = str(form.get('name', '')).strip()
        message = str(form.get('message', '')).strip()
        errors = {}
        if not name:
            errors['name'] = 'Bạn chưa nhập tên.'
        elif len(name) > 40:
            errors['name'] = 'Tên không được vượt quá 40 ký tự.'
        if not message:
            errors['message'] = 'Bạn chưa viết lời nhắn.'
        elif len(message) > 600:
            errors['message'] = 'Lời nhắn không được vượt quá 600 ký tự.'
        if errors:
            return templates.TemplateResponse(request, 'add.html', {
                'request': request, 'csrf': csrf(request), 'active': '/add',
                'year': datetime.now(TZ).year, 'stats': store.stats(),
                'chart_version': app.state.chart_version, 'chart_base': chart_base,
                'flash': None, 'values': {'name': name, 'message': message}, 'errors': errors,
            }, status_code=422)
        item = store.add(name, message)
        refresh_charts()
        request.session['flash'] = {'type': 'success', 'message': 'Lời nhắn của bạn đã được lưu thành công!'}
        return RedirectResponse(url=f'/?new={item["id"]}#entry-{item["id"]}', status_code=303)

    @app.post('/delete/{id}', response_class=HTMLResponse)
    async def delete_entry(id: int, request: Request):
        form = await request.form()
        verify(request, str(form.get('csrf', '')))
        if store.delete(id):
            refresh_charts()
            request.session['flash'] = {'type': 'success', 'message': 'Đã xóa lời nhắn thành công.'}
        else:
            request.session['flash'] = {'type': 'error', 'message': 'Không tìm thấy lời nhắn này.'}
        return RedirectResponse(url='/', status_code=303)

    @app.get('/stats', response_class=HTMLResponse)
    async def stats(request: Request):
        return page(request, 'stats.html')

    @app.get('/export')
    async def export_data():
        data = json.dumps(store.export(), ensure_ascii=False, indent=2)
        return Response(content=data, media_type='application/json; charset=utf-8', headers={
            'Content-Disposition': 'attachment; filename="echo-guestbook-export.json"'
        })

    @app.get('/api/entries')
    async def api_entries():
        return {'entries': store.all(), 'total': len(store.all())}

    @app.get('/api/stats')
    async def api_stats():
        return store.stats()

    @app.get('/health')
    async def health():
        return {'status': 'ok', 'storage': 'JSON + SQLite', 'entries': store.stats()['total']}

    @app.exception_handler(404)
    async def not_found(request: Request, exc: HTTPException):
        return HTMLResponse(
            content=templates.get_template('404.html').render({
                'request': request, 'csrf': csrf(request), 'active': '',
                'year': datetime.now(TZ).year, 'stats': store.stats(),
                'chart_version': app.state.chart_version, 'chart_base': chart_base,
                'flash': None,
            }), status_code=404)

    return app


app = create_app()

if __name__ == '__main__':
    import uvicorn
    print('\n  ECHO Guestbook running → http://127.0.0.1:8000\n')
    uvicorn.run(app, host='127.0.0.1', port=int(os.getenv('PORT', '8000')))
