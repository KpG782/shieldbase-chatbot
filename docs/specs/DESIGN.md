# DESIGN.md — State Machine Design & Key Decisions

## State Machine Design

### States

The chatbot operates in one of two **modes**, with the transactional mode having four **steps**:

```
Modes:
  conversational  — answering product questions via RAG
  transactional   — collecting info and generating a quote

Transactional Steps:
  identify  — determining which insurance product (auto/home/life)
  collect   — gathering product-specific details
  validate  — checking inputs are reasonable
  confirm   — user accepts, adjusts, or restarts
```

### Intent Classification

Every user message is classified into one of three intents:

| Intent | Meaning | Routing |
|--------|---------|---------|
| `question` | User is asking about insurance products | → RAG node |
| `quote` | User wants to get/start a quote | → Transactional flow |
| `response` | User is answering a bot-initiated prompt | → Current transactional step |

The `response` intent is critical. Without it, a user replying "2019 Toyota Camry" to the bot's question about their vehicle would be misclassified as a new intent.

### Edge Conditions (Conditional Routing)

```python
def route_after_router(state: ChatState) -> str:
    intent = state["intent"]
    mode = state["mode"]
    
    if intent == "question":
        return "rag_answer"
    
    if intent == "quote":
        if not state.get("insurance_type"):
            return "identify_product"
        return "collect_details"
    
    if intent == "response":
        step = state.get("quote_step", "identify")
        step_to_node = {
            "identify": "identify_product",
            "collect": "collect_details",
            "validate": "validate_quote",
            "confirm": "confirm",
        }
        return step_to_node.get(step, "router")
    
    return "rag_answer"  # default fallback
```

### Graceful Mid-Flow Transitions

This is the most important design decision. When a user asks a question while mid-quote:

```
State BEFORE question:
  mode: transactional
  quote_step: collect
  insurance_type: auto
  collected_data: { vehicle_year: 2019, make: "Toyota" }

User: "Wait, what does comprehensive coverage include?"

State DURING question:
  mode: transactional          ← NOT reset
  pending_question: "what does comprehensive coverage include?"
  collected_data: preserved    ← NOT cleared

→ Routes to rag_answer node
→ RAG answers the question
→ Checks: mode == transactional? Yes → return to collect_details
→ Bot: "Comprehensive coverage includes... Now, what model is your vehicle?"

State AFTER question:
  mode: transactional
  quote_step: collect
  collected_data: { vehicle_year: 2019, make: "Toyota" }  ← intact
```

## Product-Specific Collection Fields

### Auto Insurance
| Field | Type | Validation |
|-------|------|-----------|
| vehicle_year | int | 1900 < year ≤ current_year |
| vehicle_make | string | non-empty |
| vehicle_model | string | non-empty |
| driver_age | int | 16 ≤ age ≤ 120 |
| accidents_last_5yr | int | 0 ≤ count ≤ 10 |
| coverage_level | enum | basic / standard / comprehensive |

### Home Insurance
| Field | Type | Validation |
|-------|------|-----------|
| property_type | enum | house / condo / apartment |
| location | string | non-empty |
| estimated_value | float | > 0 |
| year_built | int | 1800 < year ≤ current_year |
| coverage_level | enum | basic / standard / comprehensive |

### Life Insurance
| Field | Type | Validation |
|-------|------|-----------|
| age | int | 18 ≤ age ≤ 85 |
| health_status | enum | excellent / good / fair / poor |
| smoker | bool | true / false |
| coverage_amount | float | > 0 |
| term_years | enum | 10 / 20 / 30 |
| coverage_level | enum | basic / standard / comprehensive |

## Quote Calculation

Simple formula: `base_rate × risk_multipliers`

```
Auto:  base × age_factor × history_factor × vehicle_age_factor
Home:  base × property_value_factor × age_factor
Life:  base × age_factor × health_factor × smoker_factor × term_factor
```

The formulas are intentionally simple. This is a chatbot assessment, not actuarial modeling.

## Error Handling Strategy

| Error | Handling |
|-------|---------|
| OpenRouter API failure | Return a controlled fallback answer or error without breaking session state |
| Invalid user input | Re-ask for that specific field with explanation |
| ChromaDB empty/missing | Return fallback "I don't have info on that" response |
| Unclassifiable intent | Default to conversational mode (safer than assuming transactional) |
| Session state corruption | Reset to clean state, inform user |

## Latency Optimizations

1. **SSE streaming** — tokens render as they generate
2. **Startup ingestion** — build or load the vector index at backend startup to avoid empty first-query retrieval
3. **Embedding cache** — knowledge base embedded once at startup, persisted to disk
4. **Small classifier prompt** — intent detection uses ~100 tokens, fast turnaround
