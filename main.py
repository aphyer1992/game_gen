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
    STONE = ("Stone", "#222222")    # dark
    DESERT = ("Desert", "#FFD966")    # yellow
    LAVA = ("Lava", "#FF0000")        # red

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

    def set_cell(self, x, y, value):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.cells[y][x] = value

    def get_cell(self, x, y):
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.cells[y][x]
        return None

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
                    island = self._flood_fill(Coordinates(x, y), split_terrain_types)
                    if island:
                        islands.append(island)
                        visited.update(island)
        return islands
    
    def draw_river(self, start, end, meander_coeff=0.5, widen_iterations=2, widen_coeff=0.2):
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
                self.set_cell(coord.x, coord.y, TerrType.WATER)



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
                    print(f"Found large water block at ({x}, {y})")
                    island_squares = [Coordinates(x, y)]
                    stack = [Coordinates(x, y)]
                    while stack:
                        current = stack.pop()
                        for neighbor in current.get_neighboring_coordinates():
                            dist_to_land = self.closest_terrain(neighbor, TerrType.GRASS)
                            if self.is_valid_coordinates(neighbor) and neighbor not in island_squares and dist_to_land >= 3 and random.random() < 0.8:
                                island_squares.append(neighbor)
                                stack.append(neighbor)
                    print('Adding island squares:', island_squares)
                    for square in island_squares:
                        if self.is_valid_coordinates(square):
                            self.set_cell(square.x, square.y, TerrType.GRASS)
                                
    def generate_castle(self):
        castle_y_size = self.random_y_value(0.25, 0.3)
        castle_x_size = self.random_x_value(0.25, 0.3)
        castle_y_min = self.random_y_value(0.6, 0.65)
        castle_x_min = self.random_x_value(0.6, 0.65)
        castle_y_max = castle_y_min + castle_y_size
        castle_x_max = castle_x_min + castle_x_size

        for y in range(castle_y_min, castle_y_max + 1):
            for x in range(castle_x_min, castle_x_max + 1):
                if self.is_valid_coordinates(Coordinates(x, y)):
                    self.set_cell(x, y, TerrType.STONE)
        
        # indent the four walls to make the corners more castle-like
        indent_depth = random.randint(1, min(2, min(castle_x_size, castle_y_size) // 3 - 1))
        indent_offset = random.randint(indent_depth + 1, min(castle_x_size, castle_y_size) // 3)
        for y in range(castle_y_min + indent_offset, castle_y_max - indent_offset + 1):
            for x in range(castle_x_min, castle_x_min + indent_depth):
                self.set_cell(x, y, TerrType.GRASS)
            for x in range(castle_x_max - indent_depth + 1, castle_x_max + 1):
                self.set_cell(x, y, TerrType.GRASS)
        for x in range(castle_x_min + indent_offset, castle_x_max - indent_offset + 1):
            for y in range(castle_y_min, castle_y_min + indent_depth):
                self.set_cell(x, y, TerrType.GRASS)
            for y in range(castle_y_max - indent_depth + 1, castle_y_max + 1):
                self.set_cell(x, y, TerrType.GRASS)

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


    def generate_map(self):
        self.generate_rivers()
        self.generate_castle()
        self.generate_lava()
        
    def export_to_excel(self, filename):
        workbook = xlsxwriter.Workbook(filename)
        worksheet = workbook.add_worksheet()
        worksheet.set_column(0, self.width - 1, 3)

        # Create a format cache to avoid duplicate formats
        format_cache = {}

        for alt_y in range(self.height): # we want low y to show up at the bottom...
            y = self.height - 1 - alt_y
            for x in range(self.width):
                cell_type = self.get_cell(x, y)
                if cell_type:
                    # Cache formats by color
                    if cell_type.color not in format_cache:
                        format_cache[cell_type.color] = workbook.add_format({'bg_color': cell_type.color})
                    cell_format = format_cache[cell_type.color]
                    worksheet.write(alt_y, x, '', cell_format)

        workbook.close()
    
    def gen_name(self):
        return('{} the {} {} of {} {} {}'.format(
            random.choice(['Against', 'Assault', 'Assail', 'Attack']),
            random.choice(['Black', 'Beshadowed']),
            random.choice(['Castle', 'Citadel']),
            random.choice(['Dread', 'Dark']),
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
        print(f"Map generated and exported to 'game_map.xlsx' with dimensions {map_width}x{map_height}.")
    input("Press Enter to exit...")