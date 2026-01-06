# encoding : utf-8 -*-                            
# @author  : 冬瓜                              
# @mail    : dylan_han@126.com    
# @Time    : 2026/1/4 17:40

import random
from datetime import datetime, timedelta


def load_customer_from_db(session_id: str):
    """
    模拟从数据库加载催收客户数据（根据 session_id 返回对应记录）
    移除了 assigned_collector 字段，仅保留基本催收信息
    """
    # 基础姓名库
    names = ["张三", "李四", "王五", "赵六", "陈七", "刘梅", "杨洋", "黄磊", "周婷", "吴昊"]
    phones = [
        "13800138001", "13900139002", "15000150003", "18600186004",
        "18700187005", "13100131006", "15200152007", "18800188008"
    ]
    stages = ["提醒期", "催收期", "强催期", "法务期"]

    def generate_customer(i: int):
        name = names[i % len(names)]
        loan_amt = round(random.uniform(5000, 50000), 2)
        overdue = random.randint(1, 180)
        # 剩余金额不超过借款金额
        remaining = round(random.uniform(1000, min(loan_amt, 40000)), 2)
        return {
            "debtor_name": name,
            "phone": phones[i % len(phones)],
            "id_card": f"11010119900101{i:04d}",  # 脱敏模拟
            "loan_amount": loan_amt,
            "overdue_days": overdue,
            "remaining_amount": remaining,
            "last_repayment_date": (datetime.now() - timedelta(days=random.randint(5, 200))).strftime("%Y-%m-%d"),
            "collection_stage": random.choice(stages)
        }

    # 预生成几条模拟数据
    mock_data = {
        "1": generate_customer(0),
        "2": generate_customer(1),
        "3": generate_customer(2),
        "4": generate_customer(3),
        "5": generate_customer(4),
    }

    return mock_data.get(session_id, {})

# 测试
if __name__ == '__main__':
    print("Session '1' 的客户信息:")
    print(load_customer_from_db("1"))

    print("\nSession '999'（不存在）:")
    print(load_customer_from_db("999"))  # 返回 {}




