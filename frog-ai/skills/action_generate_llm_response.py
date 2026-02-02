# encoding : utf-8 -*-                            
# @author  : 冬瓜                              
# @mail    : dylan_han@126.com    
# @Time    : 2026/2/2 15:19
import sys
import json
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler

# === 1. 基础配置 ===
API_KEY = "sk-cdaa3135a6294568958aa335cad6b7fe"
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"


class GenerateLLMResponse:
    def __init__(self):
        # 初始化大模型，开启 streaming=True
        # StreamingStdOutCallbackHandler 会让 Token 实时打印在控制台
        self.llm = ChatOpenAI(
            openai_api_key=API_KEY,
            openai_api_base=BASE_URL,
            model_name="qwen-plus",
            streaming=True,
            callbacks=[StreamingStdOutCallbackHandler()],
            temperature=0.8
        )

        self.system_prompt = SystemMessage(content=(
            "你的名字叫‘蕉绿蛙’，身份是用户的专属‘AI 数字人秘书’。"
            "你的核心口头禅是‘不要焦虑哇’，旨在化解办公压力。"
            "职责范围：你精通 Python 自动化，能帮用户控制 PPT（播放、翻页）、代发微信消息、查找本地文件。"
            "性格画像：专业、幽默、治愈系。回复要简练高效，带有数字人的亲和力。"
        ))
        self.chat_history = [self.system_prompt]

    async def ask(self, query: str):
        """流式提问方法"""
        print(f"\n🐸 蕉绿蛙: ", end="")
        self.chat_history.append(HumanMessage(content=query))

        # 调用 astream 进行异步流式获取
        full_response = ""
        try:
            # 在 LangChain 中，直接调用 stream 方法
            for chunk in self.llm.stream(self.chat_history):
                # chunk 是 BaseMessageChunk 对象
                content = chunk.content
                full_response += content
                # 这里不需要手动 print，因为 callbacks 已经处理了 stdout

            # 将回复存入历史，维持上下文
            self.chat_history.append(full_response)
        except Exception as e:
            print(f"\n❌ [异常]: {e}")

    # ============ 这是新增的函数 ============
    def invoke_command(self, instruction: str):
        """[非流式] 用于执行具体指令，一次性返回结果"""
        print(f"\n🌀 蕉绿蛙正在处理任务清单...")

        # 指令通常不需要太长的上下文，可以创建一个临时的消息列表
        messages = [
            self.system_prompt,
            HumanMessage(content=f"请执行以下指令：{instruction}")
        ]

        try:
            # 使用 invoke 代替 stream
            response = self.llm.invoke(messages)
            # 这里的 response 是一个完整的 AIMessage 对象
            return response.content
        except Exception as e:
            return f"❌ 任务处理失败: {e}"

    def extract_wechat_demo(self, user_input: str):
        """
        专门用于从自然语言中提取微信发送所需的元数据
        """
        extraction_prompt = (
            "你是一个指令解析器。请从用户输入中提取微信联系人姓名和消息内容。"
            "必须以 JSON 格式输出，例如：{\"contact_name\": \"张三\", \"message_content\": \"你好\"}。"
        )

        messages = [
            SystemMessage(content=extraction_prompt),
            HumanMessage(content=user_input)
        ]

        # 使用非流式调用获取结果
        response = self.llm.invoke(messages)

        try:
            # 解析 JSON 结果
            data = json.loads(response.content)
            return data["contact_name"], data["message_content"]
        except Exception as e:
            print(f"解析指令失败: {e}")
            return None, None

# === 3. 运行测试 ===
if __name__ == "__main__":
    import asyncio

    async def main():
        bot = GenerateLLMResponse()
        print("🟢 蕉绿蛙已上线！(输入 'exit' 退出)")

        while True:
            user_input = input("\n👤 你: ")
            if user_input.lower() in ['exit', 'quit', '退出']:
                break

            await bot.ask(user_input)
            print()  # 换行

    asyncio.run(main())