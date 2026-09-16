# ShopMate Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build ShopMate end to end from `PRD.md`: the five tools, the three flows (browsing, photo search, ordering), memory/preferences, and a Streamlit chat UI with image upload.

**Architecture:** A `store.db` SQLite layer (products/orders) plus the untouched `initial_setup/reviews_api.py` for ratings, wrapped by tool functions that an Anthropic Claude tool-use loop calls. A system prompt encodes the three flows, the exact output format, and the guardrails. Preferences persist in a small JSON file read at the start of every turn and folded into the system prompt so they apply automatically. Streamlit provides the chat UI and image upload; conversation history lives only in `st.session_state` (resets on restart), while orders and preferences live on disk (survive restart).

**Tech Stack:** Python 3.10, `anthropic` SDK (Claude, tool use + vision in one model), `streamlit`, `python-dotenv`, `sqlite3` (stdlib), `pytest` for the tool-layer tests.

**Spec:** `PRD.md` (this repo) — built from `PRODUCT_BRIEF.md`. Do not add anything PRD.md does not require.

## Global Constraints

- Language: Python 3.10+ (PRD §11).
- Build on top of `initial_setup/`; do not modify `setup_db.py` or `reviews_api.py` (PRD §11 rule 1).
- Ratings come only from `initial_setup/reviews_api.py`, never a direct query on `reviews` (PRD §11 rule 2, FR-05).
- API keys live in `.env`, never in code or committed (PRD §11 rule 3).
- Product list format is exactly `#N. <Name> (ID:X) — $<price> ★<rating> — organic` (organic suffix only for organic items), one blank line between entries, `(ID:X)` always present (FR-06).
- `checkout` is only called after explicit shopper confirmation, using an ID from a list already shown — never a guessed ID (FR-08, FR-09, GR-01).
- Never state a product/price/rating not returned by a tool (GR-02).
- Off-topic requests get a polite redirect, no tool call (GR-03).
- One product per order, no cart, no login, no RAG (PRD §4).

---

### Task 1: Environment setup

**Files:**
- Create: `.venv/` (virtualenv, not committed)
- Create: `requirements.txt`
- Create: `.env` (gitignored, placeholder key)
- Create: `.gitignore`
- Run: `initial_setup/setup_db.py` to create `store.db`

**Interfaces:**
- Produces: a working `.venv` with `anthropic`, `streamlit`, `python-dotenv`, `pytest` installed; `store.db` at the project root; `ANTHROPIC_API_KEY` variable name that every later task reads via `os.environ["ANTHROPIC_API_KEY"]`.

- [ ] **Step 1: Create the virtualenv and `requirements.txt`**

`requirements.txt`:
```
anthropic>=0.40.0
streamlit>=1.38.0
python-dotenv>=1.0.0
pytest>=8.0.0
```

Run:
```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
```

- [ ] **Step 2: Create `.gitignore`**

```
.venv/
.env
store.db
__pycache__/
*.pyc
preferences.json
.pytest_cache/
```

- [ ] **Step 3: Create `.env` with a placeholder and ask the user to fill in their real key**

```
ANTHROPIC_API_KEY=your-key-here
```

Tell the user: fill in `ANTHROPIC_API_KEY` in `.env` before running the app.

- [ ] **Step 4: Create the database and run the two SETUP.md sanity checks**

```bash
.venv/Scripts/python initial_setup/setup_db.py
.venv/Scripts/python initial_setup/reviews_api.py
```

Expected: `Database created at: .../store.db`, then a list starting with `Product 1: 4.62 stars (4 reviews)`.

---

### Task 2: Database layer for products and orders

**Files:**
- Create: `agent/__init__.py` (empty)
- Create: `agent/db.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Produces:
  - `search_products(keyword: str, max_price: float | None = None, is_organic: bool | None = None) -> list[dict]` — each dict has `id, name, category, price, description, is_organic`.
  - `get_product(product_id: int) -> dict | None`
  - `place_order(product_id: int) -> dict` — inserts into `orders`, returns `{id, product_id, product_name, price, ordered_at}`.
  - `get_orders() -> list[dict]` — all past orders, most recent first.
- Consumes: `store.db` created in Task 1, with the schema from `initial_setup/setup_db.py`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_db.py
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import db


def test_search_products_by_keyword():
    results = db.search_products("honey")
    assert len(results) == 8
    assert all("honey" in r["category"] for r in results)


def test_search_products_with_max_price():
    results = db.search_products("honey", max_price=15.00)
    names = {r["name"] for r in results}
    assert "Organic Manuka Honey" not in names
    assert all(r["price"] <= 15.00 for r in results)


def test_search_products_organic_only():
    results = db.search_products("honey", is_organic=True)
    assert all(r["is_organic"] == 1 for r in results)
    assert len(results) == 4


def test_search_products_no_match():
    assert db.search_products("bicycle") == []


def test_get_product_found():
    product = db.get_product(1)
    assert product["name"] == "Organic Raw Honey"


def test_get_product_not_found():
    assert db.get_product(9999) is None


def test_place_order_and_get_orders():
    order = db.place_order(30)
    assert order["product_id"] == 30
    assert order["product_name"] == "Oat Milk"
    assert order["price"] == 4.49
    assert "id" in order and "ordered_at" in order

    orders = db.get_orders()
    assert any(o["id"] == order["id"] for o in orders)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/Scripts/python -m pytest tests/test_db.py -v
```
Expected: FAIL with `ModuleNotFoundError` or `AttributeError` (no `agent/db.py` yet).

- [ ] **Step 3: Implement `agent/db.py`**

```python
"""SQLite access for the products and orders tables in store.db."""

import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "store.db")


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def search_products(keyword: str, max_price: float | None = None, is_organic: bool | None = None) -> list[dict]:
    conn = _connect()
    cursor = conn.cursor()

    clauses = ["(LOWER(name) LIKE ? OR LOWER(description) LIKE ? OR LOWER(category) LIKE ?)"]
    like = f"%{keyword.lower()}%"
    params: list = [like, like, like]

    if max_price is not None:
        clauses.append("price <= ?")
        params.append(max_price)

    if is_organic is not None:
        clauses.append("is_organic = ?")
        params.append(1 if is_organic else 0)

    query = f"SELECT id, name, category, price, description, is_organic FROM products WHERE {' AND '.join(clauses)} ORDER BY id"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_product(product_id: int) -> dict | None:
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, category, price, description, is_organic FROM products WHERE id = ?",
        (product_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def place_order(product_id: int) -> dict:
    product = get_product(product_id)
    if product is None:
        raise ValueError(f"No product with id {product_id}")

    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO orders (product_id, product_name, price) VALUES (?, ?, ?)",
        (product["id"], product["name"], product["price"]),
    )
    conn.commit()
    order_id = cursor.lastrowid
    cursor.execute("SELECT id, product_id, product_name, price, ordered_at FROM orders WHERE id = ?", (order_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row)


def get_orders() -> list[dict]:
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("SELECT id, product_id, product_name, price, ordered_at FROM orders ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/Scripts/python -m pytest tests/test_db.py -v
```
Expected: PASS (7 passed). Note the `place_order` test has a side effect (adds a real row to `orders`) — acceptable for this small assignment db, but run it last if re-running individual tests matters.

- [ ] **Step 5: Commit**

```bash
git add agent/__init__.py agent/db.py tests/test_db.py requirements.txt .gitignore .env
git commit -m "feat: add products/orders db layer with tests"
```

---

### Task 3: Preferences storage

**Files:**
- Create: `agent/preferences.py`
- Test: `tests/test_preferences.py`

**Interfaces:**
- Produces:
  - `load_preferences() -> dict` — reads `preferences.json` at project root; returns `{}` if the file does not exist.
  - `save_preference(key: str, value) -> dict` — merges `{key: value}` into the stored preferences, writes the file, returns the full updated dict.
  - Recognized keys used elsewhere: `"organic_only"` (bool), `"max_price"` (float).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_preferences.py
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import preferences

PREFS_PATH = preferences.PREFS_PATH


def _cleanup():
    if os.path.exists(PREFS_PATH):
        os.remove(PREFS_PATH)


def test_load_preferences_missing_file_returns_empty():
    _cleanup()
    assert preferences.load_preferences() == {}


def test_save_preference_persists_to_disk():
    _cleanup()
    result = preferences.save_preference("organic_only", True)
    assert result == {"organic_only": True}

    with open(PREFS_PATH) as f:
        on_disk = json.load(f)
    assert on_disk == {"organic_only": True}
    _cleanup()


def test_save_preference_merges_with_existing():
    _cleanup()
    preferences.save_preference("organic_only", True)
    result = preferences.save_preference("max_price", 20)
    assert result == {"organic_only": True, "max_price": 20}
    _cleanup()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/Scripts/python -m pytest tests/test_preferences.py -v
```
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `agent/preferences.py`**

```python
"""Durable shopper preferences (e.g. 'always organic'), stored as JSON on disk
so they apply automatically in later sessions without being restated."""

import json
import os

PREFS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "preferences.json")


def load_preferences() -> dict:
    if not os.path.exists(PREFS_PATH):
        return {}
    with open(PREFS_PATH) as f:
        return json.load(f)


def save_preference(key: str, value) -> dict:
    current = load_preferences()
    current[key] = value
    with open(PREFS_PATH, "w") as f:
        json.dump(current, f, indent=2)
    return current
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/Scripts/python -m pytest tests/test_preferences.py -v
```
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add agent/preferences.py tests/test_preferences.py
git commit -m "feat: add durable preferences storage"
```

---

### Task 4: Vision tool for photo search

**Files:**
- Create: `agent/vision.py`

**Interfaces:**
- Consumes: `anthropic.Anthropic` client (constructed from `ANTHROPIC_API_KEY`).
- Produces: `describe_product_image(client, image_bytes: bytes, media_type: str) -> dict` — returns `{"item": str, "search_keyword": str, "looks_organic": bool | None, "is_store_product": bool}`. `is_store_product` is the model's best guess at whether the photo shows a grocery/pantry item at all (used later by the off-topic guardrail for non-product photos like the elephant test image); it is not a store lookup.

This task has no automated test (it calls a live LLM). It is verified manually in Task 7.

- [ ] **Step 1: Implement `agent/vision.py`**

```python
"""Identifies a product from a photo using Claude's vision capability,
per PRD FR-10 / the describe_product_image tool."""

import base64
import json

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
    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=300,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": encoded},
                    },
                    {"type": "text", "text": VISION_PROMPT},
                ],
            }
        ],
    )
    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)
```

- [ ] **Step 2: Commit**

```bash
git add agent/vision.py
git commit -m "feat: add photo identification via Claude vision"
```

---

### Task 5: Tool schemas, dispatcher, and system prompt

**Files:**
- Create: `agent/tools.py`
- Create: `agent/system_prompt.py`
- Test: `tests/test_tools.py`

**Interfaces:**
- Consumes: `agent.db` (Task 2), `agent.preferences` (Task 3), `initial_setup.reviews_api.get_product_rating` (existing, untouched).
- Produces:
  - `TOOL_SCHEMAS: list[dict]` — Anthropic tool-use schema for `search_products`, `get_rating`, `checkout`, `get_order_history`, `save_preference`. (`describe_product_image` is called directly by the app layer when an image is attached, per Task 6 — not exposed as a schema the model invokes mid-loop, since the image bytes are supplied by Streamlit, not the model.)
  - `execute_tool(name: str, tool_input: dict) -> dict` — dispatches to the right function, returns a JSON-serializable result.
  - `agent.system_prompt.build_system_prompt(preferences: dict) -> str`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_tools.py
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import tools


def test_execute_search_products():
    result = tools.execute_tool("search_products", {"keyword": "honey", "is_organic": True})
    assert len(result["products"]) == 4
    assert all(p["is_organic"] == 1 for p in result["products"])


def test_execute_get_rating():
    result = tools.execute_tool("get_rating", {"product_id": 1})
    assert result["product_id"] == 1
    assert result["average_rating"] > 0
    assert result["review_count"] > 0


def test_execute_get_order_history_empty_or_list():
    result = tools.execute_tool("get_order_history", {})
    assert "orders" in result
    assert isinstance(result["orders"], list)


def test_execute_checkout_places_order():
    result = tools.execute_tool("checkout", {"product_id": 32})
    assert result["order_id"] is not None
    assert result["product_name"] == "Soy Milk"


def test_execute_save_preference():
    result = tools.execute_tool("save_preference", {"key": "organic_only", "value": True})
    assert result["preferences"]["organic_only"] is True


def test_unknown_tool_raises():
    import pytest
    with pytest.raises(ValueError):
        tools.execute_tool("not_a_real_tool", {})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/Scripts/python -m pytest tests/test_tools.py -v
```
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `agent/tools.py`**

```python
"""Tool schemas (Anthropic tool-use format) and the dispatcher that executes
them, per PRD section 7."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import db, preferences
from initial_setup.reviews_api import get_product_rating

TOOL_SCHEMAS = [
    {
        "name": "search_products",
        "description": "Keyword search across product name, description, and category, with optional price and organic filters.",
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "Search term, e.g. 'honey' or 'oat milk'."},
                "max_price": {"type": "number", "description": "Maximum price, inclusive. Omit if no price cap was stated."},
                "is_organic": {"type": "boolean", "description": "True to return only organic products. Omit if not stated."},
            },
            "required": ["keyword"],
        },
    },
    {
        "name": "get_rating",
        "description": "Average rating and review count for one product, from the reviews API.",
        "input_schema": {
            "type": "object",
            "properties": {"product_id": {"type": "integer"}},
            "required": ["product_id"],
        },
    },
    {
        "name": "checkout",
        "description": "Places an order for exactly one product. Only call this after the shopper has explicitly confirmed which product, and only with a product ID that came from a list already shown to the shopper.",
        "input_schema": {
            "type": "object",
            "properties": {"product_id": {"type": "integer"}},
            "required": ["product_id"],
        },
    },
    {
        "name": "get_order_history",
        "description": "Returns everything the shopper has ordered before.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "save_preference",
        "description": "Persists a standing shopper preference so it applies automatically in future sessions. Use key 'organic_only' (boolean) for statements like 'I always want organic', or 'max_price' (number) for statements like 'never show me anything over $20'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "enum": ["organic_only", "max_price"]},
                "value": {},
            },
            "required": ["key", "value"],
        },
    },
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/Scripts/python -m pytest tests/test_tools.py -v
```
Expected: PASS (6 passed).

- [ ] **Step 5: Implement `agent/system_prompt.py`**

```python
"""System prompt for ShopMate: role, the three flows, the output format,
and the guardrails, per PRD sections 6 and 8."""

BASE_PROMPT = """You are ShopMate, a shopping assistant for a small online pantry store (honey, oils, nuts and seeds, grains, tea and coffee, snacks, dairy alternatives).

## The three flows

- Browsing: the shopper describes what they want. Search for candidates, fetch the rating for each candidate, apply any minimum-rating filter the shopper stated, and present the list. Do not order.
- Photo search: if the shopper's message includes a description of an uploaded photo (identified item, search keyword, organic guess), use that keyword to search, then continue exactly like browsing.
- Ordering: the shopper confirms a choice from a list you already showed (e.g. "the second one", "order #3", "yes"). Take the product ID from that list. Never guess an ID, and never call checkout for a product you have not just shown.

## Output format

Every product list uses exactly this format, one blank line between entries, always including the ID:

#1. Organic Raw Honey (ID:1) — $14.99 ★4.62 — organic

#2. Organic Buckwheat Honey (ID:5) — $18.99 ★4.62 — organic

Only append " — organic" for products where is_organic is true; omit it otherwise. If exactly one product qualifies, still show it as a one-item list, then ask: "Would you like to order it? Just say yes or give me the number."

## Memory and preferences

{preferences_block}

When the shopper states a standing preference ("I always want organic", "never show me anything over $20"), call save_preference to store it, then confirm briefly. Apply stored preferences automatically to every future search unless the shopper's current message overrides them for that one request.

## Guardrails

- Never call checkout without an explicit confirmation from the shopper for a specific product.
- Never state a product, price, or rating that did not come from a tool result.
- If the request has nothing to do with shopping in this store, politely redirect the shopper back to shopping. Do not call any tool for such a request.
"""


def build_system_prompt(preferences: dict) -> str:
    if preferences:
        parts = []
        if preferences.get("organic_only"):
            parts.append("- Always filter to organic products unless the shopper says otherwise for this message.")
        if preferences.get("max_price") is not None:
            parts.append(f"- Always apply a maximum price of {preferences['max_price']} unless the shopper states a different cap for this message.")
        preferences_block = "The shopper has these standing preferences from earlier sessions:\n" + "\n".join(parts) if parts else "The shopper has no standing preferences yet."
    else:
        preferences_block = "The shopper has no standing preferences yet."

    return BASE_PROMPT.format(preferences_block=preferences_block)
```

- [ ] **Step 6: Commit**

```bash
git add agent/tools.py agent/system_prompt.py tests/test_tools.py
git commit -m "feat: add tool dispatcher and system prompt"
```

---

### Task 6: Agent loop (Anthropic tool-use)

**Files:**
- Create: `agent/client.py`

**Interfaces:**
- Consumes: `agent.tools.TOOL_SCHEMAS`, `agent.tools.execute_tool`, `agent.system_prompt.build_system_prompt`, `agent.preferences.load_preferences`, `agent.vision.describe_product_image`.
- Produces: `class ShopMateAgent` with:
  - `__init__(self, api_key: str)`
  - `run_turn(self, history: list[dict], user_text: str, image: tuple[bytes, str] | None = None) -> tuple[str, list[dict]]` — `image` is `(image_bytes, media_type)` or `None`. Returns `(assistant_reply_text, updated_history)`, where `updated_history` is the full Anthropic-format message list including this turn, to be passed back in on the next call.

No automated test here (live LLM calls, non-deterministic) — verified manually in Task 7.

- [ ] **Step 1: Implement `agent/client.py`**

```python
"""The ShopMate tool-use loop: sends the conversation to Claude, executes any
tool calls it makes, and loops until Claude produces a final text reply."""

import anthropic

from agent.preferences import load_preferences
from agent.system_prompt import build_system_prompt
from agent.tools import TOOL_SCHEMAS, execute_tool
from agent.vision import describe_product_image

MODEL = "claude-sonnet-5"


class ShopMateAgent:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)

    def run_turn(self, history: list[dict], user_text: str, image: tuple[bytes, str] | None = None):
        content = []
        if image is not None:
            image_bytes, media_type = image
            described = describe_product_image(self.client, image_bytes, media_type)
            content.append({
                "type": "text",
                "text": (
                    f"[Shopper uploaded a photo. Identified as: {described['item']}. "
                    f"Suggested search keyword: {described['search_keyword']}. "
                    f"Looks organic: {described['looks_organic']}. "
                    f"Looks like a store product: {described['is_store_product']}.]\n\n{user_text}"
                ),
            })
        else:
            content.append({"type": "text", "text": user_text})

        messages = history + [{"role": "user", "content": content}]
        system_prompt = build_system_prompt(load_preferences())

        while True:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=1024,
                system=system_prompt,
                tools=TOOL_SCHEMAS,
                messages=messages,
            )

            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                final_text = "".join(block.text for block in response.content if block.type == "text")
                return final_text, messages

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                result = execute_tool(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(result),
                })
            messages.append({"role": "user", "content": tool_results})
```

- [ ] **Step 2: Commit**

```bash
git add agent/client.py
git commit -m "feat: add Claude tool-use loop for ShopMate"
```

---

### Task 7: Streamlit chat UI with image upload

**Files:**
- Create: `app.py`

**Interfaces:**
- Consumes: `agent.client.ShopMateAgent`.
- Produces: a runnable Streamlit app — no further tasks depend on this.

- [ ] **Step 1: Implement `app.py`**

```python
"""ShopMate — Streamlit chat interface with image upload."""

import os

import streamlit as st
from dotenv import load_dotenv

from agent.client import ShopMateAgent

load_dotenv()

st.set_page_config(page_title="ShopMate", page_icon="🛒")
st.title("🛒 ShopMate")
st.caption("Tell me what you're looking for, or upload a photo of a product.")

api_key = os.environ.get("ANTHROPIC_API_KEY")
if not api_key or api_key == "your-key-here":
    st.error("Set ANTHROPIC_API_KEY in .env before using ShopMate.")
    st.stop()

if "agent" not in st.session_state:
    st.session_state.agent = ShopMateAgent(api_key=api_key)
if "anthropic_history" not in st.session_state:
    st.session_state.anthropic_history = []
if "display_history" not in st.session_state:
    st.session_state.display_history = []

for turn in st.session_state.display_history:
    with st.chat_message(turn["role"]):
        if turn.get("image"):
            st.image(turn["image"], width=200)
        st.markdown(turn["text"])

uploaded_image = st.file_uploader("Upload a product photo (optional)", type=["png", "jpg", "jpeg"])
user_text = st.chat_input("What are you looking for?")

if user_text:
    image_arg = None
    if uploaded_image is not None:
        image_bytes = uploaded_image.getvalue()
        media_type = uploaded_image.type or "image/png"
        image_arg = (image_bytes, media_type)

    st.session_state.display_history.append({
        "role": "user",
        "text": user_text,
        "image": uploaded_image.getvalue() if uploaded_image is not None else None,
    })
    with st.chat_message("user"):
        if uploaded_image is not None:
            st.image(uploaded_image, width=200)
        st.markdown(user_text)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            reply_text, updated_history = st.session_state.agent.run_turn(
                st.session_state.anthropic_history, user_text, image_arg
            )
        st.markdown(reply_text)

    st.session_state.anthropic_history = updated_history
    st.session_state.display_history.append({"role": "assistant", "text": reply_text, "image": None})
```

- [ ] **Step 2: Launch and smoke-test with `preview_start`**

Use `.claude/launch.json`:
```json
{
  "version": "0.0.1",
  "configurations": [
    {
      "name": "shopmate",
      "runtimeExecutable": ".venv/Scripts/streamlit.exe",
      "runtimeArgs": ["run", "app.py"],
      "port": 8501
    }
  ]
}
```

Then, in the browser preview, run through every check from `assignment.md` Step 2:
1. "organic honey with 4.5+ rating under $20" → Organic Raw Honey, Organic Buckwheat Honey, Organic Acacia Honey (not Manuka).
2. "cheapest oat milk" → Oat Milk at $4.49.
3. Upload `resources/honey.png`, "find this" → a list of honeys.
4. "yes" after a single-item list → an order confirmation with an order ID.
5. "what have I ordered before?" → the order just placed.
6. "I always want organic", then restart the Streamlit app (not just the browser tab) and search for honey → only organic honeys.

Fix anything that misses, re-run all six checks after each fix.

- [ ] **Step 3: Commit**

```bash
git add app.py .claude/launch.json
git commit -m "feat: add Streamlit chat UI with image upload"
```

---

### Task 8: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md`** covering: what ShopMate is (one paragraph, from PRD §1), prerequisites, how to set up `.env`, how to install dependencies, how to create `store.db`, how to run the app (`streamlit run app.py`), how to run the tests (`pytest`), and a placeholder line for the Step 3 demo Loom link (`## Demo\n\n<Loom link>`).

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README with setup and run instructions"
```

---

## Self-Review Notes

- Spec coverage: FR-01–04 → Task 2/5 (`search_products` + filters). FR-05 → Task 5 (`get_rating` via `reviews_api`, never direct query). FR-06/07 → Task 5 system prompt. FR-08/09 → Task 5 (`checkout` schema description) + Task 6 (loop only calls tools the model chooses). FR-10 → Task 4 + Task 6. FR-11 → Task 2/5 (`get_order_history`). FR-12 → Task 3/5/6 (`save_preference`, `build_system_prompt` reads `load_preferences` fresh every turn, so a restart picks it up). Tools table (§7) → Task 5 `TOOL_SCHEMAS`. Guardrails (§8) → system prompt in Task 5. Chat + image upload → Task 7.
- No placeholders: all code blocks are complete, no TBDs.
- Type consistency checked: `db.search_products` / `execute_tool` / `TOOL_SCHEMAS` all agree on `keyword, max_price, is_organic`; `describe_product_image` return keys (`item`, `search_keyword`, `looks_organic`, `is_store_product`) match how Task 6 reads them.
