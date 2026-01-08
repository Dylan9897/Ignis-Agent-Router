import json
import asyncio
import logging

from src.services.llm_service import LLMService
from src.services.redis_client import RedisClient
from src.core.dialog_state_tracker import StateTracker
from src.core.intent_router import IntentRouter
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from src.services.rag_service import RAGService # 导入新服务RAG预留

logger = logging.getLogger("BotLogger")


class DebtBotEngine:
    def __init__(self,settings, flow_config, prompts_config):
        self.settings = settings
        self.flow = flow_config
        self.prompts = prompts_config['stage_flow']  # 获取 flow_choice 配置

        self.llm = LLMService(settings)  # LLM 客户端
        self.redis = RedisClient(settings["redis"])
        self.intent_router = IntentRouter(self.llm, flow_config, settings)
        self.llm = LLMService(settings)
        self.rag_service = RAGService() # 初始化 RAG 服务
        
        # 预编译话术生成的 Prompt 模板
        # 我们可以把 flow_choice.yaml 里的字符串转为 LangChain 模板对象
        self.prompt_templates = {}
        for key, tmpl_str in prompts_config['stage_flow'].items():
            # 自动追加 RAG 上下文插槽（如果模板里没写的话
            final_tmpl_str = tmpl_str + "\n\n{rag_context}" 
            self.prompt_templates[key] = ChatPromptTemplate.from_template(final_tmpl_str)

    async def init_session(self, session_id, customer_data):
        # 初始化 StateTracker + 存 Redis
        state_tracker = StateTracker(business_flow=self.flow).to_dict()
        session_ctx = {
            "state_tracker": state_tracker,
            "customer": customer_data,
            "collected": {}
        }
        self.redis._client.setex(f"session:{session_id}", 1800, json.dumps(session_ctx))

    async def stream_greeting(self, session_id, customer_data):
        """
        开场话术
        :param session_id: 会话ID
        :param customer_data: 客户数据
        :return: 异步生成器，流式返回开场话术的每个字符
        """
        # 1. 从 Redis 获取 session 上下文（如果存在）
        ctx_str = self.redis._client.get(f"session:{session_id}")
        if ctx_str:
            try:
                ctx = json.loads(ctx_str)
                # 如果 Redis 中有客户数据，优先使用
                if ctx.get("customer"):
                    customer_data = ctx["customer"]
            except json.JSONDecodeError:
                pass  # 如果解析失败，使用传入的 customer_data
        
        # 2. 获取开场话术模板
        greeting_template = self.prompts.get('start-001', 
            "您好，我是{company}的客服专员{operator}，请问你是{user_name}吗？")
        
        # 3. 准备模板变量
        # 从 customer_data 中提取信息
        user_name = customer_data.get('debtor_name', '先生/女士')
        # company 和 operator 可以从配置或 customer_data 中获取，如果没有则使用默认值
        company = customer_data.get('company', 
            self.settings.get('app', {}).get('company', 'XX金融'))
        operator = customer_data.get('operator', 
            self.settings.get('app', {}).get('operator', '客服'))
        
        # 4. 填充模板
        template_vars = {
            'company': company,
            'operator': operator,
            'user_name': user_name
        }
        
        try:
            greeting_text = greeting_template.format(**template_vars)
        except KeyError as e:
            # 如果模板中有未提供的变量，使用默认值填充
            missing_var = str(e).strip("'")
            template_vars[missing_var] = ''
            greeting_text = greeting_template.format(**template_vars)
        
        # 5. 流式返回话术（逐字符返回，模拟流式效果）
        for char in greeting_text:
            yield char
            # 添加小延迟以模拟真实的流式输出效果（可选）
            await asyncio.sleep(0.01)

    async def stream_response(self, session_id, user_input):
        """
        处理用户输入，生成回复
        :param session_id: 会话ID
        :param user_input: 用户输入
        :return: 异步生成器，流式返回回复的每个 token
        """
        # 1. 从 Redis 恢复上下文（注意：redis.Redis 是同步的，不能使用 await）
        ctx_str = self.redis._client.get(f"session:{session_id}")
        if not ctx_str:
            logger.error(f"❌ [Session {session_id}] 未找到会话上下文")
            yield "抱歉，会话已过期，请重新连接。"
            return
        
        try:
            ctx = json.loads(ctx_str)
        except json.JSONDecodeError as e:
            logger.error(f"❌ [Session {session_id}] 解析会话上下文失败: {e}")
            yield "系统错误，请稍后重试。"
            return
        
        # 恢复 StateTracker 实例
        state_tracker_dict = ctx.get("state_tracker", {})
        state_tracker = StateTracker.from_dict(state_tracker_dict, self.flow)
        customer_data = ctx.get("customer", {})
        
        # 2. 使用 LLM 进行意图识别
        current_stage = state_tracker.current_node
        intent = await self.intent_router.route(user_input, current_stage)
        logger.info(f"🎯 [Session {session_id}] 当前阶段: {current_stage}, 识别意图: {intent}")
        
        # 3. 更新状态：根据意图获取下一个状态
        next_stage, action = state_tracker.get_next_state(intent)
        logger.info(f"🔄 [Session {session_id}] 状态迁移: {current_stage} -> {next_stage}, 动作: {action}")
        
        # 4. 更新对话历史
        state_tracker.history.append({
            "user": user_input,
            "intent": intent,
            "stage": current_stage
        })
        
        # 5. [新增] RAG 检索：获取业务知识库上下文
        # 即使目前 RAGService 是空的，保留这个接口让架构完整
        rag_context = self.rag_service.retrieve_context(user_input, customer_data)

        # 6. [修改] 准备 LangChain 链的输入变量
        # 将 客户数据 + RAG上下文 统一打包
        chain_inputs = {
            'company': customer_data.get('company', 'XX金融'),
            'operator': customer_data.get('operator', '客服'),
            'user_name': customer_data.get('debtor_name', '先生/女士'),
            'debt_amount': customer_data.get('remaining_amount', 0),
            'overdue_days': customer_data.get('overdue_days', 0),
            'rag_context': rag_context,  # 注入 RAG 内容
            # 如果你的 prompt 里用了 {user_input}，也可以放进去
            # 'user_input': user_input 
        }

        # 7. [修改] 获取模板并构建执行链
        stage_config = self.flow.get(next_stage, {})
        prompt_key = stage_config.get('prompt_key')
        
        # 从预编译好的模板中获取
        prompt_template = self.prompt_templates.get(prompt_key)

        if prompt_template:
            try:
                # 核心：动态构建 LCEL 链
                # Chain = Template(填充变量) | LLM(生成) | Parser(转字符串)
                gen_chain = prompt_template | self.llm.get_llm() | StrOutputParser()
                
                # 8. [修改] 流式调用 (astream)
                # LangChain 的 astream 会自动处理流式返回
                async for token in gen_chain.astream(chain_inputs):
                    yield token
                    # 在高并发下，适当让出 CPU 时间片
                    await asyncio.sleep(0)

            except Exception as e:
                logger.error(f"❌ [Session {session_id}] Chain执行失败: {e}")
                yield "抱歉，请您再说一遍。"
        else:
            logger.warning(f"⚠️ 未找到 Prompt Key: {prompt_key}")
            yield "（话术配置缺失，请联系管理员）"
        
        # 7. 更新 Redis 状态
        updated_state = state_tracker.to_dict()
        updated_ctx = {
            "state_tracker": updated_state,
            "customer": customer_data,
            "collected": ctx.get("collected", {})
        }
        self.redis._client.setex(
            f"session:{session_id}", 
            1800, 
            json.dumps(updated_ctx, ensure_ascii=False)
        )
        logger.info(f"💾 [Session {session_id}] 状态已更新到 Redis")
    
    def render_prompt(self, stage: str, customer_data: dict, state_tracker: StateTracker) -> str:
        """
        根据当前阶段和客户数据生成 prompt
        :param stage: 当前对话阶段（如"确认欠款信息"）
        :param customer_data: 客户数据
        :param state_tracker: 状态跟踪器
        :return: 填充后的 prompt 文本
        """
        # 获取当前阶段的 prompt_key
        stage_config = self.flow.get(stage, {})
        prompt_key = stage_config.get('prompt_key', '')
        
        if not prompt_key:
            logger.warning(f"⚠️ 阶段 {stage} 没有配置 prompt_key")
            return "请生成一句合适的回复。"
        
        # 从 prompts 配置中获取模板
        prompt_template = self.prompts.get(prompt_key, '')
        
        if not prompt_template:
            logger.warning(f"⚠️ 未找到 prompt_key: {prompt_key}")
            return "请生成一句合适的回复。"
        
        # 准备模板变量
        template_vars = {
            'company': customer_data.get('company', 
                self.settings.get('app', {}).get('company', 'XX金融')),
            'operator': customer_data.get('operator', 
                self.settings.get('app', {}).get('operator', '客服')),
            'user_name': customer_data.get('debtor_name', '先生/女士'),
            'debt_amount': customer_data.get('remaining_amount', 0),
            'overdue_days': customer_data.get('overdue_days', 0),
        }
        
        # 填充模板
        try:
            prompt = prompt_template.format(**template_vars)
        except KeyError as e:
            # 如果模板中有未提供的变量，使用默认值
            missing_var = str(e).strip("'")
            template_vars[missing_var] = ''
            prompt = prompt_template.format(**template_vars)
        
        return prompt