# encoding : utf-8 -*-                            
# @author  : 冬瓜                              
# @mail    : dylan_han@126.com    
# @Time    : 2026/1/27 11:59

import pyaudio
import queue
import threading
import time
from config import SAMPLE_RATE, CHANNELS

class AudioPlayer:
    """
    这是一个基于多线程和队列设计的异步音频播放管理器，它像传送带一样在后台按序处理声音数据，确保 AI 说话时前台界面依然丝滑不卡顿。
    """
    def __init__(self, interrupt_event=None):
        self.p = pyaudio.PyAudio()
        self.queue = queue.Queue()
        self.is_playing = False
        self.stream = None
        self.lock = threading.Lock()
        self.should_stop = False  # 打断标志
        self.interrupt_event = interrupt_event  # 外部打断事件

        try:
            # 初始化播放流
            self.stream = self.p.open(
                format=pyaudio.paInt16,
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                output=True
            )
        except Exception as e:
            print(f"⚠️ [AudioPlayer] 扬声器初始化失败: {e}")

        self.thread = threading.Thread(target=self._play_loop, daemon=True)
        self.thread.start()

    def _play_loop(self):
        while True:
            data = self.queue.get()
            if data is None: break

            # 检查是否需要打断
            if self.should_stop or (self.interrupt_event and self.interrupt_event.is_set()):
                with self.lock:
                    self.is_playing = False
                continue

            if self.stream:
                with self.lock:
                    self.is_playing = True
                try:
                    # 分块播放，以便能够及时响应打断
                    chunk_size = 3200  # 每次播放0.1秒的数据
                    for i in range(0, len(data), chunk_size):
                        # 每个小块播放前检查是否需要打断
                        if self.should_stop or (self.interrupt_event and self.interrupt_event.is_set()):
                            print("⚡ [AudioPlayer] 检测到打断，立即停止播放")
                            with self.lock:
                                self.is_playing = False
                            break
                        chunk = data[i:i + chunk_size]
                        self.stream.write(chunk)
                except Exception as e:
                    print(f"[AudioPlayer] 播放错误: {e}")
                with self.lock:
                    if self.queue.empty(): self.is_playing = False

    def play(self, data):
        self.queue.put(data)

    def stop(self):
        """打断播放：清空队列并停止当前播放"""
        print("🛑 [AudioPlayer] 打断播放")
        self.should_stop = True
        # 清空队列
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except queue.Empty:
                break
        with self.lock:
            self.is_playing = False
        # 重置打断标志
        self.should_stop = False

    def wait_until_done(self):
        """阻塞直到播放结束"""
        start = time.time()
        while True:
            with self.lock:
                if not self.is_playing and self.queue.empty(): break
            # 超时保护 30s
            if time.time() - start > 30: break
            # 检查是否被打断
            if self.should_stop: break
            time.sleep(0.1)
