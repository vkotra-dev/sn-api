# api-contracts.md

# Phase 1 API Contracts

---

# Standard Response Format

## Success

```json
{
  "success": true,
  "data": {}
}
```

## Error

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message"
  }
}
```

---

# Health

## GET /api/health

Checks that the app can connect to the database.

Response when healthy:

```json
{
  "success": true,
  "data": {
    "status": "ok",
    "database": "ok"
  }
}
```

Response when the database is unavailable:

```json
{
  "success": false,
  "error": {
    "code": "SERVICE_UNAVAILABLE",
    "message": "Database unavailable"
  }
}
```

---

# Authentication

## POST /api/auth/login

Request:

```json
{
  "email": "admin@example.com",
  "password": "password"
}
```

Response:

```json
{
  "success": true,
  "data": {
    "accessToken": "jwt-token",
    "user": {
      "id": "uuid",
      "email": "admin@example.com",
      "role": "admin"
    }
  }
}
```

---

# Layouts

## POST /api/admin/layouts

Upload a new layout. Auth: required.

Request: `multipart/form-data`

```text
name:       string   — display name e.g. "Suryapet Phase 1"
dxf_file:   File     — .dxf layout file
excel_file: File     — .xlsx plot data file
```

Response (immediate — processing begins in background):

```json
{
  "success": true,
  "data": {
    "layoutId": "uuid",
    "name": "Suryapet Phase 1",
    "slug": "suryapet-phase-1",
    "status": "processing"
  }
}
```

---

## GET /api/admin/layouts

List all layouts. Auth: required.

Response:

```json
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "name": "Suryapet Phase 1",
      "slug": "suryapet-phase-1",
      "status": "published",
      "plotCount": 941,
      "shareUrl": "/layouts/suryapet-phase-1",
      "createdAt": "2026-05-20T10:00:00Z"
    }
  ]
}
```

---

## GET /api/admin/layouts/{layoutId}

Get single layout with full detail. Auth: required.

Response:

```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "name": "Suryapet Phase 1",
    "slug": "suryapet-phase-1",
    "status": "published",
    "plotCount": 941,
    "previewUrl": "/storage/layouts/uuid/preview.png",
    "hotspotsUrl": "/storage/layouts/uuid/hotspots.json",
    "shareUrl": "/layouts/suryapet-phase-1",
    "createdAt": "2026-05-20T10:00:00Z"
  }
}
```

---

## GET /api/public/layouts/{slug}

Get public layout with all plot data. Auth: not required.

Response:

```json
{
  "success": true,
  "data": {
    "name": "Suryapet Phase 1",
    "slug": "suryapet-phase-1",
    "previewUrl": "/storage/layouts/uuid/preview.png",
    "hotspotsUrl": "/storage/layouts/uuid/hotspots.json",
    "plots": [
      {
        "plotNo": "28",
        "status": "available",
        "hotspot": { "x": 1204, "y": 876, "r": 18 },
        "areaSqFt": 1650,
        "areaSqYd": 183.3,
        "dimFt": "33*50",
        "facing": "East"
      }
    ]
  }
}
```

Fields never returned publicly: `owner`, `extra`.

### Storage URLs

`previewUrl` and `hotspotsUrl` are not guaranteed to be absolute URLs.

| Environment | Example value |
|---|---|
| Local / dev | `/storage/layouts/uuid/preview.png` |
| Production with CDN base | `https://cdn.example.com/layouts/uuid/preview.png` |
| S3 without CDN base | `s3://bucket/layouts/uuid/preview.png` |

Consumer rule: resolve storage URLs against the API origin before use.

```ts
const resolvedUrl = new URL(storageUrl, apiOrigin).toString();
```

Use the API origin, not the frontend app origin.
If the backend is configured without a CDN base in S3 mode, the value may be an `s3://` URI and should not be treated as directly fetchable by a browser.

---

# Plots

## GET /api/admin/layouts/{layoutId}/plots/{plotNo}

Get a single plot with full detail. Auth: required.

Response:

```json
{
  "success": true,
  "data": {
    "plotNo": "28",
    "status": "available",
    "owner": "Mr. Varun",
    "dimFt": "40*50",
    "dimType": "rect",
    "areaSqFt": 2000,
    "areaSqYd": 222.2,
    "facing": "East",
    "hotspot": { "x": 1204, "y": 876, "r": 18 }
  }
}
```

---

## PATCH /api/admin/layouts/{layoutId}/plots/{plotNo}/status

Update plot availability. Auth: required.

Request:

```json
{
  "status": "sold"
}
```

Response:

```json
{
  "success": true,
  "data": {
    "plotNo": "28",
    "status": "sold"
  }
}
```

Error on invalid transition:

```json
{
  "success": false,
  "error": {
    "code": "INVALID_STATUS_TRANSITION",
    "message": "Cannot transition from sold to available"
  }
}
```

---

# Plot Status Values

```text
available
reserved
sold
blocked
```

### Transition rules

| From | Allowed to |
|---|---|
| `available` | `reserved`, `blocked` |
| `reserved` | `available`, `sold`, `blocked` |
| `sold` | `blocked` only |
| `blocked` | `available` |

---

# Error Codes

| Code | HTTP | Meaning |
|---|---|---|
| `UNAUTHORIZED` | 401 | Login required |
| `FORBIDDEN` | 403 | Access denied |
| `LAYOUT_NOT_FOUND` | 404 | Layout does not exist |
| `PLOT_NOT_FOUND` | 404 | Plot does not exist |
| `LAYOUT_PROCESSING` | 409 | Layout is still being processed |
| `LAYOUT_FAILED` | 422 | Layout processing failed |
| `INVALID_STATUS` | 400 | Status value not recognised |
| `INVALID_STATUS_TRANSITION` | 400 | Transition not permitted |
| `INVALID_UPLOAD` | 400 | File missing, wrong type or too large |
| `DUPLICATE_LAYOUT_NAME` | 409 | Layout name already exists |
| `INTERNAL_ERROR` | 500 | Unexpected server error |
