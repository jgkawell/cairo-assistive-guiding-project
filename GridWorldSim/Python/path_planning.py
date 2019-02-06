import sys
import numpy as np
import heapq

class PriorityQueue:
    def __init__(self):
        self.elements = []

    def empty(self):
        return len(self.elements) == 0

    def put(self, item, priority):
        heapq.heappush(self.elements, (priority, item))

    def get(self):
        return heapq.heappop(self.elements)[1]

class Vertex():
    def __init__(self, key, cell_type = None):
        self.key = key
        self.cell_type = cell_type
        self.reward = 0
        self.neighbor_list = {}
        self.parent = -1
        self.dist = sys.maxsize #distance to start vertex 0
        self.visited = False

        if cell_type == "Reward":
            self.reward = 1

    def add_neighbor(self, neighbor, weight=1):
        self.neighbor_list[neighbor] = weight

    def get_neighbors(self):
        return self.neighbor_list.keys()

    def get_xy(self, world_size):
        x = self.key % world_size
        y = int((self.key - x) / world_size)
        return (x, y)

    def __lt__(self, other):
        if self.dist < other.dist: return True
        return False

    def __eq__(self, other):
        if self.dist == other.dist: return True
        return False

    def __hash__(self):
        return hash(self.key)

class Graph():
    def __init__(self, directed=False):
        self.vertices = {}
        self.num_walls = 0

    def setup_graph(self, world, world_size):
        self.world_size = world_size

        for i in range(0, world_size):
            for j in range(0, world_size):
                key = i + world_size * j
                celltype = world[i][j]
                v = Vertex(key, celltype)
                self.add_vertex(v)

        for i in range(world_size**2):
            v_cur = self.get_vertex(i)
            if v_cur.cell_type != "Wall": # 'i' rows by 'j' columns, key = world_size * i + j
                if i % world_size != world_size-1 and self.get_vertex(i+1).cell_type != "Wall":
                    self.add_edge(i, i+1) #try to add cell to the right
                if i % world_size != 0 and self.get_vertex(i-1).cell_type != "Wall":
                    self.add_edge(i, i-1) #cell to the left
                if i + world_size < world_size**2 and self.get_vertex(i+world_size).cell_type != "Wall":
                    self.add_edge(i, i+world_size) #cell above
                if i - world_size > 0 and self.get_vertex(i-world_size).cell_type != "Wall":
                    self.add_edge(i, i-world_size) #cell below

    def add_vertex(self, vertex):
        self.vertices[vertex.key] = vertex

    def get_vertex(self, key):
        return self.vertices[key]

    def get_vertices(self):
        return self.vertices.keys()

    def get_key(self, x, y):
        return x + self.world_size * y

    def __iter__(self):
        return self.vertices.values().__iter__()

    def add_edge(self, from_key, to_key, weight=1): #assume bidirectional
        self.vertices[from_key].add_neighbor(self.vertices[to_key], weight=weight)
        self.vertices[to_key].add_neighbor(self.vertices[from_key], weight=weight)

def heuristic(goal_pos, vertex_pos): #manhattan distance - admissible
    (x1, y1) = goal_pos
    (x2, y2) = vertex_pos
    return abs(x1 - x2) + abs(y1 - y2)

def trace(vertex, graph):
    trace = []
    trace.append(vertex.get_xy(graph.world_size))
    curr = vertex
    while curr.parent != -1:
        v_parent = graph.get_vertex(curr.parent)
        trace.append(v_parent.get_xy(graph.world_size))
        curr = v_parent
    return trace

def a_star(graph, start, goal):
    frontier = PriorityQueue()
    frontier.put(start, 0)
    frontier_tracker = {}
    frontier_tracker[start] = 0

    start.dist = 0
    explored = {}
    cost_so_far = {}
    cost_so_far[start] = 0
    while not frontier.empty():
        current = frontier.get()

        if current == goal: break

        neighbors = current.get_neighbors()
        for neighbor in neighbors:
            cost = current.dist + 1 - neighbor.reward#assume uniform cost across all edges
            if cost < neighbor.dist and neighbor in frontier_tracker: #found a better path to neighbor
                frontier_tracker.pop(neighbor)
            if cost < neighbor.dist and neighbor in cost_so_far:
                cost_so_far.pop(neighbor)
            if neighbor not in frontier_tracker and neighbor not in cost_so_far:
                neighbor.dist = cost
                frontier_tracker[neighbor] = cost
                priority = cost + heuristic(goal.get_xy(graph.world_size), neighbor.get_xy(graph.world_size))
                frontier.put(neighbor, priority)
                neighbor.parent = current.key
    return trace(goal, graph)
