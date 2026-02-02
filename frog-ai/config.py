# encoding : utf-8 -*-                            
# @author  : 冬瓜                              
# @mail    : dylan_han@126.com    
# @Time    : 2026/2/2 15:42

# 🔴 请替换为你的阿里云 API KEY
DASHSCOPE_API_KEY = "sk-cdaa3135a6294568958aa335cad6b7fe"

# 资源配置
IMAGE_NAME = "frog_avatar.png"

# 音频参数
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SIZE = 3200

# 模型配置
MODEL_ASR = 'paraformer-realtime-v1'
MODEL_LLM = 'qwen-turbo'
MODEL_TTS = 'sambert-zhimao-v1'  # 知猫 - 娇俏可爱女声 💕

# Rasa 网关配置
RASA_GATEWAY_URL = "http://localhost:8000/intent_slots"
RASA_SENDER_ID = "desktop_frog_user"

wechat_message_prompt = """
你是一个精确的指令解析器。请从用户的输入中提取“联系人姓名”和“消息内容”。
输出格式要求（仅输出 JSON）: 
    { "contact_name": "提取的人名或备注", "message_content": "提取的具体消息" }

约束条件：
1、如果用户没提到联系人，contact_name 返回 "None"。
2、如果消息内容包含“不要焦虑哇”，请务必完整保留。
3、不要输出任何多余的解释，只返回 JSON 字符串。

示例： 
输入：给冬瓜发个微信说方案过了不要焦虑哇 
输出：{"contact_name": "冬瓜", "message_content": "方案过了不要焦虑哇"}
"""

