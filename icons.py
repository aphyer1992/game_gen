"""
Little vector icons for map tiles, shared by play.py (tkinter) and
render_png.py (Pillow), so both look the same.

Each icon is a list of shapes in a unit box (0..1, y down):
  ('poly', [x, y, x, y, ...], fill, outline)
  ('oval', [x0, y0, x1, y1], fill, outline)
  ('rect', [x0, y0, x1, y1], fill, outline)
  ('line', [x, y, x, y, ...], color, width)    width as a fraction of the tile
icon(kind, **state) returns the shapes; draw_tk / draw_pil paint them into a
tile box. Kinds: the item CellContents, 'shrine', 'seal', 'gate', 'gem',
'ogre', 'ghost', 'boss', 'snake'.
"""
import math

from support_classes import CellContents as K

BADGE = ('oval', [0.0, 0.0, 1.0, 1.0], '#FFF8E1', '#222222')   # items sit on a cream disc


def _arc(cx, cy, r, a0, a1, n=8):
    pts = []
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        pts += [cx + r * math.cos(a), cy + r * math.sin(a)]
    return pts


def _star(cx, cy, r_out, r_in, points=5, rot=-90):
    pts = []
    for i in range(points * 2):
        r = r_out if i % 2 == 0 else r_in
        a = math.radians(rot + i * 180 / points)
        pts += [cx + r * math.cos(a), cy + r * math.sin(a)]
    return pts


ITEM_ICONS = {
    K.WATER_BOOTS: [   # the Boat
        ('poly', [0.12, 0.58, 0.88, 0.58, 0.72, 0.82, 0.28, 0.82], '#8D5524', '#3E2723'),
        ('line', [0.5, 0.14, 0.5, 0.58], '#3E2723', 0.06),
        ('poly', [0.53, 0.16, 0.53, 0.54, 0.82, 0.54], '#FFFFFF', '#555555'),
        ('poly', [0.47, 0.24, 0.47, 0.54, 0.26, 0.54], '#E3F2FD', '#555555'),
    ],
    K.FIRE_SHIELD: [
        ('poly', [0.2, 0.14, 0.8, 0.14, 0.8, 0.5, 0.5, 0.9, 0.2, 0.5], '#D32F2F', '#5D0000'),
        ('line', [0.5, 0.22, 0.5, 0.74], '#FFD54F', 0.08),
        ('line', [0.3, 0.38, 0.7, 0.38], '#FFD54F', 0.08),
    ],
    K.AXE: [
        ('line', [0.3, 0.9, 0.62, 0.18], '#6D4C41', 0.1),
        ('poly', [0.5, 0.12, 0.86, 0.18, 0.82, 0.52, 0.6, 0.38], '#9E9E9E', '#424242'),
    ],
    K.DESERT_CLOAK: [
        ('poly', [0.38, 0.26, 0.62, 0.26, 0.86, 0.9, 0.14, 0.9], '#C0A030', '#5D4A00'),
        ('oval', [0.36, 0.08, 0.64, 0.34], '#C0A030', '#5D4A00'),
        ('oval', [0.43, 0.16, 0.57, 0.3], '#3E2723', ''),
    ],
    K.BOW: [
        ('line', _arc(0.3, 0.5, 0.42, -65, 65), '#6D4C41', 0.09),
        ('line', [0.48, 0.12, 0.48, 0.88], '#EEEEEE', 0.03),
        ('line', [0.14, 0.5, 0.86, 0.5], '#424242', 0.05),
        ('poly', [0.92, 0.5, 0.78, 0.42, 0.78, 0.58], '#424242', ''),
    ],
    K.BLESSING: [
        ('oval', [0.18, 0.18, 0.82, 0.82], '', '#1565C0'),
        ('poly', [0.5, 0.04, 0.6, 0.4, 0.96, 0.5, 0.6, 0.6, 0.5, 0.96, 0.4, 0.6, 0.04, 0.5, 0.4, 0.4],
         '#FFD54F', '#1565C0'),
        ('oval', [0.42, 0.42, 0.58, 0.58], '#1565C0', ''),
    ],
    K.SILVER_SWORD: [
        ('poly', [0.5, 0.04, 0.57, 0.16, 0.56, 0.64, 0.44, 0.64, 0.43, 0.16], '#CFD8DC', '#455A64'),
        ('rect', [0.26, 0.63, 0.74, 0.71], '#B8860B', '#5D4A00'),
        ('rect', [0.45, 0.71, 0.55, 0.88], '#6D4C41', ''),
        ('oval', [0.42, 0.86, 0.58, 0.97], '#B8860B', ''),
    ],
    K.HORSE: [
        ('poly', [0.32, 0.92, 0.36, 0.58, 0.24, 0.5, 0.12, 0.54, 0.08, 0.44, 0.3, 0.22, 0.42, 0.08,
                  0.48, 0.2, 0.62, 0.22, 0.78, 0.46, 0.74, 0.92], '#8D6E63', '#3E2723'),
        ('line', [0.48, 0.2, 0.66, 0.3, 0.76, 0.5], '#3E2723', 0.07),
        ('oval', [0.3, 0.3, 0.38, 0.38], '#000000', ''),
    ],
}


def icon(kind, visited=True, broken=False):
    if kind in ITEM_ICONS:
        return [BADGE] + ITEM_ICONS[kind]
    if kind == 'gem':
        return [('poly', [0.5, 0.08, 0.86, 0.5, 0.5, 0.92, 0.14, 0.5], '#FFFFFF', '#000000'),
                ('line', [0.14, 0.5, 0.86, 0.5], '#90CAF9', 0.04)]
    if kind == 'shrine':
        col = '#00B0F0' if visited else '#0B4F6C'
        return [('rect', [0.04, 0.04, 0.96, 0.96], col, '#FFFFFF'),
                ('poly', [0.12, 0.36, 0.5, 0.1, 0.88, 0.36], '#FFFFFF', ''),
                ('rect', [0.2, 0.38, 0.3, 0.8], '#FFFFFF', ''),
                ('rect', [0.7, 0.38, 0.8, 0.8], '#FFFFFF', ''),
                ('rect', [0.14, 0.8, 0.86, 0.9], '#FFFFFF', '')]
    if kind == 'seal':
        if broken:
            return [('oval', [0.06, 0.06, 0.94, 0.94], '#777777', '#FFFFFF'),
                    ('line', [0.3, 0.15, 0.5, 0.45, 0.4, 0.6, 0.65, 0.88], '#000000', 0.07)]
        return [('oval', [0.06, 0.06, 0.94, 0.94], '#D50000', '#FFFFFF'),
                ('poly', _star(0.5, 0.52, 0.36, 0.15), '#FFEB3B', '')]
    if kind == 'gate':
        return [('rect', [0.08, 0.08, 0.92, 0.92], '#B8860B', '#3E2723')] + \
               [('line', [x, 0.12, x, 0.88], '#3E2723', 0.06) for x in (0.3, 0.5, 0.7)] + \
               [('line', [0.12, y, 0.88, y], '#3E2723', 0.06) for y in (0.35, 0.65)]
    if kind == 'ogre':
        return [('poly', [0.24, 0.36, 0.14, 0.04, 0.4, 0.28], '#EEEEEE', '#333333'),
                ('poly', [0.76, 0.36, 0.86, 0.04, 0.6, 0.28], '#EEEEEE', '#333333'),
                ('oval', [0.12, 0.22, 0.88, 0.98], '#A0522D', '#3E2723'),
                ('oval', [0.3, 0.44, 0.42, 0.56], '#FFEB3B', ''),
                ('oval', [0.58, 0.44, 0.7, 0.56], '#FFEB3B', ''),
                ('line', [0.34, 0.76, 0.66, 0.76], '#3E2723', 0.07)]
    if kind == 'ghost':
        return [('poly', [0.18, 0.94, 0.18, 0.45] + _arc(0.5, 0.45, 0.32, 180, 360)[2:-2] +
                 [0.82, 0.45, 0.82, 0.94, 0.7, 0.82, 0.6, 0.94, 0.5, 0.82, 0.4, 0.94, 0.3, 0.82],
                 '#E8EAF6', '#5C6BC0'),
                ('oval', [0.32, 0.36, 0.44, 0.52], '#1A237E', ''),
                ('oval', [0.56, 0.36, 0.68, 0.52], '#1A237E', '')]
    if kind == 'boss':
        return [('oval', [0.12, 0.3, 0.88, 0.98], '#4A148C', '#FFFFFF'),
                ('poly', [0.16, 0.42, 0.16, 0.08, 0.33, 0.26, 0.5, 0.02, 0.67, 0.26, 0.84, 0.08, 0.84, 0.42],
                 '#FFD54F', '#5D4A00'),
                ('oval', [0.3, 0.56, 0.42, 0.68], '#FF1744', ''),
                ('oval', [0.58, 0.56, 0.7, 0.68], '#FF1744', '')]
    if kind == 'snake':
        return [('line', [0.12, 0.88, 0.36, 0.7, 0.18, 0.5, 0.44, 0.34, 0.64, 0.38], '#2E7D32', 0.16),
                ('oval', [0.56, 0.14, 0.9, 0.46], '#2E7D32', '#0B3D0B'),
                ('oval', [0.7, 0.22, 0.78, 0.3], '#FFEB3B', ''),
                ('line', [0.88, 0.36, 0.98, 0.44], '#D50000', 0.05)]
    return []


def _scale(coords, x0, y0, size):
    return [x0 + v * size if i % 2 == 0 else y0 + v * size for i, v in enumerate(coords)]


def draw_tk(cv, shapes, x0, y0, size, tags='dyn'):
    for kind, coords, a, b in shapes:
        pts = _scale(coords, x0, y0, size)
        if kind == 'poly':
            cv.create_polygon(*pts, fill=a, outline=b, tags=tags)
        elif kind == 'oval':
            cv.create_oval(*pts, fill=a, outline=b, tags=tags)
        elif kind == 'rect':
            cv.create_rectangle(*pts, fill=a, outline=b, tags=tags)
        elif kind == 'line':
            cv.create_line(*pts, fill=a, width=max(1, round(b * size)), capstyle='round',
                           joinstyle='round', tags=tags)


def draw_pil(d, shapes, x0, y0, size):
    for kind, coords, a, b in shapes:
        pts = _scale(coords, x0, y0, size)
        fill = a or None
        outline = b or None
        if kind == 'poly':
            d.polygon(pts, fill=fill, outline=outline)
        elif kind == 'oval':
            d.ellipse(pts, fill=fill, outline=outline)
        elif kind == 'rect':
            d.rectangle(pts, fill=fill, outline=outline)
        elif kind == 'line':
            d.line(pts, fill=a, width=max(1, round(b * size)), joint='curve')
