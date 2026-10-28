# 安装：把下面这段复制给你的 AI

> 适用于 Codex、WorkBuddy、Claude Code、Cursor 等能执行命令的 AI。
> 你不用看懂代码，它自己会跑检查、自己修错、自己问你要数据。

---

## 一、直接粘这段

```
我要安装「AI 指挥舱」——一个本地运行的 agent 监控大屏，代码我已经下载到本目录了。
请按顺序执行，每一步出问题先自己排查，不要让我手动调：

1. 确认 Python 版本：python --version（macOS/Linux 试 python3）。
   低于 3.9 就停下来告诉我怎么升级。

2. 跑一次全量采集：python core/runner.py --all
   期望看到若干 [OK]，其中 hello / example-json / example-http / example-scan 必须是 OK。
   如果有 [ERR]，去读 agents/<那个插件>/run.log，把原因告诉我。

3. 生成大屏数据：python core/aggregate.py
   期望输出形如 `agents=4 ok=4 ...` 且生成 state.json、state.js。

4. 打开 index.html（Windows 直接双击），确认页面出现 4 个岗位卡。
   如果空白或者只有旧的硬编码数据，说明 JS 报错了，用浏览器控制台看错误告诉我。

5. 以上都通过后，问我：我的业务数据在哪里？
   （可能是：一个 JSON/CSV 文件、一个 HTTP 接口、一个数据库、或者一个装满产出物的目录）
   拿到路径后，帮我新建 agents/<业务名>/agent.json 和 fetch.py。
   参考现成三种范式照抄：
     - agents/example-json/  读本地文件
     - agents/example-http/  调 HTTP 接口
     - agents/example-scan/  扫目录数文件

6. 每写完一个插件，立刻跑 python core/runner.py --agent <业务名> 验证。
   有错就自己看 agents/<业务名>/run.log 修到 OK，再告诉我结果。
   最后跑 python core/aggregate.py，确认大屏多了一列。

铁律：
- 不要修改 core/ 下的任何文件，那是框架。
- 不要动我已经能跑的插件。
- 所有路径写进 config.json（复制 config.example.json 改），不要硬编码在 fetch.py 里。
- 插件里任何数据读不到，返回 ctx.unplugged('原因')，不要抛异常。
```

---

## 二、为什么要给 AI 这段，而不是让你看文档

因为这套东西的安装**不是点下一步**，而是「摸清你机器上的 Python、跑通示例、再按你的数据源写一个插件」。这三步每一步都可能因为环境差异卡住，而卡住时的报错信息只有 AI 看得懂、改得快。

人看文档装，卡在第二步就开始搜教程了。AI 装，卡住它会自己读日志、改路径、重试。

---

## 三、AI 装完之后，你该看到什么

```
┌────────┬────────┬────────┬────────┐
│ 示例   │ 文件型 │ 接口型 │ 目录型 │
│ 133件  │ ¥2,130 │ $80,792│ 5 个   │
└────────┴────────┴────────┴────────┘
```

四列都在跑，说明框架通了。这时候你的业务还没接 —— 接下来每接一个，就多一列。

**验证标准只有一条**：双击 `index.html`，看到 `示例` 这一列有数字。有，就是装好了。

---

## 四、AI 装不下去时，你手动排查这三步

| 现象 | 先看这里 |
|---|---|
| 双击 bat 闪一下就关 | 命令行跑 `python serve.py`，看报什么错 |
| `[ERR]` 说找不到模块 | Python 版本太低，或者没在项目根目录执行 |
| 页面空白 / 只有旧数据 | 浏览器 F12 → Console，看红色报错 |
| 某一列一直「未接入」 | 对应插件的 `run.log`；或 `config.json` 里那条路径没填 |

---

## 五、如果你想让 AI 顺便帮你挂定时任务

再补一句给它：

```
顺便帮我注册 Windows 计划任务，让每个插件按 agent.json 里的 interval 自动跑：
执行 python install_tasks.py，然后 python install_tasks.py --list 确认都注册上了。
如果 schtasks 报权限问题，告诉我怎么用管理员身份重跑。
```

macOS / Linux 用户：让它把 `install_tasks.py` 换成 `crontab -e` 或 `launchd` 的写法，逻辑一样（按 interval 调 `core/runner.py --agent <id>`）。
