# Small hand-built maps checking the snake and desert rules in verify.py.
# Run: python test_snakes.py
import sys; sys.path.insert(0,'.')
from map import Map
from support_classes import *
import verify
def build(rows):
    # rows given top-to-bottom; 'W' water, '.' grass, 'S' snake (on lava), 'D' desert
    h=len(rows); w=max(len(r) for r in rows); m=Map(w,h)
    for i,r in enumerate(rows):
        y=h-1-i
        for x in range(w):
            ch=r[x] if x<len(r) else 'W'
            if ch=='W': m.set_cell(x,y,TerrType.WATER)
            if ch=='D': m.set_cell(x,y,TerrType.DESERT)
            if ch=='S': m.set_cell(x,y,TerrType.LAVA); m.set_cell_contents(x,y,CellContents.DRAGON)
    return m
def test(name, rows, target, expect, items=frozenset()):
    m=build(rows); v=verify.Verifier(m)
    h=len(rows); tx,ty=target; t=Coordinates(tx,h-1-ty)
    got = t in v.reachable(frozenset(items))
    print(('OK  ' if got==expect else 'FAIL'), name, 'reachable' if got else 'blocked')
# Example 1: walk past a snake beside a 1-wide corridor
test('pass beside snake', ['W.WW','W.WW','W.SW','W.WW','..WW'], (1,0), True)
# Example 2: walk along a snake's line from column 1 to column 5
test('along line, range 5', ['W.WWW.W','W.WWW.W','W.....S','.WWWWWW'][::1], (5,0), False)
# start at bottom-left: make (0,0) connect to column 1
test('along line, range 5 (fixed start)', ['W.WWW.W','W.WWW.W','W.....S','..WWWWW'], (5,0), False)
# Same corridor but the snake is one tile further on: the turn-off at column 5 is
# an A tile, so with Andrew's four-walls model (2026-11-23) you never cross A-B.
test('along line, longer corridor', ['W.WWW.WW','W.WWW.WW','W......S','..WWWWWW'], (5,0), True)
# Line broken by a gap: snake far away (distance 6+): free
test('snake out of range', ['W.WWW.WWW','W.WWW.WWW','W.....WWS','..WWWWWWW'], (5,0), True)
# Standing next to a snake (on a B) is fine: you melee it
test('pickup next to snake', ['W.WW','W.WW','W.SW','W.WW','..WW'], (1,2), True)
# Hallway with an L-bend at B: coming along the line A->B is walled off without the Bow
from support_classes import CellContents as _K
hall = ['WWW.W','WWW.W','....S','.WWWW']
test('hallway bend blocked', hall, (3,0), False)
test('hallway bend with Bow', hall, (3,0), True, items={_K.BOW})
# Same bend, but a side passage reaches B from the other side: melee kill opens it
test('hallway bend, side access', ['WWW..','WWW.W','....S','.WW.W','.....'], (4,0), True)
# Desert: 1-wide crossable, 2-wide not, pickup on desert not
test('1-wide desert', ['...D...'], (6,0), True)
test('2-wide desert', ['...DD..'], (6,0), False)
test('pickup on desert', ['...D...'], (3,0), False)
