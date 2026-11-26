"""
Very simple game UI: type a route, see the game state after any turn.

    python play.py            (seed 1)
    python play.py 17         (seed 17)

Left: the map at the selected turn (you = white circle, your path so far =
white line). Right: the route box, the list of turns, and the full state of
the selected turn. The route re-runs as you type. Click a turn (or use the
arrow keys in the list) to see the state after it. Hover the map to see a
tile's coordinates and contents. The command list is in game.py.
"""
import sys
import tkinter as tk
from tkinter import ttk

import game
import icons
from support_classes import Coordinates, TerrType, CellContents

TILE = 16          # largest tile size; the map shrinks tiles to fit the screen (MIN_TILE..TILE)
MIN_TILE = 9
ITEM_TAGS = {
    CellContents.WATER_BOOTS: 'Bo', CellContents.FIRE_SHIELD: 'Sh', CellContents.AXE: 'Ax',
    CellContents.DESERT_CLOAK: 'Cl', CellContents.BOW: 'Bw', CellContents.BLESSING: 'Bl',
    CellContents.SILVER_SWORD: 'Sw', CellContents.HORSE: 'Ho',
}
HELP = ("Commands, 2 characters per turn:  ww / wa / d. = move (w up, a left, s down, d right)   "
        "xa = attack west   e. = interact   ed = interact east (board/leave the Boat)   "
        "e0..e9 = warp to shrine N (needs Blessing)   h. = mount the Horse (then each letter moves 2)   "
        ".. = wait   dd*5 = repeat   # comment")

EXAMPLE = "# Example route: edit freely\ndd dd ww\n"


class App:
    def __init__(self, root, seed):
        self.root = root
        root.title('Speedrun routing')
        self.map = None
        self.sim = None
        self.states = []
        self.after_id = None
        self.picked = None        # turn index the user last clicked

        # --- top bar ---
        top = ttk.Frame(root, padding=4)
        top.pack(side='top', fill='x')
        ttk.Label(top, text='Seed:').pack(side='left')
        self.seed_var = tk.StringVar(value=str(seed))
        e = ttk.Entry(top, textvariable=self.seed_var, width=8)
        e.pack(side='left')
        e.bind('<Return>', lambda ev: self.new_map())
        self.verified_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text='verified maps only', variable=self.verified_var).pack(side='left', padx=6)
        ttk.Button(top, text='Load map', command=self.new_map).pack(side='left')
        ttk.Button(top, text='Fill in a rough auto-route', command=self.auto_route).pack(side='left', padx=(6, 0))
        self.map_label = ttk.Label(top, text='')
        self.map_label.pack(side='left', padx=10)
        self.hover_label = ttk.Label(top, text='', foreground='#444')
        self.hover_label.pack(side='right')
        ttk.Button(top, text='+', width=2, command=lambda: self.zoom(1)).pack(side='right')
        ttk.Button(top, text='−', width=2, command=lambda: self.zoom(-1)).pack(side='right')
        ttk.Label(top, text='Zoom:').pack(side='right', padx=(10, 2))
        self.tile = TILE

        ttk.Label(root, text=HELP, foreground='#555', padding=(4, 0), wraplength=1100).pack(side='top', anchor='w')

        body = ttk.Frame(root, padding=4)
        body.pack(side='top', fill='both', expand=True)

        # --- map ---
        # map in a scrollable frame, in case it's still bigger than the window
        mapframe = ttk.Frame(body)
        mapframe.pack(side='left', anchor='n', fill='y')
        self.canvas = tk.Canvas(mapframe, width=50 * TILE, height=50 * TILE, bg='black', highlightthickness=0)
        vbar = ttk.Scrollbar(mapframe, orient='vertical', command=self.canvas.yview)
        hbar = ttk.Scrollbar(mapframe, orient='horizontal', command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)
        self.canvas.grid(row=0, column=0, sticky='nsew')
        vbar.grid(row=0, column=1, sticky='ns')
        hbar.grid(row=1, column=0, sticky='ew')
        mapframe.rowconfigure(0, weight=1)
        self.canvas.bind('<Motion>', self.on_hover)

        # --- right panel ---
        right = ttk.Frame(body, padding=(8, 0, 0, 0))
        right.pack(side='left', fill='both', expand=True)

        ttk.Label(right, text='Route').pack(anchor='w')
        self.route = tk.Text(right, height=9, width=48, font=('Consolas', 11), undo=True)
        self.route.pack(fill='x')
        self.route.insert('1.0', EXAMPLE)
        self.route.bind('<<Modified>>', self.on_route_changed)
        self.error_label = ttk.Label(right, text='', foreground='#B00020')
        self.error_label.pack(anchor='w')
        self.result_label = ttk.Label(right, text='', font=('Segoe UI', 11, 'bold'))
        self.result_label.pack(anchor='w', pady=(2, 4))

        lists = ttk.Frame(right)
        lists.pack(fill='both', expand=True)
        ttk.Label(lists, text='Turns (click one)').grid(row=0, column=0, sticky='w')
        ttk.Label(lists, text='State after that turn').grid(row=0, column=2, sticky='w', padx=(8, 0))
        self.steps = tk.Listbox(lists, width=30, font=('Consolas', 10), activestyle='none',
                                exportselection=False)
        sb = ttk.Scrollbar(lists, orient='vertical', command=self.steps.yview)
        self.steps.configure(yscrollcommand=sb.set)
        self.steps.grid(row=1, column=0, sticky='ns')
        sb.grid(row=1, column=1, sticky='ns')
        self.steps.bind('<<ListboxSelect>>', self.on_pick)
        self.detail = tk.Text(lists, width=46, font=('Consolas', 10), wrap='word', state='disabled',
                              background='#F7F7F7')
        self.detail.grid(row=1, column=2, sticky='nsew', padx=(8, 0))
        lists.rowconfigure(1, weight=1)
        lists.columnconfigure(2, weight=1)

        self.new_map()

    def auto_route(self):
        """Replace the route with autoroute.py's greedy (slow, not optimal) route."""
        import autoroute
        self.root.config(cursor='watch')
        self.root.update_idletasks()
        try:
            cmds, st, done = autoroute.autoroute(self.map)
        finally:
            self.root.config(cursor='')
        if done:
            what = 'reaches the boss room with {} gems in {} turns; the boss fight is up to you'.format(st.gems, st.turn)
        else:
            what = 'gets stuck after {} turns'.format(st.turn)
        head = '# Greedy auto-route: {}. Far from optimal, beat it!\n'.format(what)
        body = '\n'.join(' '.join(cmds[i:i + 15]) for i in range(0, len(cmds), 15))
        self.route.delete('1.0', 'end')
        self.route.insert('1.0', head + body + '\n')
        self.rerun()

    # --- map loading and drawing -----------------------------------------------
    def new_map(self):
        self.picked = None
        try:
            seed = int(self.seed_var.get())
        except ValueError:
            self.map_label.config(text='Seed must be a number')
            return
        self.map_label.config(text='Generating map...')
        self.root.config(cursor='watch')
        self.root.update_idletasks()
        try:
            self.map, actual = game.load_map(seed, verified=self.verified_var.get())
        finally:
            self.root.config(cursor='')
        self.seed_var.set(str(actual))
        self.sim = game.Simulator(self.map)
        note = '' if actual == seed else '  (seed {} was rejected by the verifier)'.format(seed)
        self.map_label.config(text='Map seed {}{}'.format(actual, note))
        self.fit_tile()
        self.draw_static()
        self.rerun()

    def box(self, c):
        t = self.tile
        x0 = c.x * t
        y0 = (self.map.height - 1 - c.y) * t
        return x0, y0, x0 + t, y0 + t

    CHROME = 90   # title bar + taskbar, roughly

    def spare_height(self):
        """Screen height left for the map: screen minus everything else in
        the window (measured) minus the title bar and taskbar."""
        self.root.update_idletasks()
        other = self.root.winfo_reqheight() - self.canvas.winfo_reqheight()
        return self.root.winfo_screenheight() - other - self.CHROME

    def fit_tile(self):
        """Largest tile size (MIN_TILE..TILE) that fits the map on screen."""
        self.tile = max(MIN_TILE, min(TILE, self.spare_height() // max(1, self.map.height)))

    def zoom(self, step):
        if self.map is None:
            return
        self.tile = max(6, min(32, self.tile + step))
        self.draw_static()
        self.rerun()

    def center(self, c):
        x0, y0, x1, y1 = self.box(c)
        return (x0 + x1) / 2, (y0 + y1) / 2

    def draw_static(self):
        cv, m = self.canvas, self.map
        cv.delete('all')
        w, h = m.width * self.tile, m.height * self.tile
        cv.config(width=w, height=max(200, min(h, self.spare_height())), scrollregion=(0, 0, w, h))
        for y in range(m.height):
            for x in range(m.width):
                cv.create_rectangle(*self.box(Coordinates(x, y)), fill=m.get_cell(x, y).color,
                                    outline='', tags=('terrain', 't{}_{}'.format(x, y)))
        for y in range(m.height):
            for x in range(m.width):
                c = Coordinates(x, y)
                x0, y0, x1, y1 = self.box(c)
                if x + 1 < m.width and Coordinates(x + 1, y) not in self.sim.open[c]:
                    cv.create_line(x1, y0, x1, y1, fill='black', width=3, tags='wall')
                if y + 1 < m.height and Coordinates(x, y + 1) not in self.sim.open[c]:
                    cv.create_line(x0, y0, x1, y0, fill='black', width=3, tags='wall')

    def draw_state(self, st, upto):
        cv, m, sim = self.canvas, self.map, self.sim
        cv.delete('dyn')
        for c in st.cut_trees:
            cv.create_rectangle(*self.box(c), fill=TerrType.GRASS.color, outline='', tags='dyn')
        small = ('Arial', 7, 'bold')
        for y in range(m.height):
            for x in range(m.width):
                c = Coordinates(x, y)
                cont = sim.contents(st, c)
                if cont == CellContents.EMPTY or cont == CellContents.FORCE_EMPTY:
                    continue
                x0, y0, x1, y1 = self.box(c)
                cx, cy = self.center(c)
                if cont == CellContents.GEM:
                    icons.draw_tk(cv, icons.icon('gem'), x0, y0, self.tile)
                elif cont in ITEM_TAGS:
                    icons.draw_tk(cv, icons.icon(cont), x0, y0, self.tile)
                elif cont == CellContents.SHRINE:
                    seen = c in st.visited_shrines   # visited = a warp target; unvisited drawn dark
                    icons.draw_tk(cv, icons.icon('shrine', visited=seen), x0, y0, self.tile)
                    cv.create_text(x1 - 3, y1 - 4, text=str(sim.shrines.index(c)), font=small,
                                   fill='#FFEB3B', tags='dyn')
                elif cont == CellContents.SEAL:
                    icons.draw_tk(cv, icons.icon('seal', broken=c in st.seals_broken), x0, y0, self.tile)
                elif cont == CellContents.GATE:
                    if not st.gate_open:
                        icons.draw_tk(cv, icons.icon('gate'), x0, y0, self.tile)
        for e in st.enemies:
            if not e.alive:
                continue
            x0, y0, x1, y1 = self.box(e.pos)
            cx, cy = self.center(e.pos)
            icons.draw_tk(cv, icons.icon(e.kind), x0, y0, self.tile)
            if e.kind == 'snake':
                if e.aim:
                    dx, dy = e.aim
                    cv.create_line(cx, cy, cx + dx * self.tile * 2, cy - dy * self.tile * 2, fill='yellow',
                                   width=2, arrow='last', tags='dyn')
        # path so far
        pts = []
        for s in self.states[:upto + 1]:
            for c in (s.trail or [s.pos]):
                pts.extend(self.center(c))
        if len(pts) >= 4:
            cv.create_line(*pts, fill='white', width=2, tags='dyn')
        # this turn's movement
        if len(st.trail) >= 2:
            p = []
            for c in st.trail:
                p.extend(self.center(c))
            cv.create_line(*p, fill='#FF00FF', width=3, arrow='last', tags='dyn')
        if not st.warp:
            x0, y0, x1, y1 = self.box(st.pos)
            cv.create_oval(x0, y0, x1, y1, fill='#8D5524' if st.in_boat else 'white',
                           outline='white' if st.in_boat else 'black', width=2, tags='dyn')
        cv.tag_raise('wall')     # walls stay visible on top of items, enemies and you

    # --- simulation -------------------------------------------------------------
    def on_route_changed(self, ev=None):
        if not self.route.edit_modified():
            return
        self.route.edit_modified(False)
        if self.after_id:
            self.root.after_cancel(self.after_id)
        self.after_id = self.root.after(300, self.rerun)

    def rerun(self):
        self.after_id = None
        if not self.sim:
            return
        # Where to put the selection afterwards: follow the end of the route
        # unless the user picked an earlier turn (self.picked).
        cmds, errors = game.parse_commands(self.route.get('1.0', 'end'))
        if not errors:
            self.error_label.config(text='')
        elif errors[0][1].startswith(game.UNFINISHED):
            self.error_label.config(text='Line {}: {} (waiting for its 2nd character)'.format(*errors[0]),
                                    foreground='#777')
        else:
            self.error_label.config(text='Line {}: {}  (route stops there)'.format(*errors[0]),
                                    foreground='#B00020')
        self.states = self.sim.run(cmds)
        last = self.states[-1]
        if last.won:
            self.result_label.config(text='VICTORY in {} turns ({} seconds)'.format(last.turn, last.turn),
                                     foreground='#1B5E20')
        else:
            self.result_label.config(
                text='Not finished yet: {} turns so far, {} gems held, {}/{} seals'.format(
                    last.turn, last.gems, len(last.seals_broken), len(self.sim.seals)),
                foreground='#333')
        self.steps.delete(0, 'end')
        for st in self.states:
            if st.command is None:
                label = '   0  start'
            else:
                flag = ''
                if any(e.startswith('DIED') for e in st.events):
                    flag = ' DIED'
                elif any('hits you' in e for e in st.events):
                    flag = ' hit'
                elif st.won:
                    flag = ' WIN'
                label = '{:4d}  {:2s}  ({:2d},{:2d}) L{}{}'.format(st.turn, st.command.text, st.pos.x, st.pos.y,
                                                                st.life, flag)
            self.steps.insert('end', label)
            if st.command is not None and (any(e.startswith('DIED') for e in st.events)):
                self.steps.itemconfig('end', foreground='#B00020')
            elif any('hits you' in e for e in st.events):
                self.steps.itemconfig('end', foreground='#E65100')
        if self.picked is None:
            sel = len(self.states) - 1
        else:
            # remembered separately, so a route that is briefly shorter while
            # you type doesn't lose your place
            sel = min(self.picked, len(self.states) - 1)
        self.steps.selection_set(sel)
        self.steps.see(sel)
        self.show_selected()

    def on_pick(self, ev=None):
        sel = self.steps.curselection()
        if sel:
            self.picked = None if sel[0] == len(self.states) - 1 else sel[0]
        self.show_selected()

    def show_selected(self):
        sel = self.steps.curselection()
        if not sel or not self.states:
            return
        i = sel[0]
        st = self.states[i]
        lines = [st.describe(len(self.sim.seals), self.sim.shrines), '']
        if st.command is not None:
            lines.append('Command: {}'.format(st.command.text))
        if st.events:
            lines.append('This turn:')
            lines.extend('  - ' + e for e in st.events)
        near = [e for e in st.enemies if e.alive and e.pos.get_distance(st.pos) <= 8]
        if near:
            lines.append('')
            lines.append('Enemies within 8 tiles:')
            lines.extend('  ' + e.describe() for e in sorted(near, key=lambda e: e.pos.get_distance(st.pos)))
        self.detail.config(state='normal')
        self.detail.delete('1.0', 'end')
        self.detail.insert('1.0', '\n'.join(lines))
        self.detail.config(state='disabled')
        self.draw_state(st, i)

    # --- hover ----------------------------------------------------------------
    def on_hover(self, ev):
        if not self.map:
            return
        x = int(self.canvas.canvasx(ev.x)) // self.tile
        y = self.map.height - 1 - int(self.canvas.canvasy(ev.y)) // self.tile
        if not (0 <= x < self.map.width and 0 <= y < self.map.height):
            return
        c = Coordinates(x, y)
        st = self.current_state()
        terr = self.sim.terrain(st, c) if st else self.map.get_cell(x, y)
        bits = ['({}, {})'.format(x, y), terr.label]
        cont = self.sim.contents(st, c) if st else self.map.get_cell_contents(x, y)
        if cont not in (CellContents.EMPTY, CellContents.FORCE_EMPTY):
            bits.append((game.item_name(cont) if cont in game.ITEMS else cont.label) + (' {}'.format(self.sim.shrines.index(c)) if cont == CellContents.SHRINE else ''))
        if st:
            e = self.sim.enemy_at(st, c)
            if e:
                bits.append(e.label)
        self.hover_label.config(text='   '.join(bits))

    def current_state(self):
        sel = self.steps.curselection()
        if sel and self.states:
            return self.states[sel[0]]
        return None


def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    root = tk.Tk()
    App(root, seed)
    root.mainloop()


if __name__ == '__main__':
    main()
