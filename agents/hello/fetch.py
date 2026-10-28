# -*- coding: utf-8 -*-
"""
示例插件 —— 复制这个目录改成你自己的 Agent，改三处就能用：
  1. agent.json 里的 id / name / icon / color / metric
  2. 本文件的 _read_your_data()，换成读你自己的数据源
  3. 需要动作就改 act()

这个插件不依赖任何外部系统，装上就能跑，用来确认框架是通的。
"""
from __future__ import annotations

import os
import random
import time


def _read_your_data():
    """
    换成你自己的数据读取逻辑。可以是：
      - 读一个 JSON / CSV / SQLite
      - 调一个 HTTP 接口（用 ctx.http_json）
      - 扫一个目录数文件
    下面只是演示返回值结构。
    """
    # 演示：每次跑给一个随机数，证明插件真的在重新执行
    today = time.strftime('%Y-%m-%d')
    n = random.randint(100, 140)
    return {
        'date': today,
        'processed': n,
        'queued': random.randint(0, 20),
        'success_rate': 98.4,
        'avg_seconds': 1.8,
        'errors': 0,
        'recent': [
            {'at': time.strftime('%H:%M', time.localtime(time.time() - 300)), 'text': '处理批次 A'},
            {'at': time.strftime('%H:%M', time.localtime(time.time() - 900)), 'text': '处理批次 B'},
        ],
    }


def fetch(ctx):
    data = _read_your_data()

    # ctx.cfg 读 config.json，例如：
    #   root = ctx.cfg('paths.my_agent')
    #   if not root or not os.path.exists(root):
    #       return ctx.unplugged('未配置 paths.my_agent')
    _ = ctx.cfg('paths.hello_demo')   # 这行只是演示怎么读配置

    items = [
        {'name': '队列', 'value': str(data['queued']), 'note': '待处理',
         'tone': 'warn' if data['queued'] > 10 else 'ok'},
        {'name': '成功率', 'value': f"{data['success_rate']}%", 'note': '近 24h', 'tone': 'ok'},
        {'name': '平均耗时', 'value': f"{data['avg_seconds']}s", 'note': '单件', 'tone': 'ok'},
        {'name': '异常', 'value': str(data['errors']), 'note': '今日',
         'tone': 'ok' if data['errors'] == 0 else 'down'},
    ]

    return {
        'status': 'ok',
        'metric': {'value': data['processed'], 'unit': '件'},
        'sub': f"示例插件 · {data['date']}",
        'items': items,
        'events': [{'at': r['at'], 'kind': 'dispatch', 'text': r['text']}
                   for r in data['recent']],
        'todo': ([{'text': '队列积压，检查下游', 'pri': 'P1'}]
                 if data['queued'] > 15 else []),
        'schedule': {'last': ctx.now(), 'next': ''},
        'source': '内置示例',
        'source_path': os.path.dirname(os.path.abspath(__file__)),
        'source_ts': time.strftime('%Y-%m-%dT%H:%M:%S'),
        # 可选：给底部闸门贡献计数
        'gate': {'auto': 0, 'model': 0, 'human': 0},
    }


def act(ctx, action_id, payload=None):
    if action_id == 'ping':
        ctx.log('收到测试动作')
        return {'ok': True, 'msg': f'收到！参数 {payload or "{}"}'}
    return {'ok': False, 'msg': f'未实现的动作：{action_id}'}
