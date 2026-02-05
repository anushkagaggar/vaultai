# VaultAI v1.0.0

## 📌 Overview

VaultAI v1.0.0 (Ledger Core) is a cloud-deployed personal finance system that provides secure expense tracking with hybrid authentication.

It serves as the foundation for a multi-phase, agentic financial assistant that will evolve into an autonomous financial advisor in later versions.

Current features:

- Secure JWT-based authentication
- User-isolated expense tracking
- Cloud-hosted PostgreSQL database (Neon)
- FastAPI backend
- Next.js frontend
- Production deployment on Render and Vercel

This version focuses on reliability, security, and scalability fundamentals.

---

## 🎯 Version Roadmap

VaultAI evolves in four stages:

### 🟢 V1 — Ledger Core (Current)
- Expense recording and retrieval
- Authentication
- Cloud deployment
- Data isolation

### 🔵 V2 — Insight Engine
- Spending analysis
- Risk detection
- RAG integration

### 🟠 V3 — Strategy Lab
- Savings optimization
- Investment planning
- Multi-agent workflows

### 🔴 V4 — Autonomous Guard
- Proactive interventions
- Continuous monitoring
- Decision automation

Each version builds on the previous one. No rewrites.

---

## 🏗️ Architecture

Frontend (Next.js on Vercel)
↓ JWT
Backend (FastAPI on Render)
↓
Auth Middleware
↓
CRUD Services
↓
PostgreSQL (Neon)



LLM usage in V1 is limited to optional UI assistance only.  
No AI reasoning is used in core data flows.

---

## 📁 Project Structure

vaultai/
│
├── backend/
│ ├── app/
│ │ ├── main.py
│ │ ├── config.py
│ │ ├── database.py
│ │
│ │ ├── models/
│ │ │ ├── user.py
│ │ │ └── expense.py
│ │
│ │ ├── schemas/
│ │ │ ├── user.py
│ │ │ └── expense.py
│ │
│ │ ├── routes/
│ │ │ ├── auth.py
│ │ │ └── expenses.py
│ │
│ │ ├── services/
│ │ │ └── expense_service.py
│ │
│ │ └── middleware/
│ │ └── auth.py
│ │
│ └── requirements.txt
│
├── frontend/
│ └── nextjs-app/
│
└── docker-compose.yml (optional)


This structure is maintained across versions.

---

## ⚙️ Local Setup

### Prerequisites

- Python 3.10+
- Node.js 18+
- PostgreSQL (Neon account)
- Git

---

## Backend Setup

```bash
git clone <repo-url>
cd vaultai/backend

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### Create .env file:
```bash
DATABASE_URL=postgresql+asyncpg://...
JWT_SECRET=your_secret
REFRESH_SECRET=your_refresh_secret
ENV=development
```

### Run migrations:
`alembic upgrade head`

### Start server:
`uvicorn app.main:app --reload`

---

## Frontend Setup
```bash
cd frontend/nextjs-app
npm install
```

### Create .env.local:
`NEXT_PUBLIC_API_URL=http://localhost:8000`

### Run frontend:
`npm run dev`

---

## 🔐 Environment Variables
### Backend (Render / Local)
| Variable       | Description              |
| -------------- | ------------------------ |
| DATABASE_URL   | Neon Postgres connection |
| JWT_SECRET     | JWT signing secret       |
| REFRESH_SECRET | Refresh token secret     |
| ENV            | Environment (dev/prod)   |

---

### Frontend (Vercel / Local)
| Variable            | Description     |
| ------------------- | --------------- |
| NEXT_PUBLIC_API_URL | Backend API URL |

---

## 🚀 Deployment
### Backend — Render
- Connected to GitHub repository
- Auto-deploy on push
- Environment variables configured in dashboard
- HTTPS enabled by default

### Deployment flow:
GitHub → Render → FastAPI → Neon

---

## Database — Neon
- Managed PostgreSQL
- Production database
- Backups enabled
- Accessed via DATABASE_URL

---

## Frontend — Vercel
- Connected to GitHub
- Auto-deploy on push
- Environment variables configured
- CDN + HTTPS enabled

### Deployment flow:
GitHub → Vercel → Next.js

---

## 🔄 Authentication System
- Backend-owned authentication
- Email + password
- Bcrypt hashing
- JWT access tokens (short-lived)
- Refresh tokens (long-lived)
- Authorization middleware

Supabase/Auth providers are not used.
Postgres is the source of truth.

---

## 🧪 Testing & Validation
- V1 enforces:
- Multi-user isolation testing
- Auth flow testing
- Token expiration testing
- CRUD validation
- Pagination checks
- Minimum test users are maintained for isolation validation.

---

## 📦 Migration Policy
- Alembic is mandatory
- No manual database edits
- All schema changes are versioned
- Production DB only modified via migrations
- Violating this policy invalidates schema integrity.

---

## 📈 Current Status
Release: v1.0.0
Phase: Ledger Core
Stability: Production-ready foundation
Next Milestone: V2 — Insight Engine

---

## 🏷️ Release Tagging
Each major version is tagged:
Example:
```bash
git tag v1.0.0
git push origin v1.0.0
```
Tags represent stable milestones.

---

## 📜 License
MIT License (or update as needed)

---

## 👤 Author
Developed by Anushka
Project: VaultAI