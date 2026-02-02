# encoding : utf-8 -*-                            
# @author  : 冬瓜                              
# @mail    : dylan_han@126.com    
# @Time    : 2026/2/2 15:19
import os
import json
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler

# === 1. 基础配置 ===
API_KEY = "sk-cdaa3135a6294568958aa335cad6b7fe"
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# 获取 mappings.txt 的路径
ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
MAPPINGS_FILE = os.path.join(ASSETS_DIR, "mappings.txt")
DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs")


class GenerateLLMResponse:
    def __init__(self):
        # 初始化大模型，开启 streaming=True
        self.llm = ChatOpenAI(
            openai_api_key=API_KEY,
            openai_api_base=BASE_URL,
            model_name="qwen-plus",
            streaming=True,
            callbacks=[StreamingStdOutCallbackHandler()],
            temperature=0.8
        )
        
        # 非流式 LLM 用于槽位提取等任务
        self.llm_sync = ChatOpenAI(
            openai_api_key=API_KEY,
            openai_api_base=BASE_URL,
            model_name="qwen-turbo",
            streaming=False,
            temperature=0.1  # 低温度保证稳定输出
        )

        self.system_prompt = SystemMessage(content=(
            "你的名字叫'蕉绿蛙'，身份是用户的专属'AI 数字人秘书'。"
            "你的核心口头禅是'不要焦虑哇'，旨在化解办公压力。"
            "职责范围：你精通 Python 自动化，能帮用户控制 PPT（播放、翻页）、代发微信消息、查找本地文件。"
            "性格画像：专业、幽默、治愈系。回复要简练高效，带有数字人的亲和力。"
        ))
        self.chat_history = [self.system_prompt]
        
        # 加载联系人映射表
        self.contact_mappings = self._load_contact_mappings()

    def _load_contact_mappings(self) -> dict:
        """加载联系人映射表（ASR错别字 -> 正确姓名）"""
        mappings = {}
        if not os.path.exists(MAPPINGS_FILE):
            print(f"⚠️ 映射文件不存在: {MAPPINGS_FILE}")
            return mappings
        
        try:
            with open(MAPPINGS_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # 跳过空行和注释
                    if not line or line.startswith('#'):
                        continue
                    parts = line.split(',')
                    if len(parts) >= 2:
                        asr_text = parts[0].strip()
                        correct_name = parts[1].strip()
                        mappings[asr_text] = correct_name
            print(f"✅ 已加载 {len(mappings)} 条联系人映射")
        except Exception as e:
            print(f"❌ 加载映射文件失败: {e}")
        
        return mappings

    def map_contact_name(self, asr_name: str) -> str:
        """将 ASR 识别的联系人名映射到正确的姓名"""
        # 直接匹配
        if asr_name in self.contact_mappings:
            return self.contact_mappings[asr_name]
        
        # 模糊匹配（包含关系）
        for asr_text, correct_name in self.contact_mappings.items():
            if asr_text in asr_name or asr_name in asr_text:
                return correct_name
        
        # 没有匹配到，返回原始值
        return asr_name

    async def ask(self, query: str):
        """流式提问方法（闲聊）"""
        print(f"\n🐸 蕉绿蛙: ", end="")
        self.chat_history.append(HumanMessage(content=query))

        full_response = ""
        try:
            for chunk in self.llm.stream(self.chat_history):
                content = chunk.content
                full_response += content

            self.chat_history.append(full_response)
        except Exception as e:
            print(f"\n❌ [异常]: {e}")

    def ask_sync(self, query: str) -> str:
        """同步提问方法（闲聊），返回完整回复"""
        self.chat_history.append(HumanMessage(content=query))
        
        try:
            response = self.llm_sync.invoke(self.chat_history)
            full_response = response.content
            self.chat_history.append(full_response)
            return full_response
        except Exception as e:
            print(f"\n❌ [异常]: {e}")
            return "抱歉，我暂时无法回答，请稍后再试。"

    def extract_wechat_slots(self, user_input: str) -> tuple:
        """
        从自然语言中提取微信发送所需的槽位
        返回: (contact_name, message_content)
        """
        extraction_prompt = (
            "你是一个精确的指令解析器。请从用户的输入中提取\"联系人姓名\"和\"消息内容\"。\n"
            "输出格式要求（仅输出 JSON）:\n"
            '{ "contact_name": "提取的人名或备注", "message_content": "提取的具体消息" }\n\n'
            "约束条件：\n"
            "1、如果用户没提到联系人，contact_name 返回 \"None\"。\n"
            "2、如果消息内容包含\"不要焦虑哇\"，请务必完整保留。\n"
            "3、消息内容应该是用户想发送的实际内容，不是整句话。\n"
            "4、不要输出任何多余的解释，只返回 JSON 字符串。\n\n"
            "示例：\n"
            "输入：给冬瓜发个微信说方案过了不要焦虑哇\n"
            '输出：{"contact_name": "冬瓜", "message_content": "方案过了不要焦虑哇"}'
        )

        messages = [
            SystemMessage(content=extraction_prompt),
            HumanMessage(content=user_input)
        ]

        try:
            response = self.llm_sync.invoke(messages)
            content = response.content.strip()
            
            # 尝试提取 JSON（处理可能的 markdown 代码块）
            if "```" in content:
                import re
                json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', content, re.DOTALL)
                if json_match:
                    content = json_match.group(1)
            
            data = json.loads(content)
            contact_name = data.get("contact_name", "None")
            message_content = data.get("message_content", "")
            
            # 映射联系人姓名（处理 ASR 错别字）
            if contact_name and contact_name != "None":
                contact_name = self.map_contact_name(contact_name)
            
            print(f"📝 [槽位提取] 联系人: {contact_name}, 消息: {message_content}")
            return contact_name, message_content
            
        except Exception as e:
            print(f"❌ 解析微信槽位失败: {e}")
            return None, None

    def extract_file_keyword(self, user_input: str, file_type: str = "文件") -> str:
        """
        从自然语言中提取文件/PPT 的关键词
        :param user_input: 用户输入
        :param file_type: 文件类型描述（"文件"或"PPT"）
        :return: 提取的关键词
        """
        extraction_prompt = f"""你是一个精确的指令解析器。请从用户输入中提取要查找的{file_type}名称或关键词。

输出格式要求（仅输出 JSON）:
{{ "keyword": "提取的关键词" }}

约束条件：
1、关键词应该是{file_type}的名称、主题或关键特征词。
2、如果用户提到了具体的{file_type}名，直接提取名称。
3、如果用户描述的是{file_type}内容，提取最核心的关键词。
4、不要输出任何多余的解释，只返回 JSON 字符串。

示例：
输入：打开知识库的PPT
输出：{{"keyword": "知识库"}}

输入：找一下关于财务报表的文档
输出：{{"keyword": "财务报表"}}

输入：播放智能催记的演示文稿
输出：{{"keyword": "智能催记"}}"""

        messages = [
            SystemMessage(content=extraction_prompt),
            HumanMessage(content=user_input)
        ]

        try:
            response = self.llm_sync.invoke(messages)
            content = response.content.strip()
            
            # 尝试提取 JSON
            if "```" in content:
                import re
                json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', content, re.DOTALL)
                if json_match:
                    content = json_match.group(1)
            
            data = json.loads(content)
            keyword = data.get("keyword", "")
            
            print(f"📝 [关键词提取] {file_type}关键词: {keyword}")
            return keyword
            
        except Exception as e:
            print(f"❌ 提取{file_type}关键词失败: {e}")
            return ""

    def search_file_by_relevance(self, keyword: str, file_extensions: tuple = None) -> tuple:
        """
        根据关键词搜索最相关的文件
        :param keyword: 搜索关键词
        :param file_extensions: 文件扩展名元组，如 ('.pptx', '.ppt')
        :return: (文件完整路径, 文件名) 或 (None, None)
        """
        if not keyword:
            return None, None
        
        if file_extensions is None:
            file_extensions = ('.docx', '.pptx', '.pdf', '.xlsx', '.txt', '.ppt', '.doc', '.xls')
        
        if not os.path.exists(DOCS_DIR):
            print(f"⚠️ 文档目录不存在: {DOCS_DIR}")
            return None, None
        
        # 收集所有符合扩展名的文件
        candidates = []
        for root, _, files in os.walk(DOCS_DIR):
            for f in files:
                if f.lower().endswith(file_extensions):
                    full_path = os.path.join(root, f)
                    # 计算相关性分数
                    score = self._calculate_relevance(keyword, f)
                    if score > 0:
                        candidates.append((full_path, f, score))
        
        if not candidates:
            print(f"⚠️ 未找到包含 '{keyword}' 的文件")
            return None, None
        
        # 按相关性分数排序，返回最相关的
        candidates.sort(key=lambda x: x[2], reverse=True)
        best_match = candidates[0]
        
        print(f"✅ 找到最相关文件: {best_match[1]} (相关性: {best_match[2]})")
        return best_match[0], best_match[1]

    def _calculate_relevance(self, keyword: str, filename: str) -> int:
        """
        计算关键词与文件名的相关性分数
        :param keyword: 搜索关键词
        :param filename: 文件名
        :return: 相关性分数（越高越相关）
        """
        keyword_lower = keyword.lower()
        filename_lower = filename.lower()
        
        score = 0
        
        # 完全匹配（不含扩展名）
        name_without_ext = os.path.splitext(filename_lower)[0]
        if keyword_lower == name_without_ext:
            score += 100
        
        # 包含关键词
        if keyword_lower in filename_lower:
            score += 50
            # 关键词在文件名开头加分
            if filename_lower.startswith(keyword_lower):
                score += 20
        
        # 关键词的每个字符匹配
        for char in keyword_lower:
            if char in filename_lower:
                score += 1
        
        return score

    def search_ppt_by_relevance(self, keyword: str) -> tuple:
        """
        专门搜索 PPT 文件
        :param keyword: 搜索关键词
        :return: (文件完整路径, 文件名) 或 (None, None)
        """
        return self.search_file_by_relevance(keyword, file_extensions=('.pptx', '.ppt'))


# === 3. 运行测试 ===
if __name__ == "__main__":
    import asyncio

    async def main():
        bot = GenerateLLMResponse()
        print("🟢 蕉绿蛙已上线！(输入 'exit' 退出)")
        
        # 测试槽位提取
        print("\n=== 测试微信槽位提取 ===")
        test_inputs = [
            "给冬瓜发个微信说方案过了不要焦虑哇",
            "微信通知老板晚上聚餐",
            "告诉定奥东明天的会议取消了"
        ]
        for inp in test_inputs:
            print(f"\n输入: {inp}")
            contact, msg = bot.extract_wechat_slots(inp)
            print(f"结果: 联系人={contact}, 消息={msg}")
        
        # 测试关键词提取
        print("\n=== 测试关键词提取 ===")
        test_inputs = [
            "打开知识库的PPT",
            "找一下财务报表",
            "播放智能催记的演示文稿"
        ]
        for inp in test_inputs:
            print(f"\n输入: {inp}")
            keyword = bot.extract_file_keyword(inp, "PPT")
            print(f"关键词: {keyword}")
            
            # 测试文件搜索
            path, name = bot.search_ppt_by_relevance(keyword)
            print(f"找到文件: {name}")

    asyncio.run(main())
