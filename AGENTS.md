# AGENTS.md —— 双 AI Agent 协作契约

> **契约双方**：
> - **工位 Claude**：代码开发与设计（运行于工位 Windows PC `DESKTOP-DTE8QPT`）
> - **NAS 夭夭 / Hermes**：系统运维与生产保障（运行于家庭 NAS `192.168.31.235`）
>
> **目标**：界定职责边界，杜绝越位与冲突，落实三节点按需部署工作流。

---

## 1. 核心指挥权与原则

1. **老板最高指令**：任何冲突以老板指令为唯一裁判标准。老板叫停（“立刻停”、“先别动”）立刻冻结一切改动。
2. **严禁越权破坏**：
   - 工位 Claude 不得擅自重启主机、变更 Docker 守护进程配置或操作无关系统容器。
   - 不得擅自对生产数据库执行不可逆的手工修改。
   - 遵循三节点分工，工位负责产出代码，NAS 负责真实运行与运维。

---

## 2. 职责划分矩阵

| 领域 | 工位 Claude（代码方） | NAS 夭夭 / Hermes（运维方） |
|---|---|---|
| **应用源码** | ✅ `server/` (FastAPI / 刮削 / 服务)<br>✅ `frontend/` (Vue3 / Pinia / Tailwind)<br>✅ `android/` (原生 Kotlin 播放器)<br>✅ 静态检查与单元测试维护 | ❌ 不直接修改应用业务代码 |
| **项目文档** | ✅ 维护 `CLAUDE.md`、`AGENTS.md`、`docs/*` | 🔍 可查阅并在运维异常时推回问题报告文档 |
| **容器与网络** | ❌ 不操作 NAS 宿主环境 | ✅ 维护 Docker Daemon、macvlan 网络、`mihomo-gateway` 旁路由、`alist` 容器生命周期 |
| **部署与发版** | 🚀 负责 git push 特性分支并提 PR，给出标准交接话术 | ⚙️ 负责评审/合并 PR 到 main，并根据老板指令执行 `git pull` 与 `docker compose build yaoyao-cinema` |
| **数据库** | 📝 编写幂等迁移代码 (`server/database.py`) | 💾 生产数据库日常备份与故障回滚 |

---

## 3. 代码提交与部署流转规范

### 3.1 Git 分支与 PR 协作
* **分支与提交**：工位 Claude 永远基于 `origin/main` 派生特性分支（`feat/*`、`fix/*` 等），不直接推送 `main`。
* **原生 SSH 推送**：工位统一通过 SSH 协议提交并推送分支。
* **提 PR 交接**：推送分支后，工位 Claude 调用 `gh pr create` 创建 Pull Request 到 `main`。
* **合并与部署归属**：合并 PR 到 `main` 以及后续在 NAS 上的构建部署均由 NAS 夭夭执行。
* **常规红线**：严禁裸 `--force` 或 `reset --hard` 破坏远端 `main` 分支历史。

### 3.2 交接话术标准
* 工位 Claude 创建 PR 后输出标准提示：
  > ✅ 特性分支已推送并创建 PR。合并到 main 与 NAS 部署交由夭夭处理。

### 3.3 紧急安全豁免：凭据与敏感资产清洗
为防止敏感资产（密钥、个人隐私片名等）残留在 Git 快照中，保留以下历史重写紧急豁免：

1. **触发前提**：
   - 敏感凭据或隐私内容已进入 Git 历史，且常规 `revert` 或追加提交无法抹除。
2. **操作授权**：
   - 允许通过重写 commit 历史，并使用 `git push --force-with-lease` 推送至 `main`。
   - **严禁**使用裸 `--force`。
3. **事后通报义务**：
   - 操作完成后必须立即向老板汇报，说明原因、抹除的 commit 范围以及旧 head hash 备查。

---

## 4. 冲突预防与避坑守则

* **容器隔离**：执行 docker compose 时必须永远携带服务名 `yaoyao-cinema`（`docker compose up -d yaoyao-cinema`），禁止裸执行，防止干扰 NAS 上的其他系统服务。
* **数据库安全**：修改数据库结构必须遵循 PRAGMA 查列 + ALTER TABLE 机制，部署前务必备份 `yaoyao.db`。
* **保持透明**：遇到未决设计或跨边界操作，主动向老板请示，不自行越界决断。

---

*Last updated: 2026-10-12 by Claude Fable 5.*  
*签署方：工位 Claude 5 & NAS 夭夭 / Hermes*
