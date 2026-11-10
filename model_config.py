# model_config.py

import os

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

load_dotenv()
key = os.getenv("DEEPSEEK_FLASH_KEY")
url = os.getenv("DEEPSEEK_FLASH_URL")

model = init_chat_model(
    model="deepseek-flash",
    model_provider="openai",
    api_key=key,
    base_url=url,
       # 关闭思考模式
    extra_body={
        "thinking": {
            "type": "disabled",
        }
    },
)