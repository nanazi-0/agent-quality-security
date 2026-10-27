# Agent Quality & Security（智能体产品质量与安全验收体系）

这是一个可执行、低成本、厂商中立的发布验收闭环。它统一验证传统软件质量、智能体/RAG行为、AI安全、应用安全、性能、可访问性、业务最终结果和可观测性，并将证据、失败回流、发布决策和审计记录放入同一控制面。

## 当前强制门禁

`quality-gates.toml` 中所有检查均为 `required=true`：

| 维度 | 真实执行器 | 证据 |
|---|---|---|
| 单元与框架测试 | Python unittest | 独立日志 |
| 智能体业务结果 | qualityctl案例运行器 | `reports/demo/case-results.json` |
| 追踪标准 | OpenTelemetry OTLP + OpenInference属性 | `reports/telemetry/results.json` |
| 智能体/RAG评测平台 | Phoenix自托管 | `reports/phoenix/results.json` |
| AI安全 | Promptfoo官方隔离容器 | `reports/promptfoo/results.json` |
| Web/UI与可访问性 | Playwright + axe-core | `reports/playwright/results.json` |
| 性能 | k6官方容器 | `reports/k6/summary.json` |
| 源码安全 | Semgrep官方容器 | `reports/semgrep/results.json` |
| 依赖、密钥与配置 | Trivy官方容器 | `reports/trivy/results.json` |
| Web动态安全 | OWASP ZAP官方容器 | `reports/zap/results.json` |

任何必需工具缺失、命令失败或证据文件缺失都会使发布门禁失败。

## 安装与运行

要求：Python 3.11+、Node.js 24+、Docker Desktop。

```powershell
cd D:\Portfolio\agent-quality-security
.\scripts\setup.ps1
.\scripts\closed-loop.ps1
```

Python包只安装在项目 `.venv`；Node包只安装在项目 `node_modules`；Promptfoo、k6、Semgrep、Trivy、ZAP和Phoenix使用隔离容器。Phoenix默认地址为 `http://127.0.0.1:6006`。

`closed-loop.ps1` 会启动Phoenix、执行全部强制门禁、记录SQLite账本、生成证据哈希、给出自动放行资格并校验审计链。

## 已实现的闭环

- 版本化黄金案例、风险等级和确定性断言；
- 智能体响应、工具名称、工具参数、RAG依据和成本/时延入口；
- 从权威业务接口验证最终状态，文本回答不能替代业务真值；
- 提示注入、越权、泄露、危险动作和无副作用拒绝测试；
- 重复操作幂等性、API、UI、可访问性和性能阈值；
- SAST、依赖、密钥、配置和DAST扫描；
- OpenTelemetry/OpenInference轨迹进入Phoenix；
- JSON、HTML、Prometheus指标和本地看板；
- SQLite运行、检查、失败、发布决策账本；
- SHA-256证据绑定和追加式审计哈希链；
- 自动阻断、自动放行资格、具名人工批准和回滚计划；
- 失败进入反馈队列，且必须绑定回归案例后才能关闭；
- GitHub Actions完整门禁。

## 报告

```text
reports/<UTC时间>/gate-report.json
reports/<UTC时间>/gate-report.html
reports/dashboard.html
reports/quality.prom
reports/releases/<decision-id>.json
data/quality.db
```

## 接入真实智能体

复制 `cases/demo-suite.json` 并将URL、账号、权限和业务状态断言替换为真实测试环境。然后执行：

```powershell
$env:TARGET_BASE_URL = 'https://your-test-agent.example'
.\.venv\Scripts\python.exe qualityctl.py case-run cases/your-suite.json
```

演示系统的通过结果只证明验收基础设施可运行，不代表用户的生产智能体已经通过。正式验收必须使用隔离测试环境、最小权限凭据和真实业务黄金案例。

完整闭环与平台状态见 `docs/CLOSED_LOOP.md`、`docs/ADOPTION.md` 和 `integrations/platforms.json`。
