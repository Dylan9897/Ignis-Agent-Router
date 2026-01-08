import logging
from langchain_core.prompts import (
    ChatPromptTemplate, 
    FewShotChatMessagePromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate
)
from langchain_core.output_parsers import StrOutputParser

logger = logging.getLogger("BotLogger")

class IntentRouter:
    def __init__(self, llm_service, flow_config, settings):
        self.llm = llm_service.get_intent_llm()
        self.flow_config = flow_config
        self.settings = settings
        
        # 1. 获取基础 System Prompt 模板 (来自 settings.yaml)
        # 建议模板内容保持： "你是一个... 定义如下: {definitions}..."
        self.system_tmpl_str = settings.get('llm', {}).get('system_prompt_template', '')

    def _build_chain(self, current_stage):
        """
        动态构建当前阶段的 Chain (包含 Few-Shot)
        """
        stage_config = self.flow_config.get(current_stage, {})
        examples = stage_config.get('examples', [])
        
        # --- A. 构建 Few-Shot 模板 ---
        if examples:
            # 1. 定义单个示例的格式
            example_prompt = ChatPromptTemplate.from_messages(
                [
                    ("human", "{input}"),
                    ("ai", "{output}"),
                ]
            )
            
            # 2. 构建 Few-Shot 模板
            few_shot_prompt = FewShotChatMessagePromptTemplate(
                example_prompt=example_prompt,
                examples=examples, # 这里直接传入 YAML 里读出来的 list
            )
        else:
            few_shot_prompt = None

        # --- B. 准备 System Prompt 变量 ---
        valid_intents = stage_config.get('valid_intents', [])
        intent_definitions = stage_config.get('intent_definitions', {})
        definitions_text = "\n".join([f"- {k}: {v}" for k, v in intent_definitions.items()])

        # --- C. 组装最终 Prompt ---
        # 结构：System Message -> Few-Shot Examples -> Current User Input
        messages = [
            SystemMessagePromptTemplate.from_template(self.system_tmpl_str),
        ]
        
        if few_shot_prompt:
            messages.append(few_shot_prompt)
            
        messages.append(HumanMessagePromptTemplate.from_template("{user_input}"))
        
        final_prompt = ChatPromptTemplate.from_messages(messages)
        
        # --- D. 绑定变量 ---
        # 这里虽然创建了 template，但此时是一个 partial 的状态，
        # 我们可以在构建 chain 时把静态变量(definitions等)先填进去，减少 invoke 时的传参
        final_prompt = final_prompt.partial(
            stage=current_stage,
            valid_intents=", ".join(valid_intents),
            definitions=definitions_text
        )

        return final_prompt | self.llm | StrOutputParser()

    async def route(self, user_input: str, current_stage: str) -> str:
        # 动态构建针对当前 Stage 的 Chain
        # (注：为了性能，可以将 build_chain 的结果缓存起来，不要每次 route 都重新 build)
        chain = self._build_chain(current_stage)

        try:
            # 执行
            intent = await chain.ainvoke({"user_input": user_input})
            intent = intent.strip()
            
            # ... 后续清洗校验逻辑保持不变 ...
            stage_config = self.flow_config.get(current_stage, {})
            valid_intents = stage_config.get('valid_intents', [])
            
            if intent in valid_intents:
                logger.info(f"✅ 意图识别: {intent}")
                return intent
                
            # ... 模糊匹配逻辑 ...
            for valid in valid_intents:
                if valid in intent:
                    return valid
            
            return "其他"   

        except Exception as e:
            logger.error(f"❌ 意图识别失败: {e}")
            return "其他"