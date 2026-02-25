# VaultAI V2 🔐

**Intelligent Financial Analytics Platform with AI-Powered Insights**

## 📋 Table of Contents

- [Overview](#overview)
- [What's New in V2](#whats-new-in-v2)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Features](#features)
- [Deployment](#deployment)
- [Development Phases](#development-phases)
- [Testing & Edge Cases](#testing--edge-cases)
- [Challenges & Solutions](#challenges--solutions)
- [What's Next (V3)](#whats-next-v3)
- [Installation](#installation)

---

## 🎯 Overview

**VaultAI V2** is a deterministic financial intelligence platform that transforms raw expense data into **trusted, validated insights** using AI-powered reasoning backed by mathematical validation.

### V1 Recap (Secure Ledger)
- ✅ User authentication & authorization
- ✅ Expense tracking with categories
- ✅ CRUD operations for financial records
- ✅ Dashboard with basic statistics
- ✅ Secure PostgreSQL storage
- ✅ REST API endpoints

**Tag:** [`v1.0.0`](https://github.com/anushkagaggar/vaultai/releases/tag/v1.0.0)

---

## 🚀 What's New in V2

### Core Capabilities

#### 1️⃣ **Deterministic Insight Engine**
- Multi-dimensional trend detection
- Rolling window analytics (30/60/90-day averages)
- Month-over-month comparison with percent change
- Category-level spending breakdown
- Automated anomaly detection

#### 2️⃣ **AI-Powered Explanations**
- LLM-generated natural language summaries
- RAG (Retrieval-Augmented Generation) integration
- Context-aware financial reasoning
- Document-grounded explanations

#### 3️⃣ **Validation & Trust Layer**
- **Phase 3:** Orchestrator with state management
- **Phase 4:** Multi-guard validation system
  - Numeric consistency guards
  - Claim verification
  - RAG grounding checks
- **Phase 5:** Confidence scoring (0-100%)
- Artifact persistence with lineage tracking

#### 4️⃣ **Intelligence UI**
- Insight list with confidence meters
- Full reasoning detail pages
- Document upload management
- Execution monitor dashboard
- Real-time computation tracking

#### 5️⃣ **RAG Document System**
- PDF/TXT document upload
- Vector embeddings via Qdrant
- User-isolated document retrieval
- Trust-level scoring
- Version control for documents

---

## 🏗️ Architecture

### System Design

```
┌─────────────────────────────────────────────────────────────────┐
│                         VaultAI V2                              │
│                    Insight Engine Layer                         │
└─────────────────────────────────────────────────────────────────┘

┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│   Frontend   │─────▶│   Backend    │─────▶│   Database   │
│  (Next.js)   │      │  (FastAPI)   │      │  (Neon DB)   │
└──────────────┘      └──────────────┘      └──────────────┘
       │                      │                      │
       │                      ▼                      │
       │              ┌──────────────┐               │
       │              │ Orchestrator │               │
       │              │   (Phase 3)  │               │
       │              └──────────────┘               │
       │                      │                      │
       │                      ▼                      │
       │              ┌──────────────┐               │
       │              │  Validation  │               │
       │              │   (Phase 4)  │               │
       │              └──────────────┘               │
       │                      │                      │
       ▼                      ▼                      ▼
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│   Vector DB  │◀─────│   LLM API    │      │  Artifacts   │
│  (Qdrant)    │      │   (Groq)     │      │   Storage    │
└──────────────┘      └──────────────┘      └──────────────┘
```

### Data Flow

```
User Action → Frontend → Backend API
                           │
                           ▼
                    Orchestrator (Phase 3)
                           │
                           ├─▶ Analytics Engine (deterministic math)
                           ├─▶ LLM Client (AI explanation)
                           └─▶ RAG Retrieval (document context)
                           │
                           ▼
                    Validation Layer (Phase 4)
                           │
                           ├─▶ Numeric Guards
                           ├─▶ Claim Verification
                           └─▶ RAG Support Check
                           │
                           ▼
                    Decision Classification
                           │
                           ├─▶ SUCCESS (trusted)
                           ├─▶ FALLBACK (degraded)
                           └─▶ SUPPRESS (hidden)
                           │
                           ▼
                    Artifact Storage (Phase 5)
                           │
                           └─▶ Confidence Scoring → Frontend Display
```

---

## 🛠️ Tech Stack

### Frontend
- **Framework:** Next.js 14 (App Router)
- **Language:** TypeScript
- **Styling:** Tailwind CSS
- **State:** React Hooks
- **Deployment:** Vercel

### Backend
- **Framework:** FastAPI (Python 3.11)
- **ORM:** SQLAlchemy (async)
- **Database:** Neon PostgreSQL
- **Migrations:** Alembic
- **Authentication:** JWT (python-jose)
- **Deployment:** Hugging Face Spaces

### AI & Vector Search
- **LLM Provider:** Groq API (llama-3.1-8b-instant)
- **Vector DB:** Qdrant Cloud
- **Embeddings:** Sentence Transformers (384-dim)
- **RAG:** Custom retrieval pipeline

### Infrastructure
- **Frontend:** https://vaultai-frontend.vercel.app/
- **Backend:** https://gaggaranushka-vault.hf.space/
- **Database:** Neon (serverless Postgres)
- **Vector DB:** Qdrant Cloud (managed)

---

## 📁 Project Structure

```
vaultai/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI application
│   │   ├── config.py                  # Environment configuration
│   │   ├── database.py                # Database session management
│   │   │
│   │   ├── models/                    # SQLAlchemy models
│   │   │   ├── user.py
│   │   │   ├── expense.py
│   │   │   ├── insight.py             # V2: Artifact storage
│   │   │   ├── insight_execution.py   # V2: Execution tracking
│   │   │   └── rag_document.py        # V2: Document metadata
│   │   │
│   │   ├── routes/                    # API endpoints
│   │   │   ├── auth.py
│   │   │   ├── expenses.py
│   │   │   ├── insights.py            # V2: Insight endpoints
│   │   │   ├── executions.py          # V2: Execution polling
│   │   │   ├── rag.py                 # V2: Document upload/retrieval
│   │   │   └── system.py              # V2: Metrics endpoint
│   │   │
│   │   ├── orchestrator/              # ⭐ Phase 3
│   │   │   ├── runner.py              # Execution orchestration
│   │   │   ├── state.py               # State machine
│   │   │   ├── analytics.py           # Math-driven insights
│   │   │   └── hash.py                # Source hash computation
│   │   │
│   │   ├── validation/                # ⭐ Phase 4
│   │   │   ├── guards/
│   │   │   │   ├── numeric.py         # Numeric validation
│   │   │   │   ├── claim.py           # Claim extraction
│   │   │   │   └── rag.py             # RAG support check
│   │   │   ├── decision.py            # Classification logic
│   │   │   └── engine.py              # Validation orchestration
│   │   │
│   │   ├── confidence/                # ⭐ Phase 4
│   │   │   ├── scorer.py              # Confidence computation
│   │   │   └── collector.py           # Signal collection
│   │   │
│   │   ├── insights/                  # ⭐ Phase 4
│   │   │   ├── resolver.py            # Artifact resolver
│   │   │   └── service.py             # Artifact creation
│   │   │
│   │   ├── rag/                       # ⭐ V2
│   │   │   ├── indexer.py             # Document chunking
│   │   │   ├── retriever.py           # Context retrieval
│   │   │   └── embedder.py            # Embedding generation
│   │   │
│   │   ├── llm/                       # ⭐ V2
│   │   │   └── client.py              # LLM API client (Groq)
│   │   │
│   │   ├── vectordb/                  # ⭐ V2
│   │   │   └── qdrant_client.py       # Qdrant operations
│   │   │
│   │   └── middleware/
│   │       ├── auth.py                # JWT verification
│   │       ├── logging.py             # Request logging
│   │       └── errors.py              # Error handlers
│   │
│   ├── alembic/                       # Database migrations
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/                          # ⭐ Phase 5
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   │
│   │   ├── auth/
│   │   │   └── page.tsx               # V1: Login/register
│   │   │
│   │   ├── dashboard/
│   │   │   └── page.tsx               # V1: Expense management
│   │   │
│   │   ├── insights/                  # ⭐ V2: Intelligence UI
│   │   │   ├── page.tsx               # Insight list
│   │   │   └── [id]/
│   │   │       └── page.tsx           # Detail view
│   │   │
│   │   ├── uploads/                   # ⭐ V2: Document management
│   │   │   └── page.tsx
│   │   │
│   │   ├── runs/                      # ⭐ V2: Execution monitor
│   │   │   └── page.tsx
│   │   │
│   │   └── components/                # ⭐ V2: Reusable UI
│   │       ├── InsightCard.tsx
│   │       ├── ConfidenceMeter.tsx
│   │       ├── StatusBadge.tsx
│   │       ├── ExplanationBlock.tsx
│   │       ├── RefreshButton.tsx
│   │       ├── UploadDropzone.tsx
│   │       ├── UploadStatus.tsx
│   │       ├── ExecutionTimeline.tsx
│   │       └── EmptyState.tsx
│   │
│   ├── lib/
│   │   └── backend.ts                 # API client (V1 + V2)
│   │
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   └── next.config.ts
│
└── README.md
```

---

## ✨ Features

### V2 Feature Breakdown

#### **Analytics Engine**
- ✅ Rolling window averages (30/60/90 days)
- ✅ Month-over-month comparison
- ✅ Percent change calculation
- ✅ Category-level aggregation
- ✅ Trend type detection (spike/decline/stable/growth)

#### **AI Explanation**
- ✅ Natural language summaries
- ✅ RAG-grounded context
- ✅ Document-aware reasoning
- ✅ Deterministic fallback (metrics-only mode)

#### **Validation System**
- ✅ **Numeric Guards:** Verify all numbers in explanation
- ✅ **Claim Verification:** Extract and validate factual claims
- ✅ **RAG Support:** Ensure document grounding
- ✅ **Decision Classification:** SUCCESS/FALLBACK/SUPPRESS

#### **Confidence Scoring**
- ✅ Data coverage score (transaction density)
- ✅ Window completeness (history span)
- ✅ Stability score (spending volatility)
- ✅ RAG support score (document grounding)
- ✅ Weighted formula: `0.4×coverage + 0.3×window + 0.2×stability + 0.1×rag`

#### **Artifact System**
- ✅ Persistent insight storage
- ✅ Source hash tracking (freshness detection)
- ✅ Lineage tracking (execution provenance)
- ✅ Version control
- ✅ Cache invalidation on data change

#### **Frontend Intelligence UI**
- ✅ Insight cards with confidence visualization
- ✅ Full reasoning detail pages
- ✅ Status badges (TRUSTED/DEGRADED/STALE)
- ✅ Real-time execution tracking
- ✅ Document upload with status
- ✅ Execution monitor dashboard

---

## 🚢 Deployment

### Production Endpoints

| Service | URL |
|---------|-----|
| **Frontend** | https://vaultai-frontend.vercel.app/ |
| **Backend API** | https://gaggaranushka-vault.hf.space/ |
| **API Docs** | https://gaggaranushka-vault.hf.space/docs |

### Environment Variables

#### Backend (Hugging Face Spaces)
```env
DATABASE_URL=postgresql+asyncpg://...
SECRET_KEY=your-secret-key
GROQ_API_KEY=gsk_...
QDRANT_HOST=https://...qdrant.io
QDRANT_API_KEY=your-qdrant-key
```

#### Frontend (Vercel)
```env
NEXT_PUBLIC_API_URL=https://gaggaranushka-vault.hf.space
```

---

## 🔄 Development Phases

### Phase 1 ✅ (V1 Foundation)
- User authentication
- Expense CRUD
- Basic dashboard
- PostgreSQL setup

### Phase 2 ✅ (Analytics Setup)
- Analytics engine development
- RAG pipeline setup
- LLM integration
- Vector DB configuration

### Phase 3 ✅ (Orchestrator)
- State machine implementation
- Execution tracking
- Source hash computation
- Pipeline versioning

### Phase 4 ✅ (Validation & Artifacts)
- Multi-guard validation system
- Decision classification
- Confidence scoring
- Artifact persistence
- Cache invalidation

### Phase 5 ✅ (Intelligence UI)
- Insight list & detail pages
- Document upload UI
- Execution monitor
- Status tracking components

---

## 🧪 Testing & Edge Cases

### Test Coverage

#### **Backend**
- ✅ Numeric validation (exact match, tolerance-based)
- ✅ Claim extraction (zero, one, multiple claims)
- ✅ RAG grounding (high/low support)
- ✅ Decision classification (all paths)
- ✅ Confidence scoring (edge cases: 0 txn, 1 txn, 1000 txn)
- ✅ Artifact resolver (fresh/stale/unavailable)

#### **Frontend**
- ✅ Empty state handling
- ✅ Loading skeleton display
- ✅ Low confidence dimming
- ✅ Degraded insight warnings
- ✅ Stale data detection
- ✅ Async refresh (no page reload)
- ✅ Polling cleanup on unmount
- ✅ Upload status tracking
- ✅ Network error recovery

#### **Edge Cases Handled**
- 🔹 User with zero expenses → Empty state
- 🔹 Single expense → Low confidence warning
- 🔹 Data changes during execution → Hash mismatch, stale status
- 🔹 LLM generates invalid numbers → FALLBACK mode
- 🔹 No RAG documents uploaded → Lower confidence
- 🔹 Duplicate refresh clicks → Execution reuse
- 🔹 Network timeout → Graceful error
- 🔹 Token expiry mid-session → Redirect to auth
- 🔹 Tab close during polling → Cleanup triggered

---

## 🚧 Challenges & Solutions

### Major Challenges Faced

#### **1. LLM Hallucination**
- **Problem:** AI generated incorrect numbers
- **Solution:** Multi-layer numeric validation guards with exact matching and tolerance checks

#### **2. Source Freshness Tracking**
- **Problem:** Detecting when cached insights become stale
- **Solution:** Source hash computation from (expenses + RAG docs + pipeline version)

#### **3. Confidence Quantification**
- **Problem:** How to measure insight reliability
- **Solution:** 4-signal weighted formula (coverage, window, stability, RAG support)

#### **4. Execution State Management**
- **Problem:** Coordinating async LLM calls, validation, and storage
- **Solution:** State machine with PENDING → RUNNING → SUCCESS/FALLBACK/FAILED transitions

#### **5. Frontend-Backend Sync**
- **Problem:** Real-time execution status without WebSockets
- **Solution:** Polling with 2.5s intervals, cleanup on unmount, terminal state detection

#### **6. Ngrok Dependency**
- **Problem:** Local Ollama + Ngrok unstable for production
- **Solution:** Migrated to Groq Cloud API (free tier, always available)

#### **7. Qdrant Index Missing**
- **Problem:** Filtering by `user_id` failed with 400 error
- **Solution:** Created payload indexes for `user_id` (INTEGER) and `active` (BOOLEAN)

#### **8. CORS Issues**
- **Problem:** Vercel preview URLs not whitelisted
- **Solution:** Added wildcard `https://*.vercel.app` to CORS origins

#### **9. Environment Variables**
- **Problem:** `.env.local` not loading in Next.js
- **Solution:** Hardcoded temporarily, then used PowerShell `Set-Content` with UTF-8 encoding

#### **10. Validation Performance**
- **Problem:** Running 3 guards sequentially = slow
- **Solution:** Parallel execution with `asyncio.gather()`, exit early on critical failures

---

## 🔮 What's Next (V3)

### VaultAI V3: Strategy Lab (Planned)

**Nature:** Prescriptive + Optimization Intelligence

#### Key Features
- 🎯 **Savings Optimization Engine**
  - Target savings rate recommendations
  - Category spending caps
  - Reduction simulations

- 📊 **Investment Allocation Logic**
  - Asset allocation templates
  - Risk tolerance mapping
  - Cash reserve recommendations

- 🔮 **Scenario Simulation**
  - What-if projections
  - Multi-period forecasting
  - Compounding logic

- 🤖 **Chatbot Integration**
  - Conversational financial planning
  - Natural language queries
  - Interactive strategy refinement

- ⚙️ **Optimization Models**
  - Linear programming for budget optimization
  - Constraint satisfaction
  - Goal-based planning

**Timeline:** Q2 2026

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
cd vaultai/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload --port 8000
```

### Frontend Setup

```bash
cd ../frontend

# Install dependencies
npm install

# Configure environment
cp .env.local.example .env.local
# Edit .env.local with backend URL

# Start dev server
npm run dev
```

### Access
- **Frontend:** http://localhost:3000
- **Backend:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details

---

## 👥 Contributors

- **Anushka Maheshwari** - Lead Developer

---

## 🔗 Links

- **V1 Release:** [v1.0.0](https://github.com/anushkagaggar/vaultai/releases/tag/v1.0.0)
- **V2 Release:** [v2.0.0](https://github.com/anushkagaggar/vaultai/releases/tag/v2.0.0)
- **Frontend:** [vaultai-frontend.vercel.app](https://vaultai-frontend.vercel.app/)
- **Backend:** [gaggaranushka-vault.hf.space](https://gaggaranushka-vault.hf.space/)
- **Documentation:** [API Docs](https://gaggaranushka-vault.hf.space/docs)
