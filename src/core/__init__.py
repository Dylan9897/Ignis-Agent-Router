# src/core/__init__.py

from .agent_engine import DebtBotEngine

# 定义当执行 from src.core import * 时导出哪些模块（可选，但推荐规范）
__all__ = ['DebtBotEngine']

"""
# debt_bot_engine.py
class DebtBotEngine:
    def __init__(self):
        self.llm = AsyncLLMService(...)  # 异步 LLM 客户端
        self.redis = aioredis.from_url("redis://...")

    async def init_session(self, session_id, customer_data):
        # 初始化 StateTracker + 存 Redis
        state_tracker = StateTracker(business_flow=self.flow)
        session_ctx = {
            "state_tracker": state_tracker,
            "customer": customer_data,
            "collected": {}
        }
        await self.redis.setex(f"session:{session_id}", 1800, json.dumps(session_ctx))

    async def stream_response(self, session_id, user_input):
        # 1. 从 Redis 恢复上下文
        ctx = await self.redis.get(f"session:{session_id}")
        # 2. 路由意图 + 更新状态
        intent = self.intent_router.route(user_input)
        new_state = ctx["state_tracker"].update(intent)
        # 3. 生成 prompt + 流式调用 LLM
        prompt = self.render_prompt(new_state, ctx["customer"])
        async for token in self.llm.astream(prompt):
            yield token
        # 4. 更新 Redis 状态
        await self.redis.setex(...)
"""
