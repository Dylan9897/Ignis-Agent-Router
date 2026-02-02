# encoding : utf-8 -*-                            
# @author  : 冬瓜                              
# @mail    : dylan_han@126.com    
# @Time    : 2026/1/27 13:20
from dashscope.audio.asr import RecognitionCallback, RecognitionResult


class ConversationCallback(RecognitionCallback):
    """
    实时语音识别的回调接口
    """
    def __init__(self, worker):
        super().__init__()
        self.worker = worker

    def on_event(self, result: RecognitionResult):
        try:
            sentence = result.get_sentence()
            if sentence:
                text = sentence['text']
                # 打印实时听写日志
                print(f"\r[ASR] {text}", end="", flush=True)

                # 检测到句子结束 (VAD)
                if result.is_sentence_end(sentence):
                    print("\n[VAD] 句子结束")
                    self.worker.user_input_buffer = text
                    self.worker.vad_event.set()
        except Exception as e:
            print(f"\n[Callback Error] {e}")

    def on_complete(self):
        pass

    def on_error(self, result: RecognitionResult):
        print(f"\n[ASR Error] {result}")


class InterruptCallback(RecognitionCallback):
    """
    打断检测回调：在SPEAKING状态时监听用户语音
    """
    def __init__(self, worker):
        super().__init__()
        self.worker = worker
        self.has_interrupted = False  # 防止重复触发

    def on_event(self, result: RecognitionResult):
        try:
            # 如果已经触发过打断，不再处理
            if self.has_interrupted:
                return
                
            sentence = result.get_sentence()
            if sentence:
                text = sentence['text'].strip()
                # 只在句子结束时才触发打断，避免中间识别结果误触发
                if result.is_sentence_end(sentence) and len(text) > 0:
                    print(f"\n⚡ [打断检测] 检测到用户说话: {text}")
                    self.worker.interrupt_event.set()
                    # 保存用户新的输入
                    self.worker.user_input_buffer = text
                    self.has_interrupted = True  # 标记已触发
        except Exception as e:
            print(f"\n[InterruptCallback Error] {e}")

    def on_complete(self):
        pass

    def on_error(self, result: RecognitionResult):
        pass