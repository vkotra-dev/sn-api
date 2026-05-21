# PostgreSQL Schema

# Phase 1 Database Schema

---

# Extensions

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
```

PostGIS is **not required in Phase 1**. Deferred to Phase 2 when GIS/Maps integration is added.

---

# layouts

```sql
CREATE TABLE layouts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                TEXT NOT NULL,
    slug                TEXT UNIQUE NOT NULL,

    -- Source files
    dxf_file_url        TEXT,           -- original uploaded DXF
    excel_file_url      TEXT,           -- original uploaded Excel

    -- Generated assets
    preview_url         TEXT,           -- rendered PNG (2400x2400)
    hotspots_url        TEXT,           -- plot hotspot JSON {plot_no: {x,y,r}}

    -- State
    status              TEXT NOT NULL DEFAULT 'processing',
                        -- processing | published | failed

    plot_count          INTEGER DEFAULT 0,

    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);
```

### status values

| Value | Meaning |
|---|---|
| `processing` | DXF/Excel upload received, parsing in progress |
| `published` | Parse complete, public URL active |
| `failed` | Parse failed, admin must re-upload |

### Notes

- `dxf_file_url` and `excel_file_url` store the original uploaded files for re-processing if needed.
- `preview_url` and `hotspots_url` point to CDN-served generated assets.
- `plot_count` is set after successful parse — convenience field for listing views.

---

# plots

```sql
CREATE TABLE plots (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    layout_id           UUID NOT NULL REFERENCES layouts(id) ON DELETE CASCADE,

    -- Identity
    plot_no             TEXT NOT NULL,  -- always TEXT, e.g. "28", "28A"

    -- Availability
    status              TEXT NOT NULL DEFAULT 'available',
                        -- available | reserved | sold | blocked

    -- Hotspot (pixel position on preview PNG)
    hotspot             JSONB NOT NULL,
                        -- { "x": 1204, "y": 876, "r": 18 }

    -- Dimensions from Excel
    dim_ft              TEXT,           -- raw string e.g. "33*50" or "108.9,110.3*160.3"
    dim_type            TEXT,           -- "rect" or "trap"
    area_sq_ft          NUMERIC,
    area_sq_yd          NUMERIC,

    -- Metadata from Excel
    owner               TEXT,           -- current owner name
    facing              TEXT,           -- road facing direction (may be empty)

    -- Flexible metadata for future fields
    extra               JSONB DEFAULT '{}',

    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW(),

    UNIQUE(layout_id, plot_no)
);
```

### hotspot field

Stores the pixel position of this plot's clickable circle on the preview PNG:

```json
{ "x": 1204, "y": 876, "r": 18 }
```

`x`, `y` — pixel centre position. `r` — circle radius in pixels.

### dim_ft format

| Value | Type | Meaning |
|---|---|---|
| `"33*50"` | `rect` | 33ft wide × 50ft deep |
| `"108.9,110.3*160.3"` | `trap` | front 108.9ft, back 110.3ft, depth 160.3ft |

### status transition rules

| From | Allowed transitions |
|---|---|
| `available` | `reserved`, `blocked` |
| `reserved` | `available`, `sold`, `blocked` |
| `sold` | `blocked` *(admin override only)* |
| `blocked` | `available` |

`sold` → `available` is intentionally not allowed without explicit admin override to prevent accidental re-listing.

### extra field

Reserved for future fields added without a migration — e.g. price, road width, corner flag. Empty by default. Never exposed publicly without explicit whitelisting.

---

# admin_users

```sql
CREATE TABLE admin_users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,      -- bcrypt
    role            TEXT NOT NULL DEFAULT 'admin',
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);
```

### Notes

- Seeded on first deploy via migration or seed script.
- `is_active = FALSE` disables login without deleting the record.
- Phase 1 has one role: `admin`. Additional roles deferred to Phase 2.
- Passwords hashed with bcrypt (min 12 rounds).

---

# Indexes

```sql
-- layouts
CREATE INDEX idx_layouts_status      ON layouts(status);

-- plots
CREATE INDEX idx_plots_layout_id     ON plots(layout_id);
CREATE INDEX idx_plots_status        ON plots(status);
CREATE INDEX idx_plots_layout_status ON plots(layout_id, status);  -- for availability counts

-- admin_users
CREATE INDEX idx_admin_users_email   ON admin_users(email);
```

---

# Removed from Phase 1

| Item | Reason |
|---|---|
| `postgis` extension | Nothing in Phase 1 uses geo queries. Phase 2. |
| `geom geometry(Polygon, 4326)` | Requires PostGIS. Phase 2. |
| `area_sq_m` | Not in source data. Excel provides sq_ft and sq_yd only. |
| `svg_points JSONB` | Renamed to `hotspot` — stores `{x,y,r}`, not polygon points. |
| `metadata JSONB` | Replaced by explicit columns: `owner`, `facing`, `dim_ft`, `extra`. |
| `original_file_url` | Split into `dxf_file_url` and `excel_file_url`. |

---

# layout_upload_jobs

```sql
CREATE TABLE layout_upload_jobs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    layout_id           UUID UNIQUE NOT NULL REFERENCES layouts(id) ON DELETE CASCADE,
    status              TEXT NOT NULL DEFAULT 'pending',
                        -- pending | running | succeeded | failed
    source_dxf_key      TEXT NOT NULL,
    source_excel_key    TEXT NOT NULL,
    error_message       TEXT,
    started_at          TIMESTAMP,
    finished_at         TIMESTAMP,
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);
```

### Notes

- Each layout has exactly one upload job record.
- The job stores object-storage keys for the original source files so a worker can re-download them later.
- `status` tracks the job lifecycle separate from the layout lifecycle.

### Indexes

```sql
CREATE INDEX idx_layout_upload_jobs_layout_id ON layout_upload_jobs(layout_id);
CREATE INDEX idx_layout_upload_jobs_status     ON layout_upload_jobs(status);
```
