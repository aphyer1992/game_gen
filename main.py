import xlsxwriter
from enum import Enum
import math
import random
import os
from support_classes import Coordinates, TerrType, CellContents
import itertools

class Map:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.cells = [[TerrType.GRASS for _ in range(width)] for _ in range(height)]
        self.room_numbers = [[0 for _ in range(width)] for _ in range(height)]
        self.cell_contents = [[CellContents.EMPTY for _ in range(width)] for _ in range(height)]
        self.next_room_number = 1
        self.doors = []

    def set_cell(self, x, y, value):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.cells[y][x] = value

    def get_cell(self, x, y):
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.cells[y][x]
        return None
    
    def get_room_number(self, x, y):
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.room_numbers[y][x]
        return None
    
    def get_room_contents(self, room_number):
        contents = []
        for y in range(self.height):
            for x in range(self.width):
                if self.room_numbers[y][x] == room_number:
                    contents.append(Coordinates(x, y))
        return contents

    def add_room(self, contents):
        for coord in contents:
            if self.is_valid_coordinates(coord):
                self.room_numbers[coord.y][coord.x] = self.next_room_number
                self.set_cell(coord.x, coord.y, TerrType.BUILDING)
        self.next_room_number += 1

    def is_door(self, coord1, coord2):
        return (coord1, coord2) in self.doors or (coord2, coord1) in self.doors

    def is_wall(self, coord1, coord2):
        if self.room_numbers[coord1.y][coord1.x] == self.room_numbers[coord2.y][coord2.x]:
            return False
        if self.is_door(coord1, coord2):
            return False
        return True

    def is_valid_coordinates(self, coordinates):
        return 0 <= coordinates.x < self.width and 0 <= coordinates.y < self.height
    
    def closest_terrain(self, coordinates, terrain_type):
        if not self.is_valid_coordinates(coordinates):
            return None
        closest_distance = float('inf')
        closest_coord = None
        for y in range(self.height):
            for x in range(self.width):
                if self.get_cell(x, y) == terrain_type:
                    distance = coordinates.get_distance(Coordinates(x, y))
                    if distance < closest_distance:
                        closest_distance = distance
                        closest_coord = Coordinates(x, y)
        return closest_distance
    
    def valid_coordinates_in_range(self, coordinates, distance, exact=False):
        valid_coords = []
        for coord in coordinates.get_coordinates_in_range(distance, exact=exact):
            if self.is_valid_coordinates(coord):
                valid_coords.append(coord)
        return valid_coords

    def random_x_value(self, min_pct, max_pct):
        min_x = math.ceil(self.width * min_pct)
        max_x = math.floor(self.width * min(max_pct, 0.99999)) # we can't use 1.0 because it would be out of bounds
        return random.randint(min_x, max_x)
    
    def random_y_value(self, min_pct, max_pct):
        min_y = math.ceil(self.height * min_pct)
        max_y = math.floor(self.height * min(max_pct, 0.99999)) # we can't use 1.0 because it would be out of bounds
        return random.randint(min_y, max_y)
    
    def split_into_continuous_regions(self, area):
        visited = set()
        regions = []
        for i in area:
            if i not in visited:
                stack = [i]
                region = []
                while stack:
                    current = stack.pop()
                    assert current not in visited
                    visited.add(current)
                    region.append(current)
                    for neighbor in current.get_neighboring_coordinates():
                        if self.is_valid_coordinates(neighbor) and neighbor not in visited and neighbor not in stack and neighbor in area:
                            stack.append(neighbor)
                regions.append(region)
        return regions

    def flood_fill(self, start, blocking_terrain_types, blocked_walls=False):
        if not self.is_valid_coordinates(start):
            return []
        
        visited = set()
        stack = [start]
        island = []

        while stack:
            current = stack.pop()
            if current in visited:
                continue
            
            visited.add(current)
            island.append(current)

            for neighbor in current.get_neighboring_coordinates():
                if self.is_valid_coordinates(neighbor) and self.get_cell(neighbor.x, neighbor.y) not in blocking_terrain_types:
                    if not blocked_walls or not self.is_wall(current, neighbor):
                        stack.append(neighbor)

        return island if island else []
    
    def reachable_coordinates(self):
        reachable_terrains = [t for t in TerrType if t.clear_terrain]
        possible_blocking_terrains = [TerrType.LAVA, TerrType.WATER, TerrType.TREE, TerrType.DESERT]
        blocking_terrain_combinations = [tuple(list(subset)) for r in range(len(possible_blocking_terrains) + 1) for subset in itertools.combinations(possible_blocking_terrains, r)]
        results = {}
        for combo in blocking_terrain_combinations:
            items = tuple([b for b in possible_blocking_terrains if b not in combo])
            island = self.flood_fill(Coordinates(0, 0), combo, blocked_walls=True)
            results[items] = {
                'all' : island,
                'clear' : [c for c in island if self.get_cell(c.x, c.y) in reachable_terrains],
            }
        for items in results.keys():
            print('With items {}: {} reachable cells of which {} are clear'.format(
                items, 
                len(results[items]['all']),
                len(results[items]['clear'])
            ))
        return results

    def evaluate_item_usefulness(self):
        reachable = self.reachable_coordinates()
        possible_blocking_terrains = [TerrType.LAVA, TerrType.WATER, TerrType.TREE, TerrType.DESERT]
        for t in possible_blocking_terrains:
            with_item = [len(reachable[k]['clear']) for k in reachable.keys() if t in k]
            without_item = [len(reachable[k]['clear']) for k in reachable.keys() if t not in k]
            assert(len(with_item) == len(without_item)), "Mismatch in item counts"
            print('Terrain {}: {} reachable with, {} reachable without'.format(
                t.label,
                sum(with_item)/len(with_item), 
                sum(without_item)/len(without_item)

            ))

    def split_map_by_terrain(self, split_terrain_types):
        visited = set()
        islands = []
        for y in range(self.height):
            for x in range(self.width):
                if self.get_cell(x, y) not in split_terrain_types:
                    island = self.flood_fill(Coordinates(x, y), split_terrain_types)
                    if island:
                        islands.append(island)
                        visited.update(island)
        return islands
    
    def draw_river(self, start, end, set_terrain=TerrType.WATER, meander_coeff=0.5, widen_iterations=2, widen_coeff=0.2, skip_terrains=[]):
        river_coords = [start]
        current_coord = start
        while current_coord != end:
            options = []
            if current_coord.x <= end.x or random.random() < meander_coeff:
                options.append(Coordinates(current_coord.x + 1, current_coord.y))
            if current_coord.x >= end.x or random.random() < meander_coeff:
                options.append(Coordinates(current_coord.x - 1, current_coord.y))
            if current_coord.y <= end.y or random.random() < meander_coeff:
                options.append(Coordinates(current_coord.x, current_coord.y + 1))
            if current_coord.y >= end.y or random.random() < meander_coeff:
                options.append(Coordinates(current_coord.x, current_coord.y - 1))
            options = [coord for coord in options if self.is_valid_coordinates(coord)]
            current_coord = random.choice(options) if options else current_coord
            river_coords.append(current_coord)
        
        for i in range(widen_iterations):
            shore_coords = []
            for coord in river_coords:
                for neighbor in coord.get_neighboring_coordinates():
                    if self.is_valid_coordinates(neighbor):
                        shore_coords.append(neighbor)
            river_coords = river_coords + [c for c in shore_coords if random.random() < widen_coeff]
        
        river_coords = [c for c in river_coords if self.get_cell(c.x, c.y) not in skip_terrains]
        for coord in river_coords:
            if self.is_valid_coordinates(coord):
                self.set_cell(coord.x, coord.y, set_terrain)
        return(len(river_coords))

    def generate_rivers(self):
        # set the river up to curve through the map
        river_checkpoints = [
            Coordinates(self.random_x_value(0.2, 0.3), self.height - 1),
            Coordinates(self.random_x_value(0.3, 0.4), self.random_y_value(0.5, 0.7)),
            Coordinates(self.random_x_value(0.5, 0.7), self.random_y_value(0.2, 0.3)),
            Coordinates(self.width - 1, self.random_y_value(0.1, 0.3))
        ]
        tributary_checkpoints = [
            Coordinates(0, self.random_y_value(0.7, 0.9)),
            Coordinates(self.random_x_value(0.1, 0.2), self.random_y_value(0.4, 0.5)),
            river_checkpoints[2]
        ]
        for i in range(len(river_checkpoints) - 1):
            self.draw_river(
                river_checkpoints[i],
                river_checkpoints[i+1], 
                meander_coeff=0.5, 
                widen_iterations=2, 
                widen_coeff=0.15
            )
        for i in range(len(tributary_checkpoints) - 1):
            self.draw_river(
                tributary_checkpoints[i],
                tributary_checkpoints[i+1], 
                meander_coeff=0.5, 
                widen_iterations=2, 
                widen_coeff=0.08
            )
        # find large blocks of water (4x4 or larger)
        for y in range(self.height):
            for x in range(self.width):
                all_water = True
                for y_temp in range(y-2, y+1):
                    for x_temp in range(x-2, x+1):
                        if (not self.is_valid_coordinates(Coordinates(x_temp, y_temp))) or (self.get_cell(x_temp, y_temp) != TerrType.WATER):
                            all_water = False
                if all_water:
                    island_squares = [Coordinates(x, y)]
                    stack = [Coordinates(x, y)]
                    while stack:
                        current = stack.pop()
                        for neighbor in current.get_neighboring_coordinates():
                            dist_to_land = self.closest_terrain(neighbor, TerrType.GRASS)
                            if self.is_valid_coordinates(neighbor) and neighbor not in island_squares and dist_to_land >= 3 and random.random() < 0.8:
                                island_squares.append(neighbor)
                                stack.append(neighbor)
                    for square in island_squares:
                        if self.is_valid_coordinates(square):
                            self.set_cell(square.x, square.y, TerrType.GRASS)

    def find_closest_distance(self, first_group, second_group):
        closest_distance = float('inf')
        closest_start = None
        closest_end = None
        for coord1 in first_group:
            for coord2 in second_group:
                distance = coord1.get_distance(coord2)
                if distance < closest_distance:
                    closest_distance = distance
                    closest_start = coord1
                    closest_end = coord2
        return [closest_distance, closest_start, closest_end]


    def generate_desert(self, center, size, subcenters=0):
        marked_cells = set()
        marked_cells.add(center)
        for i in range(size):
            to_mark = set()
            for coord in marked_cells:
                for neighbor in coord.get_neighboring_coordinates():
                    if self.is_valid_coordinates(neighbor) and self.get_cell(neighbor.x, neighbor.y) == TerrType.GRASS:
                        if random.random() < 0.8:
                            to_mark.add(neighbor)
            marked_cells.update(to_mark)
        for i in range(subcenters):
            subcenter = random.choice(center.get_coordinates_in_range(size-1, exact=True))
            sub_marked_cells = set()
            sub_marked_cells.add(subcenter)
            for i in range(size // 2):
                to_mark = set()
                for coord in sub_marked_cells:
                    for neighbor in coord.get_neighboring_coordinates():
                        if self.is_valid_coordinates(neighbor) and self.get_cell(neighbor.x, neighbor.y) == TerrType.GRASS:
                            if random.random() < 0.8:
                                self.set_cell(neighbor.x, neighbor.y, TerrType.DESERT)
                                to_mark.add(neighbor)
                sub_marked_cells.update(to_mark)
            marked_cells.update(sub_marked_cells)

        for coord in marked_cells:
            if self.is_valid_coordinates(coord) and self.get_cell(coord.x, coord.y) == TerrType.GRASS:
                self.set_cell(coord.x, coord.y, TerrType.DESERT)

    def generate_deserts(self):
        # one big desert, near an edge and not near the top right/bottom left corners
        large_desert_center = random.choice([
            Coordinates(self.random_x_value(0, 0.1), self.random_y_value(0.5, 1)),
            Coordinates(self.random_x_value(0.9, 1.0), self.random_y_value(0, 0.5)),
            Coordinates(self.random_x_value(0.5, 1.0), self.random_y_value(0, 0.1)),
            Coordinates(self.random_x_value(0, 0.5), self.random_y_value(0.9, 1.0)),
        ])
        self.generate_desert(large_desert_center, size=random.randint(13, 15), subcenters=random.randint(1, 3))

        for i in range(random.randint(1, 3)):
            small_desert_center = Coordinates(
                self.random_x_value(0.0, 1.0),  
                self.random_y_value(0.0, 1.0)
            )
            while small_desert_center.get_distance(Coordinates(0,0)) < 10:
                small_desert_center = Coordinates(
                    self.random_x_value(0.0, 1.0),  
                    self.random_y_value(0.0, 1.0)
                )
            self.generate_desert(small_desert_center, size=random.randint(7,9), subcenters = random.randint(0,1))

    def generate_bridges(self):
        islands = self.split_map_by_terrain([TerrType.WATER])
        islands = [island for island in islands if random.random() * 20 <= len(island)]  # filter out most small islands
        num_bridges = random.randint(1, 3)
        bridge_locs = []
        iterations = 0
        while num_bridges > 0:
            iterations += 1
            if iterations > 100:
                print("Too many iterations, stopping bridge generation.")
                break
            start_island = random.choice(islands)
            end_island = random.choice(islands)
            if start_island == end_island:
                continue
            [closest_distance, start_coord, end_coord] = self.find_closest_distance(start_island, end_island)
            if closest_distance > 5:
                continue
            if closest_distance <= 1:
                continue
            # we repurpose the river drawing function to draw bridges
            too_close = False
            for l in bridge_locs:
                if start_coord.get_distance(l) < 20 or end_coord.get_distance(l) < 20:
                    too_close = True
            if too_close:
                continue
            print(f"Drawing bridge from {start_coord} to {end_coord}")
            self.draw_river(start_coord, end_coord, set_terrain=TerrType.ROAD, meander_coeff=0.0, widen_iterations=0)
            num_bridges -= 1

    def add_door_from_new_room(self, new_room_contents, old_room_contents):
        door_added = False
        random.shuffle(new_room_contents)
        for door_point in new_room_contents:
            if door_added and random.random() < 0.9: # usually only one door
                continue
            neighbors = door_point.get_neighboring_coordinates()
            for n in neighbors:
                if n in old_room_contents or (old_room_contents == [] and n not in new_room_contents):  # if the old room is empty, we can add a door to any neighbor
                    self.doors.append((door_point, n))
                    door_added = True
                    break
        assert door_added, "No door could be added for new room with contents: \n{}\n\nstarting from:\n{}".format(new_room_contents, old_room_contents)
                
            

    def split_building_into_rooms(self, building_contents):
        if 2 + (random.random() * random.random() * 30) > len(building_contents): # we want to allow large rooms but make them rare
            return
        
        # we have a couple different ways of splitting.
        split_type = random.choice(['x', 'y', 'fill'])
        if split_type == 'y':
            min_y = min([c.y for c in building_contents])
            max_y = max([c.y for c in building_contents])
            if min_y == max_y:
                return
            y_split = random.choice(range(min_y, max_y)) # this can give min and not max, but we will include this row in the bottom.
            new_contents = [c for c in building_contents if c.y <= y_split]
        elif split_type == 'x':
            min_x = min([c.x for c in building_contents])
            max_x = max([c.x for c in building_contents])
            if min_x == max_x:
                return
            x_split = random.choice(range(min_x, max_x))
            new_contents = [c for c in building_contents if c.x <= x_split]
        elif split_type == 'fill':
            start_point = random.choice(building_contents)
            new_contents = [start_point]
            desired_size = math.floor(len(building_contents) * random.random() * 0.6) + 1
            while len(new_contents) < desired_size:
                focus = random.choice(new_contents)
                neighbors = focus.get_neighboring_coordinates()
                for i in neighbors:
                    if i in building_contents and i not in new_contents and random.random() < 0.5:
                        new_contents.append(i)
        else:
            raise ValueError("Invalid split type: {}".format(split_type))
        
        old_contents = [c for c in building_contents if c not in new_contents]

        new_rooms = self.split_into_continuous_regions(new_contents)
        for i in new_rooms:
            if len(i) >= 1:
                self.add_room(i)
                self.add_door_from_new_room(i, old_contents)
        

        # still need to handle doors if the old room is split in two but that will take reachability.
        old_rooms = self.split_into_continuous_regions(old_contents)
        for i in old_rooms:
            if i != old_rooms[0]: # that keeps the previous id
                self.add_room(i)

        for i in old_rooms:
            self.split_building_into_rooms(i)
        for i in new_rooms:
            self.split_building_into_rooms(i)

    def get_gate_position(self, start, size):
        if size%2 == 0:
            gate_size = 2
        else:
            gate_size = 3
        range_start = start + (size-gate_size) // 2
        range_end = start + (size+gate_size) // 2
        return([range_start, range_end])

    def generate_castle(self):
        castle_y_size = self.random_y_value(0.28, 0.33)
        castle_x_size = self.random_x_value(0.28, 0.33)
        castle_y_min = self.random_y_value(0.6, 0.65)
        castle_x_min = self.random_x_value(0.6, 0.65)
        castle_y_max = castle_y_min + castle_y_size - 1
        castle_x_max = castle_x_min + castle_x_size - 1

        contents = []

        for y in range(castle_y_min, castle_y_max + 1):
            for x in range(castle_x_min, castle_x_max + 1):
                if self.is_valid_coordinates(Coordinates(x, y)):
                    contents.append(Coordinates(x, y))
        
        # indent the four walls to make the corners more castle-like
        indent_depth = random.randint(1, min(2, min(castle_x_size, castle_y_size) // 3 - 1))
        indent_offset = random.randint(indent_depth + 1, min(castle_x_size, castle_y_size) // 3)
        for y in range(castle_y_min + indent_offset, castle_y_max - indent_offset + 1):
            for x in range(castle_x_min, castle_x_min + indent_depth):
                contents.remove(Coordinates(x, y))
            for x in range(castle_x_max - indent_depth + 1, castle_x_max + 1):
                contents.remove(Coordinates(x, y))
        for x in range(castle_x_min + indent_offset, castle_x_max - indent_offset + 1):
            for y in range(castle_y_min, castle_y_min + indent_depth):
                contents.remove(Coordinates(x, y))
            for y in range(castle_y_max - indent_depth + 1, castle_y_max + 1):
                contents.remove(Coordinates(x, y))
        
        print('Castle has size {}x{} starting at ({}, {}) with indent depth {}'.format(castle_x_size, castle_y_size, castle_x_min, castle_y_min, indent_depth))
        
        # boss room has special rules to be opposite gate
        boss_room_size = 5

        if random.random() < 0.5: # gate on bottom
            [gate_x_start, gate_x_end] = self.get_gate_position(castle_x_min, castle_x_size)
            gate_y = min([c.y for c in contents if c.x == gate_x_start])
            print(f"Adding gate at ({gate_x_start}, {gate_y}) to ({gate_x_end}, {gate_y})")
            for x in range(gate_x_start, gate_x_end):
                self.doors.append((Coordinates(x, gate_y), Coordinates(x, gate_y - 1)))
            for x in range(gate_x_start, gate_x_end - 1): # keep the castle from splitting just inside the gate
                self.doors.append((Coordinates(x, gate_y), Coordinates(x + 1, gate_y)))

            boss_y_max = max([c.y for c in contents if c.x == gate_x_start]) - 2 # above the gate, with a bit of space to put the entrance opposite.
            boss_y_min = boss_y_max - boss_room_size + 1
            boss_x_min = gate_x_start - 1
            boss_x_max = boss_x_min + boss_room_size - 1
            boss_contents = []
            for x in range(boss_x_min, boss_x_max + 1):
                for y in range(boss_y_min, boss_y_max + 1):
                    if self.is_valid_coordinates(Coordinates(x, y)):
                        boss_contents.append(Coordinates(x, y))
                        contents.remove(Coordinates(x, y))
            self.add_room(boss_contents)
            self.doors.append((
                Coordinates(boss_x_min + 2, boss_y_max),
                Coordinates(boss_x_min + 2, boss_y_max + 1),
            ))

        else: # gate on left
            [gate_y_start, gate_y_end] = self.get_gate_position(castle_y_min, castle_y_size)
            gate_x = min([c.x for c in contents if c.y == gate_y_start])
            print(f"Adding gate at ({gate_x}, {gate_y_start}) to ({gate_x}, {gate_y_end})")
            for y in range(gate_y_start, gate_y_end):
                self.doors.append((Coordinates(gate_x, y), Coordinates(gate_x - 1, y)))
            for y in range(gate_y_start, gate_y_end - 1): # keep the castle from splitting just inside the gate
                self.doors.append((Coordinates(gate_x, y), Coordinates(gate_x, y + 1)))

            boss_x_max = max([c.x for c in contents if c.y == gate_y_start]) - 2 # right of the gate, with a bit of space to put the entrance opposite.
            boss_x_min = boss_x_max - boss_room_size + 1
            boss_y_min = gate_y_start - 1
            boss_y_max = boss_y_min + boss_room_size - 1
            boss_contents = []
            for x in range(boss_x_min, boss_x_max + 1):
                for y in range(boss_y_min, boss_y_max + 1):
                    if self.is_valid_coordinates(Coordinates(x, y)):
                        boss_contents.append(Coordinates(x, y))
                        contents.remove(Coordinates(x, y))
            self.add_room(boss_contents)
            self.doors.append((
                Coordinates(boss_x_max, boss_y_min + 2),
                Coordinates(boss_x_max + 1, boss_y_min + 2),
            ))
        
        self.cell_contents[boss_y_min][boss_x_min] = CellContents.SEAL
        self.cell_contents[boss_y_min][boss_x_max] = CellContents.SEAL
        self.cell_contents[boss_y_max][boss_x_min] = CellContents.SEAL
        self.cell_contents[boss_y_max][boss_x_max] = CellContents.SEAL
        self.cell_contents[boss_y_min+2][boss_x_min+2] = CellContents.BOSS

        self.add_room(contents)
        self.split_building_into_rooms(contents)

    def find_spot_for_building(self, base_x_size, base_y_size):
        for x in random.sample(range(self.width - base_x_size), 1):
            for y in random.sample(range(self.height - base_y_size), 1):
                if all(self.get_cell(x + dx, y + dy) not in [TerrType.BUILDING, TerrType.WATER] for dx in range(base_x_size) for dy in range(base_y_size)):
                    return Coordinates(x, y)

    def take_bite(self, start_coord, x_size, y_size, x_corner, y_corner, bite_size):
        if x_corner == 0:
            x_range = range(start_coord.x, start_coord.x + bite_size)
        else:
            x_range = range(start_coord.x + x_size - bite_size, start_coord.x + x_size)
        if y_corner == 0:
            y_range = range(start_coord.y, start_coord.y + bite_size)
        else:   
            y_range = range(start_coord.y + y_size - bite_size, start_coord.y + y_size)
        
        bite_contents = []
        for y in y_range:
            for x in x_range:
                if self.is_valid_coordinates(Coordinates(x, y)):
                    bite_contents.append(Coordinates(x, y)) 
        return bite_contents
        
    def open_unreachable_rooms(self):
        reachable = self.flood_fill(Coordinates(0, 0), [], blocked_walls=True)
        unreachable_rooms = [self.room_numbers[y][x] for x in range(self.width) for y in range(self.height) if Coordinates(x, y) not in reachable]
        for room_number in set(unreachable_rooms):
            if room_number > 0: # we can have an outdoor area that is unreachable because of being blocked off by rooms missing doros.  This should resolve itself when the rooms get doors.
                self.add_door_from_new_room(self.get_room_contents(room_number), [])

    def generate_building(self):
        start_coord = None
        while start_coord is None:
            base_x_size = random.randint(1, 8)
            base_y_size = random.randint(1, 8)
            start_coord = self.find_spot_for_building(base_x_size, base_y_size)
        
        contents = []
        for y in range(start_coord.y, start_coord.y + base_y_size):
            for x in range(start_coord.x, start_coord.x + base_x_size):
                if self.is_valid_coordinates(Coordinates(x, y)):
                    contents.append(Coordinates(x, y))
        # building shapes are rectangles with 0, 1, 2 or 4 bites taken out of corners.
        min_dim = min(base_x_size, base_y_size)
        max_dim = max(base_x_size, base_y_size)
        num_bites = 0
        if random.random() < (min_dim - 1) * 0.17: # we obviously cannot take bites from a 1x2, rarely from 2x2, always beyond 6
            if min_dim == 2:
                num_bites = 1
            else:
                num_bites = random.randint(1, 4)
            bites = random.sample([[0,1], [0,0], [1,0], [1,1]], num_bites)
            for bite in bites:
                if num_bites == 1:
                    bite_size = random.randint(1, min_dim // 2)
                else:
                    bite_size = random.randint(1, (min_dim-1) // 2)
                bite_contents = self.take_bite(start_coord, base_x_size, base_y_size, bite[0], bite[1], bite_size)
                contents = [c for c in contents if c not in bite_contents]
        self.add_room(contents)
        
        sides = ['top', 'bottom', 'left', 'right']
        
        if num_bites == 0:
            num_doors = random.choice([1,1,1,1,2,2,3])
        elif num_bites == 1:
            num_doors = random.choice([1,2])
        elif num_bites == 2:
            num_doors = random.choice([1,2])
        elif num_bites == 3:
            num_doors = random.choice([1,2,3,4])
        elif num_bites == 4:
            num_doors = random.choice([1,2,3,4])
        
        doors_made = 0
        while doors_made < num_doors:
            side = random.choice(sides)
            if side == 'top':
                top = max(coord.y for coord in contents)
                valid = [coord for coord in contents if coord.y == top]
                inside = random.choice(valid)
                outside = Coordinates(inside.x, inside.y + 1)
            elif side == 'bottom':
                bottom = min(coord.y for coord in contents)
                valid = [coord for coord in contents if coord.y == bottom]
                inside = random.choice(valid)
                outside = Coordinates(inside.x, inside.y - 1)
            elif side == 'left':
                left = min(coord.x for coord in contents)
                valid = [coord for coord in contents if coord.x == left]
                inside = random.choice(valid)
                outside = Coordinates(inside.x - 1, inside.y)
            elif side == 'right':
                right = max(coord.x for coord in contents)
                valid = [coord for coord in contents if coord.x == right]
                inside = random.choice(valid)
                outside = Coordinates(inside.x + 1, inside.y)

            if self.is_valid_coordinates(outside) and self.get_cell(outside.x, outside.y) not in [TerrType.WATER]:
                self.doors.append((inside, outside))
                doors_made += 1
                sides.remove(side)

        self.split_building_into_rooms(contents)
        return(len(contents))

    def generate_buildings(self):
        total_size = 0
        desired_size = self.width * self.height // 20 * (1 + random.random())  # 5-10% of the map
        while total_size < desired_size:
            total_size += self.generate_building()

    def generate_lava(self):
        desired_lava_count = self.width * self.height // 100 * (3 + random.random())  # 3-4% of the map
        lava_count = 0
        while lava_count < desired_lava_count:
            start = Coordinates(self.random_x_value(0.5, 1.0), self.random_y_value(0.5, 1.0))
            end = random.choice(self.valid_coordinates_in_range(start, 10, exact=False))
            lava_count += self.draw_river(start, end, set_terrain=TerrType.LAVA, meander_coeff=0.2, widen_iterations=0, widen_coeff=0, skip_terrains=[TerrType.WATER, TerrType.LAVA, TerrType.BUILDING])
            
            for y in range(self.height // 2, self.height):
                for x in range(self.width // 2, self.width):
                    if random.random() < 0.02 and self.get_cell(x, y) in [TerrType.GRASS, TerrType.DESERT]:
                        self.set_cell(x, y, TerrType.LAVA)
                        lava_count += 1
                        # lava streaks
                        for neighbor in Coordinates(x, y).get_neighboring_coordinates():
                            if self.is_valid_coordinates(neighbor) and self.get_cell(neighbor.x, neighbor.y) == TerrType.GRASS and random.random() < 0.2:
                                self.set_cell(neighbor.x, neighbor.y, TerrType.LAVA)
                                next_neighbor = neighbor + neighbor - Coordinates(x,y)
                                if self.is_valid_coordinates(next_neighbor) and self.get_cell(next_neighbor.x, next_neighbor.y) == TerrType.GRASS and random.random() < 0.5:
                                    lava_count += 1
                                    self.set_cell(next_neighbor.x, next_neighbor.y, TerrType.LAVA)
        
    def generate_forests(self):
        num_forests = random.randint(3, 5)
        for _ in range(num_forests):
            center = None
            while center is None or self.get_cell(center.x, center.y) != TerrType.GRASS:
                center = Coordinates(
                    self.random_x_value(0.1, 0.9),
                    self.random_y_value(0.1, 0.9)
                )
            base_size = random.randint(3, 6)
            for c in self.valid_coordinates_in_range(center, base_size * 2, exact=False):
                if self.get_cell(c.x, c.y) == TerrType.GRASS and random.random() < (1 - (c.get_distance(center) / (base_size * 2))):
                    self.set_cell(c.x, c.y, TerrType.TREE)
            
            while random.random() < 0.5:
                subcenter = random.choice(center.get_coordinates_in_range(base_size, exact=True))
                for c in self.valid_coordinates_in_range(subcenter, base_size, exact=False):
                    if self.get_cell(c.x, c.y) == TerrType.GRASS and random.random() < 0.5:
                        self.set_cell(c.x, c.y, TerrType.TREE)

    def scatter_trees(self):
        for y in range(self.height):
            for x in range(self.width):
                if self.get_cell(x, y) == TerrType.GRASS and random.random() < 0.01:
                    self.set_cell(x, y, TerrType.TREE)

    def place_items(self):
        self.cell_contents[0][0] = CellContents.SHRINE
        items_to_place = 31 # 20 gems, 5 shrines, 6 pickups
        items_placed = 0
        item_locations = [Coordinates(0, 0)]  # start with the shrine location
        tries = 0
        while items_placed < items_to_place:
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            new_loc = Coordinates(x, y)
            min_spread = (self.width + self.height) // 11
            if self.get_cell(x, y).clear_terrain and self.cell_contents[y][x] == CellContents.EMPTY and self.find_closest_distance([new_loc], item_locations)[0] >= min_spread :
                item_locations.append(new_loc)
                items_placed += 1
            tries += 1
            if tries > 1000:
                raise("Too many tries to place items, check the map size or item count.")
        random.shuffle(item_locations)
        for i in range(20):
            self.cell_contents[item_locations[i].y][item_locations[i].x] = CellContents.GEM
        for i in range(20, 25):
            self.cell_contents[item_locations[i].y][item_locations[i].x] = CellContents.SHRINE
        self.cell_contents[item_locations[25].y][item_locations[25].x] = CellContents.DESERT_CLOAK
        self.cell_contents[item_locations[26].y][item_locations[26].x] = CellContents.BOW
        self.cell_contents[item_locations[27].y][item_locations[27].x] = CellContents.WATER_BOOTS
        self.cell_contents[item_locations[28].y][item_locations[28].x] = CellContents.FIRE_SHIELD
        self.cell_contents[item_locations[29].y][item_locations[29].x] = CellContents.BLESSING
        self.cell_contents[item_locations[30].y][item_locations[30].x] = CellContents.AXE
    
    def generate_map(self):
        self.generate_rivers()
        self.generate_deserts()
        self.generate_bridges()
        self.generate_castle()
        self.generate_buildings()
        self.open_unreachable_rooms()
        self.generate_lava()
        self.generate_forests()
        self.scatter_trees()
        self.place_items()
        #self.evaluate_item_usefulness()

    def export_to_excel(self, filename):
        workbook = xlsxwriter.Workbook(filename)
        worksheet = workbook.add_worksheet()
        worksheet.set_column(0, self.width - 1, 3)

        # Create a format cache to avoid duplicate formats
        format_cache = {}

        for alt_y in range(self.height): # we want low y to show up at the bottom...
            y = self.height - 1 - alt_y
            for x in range(self.width):
                 # Determine borders
                borders = {}
                # Check up
                if y < self.height - 1:
                    if self.room_numbers[y][x] != self.room_numbers[y + 1][x]:
                        if not self.is_door(Coordinates(x, y), Coordinates(x, y + 1)):
                            borders['top'] = 2  # thick
                # Check down
                if y > 0:
                    if self.room_numbers[y][x] != self.room_numbers[y - 1][x]:
                        if not self.is_door(Coordinates(x, y), Coordinates(x, y - 1)):
                            borders['bottom'] = 2
                # Check left
                if x > 0:   
                    if self.room_numbers[y][x] != self.room_numbers[y][x - 1]:
                        if not self.is_door(Coordinates(x, y), Coordinates(x - 1, y)):
                            borders['left'] = 2
                # Check right
                if x < self.width - 1:
                    if self.room_numbers[y][x] != self.room_numbers[y][x + 1]:
                        if not self.is_door(Coordinates(x, y), Coordinates(x + 1, y)):
                            borders['right'] = 2
                # Build format key
                border_key = (borders.get('top', 0), borders.get('bottom', 0),
                            borders.get('left', 0), borders.get('right', 0))
            
                cell_type = self.get_cell(x, y)
                cell_contents = self.cell_contents[y][x]
                contents_key = cell_contents.label
                fmt_key = (cell_type.color, border_key, contents_key)
                if fmt_key not in format_cache:
                    fmt_dict = {'bg_color': cell_type.color}
                    if borders.get('top'): fmt_dict['top'] = borders['top']
                    if borders.get('bottom'): fmt_dict['bottom'] = borders['bottom']
                    if borders.get('left'): fmt_dict['left'] = borders['left']
                    if borders.get('right'): fmt_dict['right'] = borders['right']
                    fmt_dict['align'] = 'center'
                    fmt_dict['valign'] = 'vcenter'
                    fmt_dict['font_color'] = cell_contents.color
                    format_cache[fmt_key] = workbook.add_format(fmt_dict)
                cell_format = format_cache[fmt_key]
            
                worksheet.write(alt_y, x, cell_contents.symbol, cell_format)

        workbook.close()
    
    def gen_name(self):
        return('{} the {} {} of {} {} {}'.format(
            random.choice(['Against', 'Assault', 'Assail', 'Attack']),
            random.choice(['Black', 'Beshadowed', 'Blighted']),
            random.choice(['Castle', 'Citadel']),
            random.choice(['Dread', 'Dark', 'Despicable']),
            random.choice(['Emperor', 'Earl', 'Exarch']),
            random.choice(['Frederick', 'Festin'])
        ))

if __name__ == "__main__":
    random.seed(42)  # For reproducibility
    map_width = 50
    map_height = 50
    for i in range(3):
        game_map = Map(map_width, map_height)
        game_map.generate_map()
        name = "game_map_{}.xlsx".format(i + 1)
        game_map.export_to_excel(name)
        os.startfile(name)
        print(f"Map generated and exported to '{name}' with dimensions {map_width}x{map_height}.")
    input("Press Enter to exit...")