# ShieldBase Insurance Assistant

ShieldBase is a hybrid insurance chatbot built for a technical take-home assessment. It combines:

- conversational RAG for insurance questions
- a deterministic quote workflow for `auto`, `home`, and `life`
- backend-controlled state so users can interrupt a quote, ask a question, and resume cleanly

## What It Does

The app supports two modes in one conversation:

- `Conversational mode`
  Answers grounded insurance questions from the knowledge base.
- `Transactional mode`
  Collects quote details step by step, validates inputs, calculates a deterministic quote, and supports confirm / adjust / restart.

The core requirement is graceful switching between those two modes without losing state.

## Current Stack

| Component | Technology |
|-----------|-----------|
| Backend orchestration | Python + LangGraph-style state machine |
| API layer | FastAPI + SSE streaming |
| LLM | OpenRouter |
| Retrieval | ChromaDB + sentence-transformers |
| Frontend | Next.js App Router + React + Tailwind CSS |
| Quote logic | Deterministic Python calculator |

## High-Level Flow

```text
User -> Next.js UI -> /api/chat proxy -> FastAPI /chat
                                  |
                                  v
                         run_graph(state, message)
                                  |
                 +----------------+----------------+
                 |                                 |
                 v                                 v
              RAG path                    quote workflow path
      retrieve -> answer -> resume   identify -> collect -> validate
                                                -> quote -> confirm
```

For the fuller engineering diagrams, see:

- [ASCII architecture](/C:/Users/kpg78/Downloads/TENEXT/shieldbase-chatbot/docs/architecture/ASCII_ARCHITECTURE.md)
- [Architecture decisions](/C:/Users/kpg78/Downloads/TENEXT/shieldbase-chatbot/docs/architecture/ARCHITECTURE_DECISIONS.md)
- [Plain-English overview](/C:/Users/kpg78/Downloads/TENEXT/shieldbase-chatbot/docs/layman/OVERVIEW_IN_PLAIN_ENGLISH.md)

## Project Structure

```text
shieldbase-chatbot/
├── backend/
│   ├── main.py
│   ├── graph.py
│   ├── state.py
│   ├── nodes/
│   ├── services/
│   ├── knowledge_base/
│   └── requirements.txt
├── frontend/
│   ├── app/
│   ├── public/
│   ├── src/
│   └── package.json
├── docs/
│   ├── architecture/
│   ├── audits/
│   ├── design/
│   ├── guides/
│   ├── layman/
│   ├── plans/
│   ├── prompts/
│   ├── reports/
│   └── specs/
├── tests/
└── README.md
```

## Local Run

### Backend

```powershell
cd backend
.venv\Scripts\Activate.ps1
python -m uvicorn main:app --reload --port 8000
```

### Frontend

```powershell
cd frontend
npm run dev
```

Open `http://localhost:3000`.

More detailed instructions:

- [Local run guide](/C:/Users/kpg78/Downloads/TENEXT/shieldbase-chatbot/docs/guides/LOCAL_RUN_INSTRUCTIONS.md)
- [Purpose and flow](/C:/Users/kpg78/Downloads/TENEXT/shieldbase-chatbot/docs/guides/PURPOSE_AND_FLOW.md)
- [Knowledge base setup](/C:/Users/kpg78/Downloads/TENEXT/shieldbase-chatbot/docs/guides/KNOWLEDGE_BASE_SETUP.md)

## Main Backend Invariant

For transactional inputs, the backend now follows this order:

1. read `current_field`
2. validate the user input for that field
3. if invalid, re-prompt the same field
4. if valid, store it and move to the next field

That prevents late-validation bugs and keeps `collected_data` clean.

## Reviewer Notes

The important design choices are:

- backend state is the source of truth
- frontend renders state, it does not invent it
- quote calculation is deterministic, not LLM-generated
- RAG and transactional logic are separate but share one session

The repo also includes submission-focused docs:

- [Final submission audit](/C:/Users/kpg78/Downloads/TENEXT/shieldbase-chatbot/docs/reports/FINAL_SUBMISSION_AUDIT.md)
- [Hardening report](/C:/Users/kpg78/Downloads/TENEXT/shieldbase-chatbot/docs/reports/HARDENING_REPORT.md)
- [Docs index](/C:/Users/kpg78/Downloads/TENEXT/shieldbase-chatbot/docs/README.md)
