# 用户反馈分析与 PRD 自动生成工具

这是一个面向产品经理 / AI 产品经理作品集的项目 Demo：从用户真实反馈出发，自动完成反馈清洗、主题归类、痛点提炼、需求池沉淀、RICE 优先级排序，并生成可继续编辑的 PRD 草稿。

## 项目背景

产品经理在处理 App 评论、社群反馈、客服工单和用户访谈记录时，常遇到三个问题：

- 反馈来源分散，信息噪声高，人工整理耗时。
- 需求判断容易停留在“声音最大的人”，缺少统一优先级框架。
- 从反馈到 PRD 的链路断裂，需求洞察难以快速转化为可执行方案。

本项目尝试用数据分析与 AI 辅助写作，把“用户反馈分析”变成一条可复用的产品工作流。

## 目标岗位

- 产品经理
- AI 产品经理
- 数据产品经理
- 增长 / 用户体验方向产品经理

## 解决的问题

- 将非结构化用户反馈整理为结构化需求池。
- 帮助产品经理快速识别高频痛点、用户情绪和核心场景。
- 用 RICE 模型辅助需求优先级判断，减少拍脑袋排序。
- 自动生成 PRD 初稿，提升从洞察到方案的产出效率。
- 为面试作品集提供一个完整的 AI 产品闭环案例。

## 核心功能

- 反馈导入：支持本地 CSV / Excel，预留 Google Play 评论抓取能力。
- 数据清洗：去重、空值处理、字段标准化、评论时间和评分整理。
- 反馈分析：按主题、情绪、评分、关键词和时间趋势观察用户问题。
- 需求池生成：把相似反馈聚合为需求条目，沉淀用户场景、痛点和机会点。
- RICE 排序：从 Reach、Impact、Confidence、Effort 四个维度计算优先级。
- PRD 生成：输出背景、目标、用户故事、功能范围、验收标准和风险说明。
- 结果导出：支持导出 Excel / Markdown，便于继续加工为评审材料。

## 技术栈

- Python 3.10+
- pandas：数据清洗、聚合与结构化处理
- Streamlit：快速搭建交互式作品集 Demo
- Streamlit 内置图表：分类分布、情绪分布和需求池展示
- openpyxl / xlsxwriter：Excel 读写与导出
- python-dotenv：本地环境变量管理
- google-play-scraper：可选，用于刷新 Google Play 评论数据

## 数据来源

项目可使用以下数据作为输入：

- 应用商店公开评论，例如 Google Play 评论。
- 用户访谈纪要和客服工单脱敏样本。
- 问卷开放题反馈。
- 社群、论坛、NPS 回访问卷中的文本反馈。

作品集展示时内置 `data/sample_feedback.csv`，包含 65 条围绕 AI 写作/AI 助手产品的匿名化公开评论风格样例。统一字段为：`feedback_id`、`date`、`source`、`app_name`、`channel`、`rating`、`version`、`user_type`、`module`、`feedback_text`、`thumbs_up`。

如果需要刷新 Google Play 评论，可选安装抓取依赖后运行：

```bash
python scripts/fetch_reviews.py --app-id com.openai.chatgpt --app-name ChatGPT --count 100 --lang zh --country cn --output data/google_play_reviews.csv
```

## 项目结构

```text
.
├── data/                  # 样例反馈数据与中间数据
├── docs/                  # 作品集、复盘、面试和流程文档
├── scripts/               # 可选真实评论刷新脚本
├── src/feedback_prd/      # 字段标准化、规则分类、RICE 和 PRD 生成逻辑
├── tests/                 # 端到端导入、分析与 PRD 生成测试
├── app.py                 # Streamlit 演示入口
├── requirements.txt       # 运行依赖
├── pyproject.toml         # 项目元信息与依赖配置
└── README.md              # 项目说明
```

## 运行方式

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### 配置真实 LLM API

项目支持 OpenAI 官方与 OpenAI 兼容接口。复制 `.env.example` 为 `.env`，填入自己的 Key：

```env
LLM_API_KEY=sk-your-api-key
LLM_MODEL=gpt-4o-mini
LLM_BASE_URL=
```

如果使用 OpenAI 官方接口，`LLM_BASE_URL` 留空即可。如果使用兼容接口，例如 DeepSeek 或通义千问 OpenAI 兼容模式，填写对应的 `base_url` 和模型名：

```env
LLM_API_KEY=your-compatible-api-key
LLM_MODEL=deepseek-chat
LLM_BASE_URL=https://api.deepseek.com
```

应用会优先读取 `LLM_API_KEY`、`LLM_MODEL`、`LLM_BASE_URL`，同时兼容 `OPENAI_API_KEY`、`OPENAI_MODEL`、`OPENAI_BASE_URL`。请不要把真实 API Key 提交到仓库；`.env` 已被 `.gitignore` 忽略。

启动 Streamlit 演示：

```bash
streamlit run app.py
```

运行测试：

```bash
python -m pytest -q
```

如果仅需要查看文档，可直接阅读 `README.md` 与 `docs/` 下的作品集材料。

## 功能截图占位

> 截图 1：反馈总览 Dashboard，包括评论量、平均评分、情绪分布和高频主题。

> 截图 2：需求池列表，包括用户痛点、对应反馈数量、RICE 得分和当前状态。

> 截图 3：PRD 自动生成页面，包括需求背景、目标用户、功能范围和验收标准。

> 截图 4：导出结果示例，包括 Excel 需求池和 Markdown PRD 草稿。

## 项目亮点

- 真实产品工作流：不是单纯做文本摘要，而是覆盖反馈分析、需求判断、PRD 生成和复盘闭环。
- 产品方法论落地：将需求池、RICE、用户故事、验收标准等产品经理常用方法工具化。
- AI 提效明确：AI 负责提炼、归类和草稿生成，产品经理负责判断、校准和决策。
- 适合面试表达：能清楚展示问题定义、方案设计、数据分析、优先级判断和迭代意识。
- 可扩展性强：后续可接入更多数据源、LLM API、协作评审流程和需求状态流转。

## 可改进方向

- 接入 OpenAI / 其他大模型 API，提升主题聚类、用户故事和 PRD 生成质量。
- 增加人工校准机制，让产品经理修正主题、情绪和 RICE 权重。
- 增加需求状态流转，例如待评估、已立项、开发中、已上线、已复盘。
- 增加多来源反馈合并，支持 App 评论、客服工单、问卷和社群文本统一分析。
- 增加评估指标，例如 PRD 采纳率、人工节省时间、上线后反馈改善情况。
