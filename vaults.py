import random
from support_classes import *

class Vault:
    def __init__(self, name, probability, find_location_func, place_func):
        self.name = name
        self.probability = probability
        self.find_location_func = find_location_func
        self.place_func = place_func

def find_desert_pyramid_location(game_map):
    valid = []
    for min_x in range(game_map.width-8):
        for min_y in range(game_map.height-8):
            max_x = min_x + 8
            max_y = min_y + 8
            loc_works = True
            for dx in range(9):
                for y in [min_y, max_y]:
                    if game_map.get_cell(min_x + dx, y) != TerrType.DESERT:
                        loc_works = False
                        break
            for dy in range(9):
                for x in [min_x, max_x]:
                    if game_map.get_cell(x, min_y + dy) != TerrType.DESERT:
                        loc_works = False
                        break
            if loc_works:
                valid.append(Coordinates(min_x + 4, min_y + 4))
    return random.choice(valid) if valid else None

def place_desert_pyramid(game_map, location):
    r1 = [location]
    r2 = []
    for dx in range(-1, 2):
        for dy in range(-1, 2):
            cell_loc = Coordinates(location.x + dx, location.y + dy)
            if cell_loc not in r1:
                r2.append(cell_loc)
    
    r3 = []
    for dx in range(-2, 3):
        for dy in range(-2, 3):
            cell_loc = Coordinates(location.x + dx, location.y + dy)
            if cell_loc not in r1 and cell_loc not in r2:
                r3.append(cell_loc)
    
    r4 = []
    for dx in range(-3, 4):
        for dy in range(-3, 4):
            cell_loc = Coordinates(location.x + dx, location.y + dy)
            if cell_loc not in r1 and cell_loc not in r2 and cell_loc not in r3:
                r4.append(cell_loc)

    game_map.add_room(r1)
    game_map.add_room(r2)
    game_map.add_room(r3)
    game_map.add_room(r4)

    directions = ['up', 'down', 'left', 'right']
    latest_door = None
    for ring in range(0, 4):
        door_direction = random.choice([d for d in directions if d != latest_door])
        if door_direction == 'up':
            game_map.add_door(Coordinates(location.x, location.y + ring), Coordinates(location.x, location.y + ring + 1))
        elif door_direction == 'down':
            game_map.add_door(Coordinates(location.x, location.y - ring), Coordinates(location.x, location.y - ring - 1))
        elif door_direction == 'left':
            game_map.add_door(Coordinates(location.x - ring, location.y), Coordinates(location.x - ring - 1, location.y))
        elif door_direction == 'right':
            game_map.add_door(Coordinates(location.x + ring, location.y), Coordinates(location.x + ring + 1, location.y))
        latest_door = door_direction

    dead_ends = []
    for ring in [r2, r3, r4]:
        wall_a = random.choice(ring)
        neighbors = wall_a.get_neighboring_coordinates()
        wall_b = random.choice([n for n in neighbors if n in ring and n != wall_a])
        game_map.add_forced_wall(wall_a, wall_b)
        dead_ends.append(wall_a)
        dead_ends.append(wall_b)

    if random.random() < 0.5:
        dead_end_terr = TerrType.LAVA
    else:
        dead_end_terr = TerrType.WATER
    
    shrine_done = False
    for dead_end in dead_ends:
        if random.random() < 0.1:
            game_map.set_cell_contents(dead_end.x, dead_end.y, CellContents.GEM)
        elif random.random() < 0.1 and not shrine_done:
            game_map.set_cell_contents(dead_end.x, dead_end.y, CellContents.SHRINE)
            shrine_done = True
        elif random.random() < 0.5:
            game_map.set_cell_contents(dead_end.x, dead_end.y, CellContents.OGRE)
        else:
            game_map.set_cell(dead_end.x, dead_end.y, dead_end_terr)
    
    game_map.set_cell_contents(location.x, location.y, CellContents.ITEM)

vaults = [
    Vault(
        name='Desert Pyramid',
        probability=1.0,
        find_location_func = find_desert_pyramid_location,
        place_func = place_desert_pyramid             
    )
]