# Layouts API

# Layout Resource

A layout represents one uploaded real-estate layout plan — a DXF + Excel pair that has been parsed into a rendered preview and plot records.

---

# Fields

| Field | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| name | TEXT | Display name |
| slug | TEXT | Public URL slug |
| dxf_file_url | TEXT | Original uploaded DXF |
| excel_file_url | TEXT | Original uploaded Excel |
| preview_url | TEXT | Generated PNG (2400×2400px) |
| hotspots_url | TEXT | Generated hotspot JSON |
| status | TEXT | `processing` / `published` / `failed` |
| plot_count | INTEGER | Total plots parsed |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

---

# Create Layout

```text
POST /api/admin/layouts
Content-Type: multipart/form-data
```

Fields:

```text
name: string         — display name e.g. "Suryapet Phase 1"
dxf_file: File       — .dxf layout file
excel_file: File     — .xlsx plot data file
```

The upload is asynchronous. The API accepts the files, validates them, creates the layout record with `status: processing`, and triggers background parsing.

Response (immediate):

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

The admin polls `GET /api/admin/layouts/{layoutId}` or receives a webhook/websocket update when status changes to `published` or `failed`.

---

# Get Layout (Admin)

```text
GET /api/admin/layouts/{layoutId}
```

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
    "previewUrl": "https://cdn.example.com/layouts/uuid/preview.png",
    "hotspotsUrl": "https://cdn.example.com/layouts/uuid/hotspots.json",
    "shareUrl": "/layouts/suryapet-phase-1",
    "createdAt": "2026-05-20T10:00:00Z"
  }
}
```

---

# List Layouts (Admin)

```text
GET /api/admin/layouts
```

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

# Public Layout

```text
GET /api/public/layouts/{slug}
```

Auth: not required.

Response:

```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "name": "Suryapet Phase 1",
    "slug": "suryapet-phase-1",
    "previewUrl": "https://cdn.example.com/layouts/uuid/preview.png",
    "hotspotsUrl": "https://cdn.example.com/layouts/uuid/hotspots.json",
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

---

# Slug Rules

- Lowercase, hyphenated, unique, stable after creation
- Generated from layout name on upload
- Example: `"Suryapet Phase 1"` → `suryapet-phase-1`
- On collision append `-2`, `-3` etc.

---

# Processing States

The admin UI should handle all three states:

| Status | UI behaviour |
|---|---|
| `processing` | Show spinner, poll every 3s |
| `published` | Show layout with copy URL button |
| `failed` | Show error message with re-upload option |
