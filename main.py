import xlsxwriter
from enum import Enum
import math
import random
import os

class Coordinates:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __repr__(self):
        return f"Coordinates(x={self.x}, y={self.y})"

    def __eq__(self, other):
        if isinstance(other, Coordinates):
            return self.x == other.x and self.y == other.y
        return False
    
    def __add__(self, other):
        return Coordinates(self.x + other.x, self.y + other.y)
    
    def __sub__(self, other):
        return Coordinates(self.x - other.x, self.y - other.y)
    
    def __hash__(self):
        return hash((self.x, self.y))
    
    def get_distance(self,other):
        return(abs(self.x - other.x) + abs(self.y - other.y))
    
    def get_neighboring_coordinates(self):
        return [
            Coordinates(self.x + 1, self.y),
            Coordinates(self.x - 1, self.y),
            Coordinates(self.x, self.y + 1),
            Coordinates(self.x, self.y - 1)
        ]
    
    def get_coordinates_in_range(self, distance, exact=False):
        coordinates = []
        for dx in range(-distance, distance + 1):
            for dy in range(-distance, distance + 1):
                if (not exact) and ((abs(dx) + abs(dy)) < distance) or ((abs(dx) + abs(dy)) == distance):
                    coordinates.append(Coordinates(self.x + dx, self.y + dy))
        return coordinates

class TerrType(Enum):
    GRASS = ("Grass", "#92D050")      # light green
    TREE = ("Tree", "#548235")        # dark green
    WATER = ("Water", "#00B0F0")      # blue
    BUILDING = ("Building", "#999999")    # gray
    DESERT = ("Desert", "#FFD966")    # yellow
    LAVA = ("Lava", "#FF0000")        # red
    ROAD = ("Road", "#C2B280")        # brown

    @property
    def color(self):
        return self.value[1]

    @property
    def label(self):
        return self.value[0]


class Map:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.cells = [[TerrType.GRASS for _ in range(width)] for _ in range(height)]
        self.room_numbers = [[0 for _ in range(width)] for _ in range(height)]
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

    def add_room(self, contents):
        for coord in contents:
            if self.is_valid_coordinates(coord):
                self.room_numbers[coord.y][coord.x] = self.next_room_number
        self.next_room_number += 1

    def is_door(self, coord1, coord2):
        return (coord1, coord2) in self.doors or (coord2, coord1) in self.doors

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
    
    def flood_fill(self, start, blocking_terrain_types):
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
                    stack.append(neighbor)

        return island if island else []
    
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
    
    def draw_river(self, start, end, set_terrain=TerrType.WATER, meander_coeff=0.5, widen_iterations=2, widen_coeff=0.2):
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
        
        for coord in river_coords:
            if self.is_valid_coordinates(coord):
                self.set_cell(coord.x, coord.y, set_terrain)



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

    def get_gate_position(self, start, size):
        if size%2 == 0:
            gate_size = 2
        else:
            gate_size = 3
        range_start = start + (size-gate_size) // 2
        range_end = start + (size+gate_size) // 2
        return([range_start, range_end])

    def generate_castle(self):
        castle_y_size = self.random_y_value(0.25, 0.3)
        castle_x_size = self.random_x_value(0.25, 0.3)
        castle_y_min = self.random_y_value(0.6, 0.65)
        castle_x_min = self.random_x_value(0.6, 0.65)
        castle_y_max = castle_y_min + castle_y_size
        castle_x_max = castle_x_min + castle_x_size

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

        if random.random() < 0.5: # gate on bottom
            [gate_x_start, gate_x_end] = self.get_gate_position(castle_x_min, castle_x_size)
            gate_y = min([c.y for c in contents if c.x == gate_x_start])
            print(f"Adding gate at ({gate_x_start}, {gate_y}) to ({gate_x_end}, {gate_y})")
            for x in range(gate_x_start, gate_x_end + 1):
                self.doors.append((Coordinates(x, gate_y), Coordinates(x, gate_y - 1)))
        else: # gate on left
            [gate_y_start, gate_y_end] = self.get_gate_position(castle_y_min, castle_y_size)
            gate_x = min([c.x for c in contents if c.y == gate_y_start])
            print(f"Adding gate at ({gate_x}, {gate_y_start}) to ({gate_x}, {gate_y_end})")
            for y in range(gate_y_start, gate_y_end + 1):
                self.doors.append((Coordinates(gate_x, y), Coordinates(gate_x - 1, y)))

        self.add_room(contents)
        for coord in contents:
            if self.is_valid_coordinates(coord):
                self.set_cell(coord.x, coord.y, TerrType.BUILDING)
                

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
        for coord in contents: 
            if self.is_valid_coordinates(coord):
                self.set_cell(coord.x, coord.y, TerrType.BUILDING)
        
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

        return(len(contents))

    def generate_buildings(self):
        total_size = 0
        desired_size = self.width * self.height // 20 * (1 + random.random())  # 5-10% of the map
        while total_size < desired_size:
            total_size += self.generate_building()

    def generate_lava(self):
        for y in range(self.height // 2, self.height):
            for x in range(self.width // 2, self.width):
                if random.random() < 0.1 and self.get_cell(x, y) == TerrType.GRASS:
                    self.set_cell(x, y, TerrType.LAVA)
                    for neighbor in Coordinates(x, y).get_neighboring_coordinates():
                        if self.is_valid_coordinates(neighbor) and self.get_cell(neighbor.x, neighbor.y) == TerrType.GRASS and random.random() < 0.2:
                            self.set_cell(neighbor.x, neighbor.y, TerrType.LAVA)
                            next_neighbor = neighbor + neighbor - Coordinates(x,y)
                            if self.is_valid_coordinates(next_neighbor) and self.get_cell(next_neighbor.x, next_neighbor.y) == TerrType.GRASS and random.random() < 0.5:
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

    def generate_map(self):
        self.generate_rivers()
        self.generate_deserts()
        self.generate_bridges()
        self.generate_castle()
        self.generate_buildings()
        self.generate_lava()
        self.generate_forests()
        self.scatter_trees()

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
                fmt_key = (cell_type.color, border_key)
                if fmt_key not in format_cache:
                    fmt_dict = {'bg_color': cell_type.color}
                    if borders.get('top'): fmt_dict['top'] = borders['top']
                    if borders.get('bottom'): fmt_dict['bottom'] = borders['bottom']
                    if borders.get('left'): fmt_dict['left'] = borders['left']
                    if borders.get('right'): fmt_dict['right'] = borders['right']
                    format_cache[fmt_key] = workbook.add_format(fmt_dict)
                cell_format = format_cache[fmt_key]
            
                worksheet.write(alt_y, x, '', cell_format)

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