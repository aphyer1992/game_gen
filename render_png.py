"""
Render a Map to a PNG (needs Pillow). y = 0 is drawn at the bottom, like the xlsx.

    python render_png.py 5 6 7          # seeds -> map_<seed>.png in the current folder
    python render_png.py --out DIR 5 6

Items are drawn as labelled stars; the legend under the map lists each item's
progression sphere, and vault hiding places are outlined in white.
"""
import os
import sys
import types

if 'xlsxwriter' not in sys.modules:
    try:
        import xlsxwriter  # noqa: F401
    except ImportError:
        sys.modules['xlsxwriter'] = types.ModuleType('xlsxwriter')

from PIL import Image, ImageDraw, ImageFont

from support_classes import Coordinates, CellContents
import icons
import verify

TILE = 16
ITEM_TAGS = {
    CellContents.WATER_BOOTS: 'Bt', CellContents.FIRE_SHIELD: 'Sh', CellContents.AXE: 'Ax',
    CellContents.DESERT_CLOAK: 'Cl', CellContents.BOW: 'Bw', CellContents.BLESSING: 'Bl',
    CellContents.SILVER_SWORD: 'Sw', CellContents.HORSE: 'Ho',
}


def _font(size):
    for name in ('arialbd.ttf', 'arial.ttf', 'DejaVuSans-Bold.ttf', 'DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def render(m, path, title=None, report=None):
    w, h = m.width, m.height
    legend_h = 7 * 18 + 10
    img = Image.new('RGB', (w * TILE, h * TILE + legend_h), 'white')
    d = ImageDraw.Draw(img)
    small = _font(10)
    font = _font(13)

    def box(c):
        x0 = c.x * TILE
        y0 = (h - 1 - c.y) * TILE
        return x0, y0, x0 + TILE, y0 + TILE

    for y in range(h):
        for x in range(w):
            d.rectangle(box(Coordinates(x, y)), fill=m.get_cell(x, y).color)
    # walls
    for y in range(h):
        for x in range(w):
            c = Coordinates(x, y)
            x0, y0, x1, y1 = box(c)
            if x + 1 < w and m.is_wall(c, Coordinates(x + 1, y)):
                d.line([(x1, y0), (x1, y1)], fill='black', width=2)
            if y + 1 < h and m.is_wall(c, Coordinates(x, y + 1)):
                d.line([(x0, y0), (x1, y0)], fill='black', width=2)
    for kind, trail in getattr(m, 'trails', []):   # carved trails: paler, so you can see them
        for c in trail:
            if m.get_cell(c.x, c.y).label in ('Grass', 'Road'):
                x0, y0, x1, y1 = box(c)
                d.rectangle((x0 + 3, y0 + 3, x1 - 3, y1 - 3), fill='#D8E8B0' if m.get_cell(c.x, c.y).label == 'Grass' else '#E0D0A0')
    for s in getattr(m, 'vault_item_spots', []):
        x0, y0, x1, y1 = box(s)
        d.rectangle((x0 + 1, y0 + 1, x1 - 1, y1 - 1), outline='white', width=2)
    # contents
    for y in range(h):
        for x in range(w):
            c = Coordinates(x, y)
            cont = m.get_cell_contents(x, y)
            x0, y0, x1, y1 = box(c)
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            kind = {CellContents.GEM: 'gem', CellContents.SHRINE: 'shrine', CellContents.SEAL: 'seal',
                    CellContents.GATE: 'gate', CellContents.BOSS: 'boss', CellContents.DRAGON: 'snake',
                    CellContents.OGRE: 'ogre', CellContents.GHOST: 'ghost'}.get(cont, cont)
            shapes = icons.icon(kind)
            if shapes:
                icons.draw_pil(d, shapes, x0, y0, TILE)

    # legend
    if report is None:
        report = verify.verify_map(m)
    names = getattr(m, 'vault_spot_names', {})
    sphere_of = {}
    for i, sph in enumerate(report.spheres):
        for it in sph:
            sphere_of[it] = i
    lines = [title or '']
    lines.append('Progression: ' + '  ->  '.join(
        '[' + ', '.join(sorted(i.label for i in s)) + ']' for s in report.spheres))
    where = []
    for y in range(h):
        for x in range(w):
            cont = m.get_cell_contents(x, y)
            if cont in ITEM_TAGS:
                c = Coordinates(x, y)
                place = names.get(c)
                if place is None:
                    room = m.get_room_number(x, y)
                    place = 'castle room' if room and m.get_cell(x, y).label == 'Castle' else ('building' if room else m.get_cell(x, y).label.lower())
                where.append('{} ({}) {} @({},{})'.format(ITEM_TAGS[cont], cont.label, place, x, y))
    lines.append('Items: ' + ';  '.join(where[:3]))
    lines.append('       ' + ';  '.join(where[3:]))
    if getattr(report, 'castle_item', None) is not None:
        lines[-1] += '   |  Castle gate: {} gems; castle item {} ({})'.format(
            report.gate_gems, report.castle_item.label, 'optional' if report.castle_item_optional else 'needed')
    lines.append('Beatable: {}   free from spawn: {}   smallest winning set: {}'.format(
        report.beatable, verify._short(report.items_free),
        verify._short(report.min_win_set) if report.min_win_set is not None else 'n/a'))
    lines.append('Pale squares = carved trail.  White outline = vault hiding place.')
    for i, line in enumerate(lines):
        d.text((6, h * TILE + 6 + i * 18), line, fill='black', font=font)
    img.save(path)
    return path


if __name__ == '__main__':
    import measure
    args = sys.argv[1:]
    out = '.'
    if args and args[0] == '--out':
        out = args[1]
        args = args[2:]
    for s in [int(a) for a in args] or [0]:
        m = measure.generate(s)
        p = render(m, os.path.join(out, 'map_{}.png'.format(s)), title='seed {}'.format(s))
        print(p)
