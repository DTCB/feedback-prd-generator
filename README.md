# 反馈洞察 · Feedback Lens

面向 AI 产品经理作品集的在线工作台：从用户反馈中发现问题，核验原始证据，人工校准需求与 RICE，再生成可编辑、可追溯的 PRD。

## 现在可以体验什么

- **洞察总览**：默认载入 65 条演示反馈、8 个人工整理的需求主题，所有统计来自当前工作状态。
- **反馈分析**：搜索与筛选、原文与引用联动、修改分类和情绪、接受关联或拆分为独立需求。
- **需求决策**：查看支持证据、调整 RICE 及依据、重新排序、确认或暂缓、比较与合并需求。
- **PRD 工作台**：模板生成、真实模型生成和章节改写、接受前预览、Markdown 编辑和真实下载。
- **交付**：Excel 包含当前反馈、需求、RICE、产品背景、修改记录及 PRD。
- **会话**：当前标签页自动保存、刷新恢复、最近 15 次操作可撤销、恢复默认案例。

默认案例为**公开评论风格的演示样例**，不是经过核验的公开评论数据集。主题分组经过人工整理，不将预分析或模板输出冒充真实模型结果。

## 技术结构

前端为 React + TypeScript + Vite；后端为 FastAPI，复用 Python/pandas 分析逻辑，通过 Vercel Python Function 提供 `/api` 接口。原有 Streamlit 入口保留。

```text
web/                     React 工作台与会话逻辑
api/index.py             Vercel / uvicorn 入口
src/feedback_prd/        原分析逻辑、工作区、AI 校验与持久化限额
public/demo.json         随前端发布的案例快照
public/evaluation.json   实际执行生成的规则基线记录
evaluation/gold.json     固定人工参考标注集
tests/                   原有测试、接口测试与浏览器测试
docs/web_demo.md         部署、运行边界与验收说明
```

## 本地运行

需要 Node.js 22.12+ 和 Python 3.11+。Vercel 生产运行时选用 Python 3.12。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-web.txt
npm ci
```

在两个终端分别运行：

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.index:app --host 127.0.0.1 --port 8000
```

```powershell
npm run dev
```

浏览器打开 `http://127.0.0.1:5173`。Vite 将 `/api` 代理到本机 Python 服务。

## 模型配置与成本

复制 `.env.example` 为 `.env`，配置 `LLM_API_KEY`、`LLM_MODEL` 和可选的 `LLM_BASE_URL`。兼容已有的 `OPENAI_*` 环境变量。密钥只在后端使用，不进入浏览器。

Web 工作台调用阿里云百炼的 DeepSeek V4 混合思考模型时，默认设置 `enable_thinking=false`，避免推理过程挤占 PRD 的输出额度。确实需要思考模式时可设置 `LLM_ENABLE_THINKING=true`；其他服务商不会收到此专用参数。[阿里云参数说明](https://help.aliyun.com/zh/model-studio/deepseek-api)

Web 工作台调用阿里云百炼的 DeepSeek V4 混合思考模型时，默认设置 `enable_thinking=false`，避免推理过程挤占 PRD 的输出额度。确实需要思考模式时可设置 `LLM_ENABLE_THINKING=true`；其他服务商不会收到此专用参数。[阿里云参数说明](https://help.aliyun.com/zh/model-studio/deepseek-api)

本地开发读取现有配置；生产默认关闭实时 AI，直到同时具备：

1. 有效模型配置；
2. Upstash Redis REST 配置及独立的 `QUOTA_HASH_SECRET`；
3. 在供应商侧设置费用上限后，显式设置 `AI_BUDGET_CONFIRMED=1`。

每 IP 每日最多 3 次、全站每月最多 200 次，使用一次 Redis Lua 操作原子检查并预扣次数。失败调用也计数。Redis 不可用时拒绝实时调用，不降级到实例内计数。

调用次数不等于人民币预算；100 元总预算仍需供应商侧硬限额。没有可靠费用封顶时，生产保留完整案例、人工校准和模板生成，不开放实时调用。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
npm run build
# 先启动前后端；Windows 默认使用已安装的 Chrome，其他环境执行 npx playwright install chromium
npm run test:e2e
```

更新案例或重新评测规则：

```powershell
.\.venv\Scripts\python.exe scripts/export_web_demo.py
.\.venv\Scripts\python.exe scripts/evaluate_web.py --mode rule
```

真实模型评测与小样本联调会发送测试文本并产生模型费用，仅在确认授权与预算后执行：

```powershell
.\.venv\Scripts\python.exe scripts/smoke_web_ai.py
.\.venv\Scripts\python.exe scripts/evaluate_web.py --mode llm --output output/web/model-evaluation.json
```

`evaluation/gold.json` 为自建演示集的单人参考标注，匹配结果不代表真实用户分布、通用准确率或业务成效。

## 继续使用原 Streamlit 应用

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-streamlit.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

旧版功能文档保留在 [Streamlit 历史说明](docs/streamlit_legacy.md)。

## 上线

部署配置在 `vercel.json`；前端构建命令为 `npm run build`，输出目录为 `dist`。Git 导入时将 Framework Preset 设为 Vite，项目根目录为仓库根目录。

推荐通过 Vercel 的 GitHub 集成连接 `DTCB/feedback-prd-generator`：生产分支 `main`，推送后自动更新生产地址；`codex/*` 等其他分支生成预览。安装命令 `npm ci`，Node.js 固定 `24.x`，Python `3.12`。本地 `.env` 和 `output/` 不上传，密钥只存 Vercel 服务端环境变量。

完整步骤、环境变量、生产 AI 开放条件与验收限制见 [部署说明](docs/web_demo.md)。
