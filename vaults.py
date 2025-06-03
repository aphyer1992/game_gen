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
    r1_door = random.choice(directions)
    if r1_door == 'up':
        game_map.add_door(location, Coordinates(location.x, location.y + 1))
    elif r1_door == 'down':
        game_map.add_door(location, Coordinates(location.x, location.y - 1))
    elif r1_door == 'left':
        game_map.add_door(location, Coordinates(location.x - 1, location.y))
    elif r1_door == 'right':
        game_map.add_door(location, Coordinates(location.x + 1, location.y))
    
    r2_door = random.choice([d for d in directions if d != r1_door])
    if r2_door == 'up':
        game_map.add_door(Coordinates(location.x, location.y + 1), Coordinates(location.x, location.y + 2))
    elif r2_door == 'down':
        game_map.add_door(Coordinates(location.x, location.y - 1), Coordinates(location.x, location.y - 2))
    elif r2_door == 'left':
        game_map.add_door(Coordinates(location.x - 1, location.y), Coordinates(location.x - 2, location.y))
    elif r2_door == 'right':
        game_map.add_door(Coordinates(location.x + 1, location.y), Coordinates(location.x + 2, location.y))

    r3_door = random.choice([d for d in directions if d != r1_door])
    if r3_door == 'up':
        game_map.add_door(Coordinates(location.x, location.y + 2), Coordinates(location.x, location.y + 3))
    elif r3_door == 'down':
        game_map.add_door(Coordinates(location.x, location.y - 2), Coordinates(location.x, location.y - 3))
    elif r3_door == 'left':
        game_map.add_door(Coordinates(location.x - 2, location.y), Coordinates(location.x - 3, location.y))
    elif r3_door == 'right':
        game_map.add_door(Coordinates(location.x + 2, location.y), Coordinates(location.x + 3, location.y))

    r4_door = random.choice([d for d in directions if d != r3_door])
    if r4_door == 'up':
        game_map.add_door(Coordinates(location.x, location.y + 3), Coordinates(location.x, location.y + 4))
    elif r4_door == 'down':
        game_map.add_door(Coordinates(location.x, location.y - 3), Coordinates(location.x, location.y - 4))
    elif r4_door == 'left':
        game_map.add_door(Coordinates(location.x - 3, location.y), Coordinates(location.x - 4, location.y))
    elif r4_door == 'right':
        game_map.add_door(Coordinates(location.x + 3, location.y), Coordinates(location.x + 4, location.y))

    r2_wall_a = random.choice(r2)
    neighbors = r2_wall_a.get_neighboring_coordinates()
    r2_wall_b = random.choice([n for n in neighbors if n in r2 and n != r2_wall_a])
    game_map.add_forced_wall(r2_wall_a, r2_wall_b)
    
    r3_wall_a = random.choice(r3)
    neighbors = r3_wall_a.get_neighboring_coordinates()
    r3_wall_b = random.choice([n for n in neighbors if n in r3 and n != r3_wall_a])
    game_map.add_forced_wall(r3_wall_a, r3_wall_b)

    r4_wall_a = random.choice(r4)
    neighbors = r4_wall_a.get_neighboring_coordinates() 
    r4_wall_b = random.choice([n for n in neighbors if n in r4 and n != r4_wall_a])
    game_map.add_forced_wall(r4_wall_a, r4_wall_b)

    dead_ends = [r2_wall_a, r2_wall_b, r3_wall_a, r3_wall_b, r4_wall_a, r4_wall_b]
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