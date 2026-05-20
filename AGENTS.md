# AGENTS.md

# backend-api — Phase 1 Agent Guide

This is the coordination document for the backend-api project.

---

# What This Project Does

The backend-api powers layout uploads, DXF parsing, preview generation, public layout viewing, and plot availability management.

---

# Read First

All agents must read these docs before writing any code:

1. [Architecture](architecture.md) — overall system context
2. [API Contracts](api-contracts.md) — all endpoints, request/response shapes, error codes
3. [Overview](overview.md) — stack, modules, processing flow
4. [Coding Standards](codingstandards.md) — naming, rules, testing

Then read the doc relevant to the feature being built:

- [Upload Pipeline](upload-pipeline.md) — DXF + Excel parsing, PNG render, hotspot JSON
- [Layouts](layouts.md) — layout resource and endpoints
- [Plots](plots.md) — plot resource, status transitions, endpoints
- [Postgres Schema](postgres-schema.md) — tables, indexes, migration notes
- [Authentication](authentication.md) — JWT, admin_users table, seed script
- [Error Handling](error-handling.md) — error codes, response format
- [Deployment](deployment.md) — env vars, deploy checklist

---

# Stack

| Layer | Choice |
|---|---|
| Framework | FastAPI |
| Language | Python |
| Database | PostgreSQL |
| ORM | SQLAlchemy |
| Migrations | Alembic |
| Auth | JWT |
| File Storage | S3-compatible |
| DXF Parsing | ezdxf |
| Excel Parsing | openpyxl |
| Image Rendering | matplotlib |

```bash
pip install ezdxf matplotlib openpyxl fastapi sqlalchemy alembic python-jose bcrypt boto3
```

---

# Project Structure

```text
backend-api/
├── docs/               ← you are here
├── app/
│   ├── main.py
│   ├── auth/
│   ├── layouts/
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── parser/
│   │   │   ├── dxf.py       ← DXF parsing, PNG render, hotspot extraction
│   │   │   └── excel.py     ← Excel metadata parsing
│   │   └── storage.py       ← CDN upload
│   ├── plots/
│   ├── database/
│   └── common/
└── tests/
```

---

# Required Endpoints

```text
POST   /api/auth/login
POST   /api/admin/layouts
GET    /api/admin/layouts
GET    /api/admin/layouts/{layoutId}
GET    /api/public/layouts/{slug}
GET    /api/admin/layouts/{layoutId}/plots/{plotNo}
PATCH  /api/admin/layouts/{layoutId}/plots/{plotNo}/status
```

---

# Critical Rules

- Upload accepts **DXF + Excel only** — no KMZ, DWG, PDF, or image-only
- DXF is parsed in **block-local coordinate space** — do not apply INSERT offset
- Preview PNG is **2400×2400px at 100 DPI** rendered by matplotlib
- Hotspot positions use **text centre**, not circle centre
- Plot status transitions are **validated server-side** — see plots.md for rules
- `owner` and `extra` fields are **never returned by public endpoints**
- Upload processing is **asynchronous** — return `layoutId` immediately, process in background

---

# Definition of Done

- Admin can log in
- Admin can upload DXF + Excel → layout created with `status: processing` → transitions to `published`
- Preview PNG and hotspot JSON stored to CDN
- Public URL returns layout with all plot hotspots and public metadata
- Plot status update validates transitions and rejects invalid ones
- All endpoints match the contracts in api-contracts.md
