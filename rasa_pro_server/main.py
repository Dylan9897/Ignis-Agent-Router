# encoding : utf-8 -*-                            
# @author  : 冬瓜                              
# @mail    : dylan_han@126.com    
# @Time    : 2026/2/2 14:40
import os
import glob
import asyncio
import time
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager

from rasa.core.agent import Agent
from rasa.core.config.configuration import Configuration


# --- 1. 定义数据模型 (Schema) ---

class NLURequest(BaseModel):
    text: str = Field(..., example="我现在没钱还", description="需要解析的用户文本")
    sessionId: str = Field(..., example="call_20260202_001", description="通话或会话的唯一标识")
    message_id: Optional[str] = Field(None, description="可选的消息ID，用于链路追踪")


class Entity(BaseModel):
    entity: str
    value: Any
    start: int
    end: int
    confidence: Optional[float] = None
    extractor: Optional[str] = None


class Intent(BaseModel):
    name: str
    confidence: float


class NLUResponse(BaseModel):
    # 基础字段
    sessionId: str
    text: str
    intent: Intent
    entities: List[Entity]
    model_name: str

    # 监控字段
    latency_ms: float = Field(..., description="接口处理耗时 (毫秒)")
    input_chars: int = Field(..., description="输入文本字符数")
    output_chars: int = Field(..., description="响应 JSON 的预估字符数")


# --- 2. 辅助函数 ---

def get_latest_model(model_path="./saved_models"):
    list_of_files = glob.glob(os.path.join(model_path, "*.tar.gz"))
    if not list_of_files:
        return None
    return max(list_of_files, key=os.path.getctime)


# --- 3. 生命周期管理 ---

rasa_agent: Optional[Agent] = None
model_filename: str = ""


@asynccontextmanager
async def lifespan(app: FastAPI):
    global rasa_agent, model_filename
    config_path = Path("config.yml")
    if not config_path.exists():
        raise FileNotFoundError("项目根目录下缺少 config.yml")

    Configuration.initialise_message_processing(config_path)
    model_file = get_latest_model()
    if not model_file:
        raise RuntimeError("❌ 未找到模型包")

    rasa_agent = Agent.load(model_path=model_file)
    model_filename = os.path.basename(model_file)
    print(f"✅ Rasa Pro 加载成功: {model_filename}")
    yield


app = FastAPI(title="Rasa Pro NLU Service", lifespan=lifespan)


# --- 4. 接口路由 ---

@app.post("/nlu/parse", response_model=NLUResponse)
async def parse_message(request: NLURequest):
    if not rasa_agent:
        raise HTTPException(status_code=503, detail="Rasa Agent 未就绪")

    # 记录开始时间
    start_time = time.perf_counter()

    try:
        # 核心解析逻辑
        result = await rasa_agent.parse_message(request.text)

        # 计算耗时 (秒 -> 毫秒)
        end_time = time.perf_counter()
        latency_ms = round((end_time - start_time) * 1000, 2)

        # 构造初步响应内容以计算输出字数
        intent_data = Intent(
            name=result["intent"]["name"],
            confidence=result["intent"]["confidence"]
        )
        entities_data = [Entity(**ent) for ent in result.get("entities", [])]

        # 预估输出字数 (将关键内容转为 string 统计)
        output_content_sample = f"{intent_data.name}{str(entities_data)}"

        return NLUResponse(
            sessionId=request.sessionId,
            text=request.text,
            intent=intent_data,
            entities=entities_data,
            model_name=model_filename,
            latency_ms=latency_ms,
            input_chars=len(request.text),
            output_chars=len(output_content_sample)
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析错误: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    uvicorn.run(app, host="0.0.0.0", port=8000)