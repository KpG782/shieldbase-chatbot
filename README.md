# ShieldBase Insurance Assistant

ShieldBase is a hybrid insurance chatbot built around two coordinated behaviors in one session:

- conversational RAG for insurance and coverage questions
- deterministic quote collection for `auto`, `home`, and `life`

The backend is the source of truth for both chat state and quote state. Users can start a quote, interrupt it with a product question, and continue without losing progress.

## Current Capabilities

- Answer insurance questions from the knowledge base
- Start quotes for `auto`, `home`, and `life`
- Collect quote details step by step with field-level validation
- Preserve quote progress when the user asks a mid-flow product question
- Resume the exact pending quote field after the interruption
- Support `accept`, `adjust`, and `restart` after quote generation
- Support switching from one product quote to another in the same session
- Stream responses over SSE
- Show quote summaries in the UI
- Export quote details as:
  - `Copy JSON`
  - `Download JSON`
  - `Download CSV` for Excel

## Chat Modes

### `Conversational mode`

Used for policy and coverage questions. The backend retrieves knowledge-base chunks, generates an answer, and streams it back to the UI.

### `Transactional mode`

Used for quote flows. The backend identifies the product, collects required fields, validates them, calculates a deterministic premium, and moves the user into confirmation.

The system is explicitly designed to move between these two modes without dropping session state.

## Quote Flow

For quotes, the backend graph follows this shape:

```text
identify product -> collect details -> validate -> confirm
```

Important behavior:

- explicit quote-start messages like `I want a quote for auto insurance` are routed into the quote flow
- bare field replies like `2019` stay in the transactional branch instead of drifting into RAG
- compact auto inputs like `Toyota, Camry, 35, 0, standard` can fill multiple fields in sequence
- if the user asks a product question during collection, the assistant answers it and appends the exact resume prompt for the pending field
- `adjust` clears the current quote result and reopens collection from the first required field

## Stack

| Component | Technology |
|-----------|-----------|
| Backend orchestration | Python + LangGraph `StateGraph` |
| API layer | FastAPI + Server-Sent Events |
| LLM | OpenRouter |
| Retrieval | ChromaDB + sentence-transformers |
| Frontend | Next.js App Router + React + Tailwind CSS |
| Quote logic | Deterministic Python calculator |
| Session persistence | In-memory with Redis support |

## High-Level Request Path

```text
Browser -> Next.js UI -> /api/chat proxy -> FastAPI /chat
                                           |
                                           v
                                  LangGraph state machine
                                           |
                     +---------------------+----------------------+
                     |                                            |
                     v                                            v
                  RAG path                                  quote workflow
         retrieve -> answer -> stream               identify -> collect -> validate -> confirm
```

## Frontend UX

The UI includes:

- authenticated access flow before entering the workspace
- chat session state indicators for mode and step
- local conversation history
- quote summary cards
- a confirmation page gated by backend quote state
- compact quote export actions in the quote card

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
│   ├── src/
│   └── package.json
├── docs/
├── tests/
├── QUOTE_FLOW_TEST_CHECKLIST.md
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

## Validation

Backend integration coverage includes:

- health and reset endpoints
- auto, home, and life quote flows
- interruption and resume behavior
- invalid input re-prompts
- product switching mid-flow
- `adjust` and `restart`
- protection against LLM misclassification of quote-start and quote-field replies
- compact multi-field auto input handling

Run the backend test suite with:

```powershell
cd C:\Users\kpg78\Downloads\TENEXT\shieldbase-chatbot
.\backend\.venv\Scripts\python.exe -m pytest tests\test_backend_integration.py -q
```

## Key Invariants

- backend state is the source of truth
- quote calculation is deterministic, not LLM-generated
- invalid field input must not advance the quote step
- mid-quote product questions must not clear `collected_data`
- quote-start intents must not be downgraded into generic RAG
- the frontend renders backend state; it should not invent quote state on its own

## Useful Docs

- [Quote flow test checklist](/C:/Users/kpg78/Downloads/TENEXT/shieldbase-chatbot/QUOTE_FLOW_TEST_CHECKLIST.md)
- [ASCII architecture](/C:/Users/kpg78/Downloads/TENEXT/shieldbase-chatbot/docs/architecture/ASCII_ARCHITECTURE.md)
- [Architecture decisions](/C:/Users/kpg78/Downloads/TENEXT/shieldbase-chatbot/docs/architecture/ARCHITECTURE_DECISIONS.md)
- [Plain-English overview](/C:/Users/kpg78/Downloads/TENEXT/shieldbase-chatbot/docs/layman/OVERVIEW_IN_PLAIN_ENGLISH.md)
- [Local run guide](/C:/Users/kpg78/Downloads/TENEXT/shieldbase-chatbot/docs/guides/LOCAL_RUN_INSTRUCTIONS.md)
