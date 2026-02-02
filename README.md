# Ignis-Agent-Router

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

基于大语言模型（LLM）的下一代对话调度引擎。通过**语义路由（Semantic Routing）**取代传统意图识别，结合**有限状态机（FSM）**对大模型进行实时监控与边界约束，实现复杂业务场景下的柔性对话管理，解决传统槽位填充链路僵硬、容错率低的痛点。

## ✨ 特性

- 🧠 **智能意图识别**：基于 LLM 的语义路由，无需预定义规则，自动理解用户意图
- 🔄 **状态机驱动**：基于 FSM 的对话流程管理，确保对话逻辑清晰可控
- 💬 **流式对话**：WebSocket 实时流式响应，提供流畅的对话体验
- 🎯 **业务场景适配**：专为催收场景设计，支持多阶段对话流程
- 🔒 **会话管理**：Redis 持久化会话状态，支持断线重连
- ⚡ **高性能**：异步架构设计，支持高并发对话处理
- 🛠️ **易于配置**：YAML 配置文件，灵活定制对话流程和话术模板

## 🏗️ 架构设计

```
┌─────────────┐
│   Client    │ (WebSocket)
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────┐
│      FastAPI WebSocket API       │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│      DebtBotEngine              │
│  ┌──────────┐  ┌─────────────┐ │
│  │IntentRouter│  │StateTracker │ │
│  │  (LLM)    │  │   (FSM)     │ │
│  └──────────┘  └─────────────┘ │
└──────┬──────────────────────────┘
       │
       ├──────────────┬──────────────┐
       ▼              ▼              ▼
┌──────────┐   ┌──────────┐   ┌──────────┐
│  LLM API │   │  Redis   │   │  MySQL   │
│ (Aliyun) │   │ (Session)│   │ (Customer)│
└──────────┘   └──────────┘   └──────────┘
```

## 🚀 快速开始

### 环境要求

- Python 3.8+
- Redis 5.0+
- MySQL 5.7+ (可选，用于客户数据存储)

### 安装步骤

1. **克隆仓库**
```bash
git clone https://github.com/your-username/Ignis-Agent-Router.git
cd Ignis-Agent-Router
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

3. **配置环境变量**

创建 `.env` 文件：
```bash
# LLM API 配置（阿里云通义千问）
ALI_API_KEY=your_api_key_here
ALI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# WebSocket 认证密钥
WEBSOCKET_AUTH_KEY=your_secret_key_here
```

4. **配置系统**

复制配置示例文件并编辑：
```bash
cp config/settings.example.yaml config/settings.yaml
```

编辑 `config/settings.yaml`，配置 Redis 和 LLM 信息：
```yaml
redis:
  host: "localhost"
  port: 6379
  password: ""  # 如果需要密码认证
  db: 0
```

5. **启动服务**

```bash
# Linux/Mac
export WEBSOCKET_AUTH_KEY="your_secret_key"
uvicorn api:app --host 0.0.0.0 --port 8000

# Windows
set WEBSOCKET_AUTH_KEY=your_secret_key
uvicorn api:app --host 0.0.0.0 --port 8000
```

或使用启动脚本：
```bash
chmod +x start.sh
./start.sh
```

## 📖 使用指南

### WebSocket 连接

连接到 WebSocket 端点：
```
ws://localhost:8000/call/{session_id}?auth_key={WEBSOCKET_AUTH_KEY}
```

**参数说明：**
- `session_id`: 会话唯一标识符
- `auth_key`: WebSocket 认证密钥（必须与配置的 `WEBSOCKET_AUTH_KEY` 一致）

### 对话流程

1. **连接建立**：客户端连接后，服务器自动发送开场话术
2. **用户输入**：客户端发送用户消息（欠款人的回复）
3. **意图识别**：系统使用 LLM 识别用户意图
4. **状态更新**：根据意图更新对话状态
5. **生成回复**：LLM 生成智能客服回复并流式返回
6. **循环对话**：重复步骤 2-5，直到对话结束

### 示例代码

**Python 客户端示例：**
```python
import asyncio
import websockets

async def chat():
    uri = "ws://localhost:8000/call/123?auth_key=your_secret_key"
    async with websockets.connect(uri) as websocket:
        # 接收开场话术
        greeting = await websocket.recv()
        print(f"Bot: {greeting}")
        
        # 发送用户输入
        user_input = input("You: ")
        await websocket.send(user_input)
        
        # 接收流式回复
        response = ""
        async for message in websocket:
            response += message
            print(message, end="", flush=True)
        print(f"\nBot: {response}")

asyncio.run(chat())
```

**JavaScript 客户端示例：**
```javascript
const ws = new WebSocket('ws://localhost:8000/call/123?auth_key=your_secret_key');

ws.onmessage = (event) => {
    console.log('Bot:', event.data);
};

ws.onopen = () => {
    // 发送用户输入
    ws.send('我是张三');
};
```

## ⚙️ 配置说明

### 对话流程配置 (`config/business_flow.yaml`)

定义对话的各个阶段和状态转换：

```yaml
沟通开场:
    prompt_key: "start-001"
    valid_intents: ["本人", "号码易主", "亲属", "其他"]
    intent_map: 
        本人: {"next_stage": "确认欠款信息", "action": "proceed"}
        号码易主: {"next_stage": "身份二次确认", "action": "reconfirm"}
        # ...
```

### 话术模板配置 (`config/flow_choice.yaml`)

定义每个阶段的话术模板：

```yaml
stage_flow:
    start-001: "您好，我是{company}的客服专员{operator}，请问你是{user_name}吗？"
    C-001: "用户身份已确认。任务是通知欠款信息。请明确告知用户，系统显示其有一笔金额为 {debt_amount} 元的欠款已逾期..."
```

### 系统配置 (`config/settings.yaml`)

```yaml
app:
  max_retries: 2
  temperature: 0.1

llm:
  intent_model: "qwen-turbo"      # 意图识别模型
  generation_model: "qwen-turbo"   # 话术生成模型
```

## 📁 项目结构

```
Ignis-Agent-Router/
├── api.py                      # FastAPI WebSocket 入口
├── config/                     # 配置文件目录
│   ├── business_flow.yaml      # 业务流程配置
│   ├── flow_choice.yaml        # 话术模板配置
│   └── settings.yaml           # 系统配置
├── src/
│   ├── core/                   # 核心业务逻辑
│   │   ├── agent_engine.py     # 对话引擎
│   │   ├── intent_router.py    # 意图路由器
│   │   └── dialog_state_tracker.py  # 状态跟踪器
│   ├── services/               # 服务层
│   │   ├── llm_service.py      # LLM 服务
│   │   ├── redis_client.py     # Redis 客户端
│   │   └── mysql_service.py    # MySQL 客户端
│   └── utils/                  # 工具函数
│       ├── config_loader.py    # 配置加载器
│       ├── helper.py           # 辅助函数
│       └── logger.py           # 日志工具
├── start.sh                    # 启动脚本
├── requirements.txt            # Python 依赖
└── README.md                   # 项目文档
```

## 🔧 核心组件

### DebtBotEngine

对话引擎核心类，负责：
- 会话初始化和管理
- 意图识别和状态更新
- 话术生成和流式输出

### IntentRouter

意图路由器，使用 LLM 进行语义路由：
- 根据当前对话阶段和用户输入识别意图
- 支持多意图分类和模糊匹配

### StateTracker

状态跟踪器，基于 FSM 管理对话状态：
- 状态转换逻辑
- 对话历史记录
- 槽位信息提取

## 🛠️ 开发指南

### 添加新的对话阶段

1. 在 `config/business_flow.yaml` 中添加新阶段配置
2. 在 `config/flow_choice.yaml` 中添加对应的话术模板
3. 更新状态转换逻辑

### 自定义意图识别

修改 `config/settings.yaml` 中的 `system_prompt_template` 来调整意图识别的 prompt。

### 扩展 LLM 服务

`LLMService` 支持多种 LLM 提供商，只需实现对应的 API 接口即可。

## 📝 API 文档

启动服务后，访问 `http://localhost:8000/docs` 查看自动生成的 API 文档。

## 🤝 贡献指南

欢迎贡献代码！请遵循以下步骤：

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🙏 致谢

- [FastAPI](https://fastapi.tiangolo.com/) - 现代化的 Python Web 框架
- [通义千问](https://tongyi.aliyun.com/) - 阿里云大语言模型
- [Redis](https://redis.io/) - 内存数据库

## 📮 联系方式

如有问题或建议，请通过以下方式联系：

- 提交 [Issue](https://github.com/your-username/Ignis-Agent-Router/issues)
- 发送邮件至：your-email@example.com

---

⭐ 如果这个项目对你有帮助，请给个 Star！
