from datetime import timedelta, timezone
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.concurrency import asynccontextmanager
from fastapi.responses import FileResponse 
from api import interview,register_plan,revise,confirm,conversation,chat_stream,list_plans,list_plans_details,updata_tasks,review_load,delete_plan
from langgraph.checkpoint.memory import InMemorySaver

from database.init_database import init_database

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database()
    yield

app = FastAPI(
    title="学习计划与复盘助手",
    lifespan=lifespan,
)

app.include_router(interview.router)

app.include_router(register_plan.router,prefix = "/api/register_plan")

app.include_router(revise.router,prefix="/api/review")

app.include_router(confirm.router,prefix="/api/confirm")

app.include_router(conversation.router,prefix="/api/conversations")

app.include_router(chat_stream.router, prefix="/api/chat_stream")

app.include_router(list_plans.router,prefix="/api/list_plans")

app.include_router(updata_tasks.router,prefix="/api/updata_tasks")

app.include_router(list_plans_details.router,prefix="/api/list_plans_details")

app.include_router(review_load.router,prefix="/api/review_load")

app.include_router(delete_plan.router , prefix="/api/delete_plan")


BASE_DIR = Path(__file__).resolve().parent
BEIJING = timezone(timedelta(hours=8))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

memory = InMemorySaver()




@app.get("/")
def homepage():
    return FileResponse(
        BASE_DIR / "static" / "index3.html",
        media_type="text/html",
        # 【修改：按天规划】开发时避免旧页面缓存掩盖新表单。
        headers={"Cache-Control": "no-store"},
    )
