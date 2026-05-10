# PRD：AI SQL Safety Net

**产品代号**：SafeQuery
**版本**：v1.0
**作者**：Ricky
**最后更新**：2026-05

---

## 1. 一句话定位

> **A safety layer between your AI agent and your database. Stop catastrophic SQL before it executes.**

为接入数据库的 AI agent / text-to-SQL 系统提供执行前安全检查——拦截 catastrophic 操作，让 agent 安全地碰生产数据。

---

## 2. 问题陈述

### 2.1 用户痛点

AI agent 误删 / 误改生产数据已经是真实事故：
- Replit Agent 公开删除生产数据库事件（2025）
- 多个开源 agent 项目因为 unbounded `DELETE` / `UPDATE` 导致数据丢失
- text-to-SQL 系统生成的查询性能爆炸，把数据库拖垮
- AI 写的 migration script 漏掉 transaction，半执行半失败

**根本原因**：
- LLM 不理解"这是生产环境"
- LLM 不知道哪些表是关键表
- LLM 经常生成"语法对、语义错"的 SQL
- 没有 deterministic 的最后一道防线

### 2.2 当前缓解方案的不足

- **人工 review**：agent 自动执行场景下不可能
- **数据库账号权限隔离**：粒度太粗，要么不能写，要么能删全表
- **传统 DB firewall（Imperva 等）**：为防 SQL injection 设计的，不为防"AI 写错 SQL"设计
- **LangChain 的 `SQLDatabaseChain` warning**：只是字符串匹配，可绕过
- **自己写 SQL parser**：每个团队重新发明轮子

### 2.3 LLM 时代为什么紧迫

text-to-SQL 是 agent 最常见的能力之一（每个 RAG 系统、analytics agent、客服 agent 都有）。每个接入数据库的 LLM 应用都在裸奔——一次事故就是公司新闻头条。**这不是 if，是 when**。

### 2.4 用户画像

**核心用户**：构建 AI agent / text-to-SQL 应用的工程团队
**典型场景**：
- 用 LangChain / LlamaIndex / 自研框架
- agent 已经能跑通基础流程，开始担心生产部署
- 老板问"要是 AI 删了生产数据怎么办"
- 团队规模 5-50 工程师，AI 应用是核心产品或核心产品的一部分

**反向画像**：
- 只用 LLM 做内容生成、不碰数据库的
- 数据库只读、永远不写的（用 read-only 账号就行）
- 已有完善 DBA + change management 流程的传统企业

---

## 3. 解决方案

### 3.1 核心机制

**SafeQuery 是一层 SDK / library**，agent 在执行 SQL 前先调用 SafeQuery 检查：

```python
from safequery import SafeQuery

sq = SafeQuery(
    profile="production",
    dialect="postgresql"
)

result = sq.check(sql_query)

if result.action == "BLOCK":
    raise UnsafeQueryError(result.reason)
elif result.action == "WARN":
    log_warning(result.reason)
    # 继续执行
elif result.action == "ALLOW":
    db.execute(sql_query)
```

返回结果包含：
- `action`：ALLOW / WARN / BLOCK
- `risk_score`：0-100
- `violations`：触发的具体规则
- `reason`：人类可读解释
- `suggested_fix`：修复建议（v1.5）

### 3.2 检测维度

#### Catastrophic（默认 BLOCK）
- `DELETE` / `UPDATE` 缺少 `WHERE`
- `DROP TABLE` / `DROP DATABASE` / `TRUNCATE`
- 不带 `WHERE` 或带 `WHERE 1=1` 的 `UPDATE`
- 影响超过 N 行的 DML（基于 EXPLAIN 估算，v1.5）
- DDL 操作（除非显式启用）

#### Dangerous（默认 WARN）
- `DELETE` / `UPDATE` 缺 `LIMIT`（即使有 `WHERE`）
- 跨表 `DELETE`
- 全表 scan 的 `SELECT`（高资源消耗）
- 修改高敏感表（用户列表中标记的，如 `users`, `payments`）
- DDL with `CASCADE`

#### Suspicious（默认 LOG）
- 嵌套深度过深的子查询
- `SELECT *` from 大表
- 缺少 index 的 query（基于 EXPLAIN）
- 长执行时间预估

### 3.3 配置模型

```yaml
# safequery.yaml
profile: production

dialect: postgresql

policy:
  catastrophic:
    delete_without_where: BLOCK
    update_without_where: BLOCK
    drop_table: BLOCK
    truncate: BLOCK

  dangerous:
    delete_without_limit: WARN
    update_without_limit: WARN
    full_table_scan: WARN

protected_tables:
  - users
  - payments
  - audit_log

allowed_ddl: false  # default

max_affected_rows_warn: 1000
max_affected_rows_block: 100000

dry_run_mode: false  # 测试时设为 true，所有 BLOCK 变 WARN

audit_log:
  enabled: true
  destination: stdout  # 或 file/kafka/cloudwatch
```

### 3.4 关键设计决策

**为什么 SDK 而不是 proxy**：
- 部署 friction 极小（pip install）
- 不引入网络层延迟
- 不需要数据库账号迁移
- 让 agent 框架直接 import，自然集成

**为什么不做 LLM-based 检查**：
- LLM 检查 LLM 输出的 SQL 是回归无解
- AST + 规则集是 deterministic verifier，这是产品的核心价值
- LLM 只在"解释 violation"和"建议修复"作为辅助使用

**为什么先做 PostgreSQL**：
- AI / agent 生态最常用
- AST 解析库成熟（pg_query）
- 用户群最技术、最早 adoption
- v1.5 加 MySQL，v2 加 Snowflake / BigQuery

**为什么不做 SQL injection 防护**：
- 那是另一个问题（防恶意输入），传统 ORM 已解决
- SafeQuery 的目标是防"AI 自己写错"，不是"防被注入"
- 不混淆 positioning

---

## 4. v1.0 Scope

### 4.1 In Scope

- **Python SDK**：`pip install safequery`
- **PostgreSQL 完整支持**
- **CLI 工具**：`safequery check "DELETE FROM users"` 用于调试
- **30 条预定义规则**（覆盖上述 Catastrophic/Dangerous）
- **YAML 配置**
- **Audit log**：所有 check 写日志（stdout/file）
- **LangChain 集成**：开箱即用的 `SafeQueryTool` wrapper
- **dry-run 模式**：测试时不真正 BLOCK

### 4.2 Out of Scope（v1 明确不做）

- ❌ Node.js / Go / Java SDK（v1.5）
- ❌ MySQL / Snowflake / BigQuery（v1.5+）
- ❌ Web dashboard（v2）
- ❌ EXPLAIN-based 行数预估（v1.5）
- ❌ Auto-fix（v2，太容易出错）
- ❌ SaaS / hosted version（v2）
- ❌ 实时数据库 proxy（永远不做，positioning 就是 SDK）
- ❌ SQL injection 防护（不是产品定位）

---

## 5. 技术架构

### 5.1 技术栈

- **语言**：Python（核心 SDK，AI 生态主流语言）
- **核心依赖**：
  - `pglast`：PostgreSQL AST parser（基于 libpg_query）
  - `pydantic`：配置验证
  - `structlog`：审计日志
- **测试**：5000+ 真实 SQL 测试集（开源 + 我们自建）

### 5.2 核心模块

```
safequery/
├── safequery/
│   ├── __init__.py
│   ├── parser/         # SQL → AST
│   ├── rules/          # 规则定义
│   ├── policy/         # YAML 配置加载
│   ├── checker/        # 核心检查逻辑
│   ├── reporter/       # 结果格式化
│   ├── integrations/
│   │   ├── langchain.py
│   │   └── llamaindex.py
│   └── cli.py
├── tests/
│   └── corpus/         # 真实 SQL 测试样本
└── examples/
```

### 5.3 检测流程

```
SQL Query
    │
    ▼
[Parse to AST]  ← pglast
    │
    ▼
[Apply Rules]   ← 30 条规则并行检查
    │
    ▼
[Aggregate Score]
    │
    ▼
[Match Policy]  ← 用户配置决定 ALLOW/WARN/BLOCK
    │
    ▼
[Audit Log]
    │
    ▼
Result
```

### 5.4 性能要求

- 检查延迟 P99 < 5ms（SDK 形态，不能拖慢 agent）
- 内存占用 < 50MB
- AST cache：相同 SQL 不重复 parse

---

## 6. 用户旅程

### 6.1 首次集成（5 分钟）

```bash
pip install safequery
```

```python
from safequery import SafeQuery

sq = SafeQuery.from_file("safequery.yaml")

# 包装现有 db.execute
def safe_execute(sql):
    result = sq.check(sql)
    if result.action == "BLOCK":
        raise UnsafeQueryError(result.reason)
    return db.execute(sql)
```

### 6.2 LangChain 集成

```python
from langchain.agents import create_sql_agent
from safequery.integrations.langchain import SafeQueryCallback

agent = create_sql_agent(
    llm=llm,
    db=db,
    callbacks=[SafeQueryCallback(profile="production")]
)

# Agent 自动受 SafeQuery 保护
```

### 6.3 dry-run 验证

```yaml
# 第一周：dry_run_mode: true
# 观察哪些 query 会被 block，调整规则
# 第二周：关闭 dry_run，正式启用
```

---

## 7. 商业模式

### 7.1 开源 + 商业

**SafeQuery 核心永远开源（Apache 2.0）**——这是建立信任的关键，企业不会接受关键路径上的闭源黑盒。

商业化路径：

| Tier | 价格 | 功能 |
|------|------|------|
| **OSS** | $0 | 完整 SDK、30 条规则、PostgreSQL、社区支持 |
| **Pro** | $299/month | 高级规则集、所有数据库 dialect、邮件支持、SLA |
| **Team** | $999/month | 集中 audit dashboard、Slack 告警、自定义规则 marketplace、approval workflow |
| **Enterprise** | Custom | 私有部署、专属规则开发、合规报告、专属支持 |

**关键判断**：核心 SDK 不锁，赚的是 dashboard / collaboration / advanced rules / support 的钱。这是 GitLab / Sentry / PostHog 模式。

### 7.2 GTM 策略

**Phase 1（0-3 个月）：开源传播**
- 发 PyPI、GitHub
- LangChain / LlamaIndex 文档贡献集成 example
- 在 r/LocalLLaMA、HN、Twitter AI 圈发布
- "Replit 删库"事件类内容做 SEO
- 找 5 个 design partner（典型：YC AI 公司、agent 创业公司）

**Phase 2（3-9 个月）：建立 category**
- 写 thought leadership 内容："The AI Database Safety Stack"
- 在 AI Engineer Summit、PyCon 演讲
- 加 MySQL、Snowflake 支持，扩用户基础
- Pro tier 上线，目标 100 paid users

**Phase 3（9-18 个月）：企业销售**
- Team / Enterprise tier
- 接触受监管行业 AI 团队（fintech、healthtech）
- 目标 ARR $500k

---

## 8. 成功指标

### 8.1 v1 发布指标（前 90 天）

| 指标 | 目标 |
|------|------|
| PyPI 月下载量 | 5000+ |
| GitHub stars | 2000+ |
| 接入的 production agent 数 | 50+ |
| 公开 case study | 3+ |
| 付费用户 | 5+ |

### 8.2 北极星指标

**"Catastrophic queries blocked per week"**
聚合所有用户被 BLOCK 的 catastrophic 数。这个数字代表产品创造的"避免事故"价值。目标：v1.0 后 6 个月内累计阻止 1000+ catastrophic queries。

### 8.3 反向指标

- False positive rate < 5%（用户配置 override 的比例）
- Latency P99 < 5ms（不能影响 agent 性能）

---

## 9. 风险与对策

| 风险 | 概率 | 影响 | 对策 |
|------|------|------|------|
| LangChain / LlamaIndex 内置类似功能 | 高 | 中 | 抢先成为他们官方推荐集成。我们做深度，他们做兼容 |
| 数据库厂商（Snowflake、Supabase）内置 | 中 | 中 | 跨数据库的统一接口是优势。每个厂商都做意味着用户要学 N 套配置 |
| 大厂安全产品扩展（Cloudflare、Datadog） | 中 | 中 | 走开源路线建立社区粘性 |
| 用户嫌 5ms 延迟太多 | 低 | 高 | AST cache + 异步审计日志，把同步路径做到 < 1ms |
| AI 模型本身解决幻觉，需求消失 | 低 | 极高 | 即使 GPT-6 不再写错 SQL，"deterministic 最后一道防线"在金融、医疗等场景仍是合规需求 |
| SQL 方言地狱拖慢扩展 | 中 | 中 | 优先级：PostgreSQL → MySQL → Snowflake → BigQuery。每个独立做透 |

---

## 10. 时间线

| 阶段 | 时间 | 里程碑 |
|------|------|--------|
| **v0.1** | 第 1-2 月 | Python SDK、PostgreSQL、20 条核心规则、5 个 alpha 用户 |
| **v0.5** | 第 3 月 | 30 条规则、LangChain 集成、PyPI 发布、HN 发布 |
| **v1.0** | 第 4-6 月 | LlamaIndex 集成、CLI、文档完善、Pro tier 上线 |
| **v1.5** | 第 7-9 月 | MySQL 支持、EXPLAIN-based 行数估算、Slack 集成 |
| **v2.0** | 第 10-12 月 | Snowflake、BigQuery、Web dashboard、Team tier |

---

## 11. Open Questions

1. 是否在 v1 提供 hosted SaaS 模式（API endpoint），方便非 Python 用户？还是坚持 SDK-only？
2. 是否要支持 ORM-generated query（SQLAlchemy、Django ORM）？还是只看最终 SQL string？
3. Pro tier 的"高级规则集"具体应该是什么？（行业特定规则？合规规则？性能规则？）
4. 是否要做 "preview mode"——用户上传 schema，我们 simulate query 返回会影响多少行？
5. 何时引入 "ML-based anomaly detection"（这个 query 和你历史 query 模式不一致）？
