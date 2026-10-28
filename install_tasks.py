# -*- coding: utf-8 -*-
"""
注册 Windows 计划任务 —— 每个插件按自己的 interval 定时跑

    python install_tasks.py            # 注册 / 覆盖
    python install_tasks.py --remove   # 全部删除
    python install_tasks.py --list     # 只看当前状态

用的是当前登录用户的计划任务（不需要管理员），任务名以 AIConsole_ 开头。
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys

CONSOLE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CONSOLE)
from core.runner import AGENTS, discover, jload  # noqa: E402

PY = sys.executable
PREFIX = 'AIConsole_'


def run(cmd):
    p = subprocess.run(cmd, shell=True, capture_output=True)
    return p.returncode, ((p.stdout or b'') + (p.stderr or b'')).decode('utf-8', 'replace')


def tasks():
    out = []
    for aid in discover():
        meta = jload(os.path.join(AGENTS, aid, 'agent.json'), {}) or {}
        interval = max(1, int((meta.get('interval') or 300) // 60))
        out.append((aid, interval, meta.get('name') or aid))
    return out


def main():
    if '--list' in sys.argv:
        for aid, m, name in tasks():
            rc, out = run(f'schtasks /query /tn "{PREFIX}{aid}" /fo list 2>nul')
            print(f'  {aid:<8} {name:<5} 每 {m:>2} 分钟  '
                  f'{"已注册" if rc == 0 else "未注册"}')
        return 0

    if '--remove' in sys.argv:
        for aid, _m, _n in tasks():
            run(f'schtasks /delete /tn "{PREFIX}{aid}" /f 2>nul')
            print(f'  删除 {PREFIX}{aid}')
        run(f'schtasks /delete /tn "{PREFIX}aggregate" /f 2>nul')
        print(f'  删除 {PREFIX}aggregate')
        return 0

    for aid, m, name in tasks():
        cmd = f'"{PY}" "{os.path.join(CONSOLE, "core", "runner.py")}" --agent {aid}'
        rc, out = run(f'schtasks /create /tn "{PREFIX}{aid}" /tr "{cmd}" '
                      f'/sc minute /mo {m} /f')
        print(f'  {"OK " if rc == 0 else "ERR"} {aid:<8} {name:<5} 每 {m} 分钟'
              + ('' if rc == 0 else f'  {out[:80]}'))

    cmd = f'"{PY}" "{os.path.join(CONSOLE, "core", "aggregate.py")}"'
    rc, out = run(f'schtasks /create /tn "{PREFIX}aggregate" /tr "{cmd}" '
                  f'/sc minute /mo 1 /f')
    print(f'  {"OK " if rc == 0 else "ERR"} aggregate 每 1 分钟'
          + ('' if rc == 0 else f'  {out[:80]}'))

    print('\n已注册。查看：python install_tasks.py --list')
    print('删除：python install_tasks.py --remove')
    return 0


if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
    sys.exit(main())
