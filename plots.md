# Plots API

# Plot Resource

A plot represents a clickable circle on a layout — its position, availability status, and metadata from the Excel upload.

---

# Fields

| Field | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| layout_id | UUID | Parent layout |
| plot_no | TEXT | e.g. `"28"`, `"28A"` |
| status | TEXT | See status values |
| hotspot | JSONB | `{x, y, r}` — pixel position on preview PNG |
| dim_ft | TEXT | Raw dimension string from Excel |
| dim_type | TEXT | `rect` or `trap` |
| area_sq_ft | NUMERIC | Square feet |
| area_sq_yd | NUMERIC | Square yards |
| owner | TEXT | Owner name from Excel |
| facing | TEXT | Road facing direction (may be empty) |
| extra | JSONB | Reserved for future fields |

---

# Status Values

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

`sold` → `available` requires explicit admin override to prevent accidental re-listing.

---

# Get Single Plot (Admin)

```text
GET /api/admin/layouts/{layoutId}/plots/{plotNo}
```

Auth: required. Returns full plot detail including owner.

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

# Update Status

```text
PATCH /api/admin/layouts/{layoutId}/plots/{plotNo}/status
```

Request:

```json
{
  "status": "reserved"
}
```

Response:

```json
{
  "success": true,
  "data": {
    "plotNo": "28",
    "status": "reserved"
  }
}
```

Error if transition not allowed:

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

# Public Plot Data

The public layout endpoint returns plots with these fields only:

```json
{
  "plotNo": "28",
  "status": "available",
  "hotspot": { "x": 1204, "y": 876, "r": 18 },
  "areaSqFt": 1650,
  "areaSqYd": 183.3,
  "dimFt": "33*50",
  "facing": "East"
}
```

Never expose publicly: `owner`, `extra`, `id`, `layout_id`.
