import os
import time
import pyautogui
import pygetwindow as gw
from rasa_sdk import Action
from rasa_sdk.events import SlotSet


class ActionControlPPT(Action):
    def name(self) -> str:
        return "action_control_ppt"

    def run(self, dispatcher, tracker, domain):
        DOCS_DIR = os.path.join(os.getcwd(), "docs")
        cmd_raw = (tracker.get_slot("ppt_command") or "").lower()
        keyword = tracker.get_slot("file_keyword")

        # 1. 文件检索
        target_file = None
        target_filename = ""
        if os.path.exists(DOCS_DIR):
            files = [f for f in os.listdir(DOCS_DIR) if f.lower().endswith(('.pptx', '.ppt'))]
            for f in files:
                if keyword.lower() in f.lower():
                    target_file = os.path.join(DOCS_DIR, f)
                    target_filename = f
                    break

        # 2. 窗口检查
        existing_wins = [w for w in gw.getAllWindows() if keyword.lower() in w.title.lower() or "WPS 演示" in w.title]

        if not target_file and not existing_wins:
            dispatcher.utter_message(text=f"❌ 找不到包含“{keyword}”的演示文件。")
            return [SlotSet("action_status", "failure")]

        # 3. 打开/激活逻辑
        try:
            if not existing_wins and target_file:
                os.startfile(target_file)
                time.sleep(5.0)  # 等待加载

            active_wins = [w for w in gw.getAllWindows() if keyword.lower() in w.title.lower() or "WPS 演示" in w.title]
            if active_wins:
                win = active_wins[0]
                if win.isMinimized: win.restore()
                win.activate()
                time.sleep(0.5)
        except Exception as e:
            print(f"窗口调度异常: {e}")

        # 4. 精细化指令执行与反馈
        # 定义播放类关键词
        play_keywords = ["播放", "全屏", "放映", "开始", "启动"]
        # 定义翻页类关键词
        nav_mapping = {"right": ["下一页", "后", "下页"], "left": ["上一页", "前", "上页"], "esc": ["退出", "结束"]}

        # 逻辑判断：是播放还是普通打开
        is_play = any(word in cmd_raw for word in play_keywords)

        if is_play:
            pyautogui.press('f5')
            dispatcher.utter_message(text=f"✨ 已为您打开并全屏播放“{target_filename or keyword}”")
        else:
            # 检查是否是翻页指令
            found_nav = next((k for k, v in nav_mapping.items() if any(syn in cmd_raw for syn in v)), None)
            if found_nav:
                pyautogui.press(found_nav)
                dispatcher.utter_message(text=f"✅ 已执行：{cmd_raw}")
            else:
                # 既不是播放也不是翻页，仅仅是“打开”
                dispatcher.utter_message(text=f"✨ 已打开“{target_filename or keyword}”演示文件。")

        return [SlotSet("action_status", "success")]


if __name__ == "__main__":
    class MockTracker:
        def __init__(self, slots):
            self.slots = slots

        def get_slot(self, key):
            return self.slots.get(key)


    class MockDispatcher:
        def utter_message(self, text=None, **kwargs):
            print(f"🤖 [机器人回复]: {text}")


    # 环境准备
    DOCS_DIR = os.path.join(os.getcwd(), "docs")
    if not os.path.exists(DOCS_DIR):
        os.makedirs(DOCS_DIR)

    # 创建一个模拟文件
    test_file = os.path.join(DOCS_DIR, "知识库.pptx")
    if not os.path.exists(test_file):
        with open(test_file, "w") as f: f.write("mock")

    action = ActionControlPPT()

    # 测试用例定义
    test_cases = [
        {
            "desc": "测试场景 1：仅要求打开（不应显示播放）",
            "slots": {"ppt_command": "上一页", "file_keyword": "知识库"}
        },
        # {
        #     "desc": "测试场景 2：要求全屏播放",
        #     "slots": {"ppt_command": "帮我全屏播放", "file_keyword": "知识库"}
        # },
        # {
        #     "desc": "测试场景 3：文件不存在的情况",
        #     "slots": {"ppt_command": "打开", "file_keyword": "秘密文件"}
        # }
    ]

    print("🚀 开始功能测试...\n")
    for case in test_cases:
        print(f"📋 {case['desc']}")
        tracker = MockTracker(case['slots'])
        dispatcher = MockDispatcher()
        action.run(dispatcher, tracker, {})
        print("-" * 50)
        time.sleep(1)

    print("\n✅ 测试完成。")