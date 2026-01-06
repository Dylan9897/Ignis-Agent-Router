# encoding : utf-8 -*-                            
# @author  : 冬瓜                              
# @mail    : dylan_han@126.com    
# @Time    : 2026/1/4 11:05
import yaml
import os

def load_yaml(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def load_full_config():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    settings = load_yaml(os.path.join(base_dir, 'config', 'settings.yaml'))
    flow = load_yaml(os.path.join(base_dir, 'config', 'business_flow.yaml'))
    # 新增加载 prompts 配置
    prompts = load_yaml(os.path.join(base_dir, 'config', 'flow_choice.yaml'))
    return settings, flow, prompts

