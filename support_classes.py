
from enum import Enum
import math

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
    
    @property
    def clear_terrain(self):
        return self in (TerrType.GRASS, TerrType.DESERT, TerrType.BUILDING, TerrType.ROAD)

class CellContents(Enum):
    EMPTY = ("Empty", '', None)
    SHRINE = ("Shrine", "⛤", "#00B0F0")  
    SEAL = ("Seal", "⛤", "#FF0000")     
    OGRE = ("Ogre", "👹", "#C00000")
    BOSS = ("Boss", "☠", "#C00000")       
    DRAGON = ("Dragon", "Ϟ", "#548235")    
    GEM = ("Gem", "◆", "#FFFFFF")   
    DESERT_CLOAK = ("Cloak", "★", "#CCFF00")        
    WATER_BOOTS = ("Boots", "★", "#00F0F0")  
    FIRE_SHIELD = ("Shield", "★", "#FF0000") 
    BOW = ("Bow", "★", "#00FF00") 
    BLESSING = ("Blessing", "★", "#0000FF")
    AXE = ("Axe", "★", "#FF8000")
    ITEM = ("Item", "?", "#FF00FF") # when we haven't decided what it is yet
    
    @property
    def symbol(self):
        return self.value[1]

    @property
    def label(self):
        return self.value[0]

    @property
    def color(self):
        return self.value[2]