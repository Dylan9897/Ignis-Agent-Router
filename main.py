import os
from src.core.agent_engine import DebtBotEngine
from src.utils.config_loader import load_full_config


# ============= 加载配置 =============
from dotenv import load_dotenv
load_dotenv()

if not os.getenv("ALI_API_KEY"):
    raise Exception("Error: ALI_API_KEY not found in .env file.")
# 3. 加载配置
try:
    settings, flow_config, prompts_config = load_full_config()
except Exception as e:
    raise EnvironmentError(f"Config Error: {e}")
# ===================================
func = DebtBotEngine(settings, flow_config, prompts_config)