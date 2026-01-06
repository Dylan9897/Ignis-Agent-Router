import os
import asyncio
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, status
from fastapi.middleware.cors import CORSMiddleware
from typing import Annotated
from dotenv import load_dotenv
from src.utils.helper import load_customer_from_db
from src.core.agent_engine import DebtBotEngine
from src.utils.config_loader import load_full_config

app = FastAPI()
logger = logging.getLogger("uvicorn")

# 添加 CORS 中间件配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中建议替换为具体的域名列表
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 从环境变量读取你的安全验证 Key（所有合法客户端必须知道这个 secret）
WEBSOCKET_AUTH_KEY = os.getenv("WEBSOCKET_AUTH_KEY")
if not WEBSOCKET_AUTH_KEY:
    raise RuntimeError("请设置环境变量 WEBSOCKET_AUTH_KEY")

print(WEBSOCKET_AUTH_KEY)


MAX_CONCURRENT_CALLS = 100
call_semaphore = asyncio.Semaphore(MAX_CONCURRENT_CALLS)
# ===================================

# ============= 加载配置 =============
load_dotenv()
if not os.getenv("ALI_API_KEY"):
    raise Exception("Error: ALI_API_KEY not found in .env file.")
# 3. 加载配置
try:
    settings, flow_config, prompts_config = load_full_config()
except Exception as e:
    raise EnvironmentError(f"Config Error: {e}")
# ===================================

engine = DebtBotEngine(
    settings, flow_config, prompts_config
)  # 全局共享 LLM client, config 等

@app.websocket("/call/{session_id}")
async def websocket_endpoint(
        websocket: WebSocket,
        session_id: str
):
    # 🔑 第一步：连接握手
    # 在验证前必须先 accept，否则无法发送 text 消息给客户端
    await websocket.accept()

    query_params = websocket.query_params
    auth_key = query_params.get("auth_key")

    logger.info(f"🔍 [调试] 收到连接请求 | Session: {session_id}")
    # logger.info(f"🔍 [调试] 来源 Headers: {websocket.headers}")
    # logger.info(f"🔍 [调试] Query参数: {auth_key}")

    # 🔑 第二步：验证 WebSocket 接入密钥
    if auth_key != WEBSOCKET_AUTH_KEY:
        logger.warning(f"拒绝连接 {session_id}：无效 auth_key -> {auth_key}")
        await websocket.send_text("❌ 未经授权的访问。无效的 auth_key。")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # 🔑 第三步：并发检查
    if call_semaphore.locked():
        logger.warning(f"拒绝新连接 {session_id}：已达最大并发 {MAX_CONCURRENT_CALLS}")
        await websocket.send_text("系统繁忙，请稍后再拨。")
        await websocket.close(code=status.WS_1013_TRY_AGAIN_LATER)
        return

    # 🔑 第四步：进入业务逻辑
    async with call_semaphore:  # 使用上下文管理器自动获取和释放 Semaphore
        current_calls = MAX_CONCURRENT_CALLS - call_semaphore._value
        logger.info(f"新通话接入: {session_id}, 当前并发: {current_calls}")

        try:
            # 模拟业务流程
            await websocket.send_text(f"✅ 连接成功，Session: {session_id}")

            # >>> DebtBot 业务逻辑 <<<
            # 1. 从 MySQL 加载工单数据
            # 使用线程池执行同步的数据库查询，防止阻塞 WebSocket
            loop = asyncio.get_running_loop()
            customer_data = await loop.run_in_executor(None, load_customer_from_db, session_id)
            logger.info(f"🔍 [调试] 查询到的客户信息: {customer_data}")

            if not customer_data:
                await websocket.send_text("❌ 客户信息不存在。")
                return

            # 2. 初始化会话（存 Redis）
            await engine.init_session(session_id, customer_data)

            # 3. 发送开场白（流式）- 连接后立即发送
            async for token in engine.stream_greeting(session_id, customer_data):
                await websocket.send_text(token)

            # 4. 进入对话循环，持续监听用户输入（ASR 结果）
            try:
                while True:
                    # 接收用户输入
                    user_input = await websocket.receive_text()
                    logger.info(f"📥 [Session {session_id}] 收到用户输入: {user_input}")
                    
                    # 如果收到退出指令，结束对话
                    if user_input.strip().lower() in ['exit', 'quit', '结束', '退出']:
                        await websocket.send_text("对话已结束，感谢您的配合。")
                        break
                    
                    # 生成并流式发送回复
                    try:
                        async for token in engine.stream_response(session_id, user_input):
                            await websocket.send_text(token)
                    except Exception as e:
                        logger.error(f"❌ [Session {session_id}] 生成回复时出错: {e}")
                        await websocket.send_text("抱歉，我暂时无法理解，请重新说明一下。")
                        
            except WebSocketDisconnect:
                logger.info(f"🔌 [Session {session_id}] 客户端主动断开连接")
            except Exception as e:
                logger.error(f"❌ [Session {session_id}] 对话循环异常: {e}")
            finally:
                # 清理资源：结束会话
                try:
                    # await engine.end_session(session_id)  # 如果实现了 end_session 方法，取消注释
                    logger.info(f"🧹 [Session {session_id}] 会话已清理")
                except Exception as e:
                    logger.error(f"⚠️ [Session {session_id}] 清理会话时出错: {e}")
        except WebSocketDisconnect:
            logger.info(f"客户端断开: {session_id}")
        except Exception as e:
            logger.error(f"会话 {session_id} 异常: {e}")
        finally:
            call_semaphore.release()
            logger.info(f"释放连接: {session_id}")

"""
linux:
    export WEBSOCKET_AUTH_KEY="my-debtbot-secret-2026"
    uvicorn api:app --host 0.00 --port 8000
windows:
    set WEBSOCKET_AUTH_KEY=my-debtbot-secret-2026 && uvicorn api:app --host 0.0.0.0 --port 8000
"""