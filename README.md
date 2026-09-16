# ShopMate

ShopMate is a conversational shopping assistant for a small online pantry store (honey, oils, nuts and seeds, grains, tea and coffee, snacks, dairy alternatives). Instead of clicking through category pages and filters, a shopper describes what they want in plain language, or uploads a photo, and ShopMate searches the store, shows ratings, and places the order once the shopper confirms. Full requirements are in [PRD.md](PRD.md).

## Prerequisites

- Python 3.10+
- A [Groq](https://console.groq.com) API key

## Setup

1. Create and activate a virtual environment, then install dependencies:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Add your Groq API key to `.env`:

   ```
   GROQ_API_KEY=your-key-here
   ```

3. Create the store database (safe to re-run; it resets products/reviews and leaves orders alone):

   ```bash
   python initial_setup/setup_db.py
   ```

## Run

```bash
streamlit run app.py
```

Opens a chat UI at `http://localhost:8501`. Type what you're looking for, or upload a product photo (PNG/JPG) alongside your message.

Preferences ("I always want organic") persist in `preferences.json` and orders persist in `store.db`, so both survive an app restart. The conversation itself resets when the app restarts.

## Test

```bash
pytest
```

Runs the automated tests for the database, preferences, and tool-dispatcher layers (`tests/`). The LLM agent loop, vision tool, and UI are verified manually against the checklist in `assignment.md`.

## Demo

<Loom link>

## Architecture

- `agent/db.py` — SQLite access for `products` and `orders`
- `agent/preferences.py` — durable shopper preferences (`preferences.json`)
- `agent/vision.py` — photo identification via Groq's vision-capable model
- `agent/tools.py` — the five tool schemas and their dispatcher
- `agent/system_prompt.py` — the three flows, output format, and guardrails
- `agent/client.py` — the Groq tool-use loop
- `app.py` — the Streamlit chat interface

See [docs/superpowers/plans/2026-09-16-shopping-agent.md](docs/superpowers/plans/2026-09-16-shopping-agent.md) for the implementation plan this was built from.
