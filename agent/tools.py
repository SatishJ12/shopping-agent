"""Tool schemas (OpenAI-compatible function-calling format, used by Grok) and
the dispatcher that executes them, per PRD section 7."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import db, preferences
from initial_setup.reviews_api import get_product_rating


def _tool(name: str, description: str, parameters: dict) -> dict:
    return {"type": "function", "function": {"name": name, "description": description, "parameters": parameters}}


TOOL_SCHEMAS = [
    _tool(
        "search_products",
        "Keyword search across product name, description, and category, with optional price and organic filters.",
        {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "Search term, e.g. 'honey' or 'oat milk'."},
                "max_price": {"type": "number", "description": "Maximum price, inclusive. Omit if no price cap was stated."},
                "is_organic": {"type": "boolean", "description": "True to return only organic products. Omit if not stated."},
            },
            "required": ["keyword"],
        },
    ),
    _tool(
        "get_rating",
        "Average rating and review count for one product, from the reviews API.",
        {
            "type": "object",
            "properties": {"product_id": {"type": "integer"}},
            "required": ["product_id"],
        },
    ),
    _tool(
        "checkout",
        "Places an order for exactly one product. Only call this after the shopper has explicitly confirmed which product, and only with a product ID that came from a list already shown to the shopper.",
        {
            "type": "object",
            "properties": {"product_id": {"type": "integer"}},
            "required": ["product_id"],
        },
    ),
    _tool(
        "get_order_history",
        "Returns everything the shopper has ordered before.",
        {"type": "object", "properties": {}},
    ),
    _tool(
        "save_preference",
        "Persists a standing shopper preference so it applies automatically in future sessions. Use key 'organic_only' (boolean) for statements like 'I always want organic', or 'max_price' (number) for statements like 'never show me anything over $20'.",
        {
            "type": "object",
            "properties": {
                "key": {"type": "string", "enum": ["organic_only", "max_price"]},
                "value": {},
            },
            "required": ["key", "value"],
        },
    ),
]


def execute_tool(name: str, tool_input: dict) -> dict:
    if name == "search_products":
        products = db.search_products(
            keyword=tool_input["keyword"],
            max_price=tool_input.get("max_price"),
            is_organic=tool_input.get("is_organic"),
        )
        return {"products": products}

    if name == "get_rating":
        return get_product_rating(tool_input["product_id"])

    if name == "checkout":
        order = db.place_order(tool_input["product_id"])
        return {"order_id": order["id"], "product_name": order["product_name"], "price": order["price"]}

    if name == "get_order_history":
        return {"orders": db.get_orders()}

    if name == "save_preference":
        updated = preferences.save_preference(tool_input["key"], tool_input["value"])
        return {"preferences": updated}

    raise ValueError(f"Unknown tool: {name}")
