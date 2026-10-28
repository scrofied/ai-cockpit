# -*- coding: utf-8 -*-
"""
指挥舱本地服务 —— 提供动作能力（file:// 下浏览器无法触发 Python）

    python serve.py            # 默认 http://127.0.0.1:8765
    python serve.py --port 9000

路由：
    GET  /                    大屏
    GET  /api/state           当前 state（聚合结果）
    POST /api/run   {agent}   触发某个插件立刻跑一次
    POST /api/act   {agent,action,payload}   执行插件声明的动作
    GET  /api/audit?n=50      审计日志

安全边界：
    只监听 127.0.0.1；动作必须在 agent.json 的 actions 白名单里；全部写审计。
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
import re
import sys
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

CONSOLE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CONSOLE)

from core import schema  # noqa: E402
from core.runner import AGENTS, Ctx, discover, jload, run_one  # noqa: E402
from core.aggregate import build  # noqa: E402

AUDIT = os.path.join(CONSOLE, 'audit.jsonl')
STATIC = {'.html': 'text/html; charset=utf-8', '.js': 'application/javascript; charset=utf-8',
          '.json': 'application/json; charset=utf-8', '.png': 'image/png',
          '.css': 'text/css; charset=utf-8', '.svg': 'image/svg+xml'}


def audit(rec: dict):
    rec['at'] = time.strftime('%Y-%m-%d %H:%M:%S')
    try:
        with open(AUDIT, 'a', encoding='utf-8') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    except Exception:
        pass


def load_action_meta(agent_id: str):
    """返回 (meta, 允许的 action id 集合)"""
    raw = jload(os.path.join(AGENTS, agent_id, 'agent.json'), {}) or {}
    raw.setdefault('id', agent_id)
    meta = schema.merge_meta(raw)
    return meta, {a['id'] for a in meta['actions']}


def exec_action(agent_id: str, action_id: str, payload: dict | None):
    if agent_id not in discover():
        return {'ok': False, 'msg': f'没有这个插件：{agent_id}'}
    meta, allowed = load_action_meta(agent_id)
    if action_id not in allowed:
        return {'ok': False, 'msg': f'动作 {action_id} 未在 agent.json 里声明，拒绝执行'}

    p = os.path.join(AGENTS, agent_id, 'fetch.py')
    try:
        spec = importlib.util.spec_from_file_location(f'agent_{agent_id}', p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if not hasattr(mod, 'act'):
            return {'ok': False, 'msg': '该插件没有实现 act()'}
        ctx = Ctx(agent_id, meta)
        r = mod.act(ctx, action_id, payload or {}) or {}
        return {'ok': bool(r.get('ok')), 'msg': str(r.get('msg') or '')[:200]}
    except Exception as e:
        return {'ok': False, 'msg': f'{type(e).__name__}: {str(e)[:160]}',
                'trace': traceback.format_exc()[-600:]}


class Handler(BaseHTTPRequestHandler):
    server_version = 'Console/2.0'

    def log_message(self, fmt, *args):
        pass   # 静默，避免刷屏

    # ---------- 工具 ----------
    def _send(self, code, body: bytes, ctype='application/json; charset=utf-8'):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        try:
            self.wfile.write(body)
        except Exception:
            pass

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode('utf-8'))

    def _body(self):
        n = int(self.headers.get('Content-Length') or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode('utf-8'))
        except Exception:
            return {}

    # ---------- GET ----------
    def do_GET(self):
        u = urlparse(self.path)
        path = u.path

        if path in ('/', '/index.html'):
            path = '/index.html'

        if path == '/api/state':
            return self._json(build())

        if path == '/api/audit':
            n = int((parse_qs(u.query).get('n') or ['50'])[0])
            rows = []
            try:
                with open(AUDIT, encoding='utf-8') as f:
                    rows = [json.loads(x) for x in f if x.strip()][-n:]
            except Exception:
                pass
            return self._json({'rows': rows[::-1]})

        # 静态文件（只允许 console 目录内）
        rel = path.lstrip('/').replace('\\', '/')
        if '..' in rel:
            return self._send(403, b'forbidden', 'text/plain')
        fp = os.path.join(CONSOLE, rel)
        if not os.path.isfile(fp):
            return self._send(404, b'not found', 'text/plain')
        ext = os.path.splitext(fp)[1].lower()
        with open(fp, 'rb') as f:
            return self._send(200, f.read(), STATIC.get(ext, 'application/octet-stream'))

    # ---------- POST ----------
    def do_POST(self):
        u = urlparse(self.path)
        body = self._body()
        ip = self.client_address[0]
        if not (ip.startswith('127.') or ip == '::1'):
            return self._json({'ok': False, 'msg': '只接受本机请求'}, 403)

        if u.path == '/api/run':
            aid = str(body.get('agent') or '')
            if aid not in discover():
                return self._json({'ok': False, 'msg': '没有这个插件'}, 404)
            r = run_one(aid)
            audit({'type': 'run', 'agent': aid, 'ok': r['ok'], 'dur_ms': r['dur_ms'],
                   'error': r['error'][:120], 'ip': ip})
            return self._json({'ok': r['ok'], 'dur_ms': r['dur_ms'],
                               'error': r['error'], 'state': build()})

        if u.path == '/api/act':
            aid = str(body.get('agent') or '')
            act = str(body.get('action') or '')
            r = exec_action(aid, act, body.get('payload') or {})
            audit({'type': 'action', 'agent': aid, 'action': act, 'ok': r.get('ok'),
                   'msg': (r.get('msg') or '')[:120], 'ip': ip,
                   'payload': body.get('payload') or {}})
            return self._json(r)

        return self._json({'ok': False, 'msg': 'unknown endpoint'}, 404)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=8765)
    ap.add_argument('--no-open', action='store_true')
    args = ap.parse_args()

    srv = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    url = f'http://127.0.0.1:{args.port}/'
    print(f'指挥舱已启动：{url}')
    print(f'  插件 {len(discover())} 个 · 动作需要 agent.json 声明 · 审计写 {AUDIT}')
    print('  Ctrl+C 停止')

    if not args.no_open:
        try:
            os.startfile(url)  # noqa: S606
        except Exception:
            pass

    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\n已停止')
    finally:
        srv.server_close()


if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
    main()
