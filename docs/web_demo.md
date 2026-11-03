# 在线 Demo 部署与交付说明

## 1. 部署目标

- 平台：Vercel Hobby，初期使用免费 `.vercel.app` 域名。
- 前端：React / TypeScript / Vite，静态案例随构建发布。
- 后端：`api/index.py` 导出 FastAPI ASGI 应用，`/api/*` 交给 Python Function。
- Python：3.12；Streamlit/Plotly 单独作为本地 UI 可选依赖。
- 访客免登录；生产域名须允许外部访客访问，不能拿受保护的预览链接当简历链接。

## 2. 部署步骤

1. 先执行 Python 测试、前端构建与浏览器验收。
2. 在自己的 Vercel 免费账户通过 GitHub 导入 `DTCB/feedback-prd-generator`，仅授权这个仓库。项目名 `feedback-lens`，Root Directory 为仓库根目录；若已有同仓库项目则复用。
3. Framework Preset 选择 Vite，Install Command 为 `npm ci`，Build Command 为 `npm run build`，Output Directory 为 `dist`；Node.js 固定 `24.x`，Python 为 `3.12`。
4. 初次部署不要上传模型密钥，先验证 `/`、`/demo.json`、`/api/status`、反馈导入和 Excel 下载。
5. 使用稳定的生产项目域名，刷新后仍能进入工作台。界面导航使用 URL hash。
6. 验证国内普通网络与手机上的首页、API、下载。未经实际网络验证，不声称国内稳定可用。

## GitHub 自动更新

生产地址：[https://feedback-lens-six.vercel.app/](https://feedback-lens-six.vercel.app/)。Vercel 项目为 `feedback-lens`，连接仓库 `DTCB/feedback-prd-generator`。

Production Branch 固定为 `main`。之后推送到 `main` 自动构建并更新同一个生产地址；其他分支自动生成独立预览。日常改动使用 `codex/*` 分支，确认预览后合并到 `main`。采用 Vercel 原生 Git 集成触发部署。

首次连接完成后，在独立分支提交一处可见文案变化，检查预览的提交 SHA、构建结果和页面，再合并到 `main`，确认生产部署使用同一合并后的版本。不要将预览地址当作简历中的固定地址。

构建失败时保留上一成功生产版本。若新版本功能异常，先在 Vercel 将上一成功部署恢复到生产，再用 Git revert 撤销问题提交并推送修正，不使用强制推送改写历史。

模型密钥仅配置在 Vercel Production 环境；首次 Preview 不配置真实密钥。修改环境变量后重新部署。Supabase/Redis 等服务令牌、`.env`、`output/` 与 CLI 登录状态都不进入 Git。

Vercel 首次登录与 GitHub 仓库授权由账号本人在浏览器完成。GitHub 提交身份需关联当前 GitHub 与 Vercel Hobby 所有者。

备用 CLI 登录与部署示例（正常更新使用 GitHub）：

```powershell
npx --yes vercel@latest login --global-config output/vercel-cli
npx --yes vercel@latest deploy --prod --yes --project feedback-lens --create-if-missing --global-config output/vercel-cli
```

CLI 隔离配置位于 `output/vercel-cli`，已被 Git 和部署上传排除。不要提交登录令牌或 `.env`。若已有同名项目，明确链接到自己的目标项目后再部署。

## 3. 生产环境变量

| 变量 | 用途 |
|---|---|
| `LLM_API_KEY` | 模型服务商密钥，仅放 Vercel 环境变量 |
| `LLM_MODEL` | 现有兼容模型名称 |
| `LLM_BASE_URL` | 现有兼容服务地址；不由浏览器提交 |
| `LLM_ENABLE_THINKING` | 可选；Web 工作台对阿里云 DeepSeek V4 默认关闭思考，设为 `true` 可开启 |
| `UPSTASH_REDIS_REST_URL` | 免费 Redis 的 REST 地址 |
| `UPSTASH_REDIS_REST_TOKEN` | Redis REST 令牌 |
| `QUOTA_HASH_SECRET` | 随机生成的独立长密钥，用于按日匿名化 IP |
| `AI_BUDGET_CONFIRMED` | 供应商费用封顶已确认后设为 `1`，初始为 `0` |

Upstash 只保存匿名日计数和全站月计数，不保存反馈、背景或 PRD。Redis Lua 将两类限额放在同一次原子操作中检查和预扣，跨函数实例共享。每日与每月按 UTC 边界重置。

供应商侧费用上限须单独设置，不能把 200 次请求当作 100 元预算。若没有可靠硬限额，维持生产实时 AI 关闭。超时、供应商错误、输出截断和证据校验失败均不自动重试。

### 实时 AI 首次开放

首期采用 **20 元/月模型预算，16 元告警**。在百炼为项目创建专用 API Key，在“费用用量 → 预算管理”设置这个 Key 的预算并开启“达到预算后立即停止”。百炼明确说明停用可能有延迟，因此预算阈值不是账单绝不超额的保证。[官方预算说明](https://help.aliyun.com/zh/model-studio/budget-management)

1. 在自己的 Upstash 账号创建 `feedback-lens-quota`，选择 Free 套餐，优先新加坡区域，不启用自动付费升级；使用持久化数据库，不使用会过期的临时数据库。复制 REST URL 与可写 REST Token，不使用只读 Token。
2. 在本地被 Git 忽略的 `.env.production.local` 中填写 Redis 的两个变量，运行 `python scripts/verify_redis_quota.py --env-file .env.production.local`。检查 PING、并发日限额、跨访客月限额和计数过期。脚本只使用 `lens:verify:<随机ID>:` 下的临时计数，完成后删除自己创建的计数，不接触正式额度；中断时临时计数在 5 分钟后过期。
3. 在 Vercel 项目的 **Production** 环境配置上表八项变量：沿用已验证的百炼接口和模型，`LLM_ENABLE_THINKING=false`，`QUOTA_HASH_SECRET` 使用独立的 32 字节随机密钥，`AI_BUDGET_CONFIRMED` 先保持 `0`。Preview 不配置真实模型密钥或预算开关。
4. 预算及 Redis 验证完成后，将 `AI_BUDGET_CONFIRMED=1`，重新部署当前 `main`。网站 URL 保持不变。密钥不粘贴到聊天、GitHub 或部署日志。
5. `python scripts/verify_deployed_ai.py` 默认只检查公开状态，不消耗模型额度。加 `--live` 才会上传一条合成反馈，依次执行真实分析、生成、章节改写，再探测第四次请求是否返回每日限额 429，并检查模板仍可用。使用当天尚未消耗额度的网络运行一次，不自动重试；正常消耗 3 次模型额度，若限流失效，第四次探测也可能调用模型。

检查脚本只输出状态、计数和错误类型，不输出服务地址、令牌、模型正文或原始异常内容。线上是否开放以真实验收记录为准，不因配置完成或状态为可用就宣称联调通过。

需要关闭时，将 `AI_BUDGET_CONFIRMED=0` 并重新部署；紧急时先在百炼禁用项目专用 Key。规则分析、案例与模板继续可用。普通代码更新继续通过 GitHub → Vercel 自动部署。

## 4. API 与数据边界

| 接口 | 行为 |
|---|---|
| `GET /api/status` | 可用状态和限额，不返回密钥、服务地址或模型名 |
| `POST /api/import` | multipart CSV/XLSX，最多 2MB、500 条；清理空值、重复和非法 ID |
| `POST /api/analyze` | 工作区、模式与反馈 ID；实时模式最多 30 条、12,000 字；预览后应用 |
| `POST /api/prd` | 工作区、需求 ID、生成方式；整篇生成或章节改写，不直接覆写浏览器文档 |
| `POST /api/export` | 以当前状态生成 Excel，验证 ID、关联、引用与数值 |

工作区 JSON 请求最多 8MB，单条反馈最多 12,000 字。解析限制读取行数并检查 XLSX 解压规模；Excel 禁用公式识别及自动链接，避免用户文字作为公式运行。

上传内容只在请求处理期间使用，不持久化到服务器；访客修改保存在当前标签页的 sessionStorage，容量不足时提示下载。关闭标签页后不承诺恢复。只有主动点击实时分析或生成时，才将对应反馈、背景与草稿发送给配置的模型服务商。

引用校验保证 ID 存在、引用来自关联证据、分析引语是原文子串。它不等于事实核查，不能保证语义判断正确或方案可落地，仍需人工复核。

## 5. 验收与评测

Python 测试覆盖清洗、案例一致性、关联校验、RICE、当前状态导出、公式注入防护、伪造引用拒绝、模型失败保留、输入限制、生产开关及本地并发限额。真实 Redis 配置完成后还需服务集成验证。

浏览器测试覆盖反馈校准、会话恢复、RICE、撤销、合并、PRD 编辑与引用、Markdown/Excel 下载和 1440/768/390 宽度溢出检查。自动化测试关闭真实模型，避免测试消耗额度。

固定参考集有 20 条人工标注的演示反馈。实际规则结果在 `public/evaluation.json`，脚本可重现。真实模型烟雾测试与完整效果评测分开记录，不把接口测试通过写成模型准确率。

## 6. 截图与简历描述

截图位于 `output/web/`，包括桌面与手机总览。`output/figma/` 原型保留供设计参考。

公开部署并验证链接后，可使用以下描述：

> 独立设计并实现「反馈洞察」AI 产品工作台，串联反馈清洗、证据追溯、需求审核、RICE 校准和 PRD 编辑导出；通过原文引用校验、人工修正与生成前预览设计可控的人机协作流程，使用 React、FastAPI 与 Vercel 构建免登录演示体验。

在真实联调通过、生产实时功能开放后，再补充“支持真实模型分析及章节改写”。不填写未测量的提效比例、采纳率或上线成效。
