import asyncio
from fastapi import FastAPI,HTTPException

from langchain.chat_models import init_chat_model
from dotenv import load_dotenv
import os 
from rich import print as rprint
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
load_dotenv()

model = init_chat_model(
    model = "deepseek-flash",
    model_provider="openai",
    api_key = os.getenv("DEEPSEEK_FLASH_KEY"),
    base_url = os.getenv("DEEPSEEK_FLASH_URL")
)
class chat_request(BaseModel):
    question: str



async def create_stream_chat(question:str):
    try:
        async for chunk in model.astream([{"role":"user","content":question}]) :
            yield f"data:{chunk.content}\n\n"
        yield "data: [DONE]\n\n"
    except asyncio.CancelledError:
        print("客户端断开连接，流式任务取消")
        raise
    except Exception as e:
        print(f"模型调用失败：{e}")



    

app = FastAPI()


@app.post("/chat_model")
async def chat(request:chat_request):
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="问题内容不能为空")
    return StreamingResponse(create_stream_chat(request.question), media_type="text/event-stream")

@app.get("/", response_class=HTMLResponse)
async def get_index():
  with open("index.html", "r", encoding="utf-8") as f:
    return f.read()