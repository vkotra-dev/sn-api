# codingstandards.md

# Phase 1 Coding Standards

---

# General Rules

- Keep Phase 1 simple and shippable
- Avoid premature abstractions
- Prefer readable code
- Use strict typing
- Keep API contracts stable
- Do not duplicate business rules across projects

---

# Naming Standards

| Item | Convention |
|---|---|
| React components | PascalCase |
| React hooks | useCamelCase |
| TypeScript variables | camelCase |
| Python variables | snake_case |
| Database columns | snake_case |
| API JSON fields | camelCase |
| Constants | UPPER_SNAKE_CASE |

---

# TypeScript Rules

- Use TypeScript strict mode
- Avoid `any`
- Define API response types
- Keep DTOs separate from UI models
- Validate external API data where needed

---

# React / Next.js Rules

- One responsibility per component
- Keep route components thin
- Put reusable UI in `components/`
- Put API calls in `lib/api/`
- Put shared types in `types/`
- Avoid deeply nested prop chains
- Hotspot pixel positions come from server-generated JSON — never compute them client-side

---

# Python / FastAPI Rules

- Use Pydantic request/response models
- Keep routers small
- Keep database logic in services/repositories
- Validate all mutations
- Return consistent error responses
- DXF parsing, Excel parsing, and PNG rendering live in `app/layouts/parser/`

---

# Database Rules

- Use UUID primary keys
- Add foreign keys with cascade rules
- Add indexes for common lookups
- Use explicit columns for known fields — avoid hiding data in JSONB unless truly flexible
- Use `jsonb` only for genuinely variable data (`extra` field on plots, `hotspot` position)
- Use migrations for all schema changes

---

# Security Rules

- Admin APIs require authentication
- Public APIs must be read-only
- Never trust frontend input
- Never expose `owner`, `extra`, or internal IDs in public responses
- Validate uploaded file type, MIME type, and size
- Status transitions must be validated server-side against permitted rules

---

# Upload Rules

- Accept only `.dxf` and `.xlsx` in Phase 1
- Validate both files are present before processing begins
- DXF max size: 50MB
- Excel max size: 10MB
- Process asynchronously — never block the HTTP response on DXF parsing

---

# Git Rules

Use:

```text
main
develop
feature/*
hotfix/*
```

Pull requests must include:

- Summary
- Screenshots for UI changes
- API contract changes if any
- Migration notes if any
- Test notes

---

# Testing Rules

Minimum Phase 1 tests:

- DXF + Excel upload API (happy path)
- DXF upload with invalid/missing Excel (error path)
- Get public layout API
- Update plot status API (valid transitions)
- Update plot status API (invalid transition → 400)
- Public layout page renders with circles
- Search by plot number pans to correct position
- Admin status update flow
