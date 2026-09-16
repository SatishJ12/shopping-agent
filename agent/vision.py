"""Identifies a product from a photo using Groq's vision-capable model,
per PRD FR-10 / the describe_product_image tool."""

import base64
import json

VISION_MODEL = "qwen/qwen3.8-27b"

VISION_PROMPT = """You are looking at a photo a shopper uploaded to a pantry store's shopping assistant. The store sells honey, oils, nuts and seeds, grains, tea and coffee, snacks, and dairy alternatives.

Identify what is in the photo and respond with ONLY a JSON object, no other text:
{
  "item": "<short description of what you see>",
  "search_keyword": "<one or two words to search the store's catalogue with>",
  "looks_organic": <true, false, or null if you can't tell>,
  "is_store_product": <true if this looks like a pantry/grocery item the store could plausibly sell, false otherwise (e.g. an animal, a person, an unrelated object)>
}"""


def describe_product_image(client, image_bytes: bytes, media_type: str) -> dict:
    encoded = base64.standard_b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{media_type};base64,{encoded}"

    response = client.chat.completions.create(
        model=VISION_MODEL,
        max_tokens=300,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": VISION_PROMPT},
                ],
            }
        ],
    )
    text = response.choices[0].message.content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)
