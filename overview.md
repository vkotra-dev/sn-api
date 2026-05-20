# API Overview

# Phase 1 Backend API Project

The API project powers layout uploads, DXF parsing, preview generation, public layout viewing, and plot availability management.

---

# Responsibilities

- Authenticate admin users
- Accept DXF + Excel upload pairs
- Parse DXF → render preview PNG + extract hotspot positions
- Parse Excel → extract plot metadata
- Store layout and plot records
- Store generated assets (preview PNG, hotspot JSON) to CDN
- Generate public share URLs
- Serve public read-only layout data
- Allow admin plot status updates with transition validation

---

# Recommended Stack

| Layer | Choice |
|---|---|
| Framework | FastAPI |
| Language | Python |
| Database | PostgreSQL |
| ORM | SQLAlchemy |
| Migrations | Alembic |
| Auth | JWT |
| File Storage | S3-compatible storage |
| DXF Parsing | ezdxf |
| Excel Parsing | openpyxl |
| Image Rendering | matplotlib |

---

# Key Dependencies

```bash
pip install ezdxf matplotlib openpyxl fastapi sqlalchemy alembic python-jose bcrypt boto3
```

---

# Phase 1 Modules

```text
backend-api/
├── app/
│   ├── main.py
│   ├── auth/
│   ├── layouts/
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── parser/
│   │   │   ├── dxf.py       ← DXF parsing + PNG render + hotspot extraction
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

# Processing Flow

Layout upload is asynchronous:

```text
POST /api/admin/layouts
 → validate files
 → create layout record (status: processing)
 → return layoutId immediately
 → background task:
     parse DXF → preview PNG + hotspot JSON
     parse Excel → plot metadata
     join on plot_no → create plot records
     upload assets to CDN
     update layout status → published (or failed)
```
