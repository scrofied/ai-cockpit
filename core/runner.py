# -*- coding: utf-8 -*-
"""
单插件执行器 —— 每个 agent 跑在**自己的进程**里。

    python core/runner.py --agent store
    python core/runner.py --all              # 手动全跑一遍（调试用）
    python core/runner.py --agent store --dry  # 只打印不写 out.json

为什么独立进程：门店探针要开 ego 浏览器，慢且偶发崩溃（exit 3221225786）。
独立进程 + 超时 + 上次成功缓存，保证一个插件挂了不影响别人，也不清空大屏。

插件只需要提供 fetch.py：
    def fetch(ctx) -> dict
可选的写回动作：
    def act(ctx, action_id, payload) -> dict
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
import sys
import time
import traceback
import urllib.request
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutTimeout

CONSOLE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CONSOLE)

from core import schema  # noqa: E402

AGENTS = os.path.join(CONSOLE, 'agents')
LOG_MAX = 400_000


def jload(p, default=None):
    try:
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def atomic_write_json(path, obj):
    tmp = path + '.tmp'
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


class Ctx:
    """给插件的工具箱。插件只用得到这几个方法。"""

    def __init__(self, agent_id: str, meta: dict):
        self.id = agent_id
        self.meta = meta
        self.dir = os.path.join(AGENTS, agent_id)
        self.console = CONSOLE

    # ---------- 日志 ----------
    def log(self, msg, level='INFO'):
        line = f'[{time.strftime("%m-%d %H:%M:%S")}] {level} {msg}\n'
        p = os.path.join(self.dir, 'run.log')
        try:
            if os.path.exists(p) and os.path.getsize(p) > LOG_MAX:
                os.replace(p, p + '.1')
            with open(p, 'a', encoding='utf-8') as f:
                f.write(line)
        except Exception:
            pass

    # ---------- 上次成功的数据 ----------
    @property
    def cache(self):
        return jload(os.path.join(self.dir, '.cache.json'), {}) or {}

    def cache_set(self, payload: dict):
        atomic_write_json(os.path.join(self.dir, '.cache.json'), payload)

    # ---------- 网络 ----------
    def http(self, url: str, timeout: int = 10, headers: dict | None = None) -> bytes:
        """无代理 GET。国内必须绕代理，否则 binance 会超时。"""
        op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        hdr = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        if headers:
            hdr.update(headers)
        return op.open(urllib.request.Request(url, headers=hdr), timeout=timeout).read()

    def http_json(self, url: str, timeout: int = 10):
        return json.loads(self.http(url, timeout).decode('utf-8'))

    # ---------- 浏览器（给重型插件用，懒加载）----------
    def browser(self, space: str, page_label: str = 'p1'):
        """返回浏览器插件提供的 CDP 实例。插件目录通过 agent.json 的 browser_path 注入 sys.path。"""
        mt = self.meta.get('browser_path')
        if mt and mt not in sys.path:
            sys.path.insert(0, mt)
        from mt.ego import EgoCDP  # noqa: WPS433
        return EgoCDP(space=space, page_label=page_label)

    # ---------- 未接入的快捷返回 ----------
    def unplugged(self, sub='未配置'):
        return {
            'status': 'unplugged',
            'metric': {'value': 0, 'unit': ''},
            'sub': sub[:48],
            'items': [{'name': '未接入', 'value': '—', 'note': sub[:20], 'tone': 'off'}],
            'events': [], 'todo': [],
        }

    # ---------- 配置 ----------
    def cfg(self, path: str, default=None):
        """读 config.json：ctx.cfg('paths.hire_boss_logs')。拿不到返回 default。"""
        from core import config as _cfg
        return _cfg.get(path, default)

    # ---------- 杂项 ----------
    def now(self):
        return time.strftime('%H:%M')

    def path(self, *parts):
        return os.path.join(self.dir, *parts)

    def read_json(self, p, default=None):
        return jload(p, default)


def load_plugin(agent_id: str, meta: dict):
    """动态载入 agents/<id>/fetch.py"""
    p = os.path.join(AGENTS, agent_id, 'fetch.py')
    if not os.path.exists(p):
        raise FileNotFoundError(f'缺少 {p}')
    spec = importlib.util.spec_from_file_location(f'agent_{agent_id}', p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_one(agent_id: str, dry: bool = False) -> dict:
    adir = os.path.join(AGENTS, agent_id)
    meta_raw = jload(os.path.join(adir, 'agent.json'), {}) or {}
    meta_raw.setdefault('id', agent_id)
    meta = schema.merge_meta(meta_raw)
    out_path = os.path.join(adir, 'out.json')

    t0 = time.time()
    ctx = Ctx(agent_id, meta_raw)
    result = {'agent': agent_id, 'ok': False, 'ts': time.time(),
              'dur_ms': 0, 'error': '', 'data': None}

    try:
        mod = load_plugin(agent_id, meta)
        if not hasattr(mod, 'fetch'):
            raise AttributeError('fetch.py 里没有 fetch(ctx)')

        timeout = meta['timeout']
        with ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(mod.fetch, ctx)
            try:
                raw = fut.result(timeout=timeout)
            except FutTimeout:
                raise TimeoutError(f'fetch 超过 {timeout}s 未返回')

        data = schema.validate(meta, raw)
        data['id'] = agent_id
        result['data'] = data
        result['ok'] = True
        # 只有成功才更新缓存，失败时大屏继续显示上次的
        try:
            ctx.cache_set(raw if isinstance(raw, dict) else {})
        except Exception:
            pass
    except Exception as e:
        result['error'] = f'{type(e).__name__}: {str(e)[:200]}'
        ctx.log(result['error'], 'ERROR')
        ctx.log(traceback.format_exc()[-1200:], 'TRACE')
        # 失败降级：用上次成功的原始数据（状态标 down/stale，保留内容）
        cached = ctx.cache
        if cached:
            data = schema.validate(meta, cached)
            data['status'] = 'stale'
            data['sub'] = (data.get('sub') or '')[:36] + ' · 采集失败'
            result['data'] = data
            result['ok'] = False
        else:
            result['data'] = schema.validate(meta, None)

    result['dur_ms'] = int((time.time() - t0) * 1000)

    if not dry:
        atomic_write_json(out_path, result)
    return result


def discover() -> list[str]:
    if not os.path.isdir(AGENTS):
        return []
    out = []
    for name in sorted(os.listdir(AGENTS)):
        d = os.path.join(AGENTS, name)
        if os.path.isdir(d) and os.path.exists(os.path.join(d, 'agent.json')):
            out.append(name)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--agent')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--dry', action='store_true')
    args = ap.parse_args()

    ids = discover() if args.all else ([args.agent] if args.agent else [])
    if not ids:
        print('用法: python core/runner.py --agent <id> | --all')
        return 2

    for aid in ids:
        r = run_one(aid, dry=args.dry)
        d = r.get('data') or {}
        met = d.get('metric') or {}
        flag = 'OK ' if r['ok'] else 'ERR'
        print(f"[{flag}] {aid:<8} {r['dur_ms']:>6}ms  "
              f"{d.get('status','?'):<10} {met.get('label','')}={met.get('value','')}"
              f"{met.get('unit','')}"
              + (f"  ! {r['error'][:70]}" if r['error'] else ''))
    return 0


if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
    sys.exit(main())
