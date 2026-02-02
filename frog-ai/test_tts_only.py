"""
测试TTS功能是否正常 - 支持多种音色
"""
import dashscope
from dashscope.audio.tts import SpeechSynthesizer
from config import DASHSCOPE_API_KEY, SAMPLE_RATE, MODEL_TTS
import pyaudio
import time

# 设置API KEY
dashscope.api_key = DASHSCOPE_API_KEY

# 阿里云TTS官方可用音色（Sambert多情感）
VOICE_OPTIONS = {
    "1": ("sambert-zhichu-v1", "知趣 (温柔自然女声) ⭐默认"),
    "2": ("sambert-zhigui-v1", "知柜 (客服女声)"),
    "3": ("sambert-zhimao-v1", "知猫 (娇俏可爱女声) 💕"),
    "4": ("sambert-zhiting-v1", "知婷 (电台女声，优雅知性)"),
    "5": ("sambert-zhiyue-v1", "知悦 (温柔女声)"),
    "6": ("sambert-zhiwei-v1", "知微 (萝莉女声，阅读产品简介)"),
}

def test_tts(text, voice_model=None):
    """测试TTS合成和播放"""
    # 如果没有指定音色，使用默认的
    if voice_model is None:
        voice_model = MODEL_TTS
    
    print(f"\n[测试] 准备合成文本: {text}")
    print(f"[测试] 使用音色模型: {voice_model}")
    
    try:
        # 1. 测试TTS合成
        print("[测试] 正在调用TTS...")
        
        result = SpeechSynthesizer.call(
            model=voice_model,
            text=text,
            sample_rate=SAMPLE_RATE
        )
        
        # 打印完整的结果信息用于调试
        print(f"[调试] TTS返回状态码: {result.get_response().status_code if result.get_response() else 'N/A'}")
        
        # 2. 检查音频数据
        audio_data = result.get_audio_data()
        if audio_data:
            print(f"[测试] ✅ TTS合成成功！音频大小: {len(audio_data)} 字节")
            
            # 3. 测试播放
            print("[测试] 正在播放...")
            p = pyaudio.PyAudio()
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=SAMPLE_RATE,
                output=True
            )
            
            # 分块播放
            chunk_size = 3200
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i + chunk_size]
                stream.write(chunk)
            
            stream.stop_stream()
            stream.close()
            p.terminate()
            
            print("[测试] ✅ 播放完成！")
            return True
        else:
            print("[测试] ❌ TTS未返回音频数据")
            print("[提示] 可能原因：")
            print(f"  1. 该音色模型 '{voice_model}' 可能不可用")
            print(f"  2. API KEY可能没有该音色的使用权限")
            print(f"  3. 网络连接问题或TTS服务限流")
            return False
            
    except Exception as e:
        print(f"[测试] ❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("🎙️  TTS 音色测试工具")
    print("=" * 60)
    
    # 检查API KEY
    if "sk-" not in DASHSCOPE_API_KEY:
        print("❌ 错误: 请在 config.py 中配置正确的 DASHSCOPE_API_KEY")
        exit(1)
    
    print(f"✅ API KEY 已配置")
    print(f"✅ 默认采样率: {SAMPLE_RATE}")
    
    # 显示可用音色
    print("\n" + "=" * 60)
    print("📢 可用音色列表：")
    print("=" * 60)
    for key, (model, desc) in VOICE_OPTIONS.items():
        print(f"  {key:2s}. {desc}")
    print("\n  0. 退出")
    
    # 测试文本选项
    test_texts = [
        "你好，很高兴认识你。",
        "好的，我已经给冬瓜发送了晚上开会。",
        "已经为您找到并打开了测试报告相关的文件。",
        "好的，PPT已经开始播放，请注意查看。",
        "今天天气真不错，心情也跟着好起来了。"
    ]
    
    while True:
        print("\n" + "=" * 60)
        choice = input("请选择音色编号 (0退出): ").strip()
        
        if choice == "0":
            print("\n👋 再见！")
            break
        
        if choice not in VOICE_OPTIONS:
            print("❌ 无效的选择，请重新输入")
            continue
        
        voice_model, voice_desc = VOICE_OPTIONS[choice]
        
        print(f"\n🎵 已选择: {voice_desc}")
        print(f"📝 音色模型: {voice_model}")
        
        # 让用户选择测试文本或自定义
        print("\n可选测试文本：")
        for i, text in enumerate(test_texts, 1):
            print(f"  {i}. {text}")
        print(f"  {len(test_texts) + 1}. 自定义文本")
        
        text_choice = input(f"\n请选择文本 (1-{len(test_texts) + 1}): ").strip()
        
        if text_choice.isdigit():
            text_idx = int(text_choice)
            if 1 <= text_idx <= len(test_texts):
                test_text = test_texts[text_idx - 1]
            elif text_idx == len(test_texts) + 1:
                test_text = input("请输入自定义文本: ").strip()
                if not test_text:
                    test_text = "你好，这是一个测试。"
            else:
                print("❌ 无效的选择")
                continue
        else:
            print("❌ 无效的选择")
            continue
        
        # 执行测试
        test_tts(test_text, voice_model)
        
        time.sleep(0.5)
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)

