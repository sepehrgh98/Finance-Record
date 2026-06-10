# RPG Document Intelligence Pipeline

## Running

```bash
python src/main.py
```

The pipeline discovers files in `shoebox/`, builds a `DocumentContext` for each
file, enriches it through format detection, content extraction, semantic
classification, and business parsing, then prints parsed entities and summaries.

## Optional Local LLM For Notes

The system can optionally use a local LLM to enrich free-form note parsing.

- Backend: Ollama local HTTP endpoint at `http://localhost:11434/api/generate`
- Default model: `llama3.2:3b`
- No API keys
- No external APIs
- No cloud services
- Only used for notes
- Invoices, statements, and receipts remain deterministic parsers
- Deterministic note parsing always runs first and remains the fallback

Enable local LLM note enrichment:

```bash
USE_LOCAL_LLM_FOR_NOTES=true LLM_MODEL=llama3.2:3b python src/main.py
```

If Ollama is not running, the system keeps the deterministic note parser result.

The LLM is only used where language understanding adds value: informal notes
that contain generic rules, claims, and action items. Note parsing extracts
semantic facts only; business interpretation is deferred to a later
reconciliation stage that can validate them against parsed invoices,
statements, and receipts.

## Full-Stack App

Install backend dependencies:

```bash
pip install -r requirements.txt
```

Run the FastAPI backend:

```bash
PYTHONPATH=src uvicorn api.main:app --reload
```

Run the React frontend:

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/analyze` and `/health` to
`http://127.0.0.1:8000`.
