# -*- coding: utf-8 -*-
"""
配置加载 —— 所有机器相关的路径、账号、参数都放 config.json，不进仓库。

优先级：config.json > config.example.json > 代码内默认值
插件里用 ctx.cfg('paths.hire') 取值，拿不到就返回 unplugged，不要抛异常。
"""
from __future__ import annotations

import json
import os

CONSOLE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRIVATE = os.path.join(CONSOLE, 'config.json')
EXAMPLE = os.path.join(CONSOLE, 'config.example.json')

_cache = None


def _load_file(p):
    try:
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def all_cfg() -> dict:
    global _cache
    if _cache is None:
        base = _load_file(EXAMPLE)
        over = _load_file(PRIVATE)
        _cache = _deep_merge(base, over)
    return _cache


def _deep_merge(a: dict, b: dict) -> dict:
    out = dict(a or {})
    for k, v in (b or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def get(path: str, default=None):
    """get('paths.hire') / get('store.target_weekday', 3000)"""
    cur = all_cfg()
    for part in path.split('.'):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    if cur in ('', None):
        return default
    return cur


def has_private() -> bool:
    return os.path.exists(PRIVATE)


def reload():
    global _cache
    _cache = None
    return all_cfg()
