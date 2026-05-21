# Upload Pipeline

# Phase 1 Upload Pipeline

---

# Goal

Allow admin users to upload a layout (DXF + Excel) and receive a shareable public URL with a fully rendered interactive layout.

---

# Supported Upload Format

Phase 1 accepts exactly two files per layout upload:

| File | Format | Purpose |
|---|---|---|
| Layout drawing | `.dxf` | Geometry, plot positions, background render |
| Plot data | `.xlsx` | Plot dimensions, owner, area per plot number |

KMZ, DWG, PDF and image-only uploads are **not supported in Phase 1**.

---

# Workflow

```text
Receive DXF + Excel upload
 → Validate file types, sizes, and structure
 → Store original uploaded files (DXF + Excel) to file storage as-is
 → Parse DXF
     → Extract valid plot labels → canonical plot set
     → Extract hotspot positions
     → Render preview PNG
     → Capture pixel-space hotspot coordinates via matplotlib transform
 → Parse and reconcile Excel against DXF canonical set
     → Drop rows with no Plot no (trailing/summary rows) — warn and log
     → Drop rows whose Plot no is not in the DXF set — warn and log
     → Fail if any DXF plot has no Excel row  ← INVALID_UPLOAD
     → Validate required columns on all kept rows
 → Join plot metadata to hotspot positions
 → Create layout record (status: processing)
 → Generate slug
 → Store preview PNG to file storage
 → Store hotspots JSON to file storage
 → Create plot records
 → Update layout status → published
```

The server stores the **original uploaded Excel bytes unchanged**. Reconciliation is performed in memory during parsing — no cleaned copy is written or stored. If any step raises an error, set layout status to `failed` and store the error message for the admin.

---

# DXF Parsing

## Library

```bash
pip install ezdxf
```

Module: `app/layouts/parser/dxf.py`

## Block extraction

All geometry lives inside a named block inserted into modelspace via a single INSERT entity. The parser must:

1. Find the INSERT entity in modelspace (exactly one required)
2. Resolve the block name
3. Work entirely in **block-local coordinate space** — do not apply the INSERT offset

```python
import ezdxf

doc = ezdxf.readfile("layout.dxf")
msp = doc.modelspace()

insert = next(e for e in msp if e.dxftype() == 'INSERT')
block  = doc.blocks[insert.dxf.name]
```

## Plot label validation

The DXF `Plot_No` layer is the source of truth for the plot list. A TEXT entity on this layer is a valid plot label if its text value **starts with one or more digits** and may optionally continue with letters — no spaces, no dots, no dashes.

Any other `TEXT` value on `Plot_No` is ignored and does not stop parsing. The upload fails only if no valid plot labels remain after filtering.

```python
import re

def _is_valid_plot_label(text: str) -> bool:
    """
    Return True if text is a valid plot label.

    Rule: starts with one or more digits and may optionally
    continue with letters, no spaces, no dots, no dashes.

This accepts labels like "28", "9B", and "28A" and rejects all
annotation, dimension, and description text that may appear on the
same layer. Non-matching text is ignored during parsing.
    """
    return bool(re.match(r'^[0-9]+[A-Za-z]+$', text.strip()))
```

| Text value | Accepted | Reason |
|---|---|---|
| `"28"` | ✅ | Pure integer |
| `"141"` | ✅ | Pure integer |
| `"9B"` | ✅ | Digit prefix with letters |
| `"28A"` | ✅ | Digit prefix with letters |
| `"CLUB HOUSE"` | ❌ | Starts with a letter |
| `"10.0M BUILDING LINE"` | ❌ | Contains dot and spaces |
| `"revised club house - 24-5-2021"` | ❌ | Starts with a letter |
| `"Plot 28"` | ❌ | Contains a space — fix the DXF |

No explicit keyword blocklist is needed. The regex is sufficient.

## Plot label normalisation

Plot labels are normalised to a canonical string form before any comparison with Excel:

```python
def _normalise_plot_label(text: str) -> str:
    """
    Normalise a DXF plot label to its canonical string form.

    Leading zeros are stripped from the numeric prefix and the letter suffix
    is uppercased ("028a" → "28A").
    """
    t = text.strip()
    m = re.match(r'^([0-9]+)([A-Za-z]+)?$', t)
    if not m:
        raise ValueError("DXF plot labels must start with one or more digits")
    plot_no = str(int(m.group(1)))
    if m.group(2):
        plot_no = f"{plot_no}{m.group(2).upper()}"
    return plot_no
```

## Plot position extraction

Plot markers are on the `Plot_No` layer as `TEXT` entities (plot numbers) and `CIRCLE` entities (visual markers).

Text entities use left/baseline alignment — compute true text centre:

```python
texts = [e for e in block
         if e.dxftype() == 'TEXT'
         and e.dxf.layer == 'Plot_No'
         and _is_valid_plot_label(e.dxf.text)]

circles = [e for e in block
           if e.dxftype() == 'CIRCLE'
           and e.dxf.layer == 'Plot_No']

plot_positions = {}
for t in texts:
    pno     = _normalise_plot_label(t.dxf.text)
    h       = t.dxf.height
    n_chars = len(t.dxf.text.strip())
    char_w  = h * 0.6  # standard CAD font width ratio
    cx      = t.dxf.insert.x + (n_chars * char_w) / 2
    cy      = t.dxf.insert.y + h / 2

    nearest = min(circles,
                  key=lambda c: (c.dxf.center.x - t.dxf.insert.x) ** 2
                              + (c.dxf.center.y - t.dxf.insert.y) ** 2)

    plot_positions[pno] = {'cx': cx, 'cy': cy, 'r': nearest.dxf.radius}
```

`parse_dxf()` returns `plot_positions` and the derived `plot_numbers` set. The set is passed directly to `parse_excel()` as the canonical reference.

---

# Preview PNG Generation

Module: `app/layouts/parser/dxf.py`

## Render layers

| Layer | Purpose | Colour | Line width |
|---|---|---|---|
| `plots` | Plot grid lines | `#555555` | 0.5 |
| `proposed road s` | Road boundaries | `#222222` | 0.8 |
| `ROAD FILLET` | Plot group outlines | `#333333` | 0.6 |
| `boundry` | Site boundary | `#000000` | 1.2 |
| `0` | General geometry | `#666666` | 0.4 |
| `DIMS` | Dimension lines | `#888888` | 0.4 |
| `Plot_No` | Circle markers + numbers | `#999999` | 0.3 |
| *(all others)* | Fallback | `#aaaaaa` | 0.3 |

## Extent calculation

Exclude `DIMS` and `TEXT` layers from the bounding-box calculation — they contain stray dimension lines that distort the layout extents. Force a **square extent** to prevent aspect-ratio drift:

```python
EXCLUDE_EXTENT = {'DIMS', 'TEXT'}
geom_x, geom_y = [], []
for e in block:
    if e.dxf.layer in EXCLUDE_EXTENT:
        continue
    # collect all x, y coordinates from LINE and LWPOLYLINE entities

x_center = (min(geom_x) + max(geom_x)) / 2
y_center = (min(geom_y) + max(geom_y)) / 2
half = max(max(geom_x) - min(geom_x), max(geom_y) - min(geom_y)) / 2 * 1.03

xmin, xmax = x_center - half, x_center + half
ymin, ymax = y_center - half, y_center + half
# Result: perfectly square extent with 3% padding
```

## Render

```python
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

DPI, FIG_SIZE = 100, 24  # 2400×2400px output

fig, ax = plt.subplots(figsize=(FIG_SIZE, FIG_SIZE), dpi=DPI)
fig.subplots_adjust(0, 0, 1, 1)
ax.set_xlim(xmin, xmax)
ax.set_ylim(ymin, ymax)
ax.axis('off')

# Draw all layers (including DIMS)
# Draw circles + numbers at plot_positions centres

plt.savefig("preview.png", dpi=DPI, facecolor='white')
```

**Do not use `set_aspect('equal')` or `invert_yaxis()`** — equal data ranges plus a square figure handle aspect automatically without drift.

## Hotspot JSON

Capture pixel positions immediately after render using matplotlib's own data transform. This guarantees hotspot positions are pixel-perfect relative to the saved PNG.

```python
fig.canvas.draw()
fig_h = fig.get_figheight() * DPI

hotspots = {}
for pno, pos in plot_positions.items():
    px, py_d = ax.transData.transform((pos['cx'], pos['cy']))
    r_px     = abs(ax.transData.transform((pos['cx'] + pos['r'] * 0.8, pos['cy']))[0] - px)
    hotspots[pno] = {
        'x': round(px),
        'y': round(fig_h - py_d),  # flip Y: matplotlib Y-up → image Y-down
        'r': max(round(r_px), 5)   # minimum 5px radius for visibility
    }
```

Output: `plot_hotspots.json` — approximately **35KB raw, 6KB gzipped**.

---

# Excel Parsing and Reconciliation

Module: `app/layouts/parser/excel.py`

## Expected columns

| Column | Field | Required |
|---|---|---|
| `Plot no` | `plot_no` | **Yes** — key column |
| `Dim ft` | `dim_ft` | **Yes** |
| `Size ft` | `area_sq_ft` | **Yes** |
| `Owner` | `owner` | Optional, admin-only |
| `Size yards` | `area_sq_yd` | Optional |
| `Facing` | `facing` | Optional |

Column names are matched case-insensitively after stripping whitespace.

## Admin guidance: prepare the workbook before uploading

The DXF `Plot_No` layer is the source of truth for the plot list. Before uploading, normalise the Excel workbook to match the DXF plot set so the upload succeeds first time:

1. Extract plot numbers from the DXF `Plot_No` layer using the same label rule — starts with one or more digits, optionally followed by letters.
2. Remove any Excel row whose `Plot no` is not in the DXF plot set.
3. Remove any trailing or summary row with a missing `Plot no`.
4. Ensure every DXF plot number has a row in Excel.
5. For every kept row, make sure `Plot no`, `Dim ft`, and `Size ft` are populated.
6. If a kept row is missing required data, restore it from the original workbook.

The server performs the same checks on the uploaded file. An uncleaned workbook will be rejected.

## Server-side reconciliation (performed in memory on the uploaded file)

The server reconciles the uploaded Excel against the DXF canonical set during parsing. The original uploaded bytes are stored unchanged; reconciliation does not produce a new file.

### Step 1 — Drop rows with no Plot no
Rows where `Plot no` is empty or `None` are dropped and logged (trailing/summary rows).

### Step 2 — Drop Excel rows not in the DXF set
Rows whose `Plot no` does not appear in the DXF canonical set are dropped and logged.

### Step 3 — Fail if DXF plots are missing from Excel (fatal)
If any DXF plot number has no Excel row after steps 1–2, the upload is **rejected**:

```
INVALID_UPLOAD: The following plot numbers are in the DXF but have no row in Excel: ['141', '690'].
Add the missing rows to the workbook and re-upload.
```

### Step 4 — Validate required columns on all kept rows
Every kept row must have non-empty values for `Dim ft` and `Size ft`. A missing value raises `INVALID_UPLOAD` and reports the row number.

## Plot no normalisation

Excel may store plot numbers in several forms. All are normalised to match the DXF canonical form before comparison:

```python
def _normalise_plot_no(raw) -> str:
    """
    Normalise an Excel Plot no cell to match the DXF canonical form.

  digit-only or letter-suffixed: "28" → "28", "9b" → "9B", "28a" → "28A"
    """
    t = str(raw).strip()
    m = re.match(r'^([0-9]+)([A-Za-z]+)?$', t)
    if not m:
        raise ValueError("Excel Plot no must start with one or more digits")
    plot_no = str(int(m.group(1)))
    if m.group(2):
        plot_no = f"{plot_no}{m.group(2).upper()}"
    return plot_no
```

## Dimension format parsing

```python
import re

def parse_dim(dim_str):
    dim_str = str(dim_str).strip()
    if ',' in dim_str:
        m = re.match(r'([\d.]+),([\d.]+)\*([\d.]+)', dim_str)
        if m:
            return {'type': 'trap', 'w1': float(m.group(1)),
                    'w2': float(m.group(2)), 'h': float(m.group(3))}
    else:
        m = re.match(r'([\d.]+)\*([\d.]+)', dim_str)
        if m:
            return {'type': 'rect', 'w': float(m.group(1)), 'h': float(m.group(2))}
    return None
```

---

# Output

Upload must return:

```json
{
  "layoutId": "uuid",
  "name": "Suryapet Phase 1",
  "slug": "suryapet-phase-1",
  "shareUrl": "/layouts/suryapet-phase-1",
  "plotCount": 941,
  "previewUrl": "/storage/layouts/uuid/preview.png",
  "hotspotsUrl": "/storage/layouts/uuid/hotspots.json"
}
```

## Storage URLs

`previewUrl` and `hotspotsUrl` are not guaranteed to be absolute URLs.

| Environment | Example value |
|---|---|
| Local / dev | `/storage/layouts/uuid/preview.png` |
| Production with CDN | `https://cdn.example.com/layouts/uuid/preview.png` |
| S3 without CDN base | `s3://bucket/layouts/uuid/preview.png` |

Consumer rule: resolve against the API origin before use.

```ts
const resolvedUrl = new URL(storageUrl, apiOrigin).toString();
```

Use the **API origin**, not the frontend app origin. If the backend is in S3 mode without a CDN base, the value may be an `s3://` URI and is not directly fetchable by a browser.

---

# Error Codes

| Code | Trigger |
|---|---|
| `INVALID_UPLOAD` | File type or size limit exceeded |
| `INVALID_UPLOAD` | DXF has no INSERT entity in modelspace |
| `INVALID_UPLOAD` | DXF has multiple INSERT entities |
| `INVALID_UPLOAD` | No valid plot labels found on `Plot_No` layer |
| `INVALID_UPLOAD` | Excel missing required column (`Plot no`, `Dim ft`, `Size ft`) |
| `INVALID_UPLOAD` | Required column empty on a kept row |
| `INVALID_UPLOAD` | DXF plot numbers missing from Excel after reconciliation |
| `DUPLICATE_LAYOUT_NAME` | Layout name already exists |
| `LAYOUT_FAILED` | Unhandled exception during background processing |

---

# Validation

Check before processing:

- [ ] DXF file extension and MIME type valid
- [ ] Excel file extension and MIME type valid
- [ ] DXF < 50 MB, Excel < 10 MB
- [ ] DXF contains exactly one INSERT entity in modelspace
- [ ] DXF `Plot_No` layer contains at least one valid plot label
- [ ] Excel has required columns: `Plot no`, `Dim ft`, `Size ft`
- [ ] Every valid DXF plot number has a corresponding Excel row (after reconciliation)
- [ ] No duplicate layout name

## Integration Test Coverage

The repository includes an end-to-end test that uploads the real sample files from the project root:

- `SURYAPET-DTCP-LAYOUT-2 - REVISED 24-5-21 club house.dxf`
- `complete plots.xlsx`

That test verifies the layout is published successfully and the resulting public layout contains the expected plot count.
