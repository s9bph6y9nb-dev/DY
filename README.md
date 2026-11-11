# Cloud Auto Task Demo —— 一个真正会按时醒来的云端任务

> 每天北京时间 **09:17**，GitHub 会临时开一台 Ubuntu 机器 → 拉取本仓库代码 → 跑单元测试 → 执行 Python 任务 → 把 `output/` 打包成可下载的 Artifact → 销毁机器。
> 你不需要任何服务器、不需要开机、不需要保持在线。

这个项目是"GitHub Actions 云端自动任务"的第一个可运行样本，刻意做到：

- **零第三方依赖**：只用 Python 标准库，`pip install` 失败也跑得起来；
- **可本地复现**：同一份代码 `python -m app.main` 就能跑，云端只是换了触发方式；
- **有测试、有日志、有产物、有通知开关**，对应生产任务的最小骨架；
- **把踩坑点写在代码注释里**（时区、空输入、一次性 Runner）。

---

## 0. 本机验证结果

| 验证项 | 命令 | 结果 |
| --- | --- | --- |
| 单元测试 | `python -m unittest discover -s tests -v` | 12 个用例全部通过 |
| 本地执行 | `python -m app.main` | 退出码 0，生成 3 个文件 |
| 模拟云端执行 | 注入 `GITHUB_RUN_ID/GITHUB_SHA/GITHUB_RUN_NUMBER` 后运行 | Run ID / Commit 正确进报告，退出码 0 |
| 工作流 YAML | PyYAML 解析 + 结构断言 | 通过（7 个 step、权限、并发组、cron/timezone 均正确） |
| Action 版本 | 2026-11-11 核实 `releases/latest` | `checkout@v7` / `setup-python@v7` / `upload-artifact@v7` |

> 注意：本地跑通 ≠ 云端跑通。云端多出来的变量是：默认分支、Secrets、Runner 环境、调度延迟。

---

## 1. 项目结构

```
cloud-auto-task/
├── .github/
│   ├── workflows/daily-task.yml       # 触发条件 + 执行步骤（本项目的大脑）
│   └── dependabot.yml                 # 每周自动检查 Action 大版本更新
├── app/
│   ├── __init__.py
│   ├── main.py                        # 入口：串流程、定退出码
│   ├── task.py                        # 业务：生成报告并落盘
│   ├── config.py                      # 配置：环境变量 > config.json > 模板 > 默认
│   └── notifier.py                    # 通知：群机器人 Webhook（默认关闭）
├── config/config.example.json         # 配置模板（可提交）
├── tests/test_task.py                 # 单元测试（stdlib unittest）
├── output/                            # 运行产物（.gitkeep 占位）
├── requirements.txt                   # 依赖清单（当前为空，纯标准库）
├── .gitignore
└── README.md
```

职责边界要记牢：**Actions 只负责"什么时候跑、在哪跑"，不负责业务逻辑。** 业务全在 `app/` 里。

---

## 2. 本地先跑通（不碰 GitHub）

```bash
cd cloud-auto-task
python -m unittest discover -s tests -v   # 先跑测试
python -m app.main                        # 再跑任务
```

预期输出（节选）：

```
INFO  cloud-auto-task | ===== 云端任务开始 =====
INFO  cloud-auto-task | 任务=daily-cloud-task 时区=Asia/Shanghai 输出目录=output
INFO  cloud-auto-task | 报告内容：{ "task": "daily-cloud-task", "status": "success", ... }
INFO  cloud-auto-task | 通知结果：{"status": "skipped", "reason": "notify 未启用"}
INFO  cloud-auto-task | ===== 云端任务成功结束 =====
```

生成文件：

| 文件 | 内容 |
| --- | --- |
| `output/result.json` | 结构化结果（机器读） |
| `output/report.md` | 人读报告 |
| `output/history.jsonl` | 每跑一次追加一行（演示"想累计状态"的朴素做法） |

改行为不用改代码，用环境变量即可：

```bash
# Windows PowerShell
$env:TASK_MESSAGE="今晚的日报"; python -m app.main

# Linux / macOS
TASK_MESSAGE="今晚的日报" python -m app.main
```

---

## 3. 推上 GitHub 并手动触发

前 5 步是"让文件到达默认分支"，第 6 步才是"手动跑一次"。

1. **建仓库**：GitHub → New repository → 名称 `cloud-auto-task`。
   - 公开仓库（Public）Actions 免费额度宽松，适合学习；
   - **不要**勾选 "Add a README"，否则本地推送要先 `git pull`。
2. **本地初始化并推送**（本机需先装 Git）：

   ```bash
   cd cloud-auto-task
   git init -b main
   git add .
   git commit -m "feat: 第一个云端定时任务"
   git remote add origin https://github.com/<你的用户名>/cloud-auto-task.git
   git push -u origin main
   ```

   没有 Git 的同学：GitHub 网页 → Add file → Upload files，把整个目录拖进去也可以（`.github/workflows/` 目录要一起上传）。

3. **确认 Workflow 被识别**：仓库顶部 **Actions** 标签 → 左侧出现 **Daily Cloud Task**。
4. **手动触发**：选中它 → 右侧 **Run workflow** → 分支选 `main` → Run。
5. **看运行**：列表出现一条黄色 → 绿色即成功。点进去能看到每个 step 的日志。
6. **下载产物**：运行详情页底部 **Artifacts** → `daily-result-<run_id>` → 解开就是 `result.json` / `report.md`。

### 看不到 Workflow？按这四个原因查

| 现象 | 原因 |
| --- | --- |
| Actions 列表里没有你的 workflow | 文件不在 **默认分支** 上（`master`/`main` 要看仓库设置） |
| 同上 | 路径必须严格是 `.github/workflows/xxx.yml`（少一层目录、拼错 `workflow`） |
| 有名字但没内容 / YAML 报错 | 缩进用了 Tab、`on:` 写成 `on：`（中文冒号）、字段拼错 |
| 只有 schedule 没有 Run workflow 按钮 | 没写 `workflow_dispatch:` |

> YAML 冷知识：`on` 在 YAML 1.1 里会被解析成布尔值 `True`。本地用 PyYAML 检查时会看到 key 是 `True`，这是正常的，GitHub 的解析器按 YAML 1.2 处理，不会出问题。

---

## 4. 定时任务真正生效的 5 个硬条件

### 4.1 Cron 五字段

```
17    9    *    *    *
│     │    │    │    └── 星期（0-7，0 和 7 都是周日）
│     │    │    └─────── 月份（1-12）
│     │    └──────────── 日期（1-31）
│     └───────────────── 小时（0-23）
└─────────────────────── 分钟（0-59）
```

常用写法：

| 表达式 | 含义 |
| --- | --- |
| `0 9 * * *` | 每天 09:00 |
| `30 8 * * 1-5` | 工作日 08:30 |
| `0 */2 * * *` | 每 2 小时 |
| `17 9 * * *` | 每天 09:17（避开整点，见 4.4） |

在线验证工具：[crontab.guru](https://crontab.guru/)。

### 4.2 时区：cron 默认是 UTC

**这是新手翻车第一名。** GitHub 的 `schedule` 历史上只按 **UTC** 解释 cron：写 `0 9 * * *`，北京时间实际是 **17:00**。

- 2026 年 3 月起，GitHub 支持在 cron 旁写 `timezone` 字段（IANA 时区），才能表达"本地时间"：

  ```yaml
  on:
    schedule:
      - cron: "17 9 * * *"
        timezone: "Asia/Shanghai"   # 每天北京时间 09:17
  ```

  来源：[GitHub Changelog：Timezone support for scheduled workflows](https://github.blog/changelog/2026-03-19-github-actions-late-march-2026-updates/) / [workflow syntax 文档](https://docs.github.com/actions/reference/workflows-and-actions/workflow-syntax#onschedule)。

  > 三个细节：① `timezone` 是 `cron` 的**同级**字段，不是写进 cron 字符串；② 一律加引号，避免被 YAML 当成别的类型；③ 对实行夏令时的时区，春季被跳过的小时（如 02:30）会**顺延**到下一个有效时间。
  > 另外，`timezone` 字段在 GitHub.com / GHES 3.22 及以上可用，更旧的 GHES 仍然只认 UTC。

- 如果你的账号/企业**不支持**该字段（旧版 GHES、或字段被忽略），就必须手动换算：
  `北京时间 09:17` → `UTC 01:17` → `cron: "17 1 * * *"`。

本项目**两者都覆盖**：workflow 里写 `timezone`，代码里再用 `zoneinfo` 按 `Asia/Shanghai` 生成带 `+08:00` 的时间戳。这样无论调度按哪个时区解释，报告里的时间永远是清楚的北京时间——**排查时先看时间戳有没有偏移，能立刻区分"调度时区错"和"任务延迟"**。

### 4.3 只认默认分支

调度器只读取**默认分支**上的 workflow 文件。在 `dev` 分支改 cron 不会生效；想让定时任务生效，改动必须先合并到默认分支。

### 4.4 最短 5 分钟 + 高负载延迟

- 最小粒度 5 分钟，`*/1` 不会变成每分钟；
- GitHub 明确说明：高峰期（尤其整点）任务可能排队延迟，可能晚几分钟到几十分钟；
- **负载足够高时，已排队但还没开始的 job 可能被直接丢弃**——所以定时任务不能假设"今天一定会跑一次"，关键业务要有补偿手段（例如手动触发入口、或让下游任务自己判断"今天的数据是否缺失"再补跑）；
- 所以项目用 **09:17** 而不是 09:00——**避开整点拥堵**，是实践中最省心的一个小技巧。

> 判断标准：日志里 `Show trigger context` 的 UTC 时间和任务自己的时间戳差几分钟，是延迟；差整 8 小时，就是时区。

### 4.5 公开仓库 60 天无活动会停用定时任务

公开仓库连续 **60 天没有任何提交/活动**，schedule 触发会被 GitHub 自动停用（docs: [Disabling and enabling a workflow](https://docs.github.com/en/actions/how-tos/manage-workflows-and-runs/disable-and-enable-workflows)）。私有仓库不受此限制。

- 重新启用：Actions → 选中 workflow → 右侧 **Enable workflow**；命令行等价写法 `gh workflow enable daily-task.yml`；
- 另一个坑：**公开仓库被 Fork 后，Fork 出来的那份默认禁用 scheduled workflow**——"Fork 一下就会自动每天跑"是错的，必须在对方仓库里手动启用；
- 规避 60 天停用：定期提交，或保留 `workflow_dispatch` 让仓库保持活跃。

### 4.6 Action 版本会退役（2026 年的现实）

`uses:` 后面的 `@v4`/`@v5` 不是装饰，它决定跑在哪个 Node 运行时上。**Node 20 已于 2026-09-23 从 Actions 移除**，所以 2024–2025 年教程里的 `checkout@v4`、`setup-python@v5`、`upload-artifact@v4` 都属于待升级状态。

| Action | 2026-11 最新大版本 | 注意点 |
| --- | --- | --- |
| `actions/checkout` | **v7** | v7 默认拒绝在 `pull_request_target` / `workflow_run` 场景下 checkout Fork PR 的代码（防投毒） |
| `actions/setup-python` | **v7** | v7 迁移 ESM，输入参数不变；v6 起需要 Node 24 |
| `actions/upload-artifact` | **v7** | v7 新增 `archive: false`（单文件直传）；v4+ 不支持 GHES，GHES 需留在 v3.2.2 |
| `actions/cache` | **v6** | v1/v2 已于 2025-02 停用，继续用会直接失败 |

- 本项目已对齐到上表版本，并加了 `.github/dependabot.yml` 每周自动提 PR 升级；
- 自托管 Runner：用 Node 24 的 Action 要求 runner ≥ **2.327.1**，老版本 runner 必须先升级。

---

## 5. Runner 是一次性的：结果到底存哪？

托管 Runner 的规则：**每个 Job 一台全新的机器，Job 结束机器销毁。** 上一个 Job 写进 `output/` 的文件，下一个 Job 看不到；本地磁盘不是数据库。

| 方案 | 能存多久 | 适合 | 代价 |
| --- | --- | --- | --- |
| **Artifact**（本项目默认） | 默认 90 天；公开仓库上限 90 天，私有/内部仓库上限 400 天 | 报告、截图、日志、测试产物 | 过期即删，不能直接被程序读回 |
| **提交回仓库** | 永久（跟 Git 历史） | 每日报告、数据快照、可视化页面 | 仓库会变大，需要 `contents: write` |
| **外部存储** | 由你决定 | 需要"上次状态"的业务（增量抓取、去重） | 要维护 DB / 对象存储 / 缓存 |

> 补充：2026-10-01 起，workflow run / check / commit status 的保留期也统一按 Actions 保留期设置执行（默认同样是 90 天），以前几百天的历史运行记录会开始过期。

Artifact 采集方式已写在 workflow 里：

```yaml
- name: Upload result
  if: always()                     # 失败也要上传，否则出问题时啥也看不到
  uses: actions/upload-artifact@v4
  with:
    name: daily-result-${{ github.run_id }}   # 带上 run_id，避免多次运行重名覆盖
    path: output/
    retention-days: 7              # 演示用，短一点省空间
```

### 想把结果提交回仓库？附录写法

需要改两处：`permissions` 加 `contents: write`，并在任务后追加一个提交步骤。

```yaml
permissions:
  contents: write

# ... 前面的 step 不变，然后追加：
- name: Commit result
  if: always()
  run: |
    git config user.name  "github-actions[bot]"
    git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
    git add output/
    git diff --cached --quiet || git commit -m "chore: 更新运行结果 $(date -u +%FT%TZ)"
    git push
```

两个要点：

1. `git diff --cached --quiet ||` 保证**没有变化就不提交**，否则每天产生空提交；
2. 用 `GITHUB_TOKEN` 推送产生的 commit **不会再次触发 workflow**（GitHub 的防循环机制），所以定时任务不会自己套娃。但如果你用 Personal Access Token 推，就会触发——这一点后面接"自动部署"时很关键。

---

## 6. Secrets 与通知：密钥永远不进代码

### 6.1 放密钥

仓库 → **Settings → Secrets and variables → Actions → New repository secret**，例如：

- Name: `DINGTALK_WEBHOOK`
- Secret: `https://oapi.dingtalk.com/robot/send?access_token=xxxx`

workflow 里用 `${{ secrets.DINGTALK_WEBHOOK }}` 注入，代码用 `os.environ` 读：

```yaml
- name: Run Python Task
  env:
    TASK_NOTIFY_ENABLED: "true"
    DINGTALK_WEBHOOK: ${{ secrets.DINGTALK_WEBHOOK }}
  run: python -m app.main
```

### 6.2 群机器人注意事项

- 本项目实现的是钉钉/企业微信机器人的**关键词模式**（`{"msgtype":"text","text":{"content":...}}`）；
- 如果机器人开启了"加签"，还需要 `timestamp + HMAC-SHA256(secret)`，在 `app/notifier.py` 里扩展即可；
- **绝对不要** `print(webhook)`、不要把 webhook 写进 `config.json` 再提交——`notifier.py` 里已做 `_mask()` 兜底；
- **Fork 来的 PR 拿不到 Secrets**（GitHub 的安全限制），所以不要指望"别人 fork 你的仓库就能发通知"。

### 6.3 为什么 Secret 打印出来是 `***`

GitHub 会把你配置的 Secret 值在日志里自动打码。但**打码只针对精确匹配**——把 token 拼接、base64 或分段输出，就可能泄露。所以正确做法是从源头就不打印。

---

## 7. 稳定性与安全清单（上线前过一遍）

| 项目 | 本项目做法 | 为什么 |
| --- | --- | --- |
| 最小权限 | `permissions: contents: read` | 默认 token 权限过大，被劫持时损失放大 |
| 并发控制 | `concurrency.group` + `cancel-in-progress: false` | 上一次没跑完不叠加，避免重复执行 |
| 超时 | `timeout-minutes: 5` | 卡死时不让它烧满 6 小时默认上限 |
| 失败留证据 | `Upload result` 用 `if: always()` | 排障靠产物，不靠猜 |
| 先测试后执行 | `Run tests` 在 `Run Python Task` 之前 | 坏代码快速失败，省额度 |
| 退出码语义 | 成功 0 / 失败 1 | Actions 的绿红完全由退出码决定 |
| 依赖锁定 | `requirements.txt` 写死版本 | 避免上游更新让今天能跑的明天挂掉 |
| 幂等 | 每次覆盖写 `result.json` | 重跑不会产生重复数据 |

---

## 8. 常见故障对照表

| 现象 | 最可能原因 | 处理 |
| --- | --- | --- |
| Actions 里找不到 workflow | 不在默认分支 / 路径错 / YAML 语法错 | 见第 3 节排查表；用 `python -c "import yaml;yaml.safe_load(open(...))"` 先验证 |
| 定时到了没跑 | 时区算错（UTC）、非默认分支、60 天停用、仓库 Actions 被禁用 | 先看 `Show trigger context`，再手动 Run 一次区分"程序问题"和"调度问题" |
| 任务成功但没 Artifact | `path` 写错 / 程序没写文件 / `if-no-files-found` 设成了 ignore | 看 step 日志里的 warning，确认 `output/` 真存在 |
| 通知没发出去 | Secret 没配 / `TASK_NOTIFY_ENABLED` 还是 false / 机器人关键词不匹配 | 日志里 `通知结果` 会写明 skipped 原因 |
| 本地能跑云端挂 | 少提交文件（`.gitignore` 误伤）、路径用反斜杠、编码不是 UTF-8 | 云端路径一律 `/`；Python 打开文件显式 `encoding="utf-8"` |
| Windows 本地报找不到时区 | 缺 tzdata | `pip install tzdata` |

---

## 9. 下一步可以怎么扩展

1. **多 Job 并行**：一个 workflow 里拆 `test` / `collect` / `report` 三个 job，用 `needs:` 串依赖；
2. **矩阵构建**：`strategy.matrix` 一次跑 Python 3.11 / 3.12 / 3.13；
3. **缓存**：`actions/cache` 缓存 pip 依赖，缩短启动时间；
4. **真实数据**：定时抓 API → 生成 Markdown 报告 → 提交回仓库变成静态网页；
5. **自托管 Runner**：需要访问局域网设备（PLC、工业相机、本地 NAS）时，用自己的 Ubuntu 机器注册为 Self-hosted Runner，托管 Runner 换成 `runs-on: [self-hosted, linux]`；
6. **环境隔离**：`environment:` + 审批人，让"生产任务"需要人工放行。

---

## 10. 参考资料

- [GitHub Actions 官方文档](https://docs.github.com/en/actions)
- [Workflow 语法（on.schedule / timeout-minutes / concurrency / permissions）](https://docs.github.com/actions/reference/workflows-and-actions/workflow-syntax)
- [触发事件说明（schedule 的 5 分钟 / 默认分支 / 60 天 / 高负载）](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
- [2026-03 时区支持公告](https://github.blog/changelog/2026-03-19-github-actions-late-march-2026-updates/)
- [2026-09 Node 20 移除公告](https://github.blog/changelog/2026-09-24-node-20-is-no-longer-available-in-github-actions/)
- [Quickstart](https://docs.github.com/en/actions/quickstart)
- [Crontab Guru（cron 在线验证）](https://crontab.guru/)
- [GitHub Marketplace（找现成 Action）](https://github.com/marketplace?type=actions)

---

## 附录：本仓库的事实核查记录

[`../research/actions-facts.md`](../research/actions-facts.md) 记录了本文所有"版本 / 配额 / 限制"类结论的官方来源与核查日期（2026-11-11），可以当作写教程前的底稿。GitHub 的产品节奏很快，**任何写死的版本号都建议标上核查日期**。
