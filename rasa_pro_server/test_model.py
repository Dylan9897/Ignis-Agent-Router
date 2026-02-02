import asyncio
import os
import glob
from pathlib import Path
from rasa.core.agent import Agent
# 关键修复：从精确的子模块导入 Configuration 类
from rasa.core.config.configuration import Configuration


# 1. 自动寻找最新的模型包
def get_latest_model(model_path="./saved_models"):
    list_of_files = glob.glob(os.path.join(model_path, "*.tar.gz"))
    if not list_of_files:
        return None
    return max(list_of_files, key=os.path.getctime)


async def run_test():
    # --- Rasa Pro 强制初始化序列 ---
    # 按照报错建议，初始化消息处理和端点配置
    print("⚙️ 正在初始化 Rasa Pro 全局配置...")
    # rasa-pro 3.15.x 需要显式传入 message processing config 路径
    # 这里复用你项目根目录的 `config.yml`
    Configuration.initialise_message_processing(Path("config.yml"))

    model_file = get_latest_model()
    if not model_file:
        print("❌ 错误：在 ./saved_models 目录下没找到模型包！")
        return

    print(f"📦 正在加载模型: {model_file}")

    try:
        # 在 Rasa Pro 中，直接加载 Agent 
        agent = Agent.load(model_path=model_file)
        print("✅ Rasa Pro 引擎加载成功！")

        # 针对外呼系统和助手的测试场景
        test_examples = [
            "你是谁呀？",
            "帮我查一下我的日报",
            "我现在没钱还"
        ]

        print("\n" + "=" * 30)
        print("🚀 NLU 语义解析测试")
        print("=" * 30)

        for text in test_examples:
            result = await agent.parse_message(text)
            intent = result['intent']['name']
            conf = result['intent']['confidence']
            print(f"输入: {text}")
            print(f"意图: {intent} (置信度: {conf:.4f})")
            if result.get('entities'):
                print(f"实体: {result['entities']}")
            print("-" * 30)

    except Exception as e:
        print(f"❌ 运行过程中发现错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 处理 Python 3.11 在某些环境下的异步循环问题
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(run_test())