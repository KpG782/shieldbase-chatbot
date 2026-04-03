# Running The Project In Plain English

There are two parts to run.

## Backend

This is the part that:

- stores the conversation state
- reads the knowledge base
- decides the next quote step
- calculates the quote

It runs on port `8000`.

## Frontend

This is the website the user sees.

It runs on port `3000` and forwards chat requests to the backend.

## Start the backend

```powershell
cd backend
.venv\Scripts\Activate.ps1
python -m uvicorn main:app --reload --port 8000
```

## Start the frontend

```powershell
cd frontend
npm run dev
```

Then open `http://localhost:3000`.

## Easiest test flow

Try these in order:

1. `What does comprehensive coverage include?`
2. `I want a quote`
3. `home`
4. answer the requested fields with realistic values
5. ask another insurance question in the middle
6. continue until the quote is generated

If that works, the main end-to-end flow is working.
