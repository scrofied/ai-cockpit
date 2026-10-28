# -*- coding: utf-8 -*-
"""
示例一：读本地 JSON 文件（最常用）

范式：业务系统定期导出一个 JSON/CSV → 插件读它 → 归一成契约格式。
换成你自己的：改 _SRC 指向你的文件，改字段映射即可。
"""
from __future__ import annotations

import json
import os


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fetch(ctx):
    # ① 路径优先从 config.json 取，取不到用插件自带的 sample.json（保证装上就能跑）
    src = ctx.cfg("paths.example_json") or ctx.path("sample.json")
    if not src or not os.path.exists(src):
        return ctx.unplugged("找不到数据文件，配置 paths.example_json")

    try:
        d = _load(src)
    except Exception as e:
        ctx.log(f"读文件失败: {e}", "ERROR")
        return {"status": "down", "metric": {"value": 0, "unit": "¥"},
                "sub": "文件读取失败", "items": [{"name": "错误", "value": "—",
                "note": str(e)[:24], "tone": "down"}]}

    stores = d.get("stores") or []
    total = sum(float(s.get("amount") or 0) for s in stores)
    coupons = sum(int(s.get("coupons") or 0) for s in stores)
    target = float(d.get("target") or 0)
    pct = (total / target * 100) if target else 0

    items = [{"name": s.get("name", "—"), "value": f"¥{float(s.get('amount') or 0):,.0f}",
              "note": f"{int(s.get('coupons') or 0)} 券", "tone": "ok"} for s in stores]
    if target:
        items.append({"name": "目标完成", "value": f"{pct:.0f}%",
                      "note": f"目标 ¥{target:,.0f}",
                      "tone": "ok" if pct >= 100 else ("warn" if pct >= 60 else "down")})

    return {
        "status": "ok",
        "metric": {"value": round(total), "unit": "¥"},   # unit 只影响显示，¥/$ 会自动加前缀
        "sub": f"{len(stores)} 条记录 · {coupons} 券",
        "items": items,
        "events": [{"at": ctx.now(), "kind": "ship",
                    "text": f"读到 {len(stores)} 条 · 合计 ¥{total:,.0f}"}],
        "todo": [] if not target or pct >= 100 else
                [{"text": f"离目标还差 ¥{max(0, target - total):,.0f}", "pri": "P1"}],
        "schedule": {"last": ctx.now(), "next": ""},
        "source": "本地 JSON",
        "source_path": src,
        "source_ts": d.get("date", ""),
    }


def act(ctx, action_id, payload=None):
    if action_id == "refresh":
        return {"ok": True, "msg": "已重新读取"}
    return {"ok": False, "msg": f"未实现：{action_id}"}
