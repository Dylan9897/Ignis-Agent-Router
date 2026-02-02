# encoding : utf-8 -*-                            
# @author  : 冬瓜                              
# @mail    : dylan_han@126.com    
# @Time    : 2026/1/20 17:00
# core/worker.py
import os
import threading
import traceback
import pyaudio
import dashscope
import requests
from http import HTTPStatus
from PyQt6.QtCore import pyqtSignal, QThread

from config import (
    DASHSCOPE_API_KEY, SAMPLE_RATE, CHANNELS, CHUNK_SIZE, 
    MODEL_ASR, MODEL_LLM, MODEL_TTS
)
from core.audio import AudioPlayer
from core.callbacks import ConversationCallback
from dashscope.audio.asr import Recognition
from dashscope.audio.tts import SpeechSynthesizer

# 导入技能模块
from skills.action_generate_llm_response import GenerateLLMResponse
from skills.server import get_intent

# 设置 API KEY
dashscope.api_key = DASHSCOPE_API_KEY

# Rasa NLU 服务配置
RASA_SESSION_ID = "frog_ai_session"


class ConversationWorker(QThread):
    # 定义信号：状态变更通知 UI
    sig_state = pyqtSignal(str)  # IDLE, LISTENING, SPEAKING

    def __init__(self):
        super().__init__()
        self.active = False
        self.pa = pyaudio.PyAudio()
        self.vad_event = threading.Event()
        self.user_input_buffer = ""
        self.interrupt_event = threading.Event()  # 打断事件
        self.current_state = "IDLE"  # 跟踪当前状态
        # 初始化 AudioPlayer，传入打断事件以便实时检查
        self.player = AudioPlayer(interrupt_event=self.interrupt_event)
        
        # 初始化 LLM 服务（用于槽位提取和闲聊）
        self.llm_service = GenerateLLMResponse()

    def stop(self):
        self.active = False
        self.quit()
        self.wait()

    def _listen_for_interrupt(self):
        """在SPEAKING状态时监听用户语音，检测打断"""
        try:
            from core.callbacks import InterruptCallback
            
            callback = InterruptCallback(self)
            mic_stream = None
            recognition = None

            # 启动 ASR 用于打断检测
            recognition = Recognition(
                model=MODEL_ASR,
                format='pcm',
                sample_rate=SAMPLE_RATE,
                callback=callback
            )
            recognition.start()

            # 打开麦克风
            mic_stream = self.pa.open(
                format=pyaudio.paInt16,
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                input=True,
                frames_per_buffer=CHUNK_SIZE
            )

            # 录音循环 - 持续监听直到SPEAKING状态结束或检测到打断
            while self.current_state == "SPEAKING" and not self.interrupt_event.is_set():
                data = mic_stream.read(CHUNK_SIZE, exception_on_overflow=False)
                recognition.send_audio_frame(data)

        except Exception as e:
            print(f"⚠️ [Interrupt] 打断监听出错: {e}")
        finally:
            if mic_stream:
                mic_stream.stop_stream()
                mic_stream.close()
            if recognition:
                try:
                    recognition.stop()
                except:
                    pass

    def run(self):
        if "sk-" not in DASHSCOPE_API_KEY:
            print("❌ 错误: 未设置 API KEY")
            return

        self.active = True
        print("[System] 核心线程启动")

        while self.active:
            # === 1. 聆听阶段 ===
            is_interrupted = self.interrupt_event.is_set()
            
            if not is_interrupted:
                self.current_state = "LISTENING"
                self.sig_state.emit("LISTENING")
                self.vad_event.clear()
                self.user_input_buffer = ""

                callback = ConversationCallback(self)
                mic_stream = None
                recognition = None

                try:
                    # 启动 ASR
                    recognition = Recognition(
                        model=MODEL_ASR,
                        format='pcm',
                        sample_rate=SAMPLE_RATE,
                        callback=callback
                    )
                    recognition.start()

                    # 打开麦克风
                    mic_stream = self.pa.open(
                        format=pyaudio.paInt16,
                        channels=CHANNELS,
                        rate=SAMPLE_RATE,
                        input=True,
                        frames_per_buffer=CHUNK_SIZE
                    )

                    # 录音循环
                    while self.active:
                        data = mic_stream.read(CHUNK_SIZE, exception_on_overflow=False)
                        recognition.send_audio_frame(data)
                        # 如果 VAD 检测到说话结束，跳出循环
                        if self.vad_event.is_set():
                            break
                except Exception as e:
                    print(f"❌ [Error] 录音阶段出错: {e}")
                    traceback.print_exc()
                finally:
                    if mic_stream:
                        mic_stream.stop_stream()
                        mic_stream.close()
                    if recognition:
                        try:
                            recognition.stop()
                        except:
                            pass

                # 如果停止了或没听到声音，重新循环
                if not self.active: break
                if not self.user_input_buffer: continue
            else:
                print("\n⚡ [System] 检测到打断，跳过监听，直接处理新输入")

            # === 2. 思考与回答阶段 ===
            self.current_state = "SPEAKING"
            self.sig_state.emit("SPEAKING")
            print(f"\n[User] {self.user_input_buffer}")

            # 清除打断标志，准备新一轮播报
            self.interrupt_event.clear()
            
            # 启动打断监听线程
            interrupt_thread = threading.Thread(target=self._listen_for_interrupt, daemon=True)
            interrupt_thread.start()

            user_query = self.user_input_buffer
            self.process_with_intent_routing(user_query)
            
            # 等待播放完成或被打断
            self.player.wait_until_done()
            
            # 检查是否被打断
            if self.interrupt_event.is_set():
                print("\n⚡ [System] 检测到打断，立即停止播报")
                self.player.stop()
            
            # 状态回到空闲
            self.current_state = "IDLE"

    def process_with_intent_routing(self, text):
        """
        核心流程：意图路由 + 分支处理
        1. 调用 Rasa-Pro 识别意图
        2. 根据意图类型分支处理
        """
        try:
            # === 步骤1: 调用 Rasa-Pro 获取意图 ===
            print(f"\n🔍 [Rasa] 正在识别意图: {text}")
            
            try:
                rasa_result = get_intent(RASA_SESSION_ID, text)
                print(f"[Rasa] 返回结果: {rasa_result}")
                
                intent_name = rasa_result.get("intent", {}).get("name", "")
                confidence = rasa_result.get("intent", {}).get("confidence", 0)
                print(f"[Rasa] 意图: {intent_name}, 置信度: {confidence:.2f}")
                
            except Exception as e:
                print(f"⚠️ [Rasa] 连接失败，降级到闲聊模式: {e}")
                intent_name = "chitchat"
                confidence = 0
            
            # === 步骤2: 根据意图分支处理 ===
            
            # 闲聊意图 - 直接调用大模型
            if intent_name == "chitchat" or confidence < 0.5:
                print(f"💬 [闲聊模式] 调用大模型对话")
                self._handle_chitchat(text)
                return
            
            # 发送微信消息意图
            if intent_name == "send_wechat_message":
                print(f"📱 [微信模式] 处理发送微信请求")
                self._handle_send_wechat(text)
                return
            
            # 控制PPT意图
            if intent_name == "control_ppt":
                print(f"📊 [PPT模式] 处理PPT控制请求")
                self._handle_control_ppt(text)
                return
            
            # 搜索文件意图
            if intent_name == "search_file":
                print(f"📁 [文件模式] 处理文件搜索请求")
                self._handle_search_file(text)
                return
            
            # 其他未识别意图，降级到闲聊
            print(f"❓ [未知意图] {intent_name}，降级到闲聊模式")
            self._handle_chitchat(text)
            
        except Exception as e:
            print(f"\n❌ [Error] 意图路由处理失败: {e}")
            traceback.print_exc()
            self._speak_text("抱歉，我遇到了一些问题，请稍后再试。")

    def _handle_chitchat(self, text):
        """处理闲聊意图 - 调用大模型流式回复"""
        self._call_llm_streaming(text)

    def _handle_send_wechat(self, text):
        """
        处理发送微信意图
        1. 调用大模型提取槽位（联系人、消息内容）
        2. 映射联系人姓名（处理ASR错别字）
        3. 执行微信发送
        4. 播报默认话术
        """
        # 1. 使用大模型提取槽位
        contact_name, message_content = self.llm_service.extract_wechat_slots(text)
        
        if not contact_name or contact_name == "None":
            self._speak_text("抱歉，我没听清要发给谁，请再说一遍。")
            return
        
        if not message_content:
            self._speak_text("抱歉，我没听清要发送什么内容，请再说一遍。")
            return
        
        # 2. 执行微信发送
        print(f"📱 [微信] 准备发送: 联系人={contact_name}, 消息={message_content}")
        
        try:
            from skills.action_send_wechat import ActionSendWechat
            
            # 创建 Mock 对象来执行 Action
            class MockTracker:
                def __init__(self, slots):
                    self.slots = slots
                def get_slot(self, key):
                    return self.slots.get(key)
            
            class MockDispatcher:
                def utter_message(self, text=None, **kwargs):
                    print(f"[微信Action] {text}")
            
            action = ActionSendWechat()
            tracker = MockTracker({
                "contact_name": contact_name,
                "message_content": message_content
            })
            dispatcher = MockDispatcher()
            
            events = action.run(dispatcher, tracker, {})
            
            # 检查执行结果
            action_status = "success"
            for event in events:
                if hasattr(event, 'key') and event.key == "action_status":
                    action_status = event.value
            
            # 3. 播报默认话术
            if action_status == "success":
                reply_text = f"好的，已经通知{contact_name}了。"
            else:
                reply_text = f"抱歉，发送给{contact_name}失败了，请检查微信是否已登录。"
            
        except Exception as e:
            print(f"❌ [微信] 执行失败: {e}")
            reply_text = "抱歉，发送微信时遇到了问题。"
        
        self._speak_text(reply_text)

    def _handle_control_ppt(self, text):
        """
        处理控制PPT意图
        1. 使用大模型提取关键词
        2. 按相关性匹配PPT文件
        3. 执行PPT操作
        4. 播报默认话术
        """
        # 1. 使用大模型提取关键词
        keyword = self.llm_service.extract_file_keyword(text, "PPT")
        
        if not keyword:
            self._speak_text("抱歉，我没听清要打开哪个PPT，请再说一遍。")
            return
        
        # 2. 按相关性搜索PPT文件
        file_path, file_name = self.llm_service.search_ppt_by_relevance(keyword)
        
        if not file_path:
            self._speak_text(f"抱歉，没有找到包含\"{keyword}\"的PPT文件。")
            return
        
        # 3. 判断是打开还是控制操作
        play_keywords = ["播放", "全屏", "放映", "开始", "启动"]
        nav_keywords = ["下一页", "上一页", "后", "前", "退出", "结束"]
        
        is_play = any(word in text for word in play_keywords)
        is_nav = any(word in text for word in nav_keywords)
        
        try:
            import pyautogui
            import pygetwindow as gw
            import time
            
            if not is_nav:
                # 打开或播放PPT
                # 检查是否已经打开
                existing_wins = [w for w in gw.getAllWindows() 
                               if keyword.lower() in w.title.lower() or "WPS 演示" in w.title]
                
                if not existing_wins:
                    os.startfile(file_path)
                    time.sleep(3.0)
                
                # 激活窗口
                active_wins = [w for w in gw.getAllWindows() 
                              if keyword.lower() in w.title.lower() or "WPS 演示" in w.title]
                if active_wins:
                    win = active_wins[0]
                    if win.isMinimized:
                        win.restore()
                    win.activate()
                    time.sleep(0.5)
                
                if is_play:
                    pyautogui.press('f5')
                    reply_text = f"已为您打开并播放{file_name}。"
                else:
                    reply_text = f"已为您打开{file_name}。"
            else:
                # 翻页或退出操作
                if "下" in text or "后" in text:
                    pyautogui.press('right')
                    reply_text = "好的，下一页。"
                elif "上" in text or "前" in text:
                    pyautogui.press('left')
                    reply_text = "好的，上一页。"
                elif "退出" in text or "结束" in text:
                    pyautogui.press('esc')
                    reply_text = "好的，已退出播放。"
                else:
                    reply_text = "好的。"
            
        except Exception as e:
            print(f"❌ [PPT] 执行失败: {e}")
            reply_text = "抱歉，控制PPT时遇到了问题。"
        
        self._speak_text(reply_text)

    def _handle_search_file(self, text):
        """
        处理搜索文件意图
        1. 使用大模型提取关键词
        2. 按相关性匹配文件
        3. 打开文件
        4. 播报默认话术
        """
        # 1. 使用大模型提取关键词
        keyword = self.llm_service.extract_file_keyword(text, "文件")
        
        if not keyword:
            self._speak_text("抱歉，我没听清要查找什么文件，请再说一遍。")
            return
        
        # 2. 按相关性搜索文件
        file_path, file_name = self.llm_service.search_file_by_relevance(keyword)
        
        if not file_path:
            self._speak_text(f"抱歉，没有找到包含\"{keyword}\"的文件。")
            return
        
        # 3. 打开文件
        try:
            os.startfile(file_path)
            reply_text = f"已为您打开{file_name}。"
        except Exception as e:
            print(f"❌ [文件] 打开失败: {e}")
            reply_text = f"抱歉，打开{file_name}时遇到了问题。"
        
        self._speak_text(reply_text)

    def _call_llm_streaming(self, text):
        """流式调用通义千问大模型（闲聊模式）"""
        responses = dashscope.Generation.call(
            model=MODEL_LLM,
            prompt=text,
            stream=True,
            result_format='message'
        )

        buffer_text = ""
        full_text = ""
        punctuations = {',', '，', '.', '。', '?', '？', '!', '！', ';', '；'}

        for response in responses:
            # 检查是否被打断
            if self.interrupt_event.is_set():
                print("\n⚡ [LLM] 检测到打断，停止生成")
                break
            if not self.active: break
            
            if response.status_code == HTTPStatus.OK:
                content = response.output.choices[0]['message']['content']
                delta = content[len(full_text):]
                full_text = content
                if not delta: continue

                print(delta, end="", flush=True)

                buffer_text += delta
                for char in delta:
                    if char in punctuations:
                        if not self.interrupt_event.is_set():
                            self.synthesize_and_play(buffer_text)
                        buffer_text = ""
                        break

        # 处理剩余的文本
        if buffer_text and self.active and not self.interrupt_event.is_set():
            self.synthesize_and_play(buffer_text)
        print()
    
    def _speak_text(self, text):
        """将文本按标点符号分段，送去 TTS 播放"""
        print(f"[AI] {text}")
        punctuations = {',', '，', '.', '。', '?', '？', '!', '！', ';', '；'}
        buffer_text = ""
        
        for char in text:
            buffer_text += char
            if char in punctuations:
                if buffer_text.strip() and not self.interrupt_event.is_set():
                    self.synthesize_and_play(buffer_text)
                buffer_text = ""
        
        # 处理剩余的文本
        if buffer_text.strip() and self.active and not self.interrupt_event.is_set():
            self.synthesize_and_play(buffer_text)

    def synthesize_and_play(self, text):
        if not text.strip(): 
            return
        try:
            result = SpeechSynthesizer.call(
                model=MODEL_TTS,
                text=text,
                sample_rate=SAMPLE_RATE
            )
            if result.get_audio_data():
                audio_data = result.get_audio_data()
                self.player.play(audio_data)
        except Exception as e:
            print(f"❌ [TTS Error] {e}")
            traceback.print_exc()
