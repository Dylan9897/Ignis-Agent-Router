# encoding : utf-8 -*-                            
# @author  : 冬瓜                              
# @mail    : dylan_han@126.com    
# @Time    : 2026/1/4 11:08
import os
import json
import logging
from datetime import datetime
from openai import OpenAI

logger = logging.getLogger("BotLogger")

class LLMService:
    def __init__(self, config):
        self.client = OpenAI(
            api_key=os.getenv("ALI_API_KEY"),
            base_url=os.getenv("ALI_BASE_URL")
        )
        # self.intent_model = config['llm'].get('intent_model', 'qwen-turbo')
        self.default_model = config['llm'].get('generation_model', 'qwen-plus')

    def generate_response(self, system_instruction,**kwargs):
        """
        流式生成催收话术：逐 token 返回，供实时消费。
        调用方应迭代此函数返回值以获取流式输出。

        Args:
            system_instruction: 用户指令（含槽位填充后的完整上下文）

        Yields:
            str: 每次生成的一个 token（或空字符串，需过滤）
        """
        try:
            model_choice = kwargs.get("model_choice",None)
            if not model_choice:
                model_choice = self.default_model
            logger.info(f"Using Generation Model: {model_choice}")
            stream = self.client.chat.completions.create(
                model=model_choice,
                messages=[
                    {
                        'role': 'system',
                        'content': (
                            "你是一名专业、合规的金融催收专员。"
                            "请根据客户情况生成温和但明确的催收话术，"
                            "语气尊重，不威胁、不夸大，每句话不超过60字。"
                            "不要加引号、不要解释，直接输出话术。"
                        )
                    },
                    {'role': 'user', 'content': system_instruction}
                ],
                stream=True,
                temperature=kwargs.get("temperature",0.5)  # 催收建议更低温度，保证稳定
            )

            for chunk in stream:
                delta = chunk.choices[0].delta
                if hasattr(delta, 'content') and delta.content is not None:
                    token = delta.content
                    yield token  # 👈 关键：逐 token 流式产出

        except Exception as e:
            logger.error(f"Streaming Generation Error: {e}")
            yield "[系统错误，请稍后重试]"