# -*- coding: utf-8 -*-
"""
示例二：调 HTTP 接口

范式：业务系统有 API → ctx.http_json() 拉一次 → 归一成契约格式。

★ 关键点：ctx.http() 走「无代理」通道。国内很多接口挂代理会超时，
  这也是为什么框架把 http 封装在 ctx 里，别自己 import requests。

演示用的是币安公开行情（无需 key）。换成你自己的：
  改 URL 和字段映射，配置项写到 config.json 的 paths.example_http_url。
"""
from __future__ import annotations

SYMBOLS = (("BTCUSDT", "BTC"), ("ETHUSDT", "ETH"), ("SOLUSDT", "SOL"))
DEFAULT_HOST = "https://data-api.binance.vision"


def fetch(ctx):
    host = ctx.cfg("example_http_host") or DEFAULT_HOST
    items, ok_n = [], 0
    first_price = 0.0

    for sym, label in SYMBOLS:
        try:
            d = ctx.http_json(f"{host}/api/v3/ticker/24hr?symbol={sym}", timeout=8)
            px = float(d["lastPrice"])
            pct = float(d["priceChangePercent"])
            if ok_n == 0:
                first_price = px
            ok_n += 1
            items.append({
                "name": label,
                "value": f"${px:,.0f}" if px >= 100 else f"${px:,.2f}",
                "note": f"24h {pct:+.2f}%",
                "tone": "ok",
            })
        except Exception as e:
            ctx.log(f"{sym} 请求失败: {e}", "ERROR")
            items.append({"name": label, "value": "—", "note": "接口超时", "tone": "off"})

    if ok_n == 0:
        return {
            "status": "down",
            "metric": {"value": 0, "unit": ""},
            "sub": "接口全部失败，检查网络或换 host",
            "items": items,
            "events": [], "todo": [{"text": "接口不通，检查网络", "pri": "P2"}],
        }

    return {
        "status": "ok" if ok_n == len(SYMBOLS) else "weak",
        "metric": {"value": round(first_price), "unit": "$"},
        "sub": f"公开行情接口 · {ok_n}/{len(SYMBOLS)} 成功",
        "items": items,
        "events": [{"at": ctx.now(), "kind": "dispatch",
                    "text": f"拉取行情 {ok_n} 个标的"}],
        "todo": [],
        "schedule": {"last": ctx.now(), "next": ""},
        "source": "HTTP 接口",
        "source_path": host,
        "source_ts": "",
    }


def act(ctx, action_id, payload=None):
    if action_id == "refresh":
        return {"ok": True, "msg": "已触发拉取，稍等几秒"}
    return {"ok": False, "msg": f"未实现：{action_id}"}
