# encoding : utf-8 -*-                            
# @author  : 冬瓜                              
# @mail    : dylan_han@126.com    
# @Time    : 2026/2/2 15:13
import os

from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

# === 你的配置区 ===
# 文档搜索路径
SEARCH_PATH = os.path.expanduser("./docs")
class ActionSearchOpenFile(Action):
    def name(self) -> Text:
        return "action_search_open_file"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        keyword = tracker.get_slot("file_keyword")
        dispatcher.utter_message(text=f"🔍 正在为您检索包含 '{keyword}' 的文档...")

        target = None
        # 只搜索常见的办公文档后缀
        valid_exts = ('.docx', '.pptx', '.pdf', '.xlsx', '.txt')

        for root, _, files in os.walk(SEARCH_PATH):
            for f in files:
                if keyword.lower() in f.lower() and f.endswith(valid_exts):
                    target = os.path.join(root, f)
                    break
            if target: break

        if target:
            os.startfile(target)
            dispatcher.utter_message(text=f"📁 已找到并为您打开：{os.path.basename(target)}")
        else:
            dispatcher.utter_message(text="❌ 抱歉，在文档目录下没找到相关文件。")

        return []


if __name__ == "__main__":
    import time


    # --- 1. 模拟 Rasa 环境的 Mock 类 ---
    class MockTracker:
        def __init__(self, slots):
            self.slots = slots

        def get_slot(self, key):
            return self.slots.get(key)


    class MockDispatcher:
        def utter_message(self, text=None, **kwargs):
            print(f"🤖 [机器人回复]: {text}")


    # --- 2. 自动化测试准备工作 ---
    # 确保测试目录存在
    TEST_DIR = os.path.join(os.getcwd(), "docs")
    if not os.path.exists(TEST_DIR):
        os.makedirs(TEST_DIR)
        print(f"📁 已创建测试目录: {TEST_DIR}")

    # 创建一个用于测试的虚拟文件
    test_filename = "2026年度财务报表_测试用.docx"
    test_file_path = os.path.join(TEST_DIR, test_filename)
    if not os.path.exists(test_file_path):
        with open(test_file_path, "w", encoding="utf-8") as f:
            f.write("这是一个用于 Rasa Action 测试的虚拟文档。")
        print(f"📄 已生成测试文件: {test_filename}")

    # --- 3. 执行测试用例 ---
    action = ActionSearchOpenFile()

    test_cases = [
        {
            "desc": "成功路径：搜索存在的关键词",
            "slots": {"file_keyword": "测试报告"}
        },
        {
            "desc": "失败路径：搜索不存在的关键词",
            "slots": {"file_keyword": "秘密计划"}
        }
    ]

    print("\n" + "=" * 30)
    print("🚀 开始 Action 功能测试")
    print("=" * 30)

    for case in test_cases:
        print(f"\n📋 测试场景: {case['desc']}")
        tracker = MockTracker(case['slots'])
        dispatcher = MockDispatcher()

        try:
            # 运行 Action 的逻辑
            action.run(dispatcher, tracker, {})
        except Exception as e:
            print(f"❌ 运行过程中出现错误: {e}")

        time.sleep(1)

    print("\n" + "=" * 30)
    print("✨ 测试流程结束")