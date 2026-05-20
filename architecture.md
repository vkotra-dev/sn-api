# architecture.md

# Interactive Layout Platform — Phase 1 Architecture

---

# Purpose

Phase 1 delivers a focused platform for uploading layout files, publishing a public layout URL, and managing plot availability.

---

# High-Level Architecture

```text
Admin User
   ↓
Next.js Admin Area
   ↓
FastAPI Backend
   ↓
PostgreSQL + File Storage (CDN)
   ↓
Public Share URL
   ↓
Next.js Public Viewer
```

---

# Phase 1 System Flow

```text
Admin logs in
 → Uploads DXF + Excel pair
 → API validates both files
 → API parses DXF block → extracts plot positions → renders preview PNG
 → API parses Excel → extracts plot metadata
 → API joins on plot number → creates plot records
 → API generates hotspot JSON → stores to CDN
 → API generates public slug
 → Layout status: processing → published
 → Admin copies public URL
 → Public user opens URL
 → Public viewer loads PNG + hotspot JSON
 → SVG circles overlaid on PNG, coloured by status
 → Public user clicks circle → sees plot details
 → Admin updates plot availability
 → Public viewer reflects new status colour
```

---

# Main Applications

## frontend-react (Next.js)

Responsible for:

- Admin dashboard
- Public layout viewer (image map)
- Upload UI (DXF + Excel pair)
- PNG background + SVG circle overlay
- Zoom and pan (react-zoom-pan-pinch)
- Search by plot number → animated pan
- Plot detail side panel
- Plot status editor (admin only)

## backend-api (FastAPI)

Responsible for:

- Authentication
- DXF + Excel upload and validation
- DXF parsing (ezdxf) → preview PNG + hotspot JSON
- Excel parsing (openpyxl) → plot metadata
- Layout and plot records
- CDN asset storage
- Public layout API
- Admin-only mutation APIs

---

# How the Layout Viewer Works

The viewer is an **image map**, not an SVG diagram or map tile system:

```text
PNG (2400×2400px, rendered from DXF)
 ↑ background image

SVG overlay (one <circle> per plot)
 ↑ coloured by status, clickable

react-zoom-pan-pinch
 ↑ wraps both — they scale together on zoom/pan

Hotspot JSON ({plot_no: {x, y, r}})
 ↑ pixel positions for SVG circles — generated server-side, never computed client-side
```

This approach was chosen because:
- DXF files contain plot position markers (circles + numbers) but not polygon boundaries
- Rendering the full DXF as a PNG gives a correct layout background
- Plot positions extracted from DXF text entities give pixel-accurate hotspot centres
- No manual polygon drawing required — fully automated

---

# Upload Format

Phase 1 accepts exactly two files per layout:

| File | Format | Purpose |
|---|---|---|
| Layout drawing | `.dxf` | Geometry render + plot positions |
| Plot data | `.xlsx` | Plot metadata per plot number |

KMZ, DWG, PDF and image-only uploads are not supported in Phase 1.

---

# Frontend Security Zones

## Public Area

Routes that do not require login:

```text
/layouts/[layoutSlug]
```

Public users can:

- View layout PNG
- See plot availability colours
- Click plots to view public metadata
- Search by plot number

Public users cannot:

- Upload layouts
- Edit status
- View admin pages
- See owner names or private metadata

## Secure Admin Area

Routes that require login:

```text
/admin
/admin/layouts
/admin/layouts/new
/admin/layouts/[layoutId]
```

Admins can:

- Upload DXF + Excel pairs
- Monitor processing status
- List layouts and copy public URLs
- Edit plot status
- View all metadata including owner

---

# Phase 1 Data Model

## Layout

Represents one uploaded layout (DXF + Excel pair).

Core fields:

- id, name, slug
- dxf_file_url, excel_file_url
- preview_url, hotspots_url
- status (processing / published / failed)
- plot_count

## Plot

Represents one clickable plot on a layout.

Core fields:

- id, layout_id, plot_no
- status (available / reserved / sold / blocked)
- hotspot `{x, y, r}` — pixel position on preview PNG
- dim_ft, dim_type, area_sq_ft, area_sq_yd
- owner, facing

---

# Async Processing

Upload is asynchronous. After files are received:

1. Layout record created with `status: processing`
2. Background task parses DXF + Excel
3. Generates preview PNG and hotspot JSON
4. Stores assets to CDN
5. Creates plot records
6. Updates layout `status: published` (or `failed` on error)

Admin UI polls for status or receives a live update.

---

# File Handling

All generated assets (preview PNG, hotspot JSON) are stored in S3-compatible object storage and served via CDN. Original uploaded files (DXF, Excel) are also retained for re-processing.

---

# Deployment

Recommended Phase 1 deployment:

```text
Frontend:  Vercel
Backend:   AWS ECS / Render / Railway / Fly.io
Database:  PostgreSQL
Storage:   S3-compatible bucket + CDN
```

---

# Phase 1 Boundary

Do not overbuild Phase 1.

The goal is a usable upload/share/status platform. The following are explicitly deferred to Phase 2:

- Google Maps / KMZ integration
- PostGIS geographic queries
- Booking and payment workflows
- Customer records
- Pricing management
- Advanced role hierarchy
- Analytics dashboard
