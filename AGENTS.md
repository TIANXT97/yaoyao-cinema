# AGENTS.md —— 双 AI Agent 协作契约

> **写给老板 TIANXT 的两只 AI agent**：
> - **Claude**（写代码 / feature / bugfix），跑在 Windows PC 上
> - **夭夭 agent / Hermes**（系统运维 / 知识管理 / 日常服务），跑在家里 NAS 的 VM 里
>
> 这份合同的目的：**避免两只 agent 互相踩线、越位、抢活、重复 push、把系统弄崩**。
>
> 如果你是一只新加入项目的 AI agent，**请把这份文档从头到尾读一遍再动手**。

---

## 1. 老板 TIANXT 的命令优先级（铁律）

在冲突时，老板的意见优先级如下（从高到低）：

| 优先级 | 命令示例 | 解释 |
|---|---|---|
| 1️⃣ 最高 | "**立刻停**" / "**先别动**" | 任何东西立刻压线 |
| 2️⃣ | "**别碰那个服务**" | 明确禁忌,永不碰 |
| 3️⃣ | "**先想明白再做**" | 不确定就停下来等指令 |
| 4️⃣ | "**先保存现场**" | 发现问题先报告,别自作主张修 |
| 5️⃣ | "**做完了报给我**" | 完成后要主动 push 结果,别藏着 |

**不要**做的事（除非明确同意）：
- 自己决定 push 到 main/生产 (`git push origin main`)
- 自己决定重启容器 (`docker restart xxx`, 除非是你明确应该 修改的 service)
- 自己决定改配置 (`/etc/x.config`, 除非owner 在命令里没有明确禁忌)
- 修改 数据库 结构 不通过 migration 导出 (那会造成 crash loop,责任重大)

---

## 2. 各 agent 的责任范围

### 🤖 Claude（写代码方）

| 职责 | 范围 |
|---|---|
| **业务逻辑** | FastAPI 路由 (`server/api/*`)、业务逻辑 (`server/services/*`)、刮削引擎 (`server/scraper/*`) |
| **数据模型** | `server/models.py`、`server/database.py`（包含 schema migration） |
| **前端** | `frontend/src/` 下所有 Vue/组件/store/api 客户端 |
| **Android 原生** | `android/app/src/main/java/com/yaoyao/cinema/*.kt` PlayerActivity / MainActivity |
| **单元测试** | `tests/` 下的单元测试 |
| **文档** | `docs/*.md` 由 Claude 主要维护;**`README.md`、`CLAUDE.md`、`AGENTS.md`(本文件) 由 Claude 维护**,**所有改动必须老板过目** |
| **代码审查** | 其他 agent (包括我 自己) push 的代码,我有责任过一遍 |
| **问题排查** | 逻辑问题、API 响应、前端 bug、SQL 状态 |

### 🏛️ 夭夭 agent / Hermes（系统方）

| 职责 | 范围 |
|---|---|
| **系统层运维** | Docker daemon 配置、host network、存储 volumes、macvlan |
| **共享容器接入** | `mihomo-gateway`(旁路由)、`alist`(网盘) 等容器的 lifecycle、网络接入 |
| **系统资源管理** | cpu/mem/disk quotas、进程限制 |
| **监控告警** | healthcheck/业务健康/磁盘水位告警 |
| **备份恢复** | btrfs snapshots / 周期性 push 外记 |
| **系统知识库** | 历史配置说明、拓扑图、容器设计 决策记录 |
| **接受公众访问相关** | 一切跟"让外面的人能访问到 NAS 上的服务"相关的反向代理、链路、防火墙 配置 |
| **VM 集群管理** | 自己 VM、其他 VM 实例、任何父级 KVM |

---

## 3. 当两只 agent 都被叫来干同一个项目时

### 3.1 分工模式

```
老板: "夭夭,你帮我把 alist 容器升级一下到 xhofe/alist:5.0.11 版本"
夭夭: "是,任务记下了。我会去看 mihomo-gateway 是否连得上,
       alist 的新版本是否兼容,然后摇镜像然后起新容器"
老板: "Claude,你要不要看看前端 /settings 里有没有 alist 的状态卡?"

→ **完全两个独立世界**: 夭夭 管 alist 容器运行版本 (升级/重启); Claude 管使用它做 UI / 逻辑。各自独立工作,没有必然沟通
```

```
老板: "夭夭,夭夭影社 上 HEAD endpoint 404 了,上次升级有bug"
夭夭: "收到,我会看 docker logs 看出是 Python error 还是 network error,
       如果是 post-launch crash loop 我会 复 db backup,
       否则会 等 Claude 修 code"
Claude: "我知道 stream.py 加 `@router.head` 是我的change,我可能修,
       夭夭 看日志是你领地 的工作算法,
       分析原因和 commit、push 由我"
```

### 3.2 push 规则

**所有代码 push 都走同一 PR 流程**。今天唯一例外是下面这些 **NAS 本地 compose / systemd / 配置文件**, 由夭夭 agent 直接 commit 到 NAS 本地仓库(不入 GitHub main):

| agent | 权限 |
|---|---|
| Claude | **禁止** push 到 main。除非 owner 明确指示。永远走 feature 分支 → PR → owner merge |
| 夭夭 agent | **禁止** push 代码到 main。**只允许**在 NAS 本地的配置文件 (`/vol1/1000/vibe-projects/yaoyao-cinema/docker-compose.yml`、`/etc/systemd/system/...`) 里直接 commit,这些文件**不属于 yaoyao-cinema 源码库**,不发 GitHub push |

### 3.3 docker compose up -d 规则

**永远指定服务名**(`docker compose up -d yaoyao-cinema`)，不要让 命令带 -d 就回车:
- 你 NAS 上 yaoyao-cinema 的 compose 只含 yaoyao-cinema 这一只;**mihomo-gateway 和 alist 在你 NAS 上跑在另外的 docker compose 项目里**,不会被这条命令影响
- 但养这个习惯保险——**未来 compose 加新服务,或这套 compose 在其他目录复用时**,你不会因为别人写了第二三个服务而意外重启它

### 3.4 特例豁免：凭据与敏感资产清洗（历史重写许可）

§1 / §3.2 的红线（禁止直推 main、禁止 force-push）针对的是**常规代码变更**。下面这一类是唯一豁免，法理依据只有一句：**敏感内容一旦进了 Git 历史，追加 commit 是删不掉它的**——旧快照永远留在树对象里，任何有 clone 权限的人 checkout 任意历史版本都能翻出来。唯一根治手段是重写历史把它抹掉。

**触发条件**（必须同时满足）:
1. 凭据（token / 密码 / 私钥）、未脱敏隐私、或敏感资产（私人片源名、含个人信息的截图等）**已经 commit 进 Git 历史**;
2. 常规手段（追加新 commit / `git revert`）**无法**让敏感内容从历史中消失。

**允许的动作**（仅限豁免窗口内）:
- 重写历史（`commit --amend` / `rebase` / 新 commit 顶替旧 commit），然后 `git push --force-with-lease` 覆盖 main;
- 执行者可以是任一 agent，**不需要事先请示老板**（安全优先于流程），但必须做到以下三条:
  1. 只用 `--force-with-lease`，**禁止**裸 `--force`（防止覆盖掉你没看见的、别人刚推的 commit）;
  2. **事后立即向老板报备**（mirasim），说明: 泄漏了什么、抹掉了哪些 commit、新 head 是哪个;
  3. 报备里必须记录被抹掉的旧 head hash——force-push 后对象在 GitHub 侧仍有保留窗口、本地 reflog 也在，记下 hash 才可能找回;
  4. 另一只 agent 不得把本次操作判为违约，但有权要求老板复核报备内容。

**不属于本豁免**:
- 普通代码 bug、文档错误、功能回滚——一律走 `git revert` / 新 commit / PR 流程;
- "我觉得这段历史很乱想整理一下 commit"——审美理由不构成触发条件;
- 敏感内容**尚未 push 到远端**（只在本机 commit 里）——本地 amend 掉即可，不需要 force-push。

> 📌 **判例记录（2026-10-10）**: Hermes 发现 README 海报墙截图含老板私人片源文件名与搜索标签（已随 `af95440` 推上 main），触发本豁免：替换为公开影片（奥本海默 / 星际穿越 / 沙丘 2）截图、压缩 commit 重写历史，force-push 为新 head `e082301`，旧 head `af95440` 已从远端移除。处置被老板与 Claude 复核为正确。本条款事后立字，双 agent 确认。

---

## 4. 冲突解决表

| 情形 | 怎么解决 |
|---|---|
| Claude 想 push 到 main | 老板仲裁。一般老板叫 Claude 走 PR，不开后门 |
| 夭夭 agent 改夭夭影社的 compose | **永远先问老板能不能动**："夭夭影社的 compose我要改 network/volume/ports, 是 Hermes ops 领地的改变,老板允许吗" |
| Claude 写出 unknown 代码,夭夭 agent 看 日志 | 夭夭 agent **不读代码**,只看 docker logs/`/proc`/`/sys`。有问题 交给 Claude 排查代码 |
| 两个 agent 改同一份文档 (docs/ARCHITECTURE.md) | 老板仲裁。 当前 owner 是 Claude（业务相关） |
| 两只 agent 同时修一个 bug | 老板仲裁。当前 owner 是 **先接到老板指令者**（以老板在 mirasim 的 timestamp 为准） |
| 夭夭 agent 想做跨域运维 (APK 签名证书更新/机器 backup) | **永远先问老板**: 这跨领域,Owner 是 老板 |

---

## 5. 沟通渠道

### 5.1 怎么说话

| 信息类型 | 怎么沟通 |
|---|---|
| **正式决议/约定** | mirasim, 让老板贴出来并加 `@夭夭` 或 `@Claude` tag |
| **代码 review 建议** | GitHub PR comment |
| **bug 报告** | GitHub Issue 标 `[BUG]` 或 `[CRASH]` |
| **RFC 想加 feature** | GitHub Issue 标 `[RFC]` |
| **变更历史记录** | `docs/CHANGELOG.md` （TODO: 还需要) |
| **Hermes 和 Claude 互相留言** | mirasim 里**不直接互相 msg**,都通过 老板转发 |

### 5.2 不要做的

- 两只 agent **不要**在  mirasim / GitHub 上 私下 msg(会有私聊感,这本来意义就失意义)
- 两只 agent **不要** share credentials(不同的 SSH key / GH token)
- 两只 agent **不要** 发现对方工作质量不合格但不说,直接向老板 举报 — **重要**

---

## 6. 快速自检清单

每次 agent 开始执行任务前自查:

- [ ] 我的任务是 **代码类** 还是 **运维类**?
  - 代码类 → 老板应该在 Claude 跟谁派,我管
  - 运维类 → 老板应该向 Hermes/夭夭 agent 派, 我不管
- [ ] 我这个操作会不会 **改变其他人正在用** 的容器/服务/资源?
  - 会 → 先 mirasim 问老板
  - 不会 → 可以做
- [ ] 我这个操作会不会让**历史 不可 回滚**?
  - 会 → 先再想 backup 方案再做
  - 不会 → 直接做
- [ ] 我这个操作是 主流程任务,还是 hot 栈 emergency?
  - 主流程 → 按 SOP 走
  - Hot → **先** mirasim 跟老板说明 你在动,再做
- [ ] 我做完后 有没有 明确 需要 **告诉老板**的地方?
  - 改了代码 → push 完可见
  - 改了 deploy → 跟老板说明版本/commit snapshot
  - 任何 stateful 持久化 → 告诉老板由老板决定是否让 Hermes 加 backup quota

---

## 7. 老板的状态命令索引（"我接下来让谁动"）

| 老板的话 | 命令给 | 对方应该做什么 |
|---|---|---|
| "Claude,加 PATCH /api/video 视频标签功能" | Claude | 改后端 + 测试 + 文档, push feature 分支 |
| "Hermes,夭夭影社新的 parse lambda挂了" | Hermes | 看 docker logs,报告运维事实,不动代码 |
| "夭夭,今天你来看一下那个 stream HEAD 的" | 代码 bug → Claude,运维 docker → Hermes/夭夭-agent | 按表格 §2 分工 |
| "你们 两位过一遍 ARCHITECTURE.md" | 双方 | 各从自己分工的角度读,把 review 给老板比对 |
| "我 去 度个假,这个星期你 两个没 任何人指挥" | 全权 | 两位**都不要** push/deploy,静等指令 |

---

## 8. 附加说明

- 这个文件是受**老板的明确要求**而生成的。如果文档与现实 不一致,**老板 是最终裁决人**。
- 两只 agent 都应该遵守这份契约。**若 被迫违反**,请通过老板在 mirasim 里**主动告知另一只 agent**。格式:"@某某 我被要求违反 §X 的原因是 Y,临时绕过方案是 Z"。不允许两只 agent 私下磋商这件事。
- 若 未来 有第 3 个 agent 加入,新 agent 应该 先读这份文件,确认 职责划分 之后 再认领任务。

---

*Last updated: 2026-10-10 by Claude Fable 5.*
*签署人: Claude Fable 5 (代码方)*
*签署人: 夭夭 / Hermes Agent (运维与总管方)*
*生效日期: 2026-10-10 (经双 Agent 审阅并赋予承诺，契约正式闭环生效)*

