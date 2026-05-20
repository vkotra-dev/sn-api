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
 → Validate both files
 → Parse DXF → extract plot positions + render preview PNG
 → Parse Excel → extract plot metadata
 → Join on plot number
 → Create layout record
 → Generate slug
 → Store preview PNG to file storage
 → Store hotspots JSON to file storage
 → Create plot records
 → Return share URL
```

---

# DXF Parsing

## Library

Use `ezdxf` (Python).

```bash
pip install ezdxf
```

## Block extraction

The layout geometry lives inside a named block inserted into the modelspace via an INSERT entity. The parser must:

1. Find the INSERT entity in modelspace
2. Resolve the block name
3. Work entirely in block-local coordinate space (do not apply INSERT offset)

```python
import ezdxf

doc = ezdxf.readfile("layout.dxf")
msp = doc.modelspace()

# Find the main block INSERT
insert = next(e for e in msp if e.dxftype() == 'INSERT')
block = doc.blocks[insert.dxf.name]
```

## Plot position extraction

Plot markers are on the `Plot_No` layer as `TEXT` entities (plot numbers) and `CIRCLE` entities (visual markers).

Text entities use left/baseline alignment — compute true text centre:

```python
texts = [e for e in block
         if e.dxftype() == 'TEXT'
         and e.dxf.layer == 'Plot_No'
         and e.dxf.text.strip().isdigit()]

plot_positions = {}
for t in texts:
    pno = int(t.dxf.text.strip())
    h = t.dxf.height
    n_chars = len(t.dxf.text.strip())
    char_w = h * 0.6  # standard CAD font width ratio
    cx = t.dxf.insert.x + (n_chars * char_w) / 2
    cy = t.dxf.insert.y + h / 2
    # Get circle radius for hotspot sizing
    circles = [e for e in block if e.dxftype() == 'CIRCLE' and e.dxf.layer == 'Plot_No']
    nearest = min(circles, key=lambda c: (c.dxf.center.x - t.dxf.insert.x)**2
                                       + (c.dxf.center.y - t.dxf.insert.y)**2)
    plot_positions[pno] = {
        'cx': cx,
        'cy': cy,
        'r':  nearest.dxf.radius
    }
```

---

# Preview PNG Generation

## Render layers

Include in render:

| Layer | Purpose | Style |
|---|---|---|
| `plots` | Plot grid lines | `#555`, lw=0.5 |
| `proposed road s` | Road boundaries | `#222`, lw=0.8 |
| `ROAD FILLET` | Plot group outlines | `#333`, lw=0.6 |
| `boundry` | Site boundary | `#000`, lw=1.2 |
| `0` | General geometry | `#666`, lw=0.4 |
| `DIMS` | Dimension lines | `#888`, lw=0.4 |
| `Plot_No` | Circle markers + numbers | `#999`, lw=0.3 |

## Extent calculation

Exclude `DIMS` and `TEXT` layers from extent — they contain stray dimension lines that distort the bounding box. Force a square extent to prevent aspect-ratio drift:

```python
EXCLUDE_EXTENT = {'DIMS', 'TEXT'}
geom_x, geom_y = [], []
for e in block:
    if e.dxf.layer in EXCLUDE_EXTENT:
        continue
    # collect all x, y coordinates from LINE and LWPOLYLINE

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

DPI, FIG_SIZE = 100, 24  # 2400x2400px output

fig, ax = plt.subplots(figsize=(FIG_SIZE, FIG_SIZE), dpi=DPI)
fig.subplots_adjust(0, 0, 1, 1)
ax.set_xlim(xmin, xmax)
ax.set_ylim(ymin, ymax)
ax.axis('off')

# Draw all layers (including DIMS)
# Draw circles + numbers at plot_positions centres

plt.savefig("preview.png", dpi=DPI, facecolor='white')
```

**Do not use `set_aspect('equal')` or `invert_yaxis()`** — equal data ranges + square figure handle aspect automatically without drift.

## Hotspot JSON

Capture pixel positions immediately after render using matplotlib's data transform:

```python
fig.canvas.draw()
fig_h = fig.get_figheight() * DPI
hotspots = {}
for pno, pos in plot_positions.items():
    px, py_d = ax.transData.transform((pos['cx'], pos['cy']))
    r_px = abs(ax.transData.transform((pos['cx'] + pos['r'] * 0.8, pos['cy']))[0] - px)
    hotspots[pno] = {
        'x': round(px),
        'y': round(fig_h - py_d),  # flip Y: matplotlib Y-up → image Y-down
        'r': max(round(r_px), 5)
    }
```

Output: `plot_hotspots.json` — approximately **35KB raw, 6KB gzipped**.

---

# Excel Parsing

## Expected columns

| Column | Field | Notes |
|---|---|---|
| Plot no | `plot_no` | Integer, 1-943 |
| Owner | `owner` | String |
| Dim ft | `dim_ft` | Raw string e.g. `33*50` or `108.9,110.3*160.3` |
| Size ft | `area_sq_ft` | Numeric |
| Size yards | `area_sq_yd` | Numeric (formula — evaluate or derive from sq_ft) |
| Facing | `facing` | String — may be empty |

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
  "previewUrl": "https://cdn.example.com/layouts/uuid/preview.png",
  "hotspotsUrl": "https://cdn.example.com/layouts/uuid/hotspots.json"
}
```

---

# Validation

Check before processing:

- DXF file extension and MIME type
- Excel file extension and MIME type
- DXF contains at least one INSERT entity
- DXF block contains Plot_No layer with TEXT entities
- Excel has required columns (Plot no, Dim ft, Size ft)
- Plot numbers in DXF match plot numbers in Excel
- No duplicate layout name
- File size limits (DXF < 50MB, Excel < 10MB)
