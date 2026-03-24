---
title: VaultAI
emoji: 🔐
colorFrom: blue
colorTo: purple
sdk: docker
app_file: app.py
pinned: false
---

# VaultAI V3 🔐

**Intelligent Financial Strategy Platform — Plan, Invest, Simulate**

> V3 is live. V2 docs are preserved below for reference.

## 📋 Table of Contents

- [Overview](#overview)
- [What's New in V3](#whats-new-in-v3)
- [V3 Architecture](#v3-architecture)
- [V3 Tech Stack](#v3-tech-stack)
- [V3 Project Structure](#v3-project-structure)
- [V3 API Reference](#v3-api-reference)
- [V3 Features](#v3-features)
- [Deployment](#deployment)
- [V3 Development Phases](#v3-development-phases)
- [Challenges & Solutions](#challenges--solutions)
- [V2 Reference](#v2-reference)
- [Installation](#installation)

---

## 🎯 Overview

**VaultAI V3** evolves from a reactive insight engine into a **prescriptive strategy platform**. Where V2 told you *what happened*, V3 tells you *what to do* — generating validated budget plans, investment allocations, and goal projections powered by a LangGraph agent with an LLM-backed explanation layer.

### Version History

| Version | Tag | Nature |
|---------|-----|--------|
| V1 — Secure Ledger | [`v1.0.0`](https://github.com/anushkagaggar/vaultai/releases/tag/v1.0.0) | CRUD + auth |
| V2 — Insight Engine | [`v2.0.0`](https://github.com/anushkagaggar/vaultai/releases/tag/v2.0.0) | Descriptive analytics + validation |
| V3 — Strategy Lab | [`v3.0.0`](https://github.com/anushkagaggar/vaultai/releases/tag/v3.0.0) | Prescriptive planning + agent graph |

---

## 🚀 What's New in V3

### Core Additions

#### 1️⃣ **LangGraph Agent (Strategy Graph)**
- Stateful multi-node execution graph compiled via LangGraph
- Intent classifier routes messages to the correct agent: `budget`, `invest`, `goal`, `simulate`, `combined`
- Each plan type has its own node chain: `optimize → validate → explain → persist`
- Degraded mode — if any node fails, falls back gracefully and marks result as degraded

#### 2️⃣ **Budget Agent**
- Deterministic budget optimizer using linear programming (`optimizer.py`)
- Reads V2 analytics (`build_trends_report`) as context — actual spending feeds the plan
- Allocates income across categories, computes savings rate, validates against target
- Fallback: template-based allocation when optimizer fails

#### 3️⃣ **Investment Allocation Agent**
- Risk-profile → allocation template: `conservative (20/60/20)`, `moderate (50/30/20)`, `aggressive (75/15/10)`
- Equity / Debt / Liquid split with per-bucket INR amounts
- LLM-generated narration via Groq (`llama3-8b-8192`) — guardrailed: never receives raw price data
- External data freshness tracking (`live / cached / fallback`)

#### 4️⃣ **Goal Planning Agent**
- Three goal sub-paths: standard savings/purchase/education/retirement, debt payoff schedule, multi-goal tradeoff
- `goal_feasibility()` — projects balance at horizon, computes coverage ratio and gap
- `contribution_required()` — back-calculates required monthly savings
- Debt path: `debt_payoff_schedule()` — amortisation table with interest/principal split
- Multi-goal: `multi_goal_tradeoff()` — allocates monthly surplus across competing goals

#### 5️⃣ **`/plans/chat` — Natural Language Entry Point**
- Single endpoint for conversational plan creation
- Server-side intent classification (same `classify_intent` used by the graph)
- Returns `422` with exact missing fields when required params are absent — HITL-ready
- Supports all plan types through one interface

#### 6️⃣ **Strategy Lab UI (Next.js Frontend)**
- **ChatInterface** — conversational plan creation with Human-in-the-Loop (HITL) forms
  - Sends every message to `/plans/chat`
  - Backend returns `422 {"detail": "Please also provide: income_monthly"}` when fields are missing
  - Frontend parses the 422 detail, renders inline form fields, and retries with collected params
- **Plan detail pages** — `/plans/budget`, `/plans/invest`, `/plans/goal` — render raw `projected_outcomes` directly from backend
- **My Plans** — localStorage-persisted list of created plans with live fetch

---

## 🏗️ V3 Architecture

### System Design

```
┌──────────────────────────────────────────────────────────────────────┐
│                          VaultAI V3                                  │
│                       Strategy Lab Layer                             │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│   Frontend   │─────▶│   Backend    │─────▶│   Neon DB    │
│  (Next.js)   │      │  (FastAPI)   │      │  (Postgres)  │
└──────────────┘      └──────────────┘      └──────────────┘
       │                      │
       │              ┌───────┴────────┐
       │              │  LangGraph     │
       │              │  Agent Graph   │
       │              └───────┬────────┘
       │                      │
       │          ┌───────────┼───────────┐
       │          ▼           ▼           ▼
       │    ┌──────────┐ ┌─────────┐ ┌────────┐
       │    │  Budget  │ │ Invest  │ │  Goal  │
       │    │  Agent   │ │  Agent  │ │  Agent │
       │    └──────────┘ └─────────┘ └────────┘
       │          │           │           │
       │          └───────────┼───────────┘
       │                      ▼
       │              ┌──────────────┐
       │              │ LLM Explain  │
       │              │  (Groq)      │
       │              └──────────────┘
       │                      │
       ▼                      ▼
┌──────────────┐      ┌──────────────┐
│  Plan Pages  │◀─────│  Plan Store  │
│  (V3 UI)     │      │  (Postgres)  │
└──────────────┘      └──────────────┘
```

### V3 Agent Graph Flow

```
User Message / API Call
        │
        ▼
  intent_classifier
        │
   ┌────┴────────────────────────┐
   ▼           ▼                 ▼
budget       invest             goal
_optimize  _allocate          _simulate
   │           │                 │
   ▼           ▼                 ▼
budget       invest             goal
_validate  _validate          _validate
   │           │                 │
   └────┬──────┘                 │
        ▼                        ▼
   [llm_explain]           goal_explain
        │                        │
        └─────────┬──────────────┘
                  ▼
            plan_persist
                  │
            PlanResponse
     (plan_id, projected_outcomes,
      explanation, confidence, graph_trace)
```

### HITL Flow (Frontend ↔ Backend)

```
User: "Help me create a budget plan"
        │
        ▼
POST /plans/chat { message: "Help me create a budget plan" }
        │
        ▼  Backend: classifies → budget, checks body → income_monthly missing
422 { "detail": "Your message was classified as a budget plan.
                  Please also provide: income_monthly." }
        │
        ▼  Frontend: parseMissingFields() → renders HitlForm
User fills in: income_monthly = 80000
        │
        ▼
POST /plans/chat { message: "...", income_monthly: 80000 }
        │
        ▼
201 PlanResponse { plan_id, projected_outcomes, explanation, ... }
```

---

## 🛠️ V3 Tech Stack

### Frontend
- **Framework:** Next.js 15 (App Router)
- **Language:** TypeScript
- **Styling:** Tailwind CSS v4 + inline styles
- **State:** React 19 hooks + localStorage (plan refs)
- **Deployment:** Vercel

### Backend
- **Framework:** FastAPI (Python 3.11)
- **Agent:** LangGraph (stateful graph execution)
- **ORM:** SQLAlchemy (async)
- **Database:** Neon PostgreSQL
- **Migrations:** Alembic
- **Authentication:** JWT (python-jose)
- **Deployment:** Hugging Face Spaces (Docker)

### AI & Planning
- **LLM Provider:** Groq API (`llama3-8b-8192`)
- **Agent Framework:** LangGraph
- **Optimiser:** `scipy.optimize` / linear programming (budget)
- **Vector DB:** Qdrant Cloud (carried from V2)
- **Embeddings:** Sentence Transformers 384-dim (carried from V2)

### Infrastructure
- **Frontend:** https://vaultai-frontend.vercel.app/
- **Backend:** https://gaggaranushka-vault.hf.space/
- **Database:** Neon (serverless Postgres)
- **Vector DB:** Qdrant Cloud

---

## 📁 V3 Project Structure

```
vaultai/
├── app/                                # FastAPI backend
│   ├── main.py                         # App factory, CORS, middleware
│   ├── config.py                       # Environment config
│   ├── database.py                     # Async DB session
│   │
│   ├── models/
│   │   ├── user.py
│   │   ├── expense.py
│   │   ├── plan.py                     # ⭐ V3: Plan storage model
│   │   ├── insight.py                  # V2: kept for compatibility
│   │   └── rag_document.py
│   │
│   ├── routes/
│   │   ├── auth.py
│   │   ├── expenses.py
│   │   ├── plans.py                    # ⭐ V3: /plans/* endpoints
│   │   ├── insights.py                 # V2
│   │   ├── executions.py               # V2
│   │   ├── rag.py                      # V2
│   │   └── system.py
│   │
│   ├── agents/                         # ⭐ V3: LangGraph agent
│   │   ├── State.py                    # VaultAIState, PlanType enum
│   │   ├── graph.py                    # compile_graph()
│   │   ├── router_node.py              # classify_intent()
│   │   │
│   │   ├── budget/
│   │   │   ├── nodes.py                # budget_optimize, budget_validate
│   │   │   └── optimizer.py            # Linear programming solver
│   │   │
│   │   ├── invest/
│   │   │   ├── nodes.py                # invest_allocate, invest_validate, invest_explain
│   │   │   └── market.py               # External rate fetcher (with fallback)
│   │   │
│   │   └── goal/
│   │       ├── nodes.py                # goal_simulate, goal_validate, goal_explain
│   │       ├── feasibility.py          # goal_feasibility(), contribution_required()
│   │       ├── debt.py                 # debt_payoff_schedule()
│   │       └── multi_goal.py           # multi_goal_tradeoff()
│   │
│   ├── analytics/
│   │   └── trends.py                   # build_trends_report() — V2 analytics fed into V3 agents
│   │
│   ├── middleware/
│   │   ├── auth.py                     # JWT verification
│   │   └── errors.py
│   │
│   └── llm/
│       └── client.py                   # Groq LLM client
│
├── vaultai-frontend/                   # Next.js frontend
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx                    # Landing / redirect
│   │   │
│   │   ├── auth/page.tsx               # Login / Register
│   │   ├── dashboard/page.tsx          # Expense management
│   │   │
│   │   ├── strategy/page.tsx           # ⭐ V3: Strategy Lab (ChatInterface)
│   │   │
│   │   ├── plans/
│   │   │   ├── page.tsx                # ⭐ V3: My Plans list
│   │   │   ├── budget/page.tsx         # ⭐ V3: Budget plan detail
│   │   │   ├── invest/page.tsx         # ⭐ V3: Investment plan detail
│   │   │   └── goal/page.tsx           # ⭐ V3: Goal plan detail
│   │   │
│   │   ├── simulate/page.tsx           # ⭐ V3: What-If Simulator
│   │   │
│   │   ├── insights/                   # V2: kept
│   │   ├── uploads/                    # V2: kept
│   │   └── runs/                       # V2: kept
│   │
│   ├── components/
│   │   ├── ChatInterface.tsx           # ⭐ V3: HITL chat + plan creation
│   │   ├── PlanCard.tsx                # ⭐ V3: Plan summary card
│   │   ├── PlanConfidence.tsx          # ⭐ V3: Confidence display
│   │   ├── GraphExecutionTrace.tsx     # ⭐ V3: Agent node trace
│   │   ├── ProjectionChart.tsx         # ⭐ V3: Savings projection chart
│   │   ├── ScenarioComparison.tsx      # ⭐ V3: Scenario comparison
│   │   ├── AllocationWheel.tsx         # ⭐ V3: Investment allocation pie
│   │   ├── GoalProgress.tsx            # ⭐ V3: Goal coverage bar
│   │   ├── AssumptionsBlock.tsx        # ⭐ V3: Plan assumptions display
│   │   └── AuthenticatedLayout.tsx     # Shared layout wrapper
│   │
│   └── lib/
│       ├── backend.ts                  # API client (ApiError class, all endpoints)
│       ├── planUtils.ts                # formatIndianCurrency, getRelativeTime
│       └── types/
│           └── plans.ts                # TypeScript plan types
│
├── alembic/                            # DB migrations
├── requirements.txt
├── Dockerfile
└── README.md
```

---

## 📡 V3 API Reference

### Plan Endpoints

#### `POST /plans/budget`
Create a budget plan directly.
```json
{
  "income_monthly": 80000,
  "savings_target_pct": 0.20,
  "fixed_categories": [],
  "message": "help me budget"
}
```

#### `POST /plans/invest`
Create an investment allocation plan.
```json
{
  "investment_amount": 50000,
  "risk_profile": "moderate",
  "horizon_months": 36,
  "income_monthly": 0,
  "message": "help me invest"
}
```
`risk_profile` must be one of: `conservative`, `moderate`, `aggressive`

#### `POST /plans/goal`
Create a savings / goal plan.
```json
{
  "goal_type": "savings",
  "target_amount": 600000,
  "horizon_months": 12,
  "current_savings": 0,
  "monthly_savings": null,
  "annual_rate": 0.07,
  "income_monthly": 0,
  "message": "help me save"
}
```
`goal_type` must be one of: `savings`, `emergency_fund`, `purchase`, `education`, `retirement`

#### `POST /plans/chat` ⭐ Primary endpoint
Natural language entry point. Backend classifies intent and returns `422` with missing fields if any required params are absent.
```json
{
  "message": "Help me budget with 80000 monthly income",
  "income_monthly": 80000
}
```
**422 HITL response example:**
```json
{
  "detail": "Your message was classified as a budget plan. Please also provide: income_monthly."
}
```

#### `GET /plans/{plan_id}`
Fetch a stored plan by integer ID.

#### `GET /plans/{plan_id}/trace`
Fetch only the execution trace (lightweight diagnostics).

### Response Shape (`PlanResponse`)

```typescript
{
  plan_id:            number | null,    // null if DB persist failed
  plan_type:          string,           // "budget" | "invest" | "goal"
  projected_outcomes: object | null,    // plan-type-specific result keys
  explanation:        string | null,    // LLM-generated narration
  confidence:         object | null,    // { overall, data_coverage, ... }
  degraded:           boolean,          // true if fallback path used
  graph_trace:        string[],         // agent node execution order
  source_hash:        string | null
}
```

### `projected_outcomes` keys by plan type

**Budget:**
```
monthly_savings, annual_savings, savings_rate,
budget_allocation, optimizer_used
```

**Invest:**
```
equity_pct, debt_pct, liquid_pct,
equity_amount, debt_amount, liquid_amount,
total_allocated, risk_profile, allocation_method
```

**Goal (standard):**
```
goal_type, feasibility_label, target_amount,
projected_balance, gap_amount, surplus,
months_to_goal, coverage_ratio,
contribution_required, total_to_contribute
```

**Goal (debt):**
```
goal_type, outstanding, monthly_payment, total_months,
total_interest_paid, total_paid, feasibility_label,
coverage_ratio, payoff_schedule[]
```

---

## ✨ V3 Features

### Strategy Lab (Chat)
- ✅ Natural language plan creation via `/plans/chat`
- ✅ HITL inline forms — backend drives what fields are needed
- ✅ Expense logging from chat (`"Add ₹500 groceries today"`)
- ✅ Expense deletion from chat
- ✅ Plan saved to localStorage for My Plans page
- ✅ Plan card inline in chat with confidence and outcome metrics
- ✅ Graph trace collapsible per message

### Budget Planning
- ✅ Deterministic budget optimiser (linear programming)
- ✅ V2 spending data feeds the plan automatically
- ✅ Income, inflation rate, min savings rate display
- ✅ Monthly and annual savings projection
- ✅ Degraded fallback when optimiser unavailable

### Investment Planning
- ✅ Three risk profiles with fixed allocation templates
- ✅ Per-bucket amounts (equity / debt / liquid)
- ✅ LLM narration guardrailed against raw price data
- ✅ External data freshness indicator (live / cached / fallback)
- ✅ Horizon display (months → years)

### Goal Planning
- ✅ Standard goals: savings, emergency fund, purchase, education, retirement
- ✅ Feasibility label: `FEASIBLE / STRETCH / INFEASIBLE`
- ✅ Coverage ratio and gap/surplus amounts
- ✅ Required monthly contribution calculation
- ✅ Debt payoff path: amortisation table with interest/principal columns
- ✅ Multi-goal tradeoff allocation

### Frontend Infrastructure
- ✅ `ApiError` class — status + detail always available in catch blocks
- ✅ All plan pages read raw `projected_outcomes` (no fragile field mapping)
- ✅ `toGraphNodes()` — converts backend `string[]` trace to typed `GraphNode[]`
- ✅ `PlanConfidence` component accepts shaped confidence object
- ✅ Auth redirect via `ApiError.status === 401`

---

## 🚢 Deployment

### Production Endpoints

| Service | URL |
|---------|-----|
| **Frontend** | https://vaultai-frontend.vercel.app/ |
| **Backend API** | https://gaggaranushka-vault.hf.space/ |
| **API Docs** | https://gaggaranushka-vault.hf.space/docs |

### Environment Variables

#### Backend (Hugging Face Spaces → Settings → Variables)
```env
DATABASE_URL=postgresql+asyncpg://...
SECRET_KEY=your-secret-key
GROQ_API_KEY=gsk_...
QDRANT_HOST=https://...qdrant.io
QDRANT_API_KEY=your-qdrant-key
```

#### Frontend (Vercel → Settings → Environment Variables)
```env
NEXT_PUBLIC_API_URL=https://gaggaranushka-vault.hf.space
```

#### Local Development
```env
# vaultai-frontend/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### HF Spaces Notes
- Backend deployed as Docker container (`sdk: docker`)
- `ProxyHeadersMiddleware` enabled — HF nginx terminates SSL, uvicorn sees HTTP
- `HTTPSRedirectMiddleware` removed — would cause redirect loop behind proxy
- CORS: `allow_origins=["http://localhost:3000", "https://*.vercel.app"]`
- Trailing slash stripped on frontend (`apiFetch`) to avoid nginx 301 → CORS preflight failure

---

## 🔄 V3 Development Phases

### Phase 1 ✅ — Agent Foundation
- LangGraph graph scaffold
- `VaultAIState` TypedDict
- `PlanType` enum (`BUDGET`, `INVEST`, `GOAL`, `SIMULATE`, `COMBINED`)
- Intent classifier node
- `make_initial_state()` helper
- Plan DB model + migration

### Phase 2 ✅ — `/plans/budget`
- `budget_optimize` node (linear programming)
- `budget_validate` checkpoint
- `budget_explain` (LLM narration)
- `plan_persist` node
- `POST /plans/budget` endpoint live

### Phase 3 ✅ — `/plans/invest`
- `invest_allocate` node (deterministic templates)
- External market rate fetcher with fallback
- `invest_validate` checkpoint
- `invest_explain` (guardrailed LLM)
- `POST /plans/invest` endpoint live

### Phase 4 ✅ — `/plans/goal`
- `goal_simulate` node
- `goal_feasibility()`, `contribution_required()`
- `debt_payoff_schedule()` sub-path
- `multi_goal_tradeoff()` sub-path
- `goal_validate` + `goal_explain`
- `POST /plans/goal` endpoint live

### Phase 5 ✅ — `/plans/chat` + Full UI
- `POST /plans/chat` with server-side intent classification
- `GET /plans/{id}` + `GET /plans/{id}/trace`
- Strategy Lab ChatInterface with HITL
- Budget / Invest / Goal plan detail pages
- My Plans page with localStorage persistence
- `ApiError` class + unified error handling

### Phase 6 🔜 — Simulate + Combined
- `POST /plans/simulate` — What-If Simulator
- `POST /plans/combined` — Multi-plan optimizer
- SimulateForm UI
- Combined plan view

---

## 🚧 Challenges & Solutions

### V3 Challenges

#### **1. Backend has no memory between requests — HITL broken**
- **Problem:** `/plans/chat` re-classifies from `body.message` every call. Frontend sent collected params but `apiFetch` threw a plain `Error`, not a typed error — `e.status` was always `undefined` so the 422 HITL branch never fired. User saw raw JSON string.
- **Solution:** Added `ApiError` class with `.status` and `.detail`. Moved it before `apiFetch`. Fixed `apiFetch` to throw `ApiError` instead of `new Error(text)`. Frontend now checks `e.status === 422`, parses `e.detail` for missing field names, renders inline form.

#### **2. `plan.riskProfile.toLowerCase()` crash**
- **Problem:** Plan detail pages typed state as `InvestPlan`/`BudgetPlan`/`GoalPlan` (camelCase frontend interfaces). `getPlan()` returns raw backend `PlanDetailResponse` (snake_case). `plan.riskProfile` was `undefined`.
- **Solution:** All plan pages now use a local `RawPlan` interface matching the exact backend response. All fields read from `projected_outcomes` and `assumptions` by their real snake_case keys.

#### **3. `GraphExecutionTrace` type mismatch**
- **Problem:** Component expects `GraphNode[]` (objects with `name/type/status/description`). Backend `graph_trace` is `string[]`. Passing typed `GraphNode[]` to `toGraphNodes(string[])` gave inverse type error.
- **Solution:** Added `toGraphNodes(trace: string[])` helper in each plan page, infers node type from name, always called on `plan.graph_trace` (snake_case raw).

#### **4. HITL form sends NaN**
- **Problem:** HitlForm inputs were `type="number"`. Users typed `₹50000` — browser rejected non-numeric chars, value was `""`, `parseFloat("")` = `NaN`.
- **Solution:** Changed inputs to `type="text" inputMode="decimal"`. All numeric `parse()` functions strip non-numeric chars first: `v.replace(/[^\d.]/g, '')`.

#### **5. Expense description always null**
- **Problem:** Description regex only matched after `for|on|bought|of`. `"Add ₹500 groceries today"` has none of these before "groceries".
- **Solution:** Word-filter approach — slice text after the amount, remove stop words and date words, remaining words are the description.

#### **6. CORS + HTTPS redirect on HF Spaces**
- **Problem:** HF nginx terminates SSL. `HTTPSRedirectMiddleware` caused redirect loop. Redirect on `expenses/` → `expenses` caused CORS preflight failure.
- **Solution:** Removed `HTTPSRedirectMiddleware`, added `ProxyHeadersMiddleware`. Frontend strips trailing slashes in `apiFetch`.

### V2 Challenges (Preserved)

#### **7. LLM Hallucination** — Multi-layer numeric validation guards
#### **8. Source Freshness** — Source hash from (expenses + RAG docs + pipeline version)
#### **9. Confidence Quantification** — 4-signal weighted formula
#### **10. Execution State** — State machine PENDING → RUNNING → SUCCESS/FALLBACK/FAILED
#### **11. Frontend-Backend Sync** — Polling at 2.5s intervals with unmount cleanup
#### **12. Qdrant Index** — Created payload indexes for `user_id` and `active`
#### **13. Environment Variables** — PowerShell `Set-Content` with UTF-8 encoding

---

## 📖 V2 Reference

> Full V2 documentation preserved below.

### V2 Overview
VaultAI V2 is a deterministic financial intelligence platform transforming raw expense data into validated insights using AI-powered reasoning backed by mathematical validation.

### V2 Architecture
- **Orchestrator** (Phase 3) — state machine, execution tracking, source hash
- **Validation Layer** (Phase 4) — numeric guards, claim verification, RAG support check
- **Confidence Scoring** — `0.4×coverage + 0.3×window + 0.2×stability + 0.1×rag`
- **Artifact System** — persistent insight storage with cache invalidation

### V2 Endpoints
| Endpoint | Description |
|----------|-------------|
| `GET /insights/trends` | Trigger insight generation |
| `GET /executions/{id}` | Poll execution status |
| `GET /system/metrics` | System health metrics |
| `POST /rag/upload` | Upload RAG document |
| `GET /rag/documents` | List user documents |

### V2 Feature Status
- ✅ Rolling window analytics (30/60/90 days)
- ✅ LLM explanations with RAG grounding
- ✅ Multi-guard validation (numeric, claim, RAG)
- ✅ Confidence scoring (0–100%)
- ✅ Artifact persistence with source hash
- ✅ Execution monitor dashboard
- ✅ Document upload with vector indexing

---

## 🛠️ Installation

### Prerequisites
- **Python 3.11+**
- **Node.js 18+**
- **PostgreSQL** (or Neon account)
- **Qdrant Cloud** account
- **Groq API** key

### Backend Setup

```bash
# Clone repository
git clone https://github.com/anushkagaggar/vaultai.git
cd vaultai

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
# Create .env with the variables listed in Deployment section

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload --port 8000
```

### Frontend Setup

```bash
cd vaultai-frontend

# Install dependencies
npm install

# Configure environment
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local

# Start dev server
npm run dev
```

### Access
- **Frontend:** http://localhost:3000
- **Backend:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 👥 Contributors

**Anushka Maheshwari** — Lead Developer

---

## 🔗 Links

- **V1 Release:** [v1.0.0](https://github.com/anushkagaggar/vaultai/releases/tag/v1.0.0)
- **V2 Release:** [v2.0.0](https://github.com/anushkagaggar/vaultai/releases/tag/v2.0.0)
- **V3 Release:** [v3.0.0](https://github.com/anushkagaggar/vaultai/releases/tag/v3.0.0)
- **V3 (main):** [github.com/anushkagaggar/vaultai](https://github.com/anushkagaggar/vaultai)
- **Frontend:** [vaultai-frontend.vercel.app](https://vaultai-frontend.vercel.app/)
- **Backend:** [gaggaranushka-vault.hf.space](https://gaggaranushka-vault.hf.space/)
- **API Docs:** [gaggaranushka-vault.hf.space/docs](https://gaggaranushka-vault.hf.space/docs)
