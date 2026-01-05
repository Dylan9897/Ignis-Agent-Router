

class StateTracker():
    def __init__(
        self,
        business_flow: dict,
        initial_node: str = "沟通开场"
    ):
        self.flow = business_flow
        self.current_node = initial_node
        self.history = []  # 存储对话历史
        self.slots = {}  # 存储提取到的信息，如金额、时间
        self.repeat_count = 0  # 记录当前节点重复次数，防止死循环

    def to_dict(self):
        """用于存入 Redis"""
        return {
            "current_node": self.current_node,
            "slots": self.slots,
            "repeat_count": self.repeat_count,
            "history": self.history
        }

    @classmethod
    def from_dict(cls, data: dict, business_flow: dict):
        """从 Redis 读取并恢复实例"""
        instance = cls(business_flow)
        instance.current_node = data.get("current_node", "沟通开场")
        instance.slots = data.get("slots", {})
        instance.repeat_count = data.get("repeat_count", 0)
        instance.history = data.get("history", [])
        return instance

    def get_next_state(self, intent: str):
        """核心逻辑：状态迁移"""
        node_config = self.flow.get(self.current_node)
        if not node_config:
            return "挂断", "hangup"

        intent_map = node_config.get("intent_map", {})
        # 获取匹配意图的跳转配置，匹配不到则用 __default__
        transition = intent_map.get(intent) or intent_map.get("__default__")

        next_stage = transition["next_stage"]
        action = transition["action"]


        # 更新状态
        if next_stage == self.current_node:
            self.repeat_count += 1
        else:
            self.repeat_count = 0

        self.current_node = next_stage
        return next_stage, action