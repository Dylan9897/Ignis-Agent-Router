import logging
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

logger = logging.getLogger("BotLogger")

class IntentRouter:
    def __init__(self, llm_service, flow_config, settings):
        self.llm = llm_service.get_intent_llm()
        self.flow_config = flow_config
        self.settings = settings
        
        # 定义 Prompt 模板（LangChain 风格）
        # 这里使用了settings.yaml 中的模板结构
        raw_template = settings.get('llm', {}).get('system_prompt_template', '')
        
        self.prompt = ChatPromptTemplate.from_template(raw_template)
        
        # 构建处理链：Prompt -> LLM -> String清洗
        self.chain = self.prompt | self.llm | StrOutputParser()

    async def route(self, user_input: str, current_stage: str) -> str:
        """
        使用 LangChain Chain 进行意图识别 (改为异步调用)
        """
        # 1. 从businees_flow准备上下文数据
        stage_config = self.flow_config.get(current_stage, {})
        valid_intents = stage_config.get('valid_intents', [])
        intent_definitions = stage_config.get('intent_definitions', {})
        
        if not valid_intents:
            return "其他"

        definitions_text = "\n".join([f"- {k}: {v}" for k, v in intent_definitions.items()])

        # 2. 执行链 (invoke)
        try:
            # LangChain 会自动填充模板中的变量
            intent = await self.chain.ainvoke({
                "stage": current_stage,
                "valid_intents": ", ".join(valid_intents),
                "definitions": definitions_text,
                "user_input": user_input
            })
            
            # 3. 结果清洗与校验 (LangChain 的 StrOutputParser 已经去除了外层引号)
            intent = intent.strip()
            
            if intent in valid_intents:
                logger.info(f"✅ [LangChain] 意图识别: {intent}")
                return intent
            
            # 模糊匹配兜底
            for valid in valid_intents:
                if valid in intent:
                    return valid
            
            return "其他"

        except Exception as e:
            logger.error(f"❌ 意图识别失败: {e}")
            return "其他"