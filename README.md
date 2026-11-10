# 面试备战助手

基于多 Agent 协作的面试准备工具，支持生成学习计划、记录任务进度、执行复盘和模拟面试，并根据薄弱点生成调整计划。

使用 Python、FastAPI、LangChain、Vue 和 SQLite 开发，提供 Minecraft 风格的网页界面。

## 项目解决什么问题

准备技术面试时，常见的问题是：

- 岗位要求很多，不清楚应该先准备什么。
- 学习计划过于宽泛，难以落实到每天。
- 完成学习后，缺少检验掌握程度的方式。
- 模拟面试发现问题后，没有对应的后续学习安排。

本项目将计划、执行、复盘和面试练习串联起来，帮助用户逐步完善准备内容。

## 主要功能

### 1. 按岗位生成准备计划

填写目标岗位、当前基础、学习天数等信息，生成按天组织的任务清单。

- 支持填写岗位 JD 和面试日期。
- 每日学习时长选填，未填写时按天数安排任务。
- 每项任务包含具体行动和预期产出。
- 计划先保存为草稿，用户确认后生效。

### 2. 记录执行进度

在计划表中勾选任务完成状态，填写实际耗时和备注。

记录保存到 SQLite，重新打开页面后仍可查看。

### 3. 学习复盘

结合原计划、任务状态和用户反馈，分析执行中的问题，给出具体调整建议。

复盘关注计划执行情况，不根据未完成任务直接推断用户的学习态度。

### 4. 模拟面试

根据岗位背景和计划内容进行文字面试。

- 支持已完成内容、整个计划、岗位综合三种范围。
- 支持基础知识、项目深挖和综合面试。
- 可选择 3、5、8 道主问题。
- 根据用户回答追问，每道主问题最多追问一次。
- 结束后展示总体评价、逐题反馈、参考回答和薄弱点。

### 5. 根据薄弱点调整计划

面试结束后，可以选择：

- **根据薄弱点调整计划**：设置后续学习日期和天数，生成新版本草稿。
- **我已经准备好了**：记录准备完成状态，并展示祝福提示。

调整草稿确认后成为正式版本，旧计划与面试报告保留，支持查看历史版本。

## 使用流程

1. 新建计划，填写岗位、基础和学习天数。
2. 检查生成的计划草稿，确认后开始执行。
3. 勾选完成任务，记录实际耗时与遇到的问题。
4. 提交复盘，分析计划执行情况。
5. 开始模拟面试，检验知识掌握程度。
6. 查看报告，根据薄弱点调整后续计划。

## Agent 分工

| Agent | 职责 |
|---|---|
| 协调 Agent | 理解用户需求，委派规划和复盘任务 |
| 规划 Agent | 根据目标、基础和学习日期生成准备任务 |
| 复盘 Agent | 分析执行记录，提出调整建议 |
| 面试官 Agent | 提出面试问题，根据回答进行追问 |
| 评估 Agent | 根据完整问答生成面试报告和薄弱点 |

Agent 负责内容生成与分析；后端代码负责状态管理、数据校验、题数限制和数据库写入。

## 实现要点

- **结构化输出**：使用 Pydantic 定义计划和评估结果的字段。
- **用户确认机制**：新计划与调整计划先保存为草稿，确认后生效。
- **计划版本管理**：通过版本关联保留调整前后的任务与报告。
- **独立面试记录**：面试问答单独保存，不混入协调 Agent 的聊天历史。
- **失败恢复**：面试回答先保存，再请求模型；部分请求失败后可继续或重试。
- **持久化存储**：SQLite 保存计划、任务、聊天、复盘和面试记录。
- **前后端交互**：Vue 页面通过 HTTP 接口与 FastAPI 通信。

## 技术栈

| 层级 | 技术 |
|---|---|
| 后端 | Python、FastAPI、Uvicorn |
| Agent | LangChain、LangGraph |
| 数据校验 | Pydantic |
| 数据存储 | SQLAlchemy、SQLite |
| 前端 | Vue 3、Element Plus、Axios |
| 模型服务 | 通过 API 调用，配置见 model_config.py |

前端通过 CDN 引入依赖，无需单独运行 Node.js 构建流程。

## 项目结构

```text
multi-agent/
├── agents/
│   ├── coordinator.py          # 协调 Agent
│   ├── planner.py              # 规划 Agent
│   ├── revs.py                 # 复盘 Agent
│   ├── interviewer.py          # 面试官与评估 Agent
│   └── plan_service.py         # 计划校验、保存与确认
├── static/
│   └── index3.html             # Vue 网页界面
├── data/                       # 运行时数据库目录
├── main.py                     # FastAPI 入口
├── model_config.py             # 模型配置
├── schemas.py                  # 数据结构与校验
├── datasets.py                 # 原有业务表与数据库配置
├── repository.py               # 数据读写
├── task_allocation.py          # 任务按天分组与校验
├── migrate_daily_plans.py      # 数据库升级兼容
├── plan_form_routes.py         # 计划表单接口
├── interview_models.py         # 面试相关数据表
├── interview_service.py        # 面试流程与报告服务
├── interview_routes.py         # 面试接口
├── .env.example                # 环境变量示例
├── requirements.txt
└── README.md
```

## 本地运行

### 1. 下载代码

```bash
git clone https://github.com/drewill/multi-agent.git
cd multi-agent
```

### 2. 创建虚拟环境

建议使用 Python 3.11，与项目开发环境保持一致。

```bash
python -m venv .venv
```

Windows：

```powershell
.venv\Scripts\activate
```

Linux / macOS：

```bash
source .venv/bin/activate
```

### 3. 安装依赖

```bash
python -m pip install -r requirements.txt
```

### 4. 配置模型

将 `.env.example` 复制为 `.env`。

Windows：

```powershell
Copy-Item .env.example .env
```

Linux / macOS：

```bash
cp .env.example .env
```

填写自己的配置：

```dotenv
DEEPSEEK_FLASH_KEY=你的API密钥
DEEPSEEK_FLASH_URL=模型服务的API地址
```

模型名称及额外参数在 `model_config.py` 中配置。

需要使用支持项目所需工具调用与结构化输出的模型服务。请勿将真实密钥提交到仓库。

### 5. 启动服务

在包含 `main.py` 的项目根目录运行：

```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

浏览器访问：

```text
http://127.0.0.1:8000
```

接口文档：

```text
http://127.0.0.1:8000/docs
```

首次启动会初始化数据库。当前版本按本地单用户、单 worker 模式设计。

## 当前限制

- 当前为本地练习项目，尚未实现完整的登录鉴权与多用户数据隔离。
- 主要对话记忆使用内存检查点，服务重启后不保证恢复完整的 Agent 对话状态。
- 模拟面试目前以文字交互为主。
- 模型评价仅作为练习参考，不能替代真实面试结果。
- 每日可投入时长是规划参考，不保证任务实际耗时。
- 模型调用会产生 API 费用，具体以服务商计费为准。

## 后续计划

- [ ] 增加登录鉴权与用户数据隔离
- [ ] 支持多模型选择
- [ ] 增加语音面试
- [ ] 增加模型调用限额与费用统计
- [ ] 完善并发处理和后台任务
- [ ] 补充部署配置与在线体验
