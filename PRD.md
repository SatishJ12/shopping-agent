# Product Requirements Document — ShopMate

**Date:** 2026-09-16
**Author:** Satish Jaiswal

---

## 1. Overview

ShopMate is a conversational shopping assistant for a small online pantry store stocking 32 products across honey, oils, nuts and seeds, grains, tea and coffee, snacks, and dairy alternatives, roughly half of them organic, priced from about $3.50 to $30. Instead of clicking through category pages and filter menus, a shopper tells the assistant what they want in plain language, or shows it a photo, and the assistant finds the right products, shows how other customers rated them, and places the order once the shopper says yes.

---

## 2. Problem

- A busy shopper who already knows roughly what they want still has to click through category pages and filter menus to find it.
- Checking how well a product is rated means looking it up separately instead of seeing it alongside the product.
- Shoppers have to repeat their constraints and preferences (like "always organic" or "nothing over $20") every time, instead of the store remembering them.

---

## 3. Goals

| Goal | How we know |
|------|-------------|
| Given a query with constraints, the right products come back and the wrong ones do not | Every product returned respects any stated price cap, organic-only filter, and minimum rating |
| The product list is always in the same format | Every list uses the exact `#N. <Name> (ID:X) — $<price> ★<rating> — organic` line format |
| The assistant never orders on its own, and never orders the wrong product | `checkout` is only called after explicit shopper confirmation, using a product ID from a list already shown |
| Off-topic requests are politely redirected | Requests unrelated to shopping in this store do not get a substantive answer or a tool call |
| Preferences stated once are honoured next time | A preference set in one session is applied automatically in a later session without the shopper repeating it |

---

## 4. Non-Goals

- No shopping cart with multiple items or quantities. One product per order.
- No payments, returns, cancellations, or delivery tracking.
- No login or multi-user support. Assume a single shopper.
- No document retrieval (RAG). The store data is structured, and that is enough.

---

## 5. Users

A busy shopper who already knows roughly what they want. They do not want to browse. They want to say "organic honey under $20 with at least a 4.5 rating" and be done in two messages.

---

## 6. Functional Requirements

### 6.1 Search

| ID | Requirement |
|----|-------------|
| FR-01 | Given a text query, the agent searches products by keyword across name, description, and category and returns matching products. |
| FR-02 | The agent applies a maximum price filter when the shopper states a price cap. |
| FR-03 | The agent applies an organic-only filter when the shopper asks for organic products. |
| FR-04 | The agent applies a minimum-rating filter when the shopper states one, after fetching ratings for the candidate products. |

### 6.2 Ratings

| ID | Requirement |
|----|-------------|
| FR-05 | Every product shown comes with its average customer rating and review count, fetched from the reviews API — never by querying the reviews table directly. |

### 6.3 Output format

Every product list uses exactly this line format, plain text, one blank line between entries. The `(ID:X)` is mandatory — it is how the agent knows what to order later.

| ID | Requirement |
|----|-------------|
| FR-06 | Every product list is rendered in the exact format below, with one blank line between entries and the `(ID:X)` always present. |
| FR-07 | If exactly one product qualifies, it is still shown as a list, followed by: "Would you like to order it? Just say yes or give me the number." |

```
#1. Organic Raw Honey (ID:1) — $14.99 ★4.62 — organic

#2. Organic Buckwheat Honey (ID:5) — $18.99 ★4.62 — organic
```

### 6.4 Ordering

| ID | Requirement |
|----|-------------|
| FR-08 | The agent places an order only after the shopper confirms a specific product from a list it has already shown (e.g. "the second one", "order #3", "yes"). |
| FR-09 | The agent takes the product ID from the list it showed earlier and calls `checkout`. It never guesses an ID. |

### 6.5 Photo search

| ID | Requirement |
|----|-------------|
| FR-10 | When the shopper provides an image, the agent works out what the product is, a search keyword, and whether it looks organic, then continues with the browsing flow (search, ratings, filters, list). |

### 6.6 Memory and preferences

| ID | Requirement |
|----|-------------|
| FR-11 | "What have I ordered before?" is answered from the orders table. |
| FR-12 | Preferences the shopper states (e.g. "I always want organic", "never show me anything over $20") persist across sessions and are applied automatically in future sessions without the shopper repeating them. Where and how they are stored is an implementation decision that must be documented. |

---

## 7. Tools

| Tool | What it does | Backed by |
|------|--------------|-----------|
| `search_products` | Keyword search across name, description, and category, with optional `max_price` and `is_organic` filters. | `products` table |
| `get_rating` | Average rating and review count for a product. | `reviews_api.py` |
| `checkout` | Places an order for one product and returns a confirmation with the order ID. | `orders` table |
| `describe_product_image` | Takes an image, returns what the product is, a search keyword, and whether it looks organic. | A vision-capable model |
| `get_order_history` | Returns what the shopper has ordered before. | `orders` table |

Additional tools may be added beyond this list; each one must have a clear reason for existing.

---

## 8. Guardrails

| ID | Guardrail | Enforced by |
|----|-----------|-------------|
| GR-01 | Never place an order without an explicit confirmation from the shopper. | Ordering flow (FR-08, FR-09) |
| GR-02 | Never invent a product, a price, or a rating that is not in the store data. | Tool results only — no data is stated unless it came from `search_products` or `get_rating` |
| GR-03 | Never answer requests that have nothing to do with shopping in this store. | Prompt — off-topic requests are politely redirected instead of answered |

---

## 9. Demonstration Scenarios

### Scenario 1 — Text search with constraints

User: `I want organic honey under $20 with at least a 4.5 rating`

Expected:

```text
→ search_products(keyword="honey", is_organic=true, max_price=20)
→ get_rating for each candidate, filtered to rating ≥ 4.5
→ Product list in the standard format, each entry with (ID:X)
```

### Scenario 2 — Single matching product

User: `<a query that returns exactly one qualifying product>`

Expected:

```text
→ The one product shown as a one-item list
→ "Would you like to order it? Just say yes or give me the number."
```

### Scenario 3 — Photo search

User: `<uploads a photo of a jar of honey>`

Expected:

```text
→ describe_product_image identifies the product as honey (and whether it looks organic)
→ search_products with the resulting keyword
→ Same product list format as browsing
```

### Scenario 4 — Ordering after browsing

User: `the second one` (after a product list was already shown)

Expected:

```text
→ checkout(product_id=<ID of the second item from the list already shown>)
→ Confirmation with the order ID
```

### Scenario 5 — Order history

User: `What have I ordered before?`

Expected:

```text
→ get_order_history()
→ Past orders from the orders table
```

### Scenario 6 — Preference stated once, honoured later

User (an earlier session): `I always want organic`

User (a later session): `Show me tea`

Expected:

```text
→ Preference "organic only" applied automatically
→ search_products(keyword="tea", is_organic=true)
```

### Scenario 7 — Guardrail: no order without confirmation

User: `I want honey` (no confirmation given)

Expected:

```text
→ search_products / get_rating, product list shown
→ checkout is not called
```

### Scenario 8 — Guardrail: off-topic request

User: `<a request unrelated to shopping in this store>`

Expected:

```text
→ No tool call
→ A polite redirect back to shopping in this store
```

---

## 10. Acceptance Criteria

- [ ] A query with stated constraints (price cap, organic, minimum rating) returns only products that satisfy all of them.
- [ ] Every product list uses the exact `#N. <Name> (ID:X) — $<price> ★<rating> — organic` format, with a blank line between entries.
- [ ] The assistant never places an order without an explicit confirmation from the shopper.
- [ ] The assistant never orders a product other than the one the shopper confirmed, and never guesses a product ID.
- [ ] The assistant never states a product, price, or rating that is not in the store data.
- [ ] Off-topic requests are politely redirected instead of answered.
- [ ] "What have I ordered before?" is answered correctly from the orders table.
- [ ] A preference stated once is applied automatically in a later session without being restated.

---

## 11. Technology and Build Instructions

| Component | Choice |
|-----------|--------|
| Language | Python 3.10+ |
| LLM provider and model | Groq (`qwen/qwen3.8-27b`), via its OpenAI-compatible API |
| Vision model | `qwen/qwen3.8-27b` — accepts image input, used for `describe_product_image` |
| UI | Streamlit |
| Preferences stored in | `preferences.json`, a small JSON file at the project root |

*Rules for Claude Code:*

1. Read `SETUP.md` first. Build on top of `initial_setup/`; do not modify it.
2. Ratings come only from `initial_setup/reviews_api.py`.
3. Keep API keys in `.env`.
4. Do not add anything outside this PRD.
