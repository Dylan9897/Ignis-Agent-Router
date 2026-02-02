# encoding : utf-8 -*-                            
# @author  : 冬瓜                              
# @mail    : dylan_han@126.com    
# @Time    : 2026/1/20 17:00
# core/worker.py
import threading
import traceback
import pyaudio
import dashscope
import requests
from http import HTTPStatus
from PyQt6.QtCore import pyqtSignal, QThread

from config import (
    DASHSCOPE_API_KEY, SAMPLE_RATE, CHANNELS, CHUNK_SIZE, 
    MODEL_ASR, MODEL_LLM, MODEL_TTS, RASA_GATEWAY_URL, RASA_SENDER_ID
)
from core.audio import AudioPlayer
from core.callbacks import ConversationCallback
from dashscope.audio.asr import Recognition
from dashscope.audio.tts import SpeechSynthesizer

# 设置 API KEY
dashscope.api_key = DASHSCOPE_API_KEY


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
            # 如果不是从打断跳转过来的，则需要监听用户输入
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
            self.process_llm_tts(user_query)
            
            # 等待播放完成或被打断
            self.player.wait_until_done()
            
            # 检查是否被打断
            if self.interrupt_event.is_set():
                print("\n⚡ [System] 检测到打断，立即停止播报")
                self.player.stop()  # 立即停止播放
            
            # 状态回到空闲（让打断监听线程退出）
            self.current_state = "IDLE"
            # 如果被打断，新的输入将在下一轮循环中处理

    def process_llm_tts(self, text):
        """混合模式：指令控制使用固定话术，闲聊使用大模型"""
        try:
            # === 步骤1: 调用 Rasa 获取意图 ===
            print(f"[Rasa] 发送消息: {text}")
            payload = {"sender_id": RASA_SENDER_ID, "text": text}
            
            try:
                resp = requests.post(RASA_GATEWAY_URL, json=payload, timeout=30)  # 增加到30秒
                resp.raise_for_status()
                rasa_result = resp.json()
                print(f"[Rasa] 返回结果: {rasa_result}")
            except requests.RequestException as e:
                print(f"⚠️ [Rasa] 连接失败，降级到纯大模型模式: {e}")
                rasa_result = None
            
            # === 步骤2: 判断意图类型 ===
            if rasa_result:
                intent_name = rasa_result.get("intent", {}).get("name")
                confidence = rasa_result.get("intent", {}).get("confidence", 0)
                
                # 指令控制类意图（前4种）
                if intent_name in ["send_wechat_message", "search_file", "control_ppt"]:
                    print(f"[指令模式] 识别到指令意图: {intent_name}")
                    reply_text = self._generate_command_reply(intent_name, rasa_result)
                    self._speak_text(reply_text)
                    print(f"[指令模式] 固定话术播报完成")
                    return
            
            # === 步骤3: 闲聊模式 - 调用大模型 ===
            print(f"[闲聊模式] 调用大模型对话")
            self._call_llm_streaming(text)
            
        except Exception as e:
            print(f"\n❌ [Error] {e}")
            import traceback
            traceback.print_exc()
    
    def _generate_command_reply(self, intent_name, rasa_result):
        """根据指令意图生成固定话术回复（简洁版）"""
        slots = rasa_result.get("slots", {})
        action_status = slots.get("action_status", "success")
        
        # 1. 发送微信消息
        if intent_name == "send_wechat_message":
            contact_name = slots.get("contact_name", "")
            if contact_name:
                return f"已通知给{contact_name}。"
            else:
                return "已通知。"
        
        # 2. 查找并打开文件
        elif intent_name == "search_file":
            file_keyword = slots.get("file_keyword", "")
            if file_keyword:
                return f"已打开{file_keyword}文件。"
            else:
                return "已打开文件。"
        
        # 3. 控制PPT
        elif intent_name == "control_ppt":
            ppt_command = slots.get("ppt_command", "")
            # 如果是开始播放，提取文件关键词
            if "开始" in ppt_command or "播放" in ppt_command or "打开" in ppt_command:
                file_keyword = slots.get("file_keyword", "")
                if file_keyword:
                    return f"已打开{file_keyword}文件。"
                else:
                    return "已打开PPT文件。"
            # 其他操作（翻页、结束等）统一回复"好的"
            else:
                return "好的。"
        
        return "好的。"
    
    def _call_llm_streaming(self, text):
        """流式调用通义千问大模型"""
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

                print(delta, end="", flush=True)  # 打印 AI 回复

                buffer_text += delta
                # 遇到标点符号，切分送去 TTS
                for char in delta:
                    if char in punctuations:
                        if not self.interrupt_event.is_set():
                            self.synthesize_and_play(buffer_text)
                        buffer_text = ""
                        break

        # 处理剩余的文本
        if buffer_text and self.active and not self.interrupt_event.is_set():
            self.synthesize_and_play(buffer_text)
        print()  # 换行
    
    def _speak_text(self, text):
        """将文本按标点符号分段，送去 TTS 播放"""
        print(f"[AI] {text}")
        punctuations = {',', '，', '.', '。', '?', '？', '!', '！', ';', '；'}
        buffer_text = ""
        
        for char in text:
            buffer_text += char
            if char in punctuations:
                if buffer_text.strip() and not self.interrupt_event.is_set():
                    print(f"[TTS] 准备播放分段: {buffer_text.strip()}")
                    self.synthesize_and_play(buffer_text)
                buffer_text = ""
        
        # 处理剩余的文本
        if buffer_text.strip() and self.active and not self.interrupt_event.is_set():
            print(f"[TTS] 准备播放剩余文本: {buffer_text.strip()}")
            self.synthesize_and_play(buffer_text)

    def synthesize_and_play(self, text):
        if not text.strip(): 
            print("[TTS] 文本为空，跳过")
            return
        try:
            print(f"[TTS] 正在合成语音: {text.strip()[:20]}...")
            result = SpeechSynthesizer.call(
                model=MODEL_TTS,
                text=text,
                sample_rate=SAMPLE_RATE
            )
            if result.get_audio_data():
                audio_data = result.get_audio_data()
                print(f"[TTS] 合成成功，音频大小: {len(audio_data)} 字节")
                self.player.play(audio_data)
                print(f"[TTS] 已加入播放队列")
            else:
                print(f"⚠️ [TTS] 未获取到音频数据")
        except Exception as e:
            print(f"❌ [TTS Error] {e}")
            import traceback
            traceback.print_exc()