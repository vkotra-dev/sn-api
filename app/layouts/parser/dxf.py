from __future__ import annotations

from dataclasses import dataclass
from math import cos, pi, sin
from pathlib import Path
from typing import Iterable

import ezdxf
from ezdxf.entities import Circle, LWPolyline, Line, Text
import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.patches import Arc, Circle as CirclePatch


EXCLUDE_EXTENT_LAYERS = {"DIMS", "TEXT"}
PLOT_LAYER = "Plot_No"


@dataclass(slots=True)
class PlotPosition:
    plot_no: str
    cx: float
    cy: float
    r: float


def load_layout_block(dxf_path: Path):
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()
    insert = next((entity for entity in msp if entity.dxftype() == "INSERT"), None)
    if insert is None:
        raise ValueError("DXF does not contain an INSERT entity")
    block = doc.blocks[insert.dxf.name]
    return block


def _is_plot_text(entity: Text) -> bool:
    text = getattr(entity.dxf, "text", None)
    return text is not None and str(text).strip() != ""


def extract_plot_positions(block) -> dict[str, PlotPosition]:
    texts = [
        entity
        for entity in block
        if entity.dxftype() == "TEXT"
        and getattr(entity.dxf, "layer", "") == PLOT_LAYER
        and _is_plot_text(entity)
    ]
    if not texts:
        raise ValueError("DXF block does not contain Plot_No TEXT entities")

    circles = [
        entity
        for entity in block
        if entity.dxftype() == "CIRCLE" and getattr(entity.dxf, "layer", "") == PLOT_LAYER
    ]

    plot_positions: dict[str, PlotPosition] = {}
    for text in texts:
        plot_no = text.dxf.text.strip()
        height = float(text.dxf.height or 0)
        char_width = height * 0.6
        insert = text.dxf.insert
        cx = float(insert.x) + (len(plot_no) * char_width) / 2
        cy = float(insert.y) + height / 2

        if circles:
            nearest = min(
                circles,
                key=lambda circle: (
                    float(circle.dxf.center.x) - float(insert.x)
                )
                ** 2
                + (float(circle.dxf.center.y) - float(insert.y)) ** 2,
            )
            radius = float(nearest.dxf.radius)
        else:
            radius = max(height * 0.4, 1.0)

        plot_positions[plot_no] = PlotPosition(plot_no=plot_no, cx=cx, cy=cy, r=radius)

    return plot_positions


def _entity_points(entity) -> Iterable[tuple[float, float]]:
    if entity.dxftype() == "LINE":
        yield (float(entity.dxf.start.x), float(entity.dxf.start.y))
        yield (float(entity.dxf.end.x), float(entity.dxf.end.y))
    elif entity.dxftype() == "LWPOLYLINE":
        for x, y, *_rest in entity.get_points("xyseb"):
            yield (float(x), float(y))
    elif entity.dxftype() == "CIRCLE":
        center = entity.dxf.center
        radius = float(entity.dxf.radius)
        yield (float(center.x) - radius, float(center.y) - radius)
        yield (float(center.x) + radius, float(center.y) + radius)
    elif entity.dxftype() == "ARC":
        center = entity.dxf.center
        radius = float(entity.dxf.radius)
        start_angle = float(entity.dxf.start_angle)
        end_angle = float(entity.dxf.end_angle)
        for angle in (start_angle, end_angle):
            radians = angle * pi / 180.0
            yield (float(center.x) + radius * cos(radians), float(center.y) + radius * sin(radians))
    elif entity.dxftype() == "TEXT":
        insert = entity.dxf.insert
        yield (float(insert.x), float(insert.y))


def _collect_extent(block) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []
    for entity in block:
        if getattr(entity.dxf, "layer", "") in EXCLUDE_EXTENT_LAYERS:
            continue
        for x, y in _entity_points(entity):
            xs.append(x)
            ys.append(y)

    if not xs or not ys:
        raise ValueError("DXF block does not contain renderable geometry")

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    x_center = (min_x + max_x) / 2
    y_center = (min_y + max_y) / 2
    half = max(max_x - min_x, max_y - min_y) / 2 * 1.03
    return x_center - half, x_center + half, y_center - half, y_center + half


def _layer_style(layer: str) -> tuple[str, float]:
    styles = {
        "plots": ("#555555", 0.5),
        "proposed road s": ("#222222", 0.8),
        "ROAD FILLET": ("#333333", 0.6),
        "boundry": ("#000000", 1.2),
        "0": ("#666666", 0.4),
        "DIMS": ("#888888", 0.4),
        PLOT_LAYER: ("#999999", 0.3),
    }
    return styles.get(layer, ("#666666", 0.4))


def render_preview_and_hotspots(
    block,
    plot_positions: dict[str, PlotPosition],
    preview_path: Path,
) -> dict[str, dict[str, int]]:
    xmin, xmax, ymin, ymax = _collect_extent(block)

    dpi = 100
    fig_size = 24
    fig, ax = plt.subplots(figsize=(fig_size, fig_size), dpi=dpi)
    fig.subplots_adjust(0, 0, 1, 1)
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.axis("off")

    for entity in block:
        layer = getattr(entity.dxf, "layer", "")
        color, linewidth = _layer_style(layer)

        if entity.dxftype() == "LINE":
            ax.plot(
                [float(entity.dxf.start.x), float(entity.dxf.end.x)],
                [float(entity.dxf.start.y), float(entity.dxf.end.y)],
                color=color,
                linewidth=linewidth,
            )
        elif entity.dxftype() == "LWPOLYLINE":
            points = [(float(x), float(y)) for x, y, *_ in entity.get_points("xyseb")]
            if entity.closed and points:
                points = points + [points[0]]
            if points:
                xs, ys = zip(*points)
                ax.plot(xs, ys, color=color, linewidth=linewidth)
        elif entity.dxftype() == "CIRCLE":
            center = entity.dxf.center
            ax.add_patch(
                CirclePatch(
                    (float(center.x), float(center.y)),
                    float(entity.dxf.radius),
                    fill=False,
                    edgecolor=color,
                    linewidth=linewidth,
                )
            )
        elif entity.dxftype() == "ARC":
            center = entity.dxf.center
            ax.add_patch(
                Arc(
                    (float(center.x), float(center.y)),
                    2 * float(entity.dxf.radius),
                    2 * float(entity.dxf.radius),
                    angle=0,
                    theta1=float(entity.dxf.start_angle),
                    theta2=float(entity.dxf.end_angle),
                    color=color,
                    linewidth=linewidth,
                )
            )
        elif entity.dxftype() == "TEXT":
            insert = entity.dxf.insert
            ax.text(
                float(insert.x),
                float(insert.y),
                entity.dxf.text,
                fontsize=max(float(entity.dxf.height or 1) * 0.8, 1),
                color=color,
                ha="left",
                va="baseline",
            )

    fig.canvas.draw()
    fig_height = fig.get_figheight() * dpi
    hotspots: dict[str, dict[str, int]] = {}
    for plot_no, pos in plot_positions.items():
        px, py = ax.transData.transform((pos.cx, pos.cy))
        radius_px = abs(ax.transData.transform((pos.cx + pos.r * 0.8, pos.cy))[0] - px)
        hotspots[plot_no] = {
            "x": round(px),
            "y": round(fig_height - py),
            "r": max(round(radius_px), 5),
        }

    preview_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(preview_path, dpi=dpi, facecolor="white")
    plt.close(fig)
    return hotspots
