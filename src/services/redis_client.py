# encoding : utf-8 -*-                            
# @author  : 冬瓜                              
# @mail    : dylan_han@126.com    
# @Time    : 2026/1/4 16:58
# redis_client.py
import json
import redis
from typing import Any, Optional

class RedisClient:
    """
    封装 Redis 连接，用于存储催收对话会话状态。
    支持自动 JSON 序列化、TTL 过期、安全读写。
    """
    def __init__(
        self,
        configs: dict
    ):
        self.host = configs.get("host")
        self.port = configs.get("port")
        self.password = configs.get("password")
        self.db = configs.get("db")

        try:
            self._client = redis.Redis(
                host=self.host,
                port=self.port,
                # password=self.password,
                db=self.db,
                decode_responses=True,          # 返回 str 而非 bytes
                socket_connect_timeout=5,
                socket_timeout=configs.get("socket_timeout",5),
                retry_on_timeout=configs.get("retry_on_timeout",True)
            )
            # 测试连接
            self._client.ping()
            print(f"✅ RedisClient: 成功连接到 {self.host}:{self.port}")
        except redis.AuthenticationError:
            raise RuntimeError("❌ Redis 认证失败：请检查密码配置")
        except redis.ConnectionError:
            raise RuntimeError(f"❌ 无法连接 Redis：{self.host}:{self.port} 未响应")
        except Exception as e:
            raise RuntimeError(f"❌ Redis 初始化失败: {e}")

    def set_json(self, key: str, value: Any, expire: int = 1800) -> bool:
        """
        存储任意 Python 对象（自动转 JSON），并设置过期时间（秒）
        默认 expire=1800 (30分钟)，适合催收会话
        """
        try:
            json_str = json.dumps(value, ensure_ascii=False)
            return self._client.setex(key, expire, json_str)
        except Exception as e:
            print(f"⚠️ Redis set_json 失败: {e}")
            return False

    def get_json(self, key: str) -> Optional[Any]:
        """从 Redis 获取 JSON 并反序列化为 Python 对象"""
        try:
            data = self._client.get(key)
            if data is None:
                return None
            return json.loads(data)
        except json.JSONDecodeError:
            print(f"⚠️ Redis 数据非 JSON 格式: key={key}")
            return None
        except Exception as e:
            print(f"⚠️ Redis get_json 失败: {e}")
            return None

    def delete(self, key: str) -> bool:
        """删除指定 key"""
        try:
            return bool(self._client.delete(key))
        except Exception as e:
            print(f"⚠️ Redis delete 失败: {e}")
            return False

    def exists(self, key: str) -> bool:
        """检查 key 是否存在"""
        try:
            return self._client.exists(key) == 1
        except Exception as e:
            print(f"⚠️ Redis exists 失败: {e}")
            return False

    def close(self):
        """关闭连接（通常不需要手动调用）"""
        self._client.close()

    @property
    def client(self):
        """如需直接访问原生 redis client（谨慎使用）"""
        return self._client

if __name__ == '__main__':
    # 初始化 Redis 客户端
    try:
        redis_client = RedisClient(
            host="192.168.1.101",
            port=16379,
            password="IUIcity88",  # 注意：当前代码中 password 被注释了，如需认证请取消注释
            db=0
        )
    except RuntimeError as e:
        print(e)
        exit(1)

    test_key = "test:session:123"
    test_value = {
        "user_id": "U1001",
        "stage": "reminder",
        "last_message": "您好，请尽快还款。",
        "timestamp": "2026-01-04T16:58:00"
    }

    print("\n🧪 开始测试 RedisClient...\n")

    # 1. 写入 JSON 数据（默认 30 分钟过期）
    print("1. 尝试写入数据...")
    if redis_client.set_json(test_key, test_value):
        print("✅ 写入成功")
    else:
        print("❌ 写入失败")

    # 2. 读取 JSON 数据
    print("\n2. 尝试读取数据...")
    retrieved = redis_client.get_json(test_key)
    if retrieved == test_value:
        print("✅ 读取成功，数据一致")
    else:
        print("❌ 读取失败或数据不一致")

    # 3. 检查 key 是否存在
    print("\n3. 检查 key 是否存在...")
    if redis_client.exists(test_key):
        print("✅ Key 存在")
    else:
        print("❌ Key 不存在")

    # 4. 删除 key
    print("\n4. 删除 key...")
    if redis_client.delete(test_key):
        print("✅ 删除成功")
    else:
        print("❌ 删除失败")

    # 5. 再次读取应返回 None
    print("\n5. 尝试读取已删除的 key...")
    if redis_client.get_json(test_key) is None:
        print("✅ Key 已成功删除，返回 None")
    else:
        print("❌ Key 仍存在，删除未生效")

    # 6. 测试过期功能（快速验证：设置 2 秒过期）
    print("\n6. 测试 TTL 过期功能（2秒后自动失效）...")
    redis_client.set_json(test_key, {"temp": "data"}, expire=2)
    import time
    time.sleep(3)
    if redis_client.get_json(test_key) is None:
        print("✅ 数据已按 TTL 自动过期")
    else:
        print("❌ TTL 未生效")

    print("\n🎉 所有测试完成！")
    redis_client.close()
