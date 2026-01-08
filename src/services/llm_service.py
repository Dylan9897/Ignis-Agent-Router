# encoding : utf-8 -*-                            
# @author  : 冬瓜                              
# @mail    : dylan_han@126.com    
# @Time    : 2026/1/4 11:08
import os
import json
import logging
from datetime import datetime
from openai import OpenAI
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage


logger = logging.getLogger("BotLogger")

class LLMService:
    def __init__(self, config):
        # 初始化 LangChain 的 Chat 模型
        # 继续使用 settings.yaml 中的配置
        self.llm = ChatOpenAI(
            model=config['llm'].get('generation_model', 'qwen-plus'),
            api_key=os.getenv("ALI_API_KEY"),
            base_url=os.getenv("ALI_BASE_URL"),
            temperature=config['app'].get('temperature', 0.1),
            streaming=True,  # 开启流式支持
            max_tokens=50    # 意图识别只需要输出几个字
        )
        
        # 也可以单独初始化一个 intent_llm，如果需要不同配置
        self.intent_llm = ChatOpenAI(
            model=config['llm'].get('intent_model', 'qwen-turbo'),
            api_key=os.getenv("ALI_API_KEY"),
            base_url=os.getenv("ALI_BASE_URL"),
            temperature=0.0  # 意图识别温度设为0
        )

    def get_llm(self):
        """
        返回用于生成的通用 LLM 对象
        给 AgentEngine 生成话术用
        """
        return self.llm

    def get_intent_llm(self):
        """
        返回用于意图识别的快速 LLM 对象
        给 IntentRouter 用
        """
        return self.intent_llm

    