"""
Local infographic diagram renderer.

Goal:
- No external rendering services (no mermaid.ink).
- Deterministic rendering to both PNG (for document insertion) and SVG (for editing).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import math
import os


def _require_pillow():
    try:
        from PIL import Image, ImageDraw, ImageFont  # noqa: F401
    except Exception as e:  # pragma: no cover
        raise RuntimeError("Pillow 未安装：请先运行 pip install pillow") from e


def _hex_to_rgba(hex_color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    c = (hex_color or "").strip().lstrip("#")
    if len(c) == 3:
        c = "".join([ch * 2 for ch in c])
    if len(c) != 6:
        return (0, 0, 0, alpha)
    r = int(c[0:2], 16)
    g = int(c[2:4], 16)
    b = int(c[4:6], 16)
    return (r, g, b, alpha)


def _escape_xml(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _pick_font_paths() -> dict[str, str]:
    # Windows-first (repo is typically run on Windows); fall back to common Linux paths.
    candidates = [
        ("regular", r"C:/Windows/Fonts/msyh.ttc"),
        ("bold", r"C:/Windows/Fonts/msyhbd.ttc"),
        ("regular", r"C:/Windows/Fonts/simsun.ttc"),
        ("bold", r"C:/Windows/Fonts/simhei.ttf"),
        ("regular", r"/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ("bold", r"/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ]
    found: dict[str, str] = {}
    for kind, path in candidates:
        if kind in found:
            continue
        if os.path.exists(path):
            found[kind] = path
    return found


@dataclass(frozen=True)
class _Fonts:
    title: Any
    header: Any
    body: Any
    body_small: Any
    bold: Any


def _load_fonts():
    _require_pillow()
    from PIL import ImageFont

    paths = _pick_font_paths()
    regular_path = paths.get("regular")
    bold_path = paths.get("bold") or paths.get("regular")

    def _tt(path: Optional[str], size: int):
        if path:
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                pass
        return ImageFont.load_default()

    return _Fonts(
        title=_tt(bold_path, 44),
        header=_tt(bold_path, 26),
        body=_tt(regular_path, 22),
        body_small=_tt(regular_path, 20),
        bold=_tt(bold_path, 22),
    )


def _text_width(draw, text: str, font) -> float:
    try:
        return float(draw.textlength(text, font=font))
    except Exception:
        bbox = draw.textbbox((0, 0), text, font=font)
        return float(bbox[2] - bbox[0])


def _wrap_text(draw, text: str, font, max_width: int) -> List[str]:
    s = (text or "").strip()
    if not s:
        return []

    lines: List[str] = []
    current = ""
    for ch in s:
        if ch == "\n":
            if current:
                lines.append(current)
            current = ""
            continue

        trial = current + ch
        if not current:
            current = ch
            continue

        if _text_width(draw, trial, font) <= max_width:
            current = trial
        else:
            lines.append(current)
            current = ch
    if current:
        lines.append(current)
    return lines


def _wrap_bullet(draw, text: str, font, max_width: int, *, bullet: str = "• ") -> List[str]:
    raw = (text or "").strip()
    if not raw:
        return []
    prefix = bullet
    prefix_w = _text_width(draw, prefix, font)
    inner = max(1, int(max_width - prefix_w))
    wrapped = _wrap_text(draw, raw, font, inner)
    if not wrapped:
        return []
    out = [prefix + wrapped[0]]
    for ln in wrapped[1:]:
        out.append(" " * len(prefix) + ln)
    return out


def _rounded_rect_png(draw, xy, radius: int, fill, outline, width: int = 2):
    # Pillow has rounded_rectangle on modern versions
    try:
        draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)
        return
    except Exception:
        # Fallback: plain rectangle
        draw.rectangle(xy, fill=fill, outline=outline, width=width)


def _arrow_png(draw, x1: int, y1: int, x2: int, y2: int, *, color, width: int = 3):
    draw.line((x1, y1, x2, y2), fill=color, width=width)
    # arrow head
    ang = math.atan2(y2 - y1, x2 - x1)
    head = 12
    a1 = ang + math.pi * 0.85
    a2 = ang - math.pi * 0.85
    p1 = (x2 + int(head * math.cos(a1)), y2 + int(head * math.sin(a1)))
    p2 = (x2 + int(head * math.cos(a2)), y2 + int(head * math.sin(a2)))
    draw.polygon([ (x2, y2), p1, p2 ], fill=color)


def _arrow_svg(x1: int, y1: int, x2: int, y2: int, *, stroke: str, stroke_width: int = 3) -> str:
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="{stroke_width}" marker-end="url(#arrow)"/>'


def _normalize_list(value: Any, *, limit: int, default: Optional[List[str]] = None) -> List[str]:
    if isinstance(value, list):
        items = [str(x).strip() for x in value if x is not None and str(x).strip()]
        return items[:limit]
    if isinstance(value, str) and value.strip():
        return [value.strip()][:limit]
    return (default or [])[:limit]


def _normalize_technical_route_spec(spec: Dict[str, Any], title: str) -> Dict[str, Any]:
    stages = spec.get("stages") or spec.get("steps") or []
    if not isinstance(stages, list):
        stages = []
    norm_stages: List[Dict[str, Any]] = []
    for s in stages:
        if not isinstance(s, dict):
            continue
        st_title = str(s.get("title") or s.get("name") or "").strip()
        bullets = _normalize_list(s.get("bullets") or s.get("items") or s.get("lines"), limit=4)
        if not st_title and not bullets:
            continue
        if not st_title:
            st_title = f"阶段 {len(norm_stages) + 1}"
        if not bullets:
            bullets = ["关键方法与技术路线", "数据/实验与验证", "阶段产出与指标"]
        norm_stages.append({"title": st_title[:32], "bullets": bullets})
        if len(norm_stages) >= 6:
            break
    if len(norm_stages) < 3:
        norm_stages = [
            {"title": "任务拆解", "bullets": ["明确目标与指标", "梳理关键问题", "分解任务包"]},
            {"title": "方法实现", "bullets": ["核心方法设计", "关键技术实现", "实验/仿真验证"]},
            {"title": "集成评估", "bullets": ["系统集成与优化", "对标评估与迭代", "形成成果输出"]},
        ]
    return {"title": title, "stages": norm_stages}


def _normalize_research_framework_spec(spec: Dict[str, Any], title: str) -> Dict[str, Any]:
    def _box(key: str, default_title: str, default_bullets: List[str]) -> Dict[str, Any]:
        raw = spec.get(key) or {}
        if not isinstance(raw, dict):
            raw = {}
        box_title = str(raw.get("title") or default_title).strip() or default_title
        bullets = _normalize_list(raw.get("bullets") or raw.get("items") or raw.get("lines"), limit=4, default=default_bullets)
        return {"title": box_title[:28], "bullets": bullets}

    goal = _box("goal", "研究目标", ["凝练核心目标", "明确创新点", "量化考核指标"])
    hypotheses = _box("hypotheses", "科学问题/假设", ["提出关键科学问题", "给出可检验假设", "定义验证路径"])
    support = _box("support", "支撑条件", ["研究基础与团队", "数据/平台/设备", "合作与资源保障"])
    outcomes = _box("outcomes", "预期成果", ["论文/专利/标准", "原型/系统/平台", "数据集/开源工具"])

    wps = spec.get("work_packages") or spec.get("modules") or spec.get("wps") or []
    if not isinstance(wps, list):
        wps = []
    norm_wps: List[Dict[str, Any]] = []
    for w in wps:
        if not isinstance(w, dict):
            continue
        wt = str(w.get("title") or w.get("name") or "").strip()
        bullets = _normalize_list(w.get("bullets") or w.get("items") or w.get("lines"), limit=4)
        if not wt and not bullets:
            continue
        if not wt:
            wt = f"WP{len(norm_wps) + 1}"
        if not bullets:
            bullets = ["研究内容与任务", "关键方法与实验", "阶段成果与指标"]
        norm_wps.append({"title": wt[:28], "bullets": bullets})
        if len(norm_wps) >= 3:
            break
    while len(norm_wps) < 3:
        idx = len(norm_wps) + 1
        norm_wps.append({"title": f"WP{idx} 研究内容", "bullets": ["研究内容与任务", "关键方法与实验", "阶段成果与指标"]})
    return {
        "title": title,
        "goal": goal,
        "hypotheses": hypotheses,
        "support": support,
        "work_packages": norm_wps,
        "outcomes": outcomes,
    }


def _render_technical_route(spec: Dict[str, Any], *, width: int = 1600) -> Tuple[bytes, str]:
    _require_pillow()
    from PIL import Image, ImageDraw

    fonts = _load_fonts()

    theme = {
        "bg": "#F8FAFC",
        "text": "#0F172A",
        "muted": "#334155",
        "border": "#CBD5E1",
        "arrow": "#64748B",
        "title": "#0F172A",
        "stage_fills": ["#FFF7ED", "#ECFDF5", "#EFF6FF", "#FDF2F8", "#F5F3FF", "#F0FDFA"],
        "stage_strokes": ["#FDBA74", "#6EE7B7", "#93C5FD", "#F9A8D4", "#C4B5FD", "#5EEAD4"],
        "accent": "#F97316",
    }

    title = str(spec.get("title") or "技术路线图").strip() or "技术路线图"
    stages: List[Dict[str, Any]] = spec.get("stages") or []

    margin_x = 88
    top = 80
    gap = 26
    arrow_gap = 18
    box_w = width - margin_x * 2
    pad = 34
    header_h = 56
    radius = 22

    # Measure & layout
    dummy = Image.new("RGBA", (width, 10), (255, 255, 255, 0))
    d = ImageDraw.Draw(dummy)
    line_h = 30

    stage_layout: List[dict] = []
    y = top + 70
    for i, st in enumerate(stages):
        st_title = str(st.get("title") or f"阶段 {i + 1}").strip() or f"阶段 {i + 1}"
        bullets = st.get("bullets") or []
        body_lines: List[str] = []
        for b in bullets:
            body_lines.extend(_wrap_bullet(d, str(b), fonts.body, box_w - pad * 2))
        if not body_lines:
            body_lines = _wrap_bullet(d, "关键方法与技术路线", fonts.body, box_w - pad * 2)
        body_h = len(body_lines) * line_h + 10
        box_h = header_h + body_h + 18
        stage_layout.append({
            "x": margin_x,
            "y": y,
            "w": box_w,
            "h": box_h,
            "title": st_title,
            "lines": body_lines,
            "fill": theme["stage_fills"][i % len(theme["stage_fills"])],
            "stroke": theme["stage_strokes"][i % len(theme["stage_strokes"])],
        })
        y += box_h + gap + arrow_gap

    height = max(900, int(y + 70))
    img = Image.new("RGBA", (width, height), _hex_to_rgba(theme["bg"]))
    draw = ImageDraw.Draw(img)

    # Title
    tb = draw.textbbox((0, 0), title, font=fonts.title)
    title_w = tb[2] - tb[0]
    draw.text(((width - title_w) // 2, top - 10), title, font=fonts.title, fill=_hex_to_rgba(theme["title"]))

    # Draw stages
    for idx, st in enumerate(stage_layout):
        x, y0, w, h = st["x"], st["y"], st["w"], st["h"]
        fill = _hex_to_rgba(st["fill"])
        stroke = _hex_to_rgba(st["stroke"])

        # shadow
        shadow = _hex_to_rgba("#0F172A", 22)
        _rounded_rect_png(draw, (x + 3, y0 + 5, x + w + 3, y0 + h + 5), radius, fill=shadow, outline=None, width=0)
        _rounded_rect_png(draw, (x, y0, x + w, y0 + h), radius, fill=fill, outline=stroke, width=2)

        # header stripe
        stripe_w = 10
        _rounded_rect_png(draw, (x, y0, x + stripe_w, y0 + h), radius, fill=_hex_to_rgba(theme["accent"], 190), outline=None, width=0)

        # stage number pill
        num = str(idx + 1)
        pill_w = 46
        pill_h = 30
        pill_x = x + pad - 6
        pill_y = y0 + 14
        _rounded_rect_png(draw, (pill_x, pill_y, pill_x + pill_w, pill_y + pill_h), 14, fill=_hex_to_rgba("#FFFFFF", 235), outline=_hex_to_rgba("#CBD5E1"), width=1)
        nb = draw.textbbox((0, 0), num, font=fonts.bold)
        nw = nb[2] - nb[0]
        nh = nb[3] - nb[1]
        draw.text((pill_x + (pill_w - nw) // 2, pill_y + (pill_h - nh) // 2 - 1), num, font=fonts.bold, fill=_hex_to_rgba(theme["muted"]))

        # header text
        header_text = st["title"]
        draw.text((x + pad + 52, y0 + 14), header_text, font=fonts.header, fill=_hex_to_rgba(theme["text"]))

        # body
        ty = y0 + header_h + 10
        for ln in st["lines"]:
            draw.text((x + pad, ty), ln, font=fonts.body, fill=_hex_to_rgba(theme["muted"]))
            ty += line_h

    # arrows between stages
    for a in range(len(stage_layout) - 1):
        cur = stage_layout[a]
        nxt = stage_layout[a + 1]
        x1 = cur["x"] + cur["w"] // 2
        y1 = cur["y"] + cur["h"] + 8
        x2 = nxt["x"] + nxt["w"] // 2
        y2 = nxt["y"] - 8
        _arrow_png(draw, x1, y1, x2, y2, color=_hex_to_rgba(theme["arrow"]), width=4)

    png_bytes = b""
    import io
    bio = io.BytesIO()
    img.convert("RGB").save(bio, format="PNG", optimize=True)
    png_bytes = bio.getvalue()

    # SVG rendering (simple, editable)
    svg_parts: List[str] = []
    svg_parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">')
    svg_parts.append("<defs>")
    svg_parts.append(
        '<marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">'
        f'<path d="M0,0 L0,6 L9,3 z" fill="{theme["arrow"]}"/>'
        "</marker>"
    )
    svg_parts.append("</defs>")
    svg_parts.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="{theme["bg"]}"/>')
    svg_parts.append(
        f'<text x="{width//2}" y="{top+28}" text-anchor="middle" font-family="Microsoft YaHei, PingFang SC, Noto Sans CJK SC, sans-serif" font-size="44" font-weight="700" fill="{theme["title"]}">{_escape_xml(title)}</text>'
    )

    for idx, st in enumerate(stage_layout):
        x, y0, w, h = int(st["x"]), int(st["y"]), int(st["w"]), int(st["h"])
        svg_parts.append(f'<rect x="{x}" y="{y0}" rx="{radius}" ry="{radius}" width="{w}" height="{h}" fill="{st["fill"]}" stroke="{st["stroke"]}" stroke-width="2"/>')
        svg_parts.append(f'<rect x="{x}" y="{y0}" rx="{radius}" ry="{radius}" width="10" height="{h}" fill="{theme["accent"]}" opacity="0.75"/>')
        # number pill
        pill_x = x + pad - 6
        pill_y = y0 + 14
        svg_parts.append(f'<rect x="{pill_x}" y="{pill_y}" rx="14" ry="14" width="46" height="30" fill="#FFFFFF" opacity="0.92" stroke="{theme["border"]}" stroke-width="1"/>')
        svg_parts.append(
            f'<text x="{pill_x + 23}" y="{pill_y + 22}" text-anchor="middle" font-family="Microsoft YaHei, PingFang SC, sans-serif" font-size="20" font-weight="700" fill="{theme["muted"]}">{idx + 1}</text>'
        )
        # header text
        svg_parts.append(
            f'<text x="{x + pad + 52}" y="{y0 + 38}" font-family="Microsoft YaHei, PingFang SC, Noto Sans CJK SC, sans-serif" font-size="26" font-weight="700" fill="{theme["text"]}">{_escape_xml(st["title"])}</text>'
        )
        # body
        ty = y0 + header_h + 10 + 22
        for ln in st["lines"]:
            svg_parts.append(
                f'<text x="{x + pad}" y="{ty}" font-family="Microsoft YaHei, PingFang SC, Noto Sans CJK SC, sans-serif" font-size="22" fill="{theme["muted"]}">{_escape_xml(ln)}</text>'
            )
            ty += line_h

    for a in range(len(stage_layout) - 1):
        cur = stage_layout[a]
        nxt = stage_layout[a + 1]
        x1 = int(cur["x"] + cur["w"] // 2)
        y1 = int(cur["y"] + cur["h"] + 8)
        x2 = int(nxt["x"] + nxt["w"] // 2)
        y2 = int(nxt["y"] - 8)
        svg_parts.append(_arrow_svg(x1, y1, x2, y2, stroke=theme["arrow"], stroke_width=4))

    svg_parts.append("</svg>")
    svg_text = "\n".join(svg_parts)
    return png_bytes, svg_text


def _render_research_framework(spec: Dict[str, Any], *, width: int = 1600) -> Tuple[bytes, str]:
    _require_pillow()
    from PIL import Image, ImageDraw

    fonts = _load_fonts()
    theme = {
        "bg": "#F8FAFC",
        "text": "#0F172A",
        "muted": "#334155",
        "border": "#CBD5E1",
        "arrow": "#64748B",
        "accent": "#F97316",
        "goal": ("#FFF7ED", "#FDBA74"),
        "row": ("#FFFFFF", "#CBD5E1"),
        "wp_fills": ["#ECFDF5", "#EFF6FF", "#F5F3FF"],
        "wp_strokes": ["#6EE7B7", "#93C5FD", "#C4B5FD"],
        "outcomes": ("#F0FDFA", "#5EEAD4"),
    }

    title = str(spec.get("title") or "研究框架图").strip() or "研究框架图"
    goal = spec.get("goal") or {}
    hypotheses = spec.get("hypotheses") or {}
    support = spec.get("support") or {}
    outcomes = spec.get("outcomes") or {}
    wps: List[Dict[str, Any]] = spec.get("work_packages") or []

    margin = 88
    gap = 26
    top = 80
    radius = 22
    pad = 28
    header_h = 54
    line_h = 30

    inner_w = width - margin * 2

    dummy = Image.new("RGBA", (width, 10), (255, 255, 255, 0))
    d = ImageDraw.Draw(dummy)

    def _box_height(box: Dict[str, Any], max_w: int) -> tuple[int, List[str]]:
        bullets = box.get("bullets") or []
        lines: List[str] = []
        for b in bullets:
            lines.extend(_wrap_bullet(d, str(b), fonts.body, max_w - pad * 2))
        if not lines:
            lines = _wrap_bullet(d, "（内容依据已知需求自动生成）", fonts.body, max_w - pad * 2)
        body_h = len(lines) * line_h + 10
        return int(header_h + body_h + 18), lines

    # Goal box
    goal_h, goal_lines = _box_height(goal, inner_w)
    y = top + 70
    goal_box = {"x": margin, "y": y, "w": inner_w, "h": goal_h, "fill": theme["goal"][0], "stroke": theme["goal"][1], "title": goal.get("title") or "研究目标", "lines": goal_lines}
    y += goal_h + gap + 10

    # Hypotheses + Support row (2 columns)
    col_w = int((inner_w - gap) / 2)
    hyp_h, hyp_lines = _box_height(hypotheses, col_w)
    sup_h, sup_lines = _box_height(support, col_w)
    row_h = max(hyp_h, sup_h)
    hyp_box = {"x": margin, "y": y, "w": col_w, "h": row_h, "fill": theme["row"][0], "stroke": theme["border"], "title": hypotheses.get("title") or "科学问题/假设", "lines": hyp_lines}
    sup_box = {"x": margin + col_w + gap, "y": y, "w": col_w, "h": row_h, "fill": theme["row"][0], "stroke": theme["border"], "title": support.get("title") or "支撑条件", "lines": sup_lines}
    y += row_h + gap + 10

    # Work packages row (3 columns)
    wp_count = min(3, len(wps)) if wps else 3
    wp_w = int((inner_w - gap * 2) / 3)
    wp_boxes: List[dict] = []
    wp_max_h = 0
    wp_lines_list: List[List[str]] = []
    for i in range(wp_count):
        w = wps[i] if i < len(wps) else {"title": f"WP{i+1} 研究内容", "bullets": ["研究内容与任务", "关键方法与实验", "阶段成果与指标"]}
        h, ln = _box_height(w, wp_w)
        wp_lines_list.append(ln)
        wp_max_h = max(wp_max_h, h)
        wp_boxes.append({
            "x": margin + i * (wp_w + gap),
            "y": y,
            "w": wp_w,
            "h": h,
            "fill": theme["wp_fills"][i % len(theme["wp_fills"])],
            "stroke": theme["wp_strokes"][i % len(theme["wp_strokes"])],
            "title": w.get("title") or f"WP{i+1}",
            "lines": ln,
        })
    # normalize heights
    for b in wp_boxes:
        b["h"] = wp_max_h

    y += wp_max_h + gap + 10

    # Outcomes
    out_h, out_lines = _box_height(outcomes, inner_w)
    out_box = {"x": margin, "y": y, "w": inner_w, "h": out_h, "fill": theme["outcomes"][0], "stroke": theme["outcomes"][1], "title": outcomes.get("title") or "预期成果", "lines": out_lines}
    y += out_h + 70

    height = max(980, int(y))
    img = Image.new("RGBA", (width, height), _hex_to_rgba(theme["bg"]))
    draw = ImageDraw.Draw(img)

    tb = draw.textbbox((0, 0), title, font=fonts.title)
    title_w = tb[2] - tb[0]
    draw.text(((width - title_w) // 2, top - 10), title, font=fonts.title, fill=_hex_to_rgba(theme["text"]))

    def _draw_box(box: dict, *, with_stripe: bool = True):
        x, y0, w, h = int(box["x"]), int(box["y"]), int(box["w"]), int(box["h"])
        fill = _hex_to_rgba(box["fill"])
        stroke = _hex_to_rgba(box["stroke"])
        shadow = _hex_to_rgba("#0F172A", 20)
        _rounded_rect_png(draw, (x + 3, y0 + 5, x + w + 3, y0 + h + 5), radius, fill=shadow, outline=None, width=0)
        _rounded_rect_png(draw, (x, y0, x + w, y0 + h), radius, fill=fill, outline=stroke, width=2)
        if with_stripe:
            _rounded_rect_png(draw, (x, y0, x + 10, y0 + h), radius, fill=_hex_to_rgba(theme["accent"], 185), outline=None, width=0)

        draw.text((x + pad, y0 + 14), str(box["title"]), font=fonts.header, fill=_hex_to_rgba(theme["text"]))
        ty = y0 + header_h + 10
        for ln in box["lines"]:
            draw.text((x + pad, ty), ln, font=fonts.body, fill=_hex_to_rgba(theme["muted"]))
            ty += line_h

    _draw_box(goal_box)
    _draw_box(hyp_box, with_stripe=False)
    _draw_box(sup_box, with_stripe=False)
    for b in wp_boxes:
        _draw_box(b)
    _draw_box(out_box)

    # Connectors
    def _center_bottom(box: dict) -> tuple[int, int]:
        return (int(box["x"] + box["w"] / 2), int(box["y"] + box["h"]))

    def _center_top(box: dict) -> tuple[int, int]:
        return (int(box["x"] + box["w"] / 2), int(box["y"]))

    # goal -> hyp & support
    gcb = _center_bottom(goal_box)
    ht = _center_top(hyp_box)
    st = _center_top(sup_box)
    _arrow_png(draw, gcb[0], gcb[1] + 6, ht[0], ht[1] - 8, color=_hex_to_rgba(theme["arrow"]), width=4)
    _arrow_png(draw, gcb[0], gcb[1] + 6, st[0], st[1] - 8, color=_hex_to_rgba(theme["arrow"]), width=4)

    # hyp/support -> each wp
    hcb = _center_bottom(hyp_box)
    scb = _center_bottom(sup_box)
    for wpb in wp_boxes:
        wpt = _center_top(wpb)
        _arrow_png(draw, hcb[0], hcb[1] + 6, wpt[0], wpt[1] - 8, color=_hex_to_rgba(theme["arrow"], 220), width=3)
        _arrow_png(draw, scb[0], scb[1] + 6, wpt[0], wpt[1] - 8, color=_hex_to_rgba(theme["arrow"], 220), width=3)

    # wp -> outcomes
    ot = _center_top(out_box)
    for wpb in wp_boxes:
        wpcb = _center_bottom(wpb)
        _arrow_png(draw, wpcb[0], wpcb[1] + 6, ot[0], ot[1] - 8, color=_hex_to_rgba(theme["arrow"]), width=4)

    import io
    bio = io.BytesIO()
    img.convert("RGB").save(bio, format="PNG", optimize=True)
    png_bytes = bio.getvalue()

    # SVG output
    svg_parts: List[str] = []
    svg_parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">')
    svg_parts.append("<defs>")
    svg_parts.append(
        '<marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">'
        f'<path d="M0,0 L0,6 L9,3 z" fill="{theme["arrow"]}"/>'
        "</marker>"
    )
    svg_parts.append("</defs>")
    svg_parts.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="{theme["bg"]}"/>')
    svg_parts.append(
        f'<text x="{width//2}" y="{top+28}" text-anchor="middle" font-family="Microsoft YaHei, PingFang SC, Noto Sans CJK SC, sans-serif" font-size="44" font-weight="700" fill="{theme["text"]}">{_escape_xml(title)}</text>'
    )

    def _svg_box(box: dict, *, stripe: bool = True):
        x, y0, w, h = int(box["x"]), int(box["y"]), int(box["w"]), int(box["h"])
        svg_parts.append(f'<rect x="{x}" y="{y0}" rx="{radius}" ry="{radius}" width="{w}" height="{h}" fill="{box["fill"]}" stroke="{box["stroke"]}" stroke-width="2"/>')
        if stripe:
            svg_parts.append(f'<rect x="{x}" y="{y0}" rx="{radius}" ry="{radius}" width="10" height="{h}" fill="{theme["accent"]}" opacity="0.75"/>')
        svg_parts.append(
            f'<text x="{x + pad}" y="{y0 + 38}" font-family="Microsoft YaHei, PingFang SC, Noto Sans CJK SC, sans-serif" font-size="26" font-weight="700" fill="{theme["text"]}">{_escape_xml(str(box["title"]))}</text>'
        )
        ty = y0 + header_h + 10 + 22
        for ln in box["lines"]:
            svg_parts.append(
                f'<text x="{x + pad}" y="{ty}" font-family="Microsoft YaHei, PingFang SC, Noto Sans CJK SC, sans-serif" font-size="22" fill="{theme["muted"]}">{_escape_xml(ln)}</text>'
            )
            ty += line_h

    _svg_box(goal_box, stripe=True)
    _svg_box(hyp_box, stripe=False)
    _svg_box(sup_box, stripe=False)
    for b in wp_boxes:
        _svg_box(b, stripe=True)
    _svg_box(out_box, stripe=True)

    # arrows in SVG
    def _cb(box: dict) -> tuple[int, int]:
        return (int(box["x"] + box["w"] / 2), int(box["y"] + box["h"] + 6))

    def _ct(box: dict) -> tuple[int, int]:
        return (int(box["x"] + box["w"] / 2), int(box["y"] - 8))

    svg_parts.append(_arrow_svg(*_cb(goal_box), *_ct(hyp_box), stroke=theme["arrow"], stroke_width=4))
    svg_parts.append(_arrow_svg(*_cb(goal_box), *_ct(sup_box), stroke=theme["arrow"], stroke_width=4))
    for wpb in wp_boxes:
        svg_parts.append(_arrow_svg(*_cb(hyp_box), *_ct(wpb), stroke=theme["arrow"], stroke_width=3))
        svg_parts.append(_arrow_svg(*_cb(sup_box), *_ct(wpb), stroke=theme["arrow"], stroke_width=3))
    for wpb in wp_boxes:
        svg_parts.append(_arrow_svg(*_cb(wpb), *_ct(out_box), stroke=theme["arrow"], stroke_width=4))

    svg_parts.append("</svg>")
    svg_text = "\n".join(svg_parts)
    return png_bytes, svg_text


def render_infographic_png_svg(diagram_type: str, raw_spec: Dict[str, Any], *, title: str) -> Tuple[bytes, str, Dict[str, Any]]:
    """
    Returns (png_bytes, svg_text, normalized_spec).
    """
    dt = (diagram_type or "").strip()
    if dt == "technical_route":
        spec = _normalize_technical_route_spec(raw_spec or {}, title)
        png, svg = _render_technical_route(spec)
        return png, svg, spec
    if dt == "research_framework":
        spec = _normalize_research_framework_spec(raw_spec or {}, title)
        png, svg = _render_research_framework(spec)
        return png, svg, spec
    raise ValueError(f"Unsupported diagram_type: {diagram_type}")

