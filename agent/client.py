"""The ShopMate tool-use loop: sends the conversation to Groq's OpenAI-
compatible API, executes any tool calls it makes, and loops until the model
produces a final text reply."""

import json

from openai import OpenAI

from agent.preferences import load_preferences
from agent.system_prompt import build_system_prompt
from agent.tools import TOOL_SCHEMAS, execute_tool
from agent.vision import describe_product_image

BASE_URL = "https://api.groq.com/openai/v1"
MODEL = "qwen/qwen3.8-27b"


class ShopMateAgent:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key, base_url=BASE_URL)

    def run_turn(self, history: list[dict], user_text: str, image: tuple[bytes, str] | None = None):
        if image is not None:
            image_bytes, media_type = image
            described = describe_product_image(self.client, image_bytes, media_type)
            user_content = (
                f"[Shopper uploaded a photo. Identified as: {described['item']}. "
                f"Suggested search keyword: {described['search_keyword']}. "
                f"Looks organic: {described['looks_organic']}. "
                f"Looks like a store product: {described['is_store_product']}.]\n\n{user_text}"
            )
        else:
            user_content = user_text

        system_prompt = build_system_prompt(load_preferences())
        messages = [{"role": "system", "content": system_prompt}] + history + [{"role": "user", "content": user_content}]

        while True:
            response = self.client.chat.completions.create(
                model=MODEL,
                max_tokens=1024,
                tools=TOOL_SCHEMAS,
                messages=messages,
            )

            message = response.choices[0].message
            messages.append(message.model_dump(exclude_none=True))

            if not message.tool_calls:
                return message.content, messages[1:]

            for tool_call in message.tool_calls:
                tool_input = json.loads(tool_call.function.arguments)
                result = execute_tool(tool_call.function.name, tool_input)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, default=str),
                })
