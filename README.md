# RPG Document Intelligence Pipeline

## Project Layout

```text
data/                 Sample input documents
docs/                 Challenge and schema references
frontend/             React/Vite UI
scripts/              Manual local smoke checks
src/
  api/                FastAPI app and routes
  core/               Config, enums, models, and shared utilities
  ingestion/          Discovery, content extraction, and OCR
  classification/     Classifier and semantic strategies
  knowledge/          Note-derived knowledge loading and lookup
  parsing/            Business document parsers
  persistence/        SQLite models, session setup, and repositories
  llm/                Local LLM/VLM client adapters
  reconciliation/     Note/entity linking and deterministic review items
  reporting/          Final report assembly
  services/           Application-level analysis services and progress state
  tests/              Unit tests
```

## CLI

```bash
python src/main.py
```

The pipeline discovers files in `data/shoebox/`, builds a `DocumentContext` for each
file, enriches it through format detection, content extraction, semantic
classification, and business parsing, then prints parsed entities and summaries.

## Local LLM For Notes

The system uses a local LLM/VLM client to extract structured knowledge from
free-form notes.

- Default provider: `qwen_vl`
- Default model: `Qwen/Qwen2.5-VL-3B-Instruct`
- No API keys
- No external APIs
- No cloud services
- Only used for notes
- Invoices, statements, and receipts remain deterministic parsers

Override the local model:

```bash
LLM_MODEL=Qwen/Qwen2.5-VL-3B-Instruct python src/main.py
```

If the local LLM is unavailable, note knowledge extraction is skipped and the
rest of the pipeline continues.

The LLM is only used where language understanding adds value: informal notes
that contain document context, financial context, applicability notes, and
action items. Review items are generated deterministically during
reconciliation.

Manual local LLM checks:

```bash
PYTHONPATH=src python scripts/llm_connection_check.py
PYTHONPATH=src python scripts/transformers_note_smoke.py
```

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

## Tests

```bash
PYTHONPATH=src python -m unittest src.tests.test_classification_node \
  src.tests.test_statement_parser \
  src.tests.test_knowledge_store \
  src.tests.test_llm_note_context_parser \
  src.tests.test_reconciliation_findings
```
