# encoding : utf-8 -*-                            
# @author  : 冬瓜                              
# @mail    : dylan_han@126.com    
# @Time    : 2026/2/2 14:47

import pyautogui
import pyperclip

from typing import Text
from rasa_sdk import Action
from rasa_sdk.events import SlotSet
import time

import win32gui
import win32con

class ActionSendWechat(Action):
    def name(self) -> Text:
        return "action_send_wechat"

    def run(self, dispatcher, tracker, domain):
        who = tracker.get_slot("contact_name")
        msg = tracker.get_slot("message_content")

        # 1. 尝试唤起微信
        pyautogui.hotkey('ctrl', 'alt', 'w')
        time.sleep(1.2)  # 增加等待，适配浏览器环境下的窗口响应

        # 2. 核心补丁：检查当前活跃窗口是不是微信
        # 如果不是，手动强制切换一次（这是正规系统调用，非黑魔法）
        hwnd = win32gui.FindWindow(None, '微信')
        print(hwnd)
        if hwnd:
            if win32gui.GetForegroundWindow() != hwnd:
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(hwnd)
                time.sleep(0.5)
        else:
            print("错误：未找到微信运行实例")
            return [SlotSet("action_status", "failed")]

        # 3. 后续逻辑保持不变，但增加少量延迟以提高稳定性
        pyautogui.hotkey('ctrl', 'f')
        time.sleep(0.5)

        pyperclip.copy(who)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(1.5)  # 给微信搜索列表留出加载时间

        pyautogui.press('enter')
        time.sleep(0.8)

        pyperclip.copy(msg)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.5)
        pyautogui.press('enter')

        # === 新增功能：最小化微信 ===
        time.sleep(0.5)  # 等待发送动作完成
        if hwnd:
            # 使用 SW_MINIMIZE 状态位来最小化窗口
            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
            print("微信已最小化")
        # ==========================

        return [SlotSet("action_status", "success")]


if __name__ == "__main__":
    # 1. 模拟 Rasa 的 Tracker 类，用于提供 Slot 数据
    class MockTracker:
        def __init__(self, slots):
            self.slots = slots

        def get_slot(self, key):
            return self.slots.get(key)


    # 2. 模拟 Rasa 的 Dispatcher 类，用于接收输出消息
    class MockDispatcher:
        def utter_message(self, text=None, **kwargs):
            print(f"【机器人回复】: {text}")


    # 3. 设置测试数据
    # 注意：请确保你的微信通讯录里确实有这个“联系人备注”或“昵称”
    test_slots = {
        "contact_name": "冬瓜",  # 建议先用文件传输助手测试，最安全
        "message_content": "这是一条来自 Rasa Action 的自动化测试消息！"
    }

    # 4. 实例化并运行
    print("🚀 准备测试 ActionSendWechat...")
    print("📢 提示：请确保微信已登录，且脚本运行期间不要移动鼠标或操作键盘。")

    action = ActionSendWechat()
    mock_tracker = MockTracker(test_slots)
    mock_dispatcher = MockDispatcher()

    try:
        # 执行 run 方法
        events = action.run(mock_dispatcher, mock_tracker, {})
        print(f"\n✅ 测试执行完毕！")
        print(f"返回事件: {events}")
    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {e}")