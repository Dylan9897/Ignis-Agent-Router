import logging
import os
from openai import OpenAI

logger = logging.getLogger("BotLogger")


class IntentRouter:
    def __init__(self, llm_service, flow_config, settings):
        """
        意图路由器，使用 LLM 进行意图分类
        :param llm_service: 已实例化的 LLMService 对象
        :param flow_config: 业务流程配置（business_flow.yaml）
        :param settings: 应用设置（包含 LLM 配置）
        """
        self.llm_service = llm_service
        self.flow_config = flow_config
        self.settings = settings
        
        # 使用传入的 LLMService 的 client（用于意图识别）
        self.client = llm_service.client
        self.intent_model = settings.get('llm', {}).get('intent_model', 'qwen-turbo')
        self.system_prompt_template = settings.get('llm', {}).get('system_prompt_template', '')
    
    def route(self, user_input: str, current_stage: str) -> str:
        """
        使用 LLM 进行意图识别
        :param user_input: 用户输入
        :param current_stage: 当前对话阶段（如"沟通开场"）
        :return: 意图标签（如"本人"、"号码易主"等）
        """
        # 获取当前阶段的配置
        stage_config = self.flow_config.get(current_stage)
        if not stage_config:
            logger.warning(f"未找到阶段配置: {current_stage}")
            return "其他"
        
        # 获取有效意图列表和定义
        valid_intents = stage_config.get('valid_intents', [])
        intent_definitions = stage_config.get('intent_definitions', {})
        
        if not valid_intents:
            logger.warning(f"阶段 {current_stage} 没有定义有效意图")
            return "其他"
        
        # 构建意图定义文本
        definitions_text = "\n".join([
            f"- {intent}: {definition}"
            for intent, definition in intent_definitions.items()
        ])
        
        # 构建 prompt
        prompt = self.system_prompt_template.format(
            stage=current_stage,
            valid_intents=", ".join(valid_intents),
            definitions=definitions_text,
            user_input=user_input
        )
        
        try:
            # 调用 LLM 进行意图识别
            response = self.client.chat.completions.create(
                model=self.intent_model,
                messages=[
                    {'role': 'system', 'content': prompt},
                    {'role': 'user', 'content': f'用户话术：{user_input}'}
                ],
                temperature=self.settings.get('app', {}).get('temperature', 0.1),
                max_tokens=50  # 意图识别只需要短输出
            )
            
            intent = response.choices[0].message.content.strip()
            
            # 清理输出：移除可能的标点符号和多余内容
            intent = intent.replace('"', '').replace("'", '').strip()
            
            # 验证意图是否在有效列表中
            if intent in valid_intents:
                logger.info(f"✅ 意图识别成功: {intent} (用户输入: {user_input})")
                return intent
            else:
                logger.warning(f"⚠️ 识别到的意图不在有效列表中: {intent}, 有效列表: {valid_intents}")
                # 尝试模糊匹配
                for valid_intent in valid_intents:
                    if valid_intent in intent or intent in valid_intent:
                        logger.info(f"✅ 模糊匹配成功: {valid_intent}")
                        return valid_intent
                # 如果都不匹配，返回"其他"
                logger.warning(f"❌ 无法匹配意图，返回'其他'")
                return "其他"
                
        except Exception as e:
            logger.error(f"❌ 意图识别失败: {e}")
            return "其他"
