# -*- coding: utf-8 -*-
"""
插件数据契约 —— 框架唯一认识的格式。

设计原则：
1. 宽容：插件少给字段就补默认，不让一个手抖的插件把整块屏搞崩
2. 截断：所有字符串强制限长，防止插件把整段日志倒进卡片
3. 边界：status / tone / kind 只能取枚举值，非法值降级成安全值
"""
from __future__ import annotations

STATUSES = ('ok', 'stale', 'weak', 'down', 'unplugged')
TONES = ('ok', 'warn', 'down', 'off')
KINDS = ('dispatch', 'ship', 'rework')

MAX_ITEMS = 6      # 前端只显示 4 条，留 2 条给抽屉
MAX_EVENTS = 12
MAX_TODO = 6
MAX_ACTIONS = 6
MAX_STR = 80       # 单字段最长
MAX_TITLE = 140    # 事件描述最长

DEFAULT_METRIC = {'label': '—', 'value': 0, 'unit': ''}


def s(v, n: int = MAX_STR) -> str:
    """安全字符串：转 str、去控制字符、截断"""
    if v is None:
        return ''
    t = str(v).replace('\n', ' ').replace('\r', ' ').strip()
    return t[:n]


def num(v):
    """数字优先；转不动就原样返回字符串（框架允许 metric.value 是 '2/2'）"""
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return v
    try:
        f = float(str(v).replace(',', '').replace('¥', '').replace('$', '').strip())
        return int(f) if f == int(f) else round(f, 2)
    except Exception:
        return s(v, 24)


def one_of(v, allowed, fallback):
    return v if v in allowed else fallback


def clean_item(it) -> dict | None:
    if not isinstance(it, dict):
        return None
    name = s(it.get('name'), 20)
    if not name:
        return None
    return {
        'name': name,
        'value': s(it.get('value'), 22),
        'note': s(it.get('note'), 34),
        'tone': one_of(it.get('tone'), TONES, 'ok'),
    }


def clean_event(e) -> dict | None:
    if not isinstance(e, dict):
        return None
    text = s(e.get('text'), MAX_TITLE)
    if not text:
        return None
    return {
        'at': s(e.get('at'), 12),
        'agent': s(e.get('agent'), 16),
        'kind': one_of(e.get('kind'), KINDS, 'dispatch'),
        'text': text,
    }


def clean_action(a) -> dict | None:
    if not isinstance(a, dict):
        return None
    aid = s(a.get('id'), 32)
    label = s(a.get('label'), 16)
    if not aid or not label:
        return None
    return {
        'id': aid,
        'label': label,
        'confirm': s(a.get('confirm') or f'确认执行「{label}」？', 60),
        'danger': bool(a.get('danger')),
        'payload': a.get('payload') if isinstance(a.get('payload'), dict) else {},
    }


def merge_meta(meta: dict) -> dict:
    """agent.json 的元数据规范化"""
    return {
        'id': s(meta.get('id'), 24),
        'name': s(meta.get('name'), 10),
        'icon': s(meta.get('icon') or '●', 4),
        'color': s(meta.get('color') or '#a78bfa', 12),
        'order': int(meta.get('order') or 99),
        'interval': max(30, int(meta.get('interval') or 300)),
        'timeout': max(5, int(meta.get('timeout') or 60)),
        'heavy': bool(meta.get('heavy')),
        'metric': {
            'label': s((meta.get('metric') or {}).get('label') or '—', 12),
            'unit': s((meta.get('metric') or {}).get('unit') or '', 4),
        },
        'actions': [x for x in (clean_action(a) for a in (meta.get('actions') or [])) if x][:MAX_ACTIONS],
        'demo': meta.get('demo') if isinstance(meta.get('demo'), dict) else {},
    }


def validate(meta: dict, raw) -> dict:
    """把插件返回的任意 dict 洗成契约格式。raw 为 None 表示插件没跑出结果。"""
    m = merge_meta(meta or {})
    if not isinstance(raw, dict):
        return {
            'id': m['id'], 'status': m.get('unplugged_status', 'down'),
            'metric': dict(DEFAULT_METRIC, label=m['metric']['label']),
            'sub': '插件无返回', 'items': [], 'events': [], 'todo': [],
        }

    status = one_of(raw.get('status'), STATUSES, 'down')

    metric = raw.get('metric') or {}
    mv = num(metric.get('value'))
    cleaned_metric = {
        'label': s(metric.get('label') or m['metric']['label'], 12),
        'value': mv if mv != '' else 0,
        'unit': s(metric.get('unit') or m['metric']['unit'], 4),
    }

    items = [x for x in (clean_item(i) for i in (raw.get('items') or [])) if x][:MAX_ITEMS]
    events = [x for x in (clean_event(e) for e in (raw.get('events') or [])) if x][:MAX_EVENTS]
    todo = []
    for t in (raw.get('todo') or [])[:MAX_TODO]:
        if not isinstance(t, dict):
            continue
        txt = s(t.get('text'), 60)
        if txt:
            todo.append({'text': txt, 'pri': s(t.get('pri') or 'P2', 3)})

    gate = raw.get('gate') if isinstance(raw.get('gate'), dict) else {}
    cleaned_gate = {
        'auto': max(0, int(gate.get('auto') or 0)),
        'model': max(0, int(gate.get('model') or 0)),
        'human': max(0, int(gate.get('human') or 0)),
    }

    return {
        'id': m['id'],
        'status': status,
        'metric': cleaned_metric,
        'sub': s(raw.get('sub'), 48),
        'items': items,
        'events': events,
        'todo': todo,
        'gate': cleaned_gate,
        'schedule': {
            'last': s((raw.get('schedule') or {}).get('last'), 12),
            'next': s((raw.get('schedule') or {}).get('next'), 12),
        },
        'source': s(raw.get('source'), 24),
        'source_path': s(raw.get('source_path'), 120),
        'source_ts': s(raw.get('source_ts'), 32),
    }
