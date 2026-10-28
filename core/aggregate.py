# -*- coding: utf-8 -*-
"""
聚合器 —— 把 agents/*/out.json 拼成大屏唯一认的 state.json。

    python core/aggregate.py            # 写 state.json + state.js
    python core/aggregate.py --check    # 只打印，不写

它不做任何业务判断：插件说什么就是什么，这里只负责排序、汇总、统计健康度。
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta

CONSOLE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CONSOLE)

from core import schema  # noqa: E402
from core.runner import AGENTS, discover, jload, atomic_write_json  # noqa: E402

TZ = timezone(timedelta(hours=8))


def build() -> dict:
    agents, events, todo = [], [], []
    gate = {'auto': 0, 'model': 0, 'human': 0}
    oldest = None

    for aid in discover():
        meta = schema.merge_meta(jload(os.path.join(AGENTS, aid, 'agent.json'), {}) or {'id': aid})
        out = jload(os.path.join(AGENTS, aid, 'out.json'), None)

        if not out or not out.get('data'):
            # 从没跑过：给一张"未接入"卡，占位但不报错
            data = schema.validate(meta, None)
            data['status'] = 'unplugged'
            data['sub'] = data.get('sub') or '插件未运行'
            ran_at = None
        else:
            data = out['data']
            ran_at = out.get('ts')

        data['id'] = aid
        data['name'] = meta['name'] or aid
        data['icon'] = meta['icon']
        data['color'] = meta['color']
        data['order'] = meta['order']
        data['actions'] = meta['actions']
        data['demo'] = meta['demo']
        data['ran_at'] = ran_at
        data['ok'] = bool(out.get('ok')) if out else False
        data['error'] = (out or {}).get('error', '')

        g = data.get('gate') or {}
        for k in gate:
            gate[k] += int(g.get(k) or 0)

        for e in data.get('events') or []:
            e = dict(e)
            e.setdefault('agent', aid)
            events.append(e)
        for t in data.get('todo') or []:
            todo.append({'agent': data['name'], 'text': t['text'], 'pri': t['pri']})

        if ran_at is None:
            oldest = ran_at
        elif oldest is not False:
            oldest = ran_at if oldest is None else min(oldest, ran_at)

        agents.append(data)

    agents.sort(key=lambda a: a['order'])
    events.sort(key=lambda e: e.get('at') or '', reverse=True)

    health = {'ok': 0, 'stale': 0, 'weak': 0, 'down': 0, 'unplugged': 0}
    for a in agents:
        health[a['status']] = health.get(a['status'], 0) + 1

    tot = sum(gate.values()) or 1
    return {
        'v': 2,
        'generated_at': datetime.now(TZ).isoformat(timespec='seconds'),
        'health': health,
        'agents': agents,
        'gate': gate,
        'gate_total': sum(gate.values()),
        'gate_pct': round((gate['auto'] + gate['model']) / tot * 100),
        'events': events[:24],
        'todo': todo[:8],
        'meta': {'agent_count': len(agents)},
    }


def main():
    state = build()
    check = '--check' in sys.argv
    if not check:
        js = json.dumps(state, ensure_ascii=False, indent=1)
        atomic_write_json(os.path.join(CONSOLE, 'state.json'), state)
        tmp = os.path.join(CONSOLE, 'state.js.tmp')
        with open(tmp, 'w', encoding='utf-8') as f:
            f.write('window.STATE=' + js + ';\n')
        os.replace(tmp, os.path.join(CONSOLE, 'state.js'))

    h = state['health']
    print(f"[{state['generated_at']}] agents={len(state['agents'])} "
          f"ok={h.get('ok')} stale={h.get('stale')} weak={h.get('weak')} "
          f"down={h.get('down')} unplugged={h.get('unplugged')} "
          f"events={len(state['events'])}")
    for a in state['agents']:
        m = a['metric']
        print(f"  {a['name']:<5} {a['status']:<10} {m['label']}={m['value']}{m['unit']}"
              f"  {a['sub']}")
    return 0


if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
    sys.exit(main())
