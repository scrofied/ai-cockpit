# -*- coding: utf-8 -*-
"""
示例三：扫目录数文件

范式：业务没有数据库，只有一堆产出物（视频、文档、图片）→ 数文件 + 看时间戳，
     就能反映「积压多少、今天做了多少」。这是最省事的监控方式。
"""
from __future__ import annotations

import glob
import os
import time


def fetch(ctx):
    root = ctx.cfg("paths.example_scan") or ctx.path("inbox")
    if not root or not os.path.isdir(root):
        return ctx.unplugged("找不到目录，配置 paths.example_scan")

    files = [f for f in glob.glob(os.path.join(root, "*")) if os.path.isfile(f)]
    if not files:
        return {"status": "ok", "metric": {"value": 0, "unit": "个"},
                "sub": "目录是空的", "items": [{"name": "待处理", "value": "0",
                "note": "inbox 为空", "tone": "ok"}], "events": [], "todo": []}

    now = time.time()
    ages = [(now - os.path.getmtime(f)) / 86400 for f in files]
    newest = min(ages)
    oldest = max(ages)
    today = sum(1 for a in ages if a < 1)

    def human(d):
        if d < 1:
            return f"{int(d * 24)} 小时前"
        return f"{int(d)} 天前"

    items = [
        {"name": "待处理", "value": str(len(files)), "note": "inbox 文件数", "tone": "ok"},
        {"name": "今日新增", "value": str(today), "note": "按修改时间", "tone": "ok"},
        {"name": "最旧", "value": human(oldest), "note": "考虑清理", 
         "tone": "warn" if oldest > 7 else "ok"},
        {"name": "最新", "value": human(newest), "note": "刚落盘", "tone": "ok"},
    ]

    return {
        "status": "ok",
        "metric": {"value": len(files), "unit": "个"},
        "sub": f"inbox 目录 · 最近 1 个 {human(newest)}",
        "items": items,
        "events": [{"at": ctx.now(), "kind": "ship",
                    "text": f"扫到 {len(files)} 个文件，今日新增 {today}"}],
        "todo": ([{"text": f"有文件积压 {int(oldest)} 天，考虑清理", "pri": "P2"}]
                 if oldest > 7 else []),
        "schedule": {"last": ctx.now(), "next": ""},
        "source": "目录扫描",
        "source_path": root,
        "source_ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now - newest * 86400)),
    }


def act(ctx, action_id, payload=None):
    if action_id == "refresh":
        return {"ok": True, "msg": "已重扫目录"}
    return {"ok": False, "msg": f"未实现：{action_id}"}
