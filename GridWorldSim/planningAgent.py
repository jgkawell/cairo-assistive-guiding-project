# Python 2 and 3 compatibility. Use Python 3 syntax
from __future__ import absolute_import, division, print_function
try:
    input = raw_input  # Python 3 style input()
except:
    pass

# Setup imports
from grobot import GRobot
from random import randint
from path_planning import Graph, PlanningPath
from timeit import default_timer as timer
import path_planning
import pickle
import time
import copy
import sys


class PlanningAgent():

    def __init__(self, abstract=True, probabilistic=False):
        # Initialise globals
        self.robot = GRobot("PlanningAgent", colour="purple")

        # human agent variables
        self.human_graph = None
        self.human_position = 1
        self.human_name = "HumanAgent"

        # abstraction/optimization variables
        self.goal_keys = []
        self.previous_paths = []
        self.show_abstraction = False
        self.desired_path = PlanningPath()
        self.desired_path_abstract = PlanningPath()
        self.mitigation_path = PlanningPath()
        self.mitigation_path_pos = 0
        self.heading = 90
        self.max_level = 5 #Equivalent to no abstraction

        # adjustable parameters
        self.cost_limit = 0.5
        self.num_samples = 3
        self.sample_size = 20
        self.robot_speed = 10
        self.human_optimality_prob = 0.8
        self.start_distance = 5
        self.time_limit = 20
        self.time_spent = 0

        # use for experiments
        self.abstract = abstract
        self.probabilistic = probabilistic
        
        # import world
        self.world = pickle.load(open(self.robot.get_cur_file(), 'rb'))
        self.world_size = len(self.world)

        # set up the real graph world
        self.real_graph = Graph()
        self.real_graph.setup_graph(self.world, self.world_size)

        # get reward keys
        for vertex in self.real_graph:
            if vertex.cell_type == "Reward":
                self.goal_keys.append(vertex.key)

        # get human graph from sim
        self.human_graph = self.getHumanGraph()

        # request the current human position from the sim
        self.human_position = self.real_graph.get_key(self.robot.get_xy_pos(self.human_name))

        # save empty states
        self.empty_states = []
        for i in range(0, self.world_size):
            for j in range(0, self.world_size):
                cell_type = self.world[i][j]
                if cell_type == None:
                    # save empy states for start generation
                    self.empty_states.append((i,j))

        # generate a start position distant from goal states
        start_x, start_y = 0, 0
        x2, y2 = self.real_graph.get_vertex(self.human_position).get_xy(self.world_size)
        while True:
            x1, y1 = self.empty_states[randint(0, len(self.empty_states)-1)]
            temp_path = path_planning.a_star(self.real_graph, self.real_graph.get_key((x1,y1)), [self.real_graph.get_key((x2,y2))])

            if len(temp_path.vertex_keys) <= self.start_distance:
                start_x, start_y = x1, y1
                break

        # print start info
        print("ROBOT:  Start: " + str((start_x, start_y)))
        self.robot = GRobot("PlanningAgent", posx=start_x, posy=start_y, colour="purple")

    def run(self):

        # run plan and move until human reaches a goal
        while self.human_position not in self.goal_keys:
            # check if human has exited
            if self.robot.is_exited():
                print("ROBOT: Sim exited")
                break
            
            # plan action
            found_sol = self.plan()

            if found_sol:
                # execute action
                self.move()
                self.robot.set_can_robot_move(False)

            # allow the human to move
            self.robot.set_can_human_move(True)

            time.sleep(1)
            while True:
                if self.robot.can_robot_move():
                    break
                else:
                    time.sleep(1)

            # request the current human position from the sim
            self.human_position = self.real_graph.get_key(self.robot.get_xy_pos(self.human_name))
            self.removeDesiredPathFirstEntry()

    # gets the human_graph from the sim
    def getHumanGraph(self):
        sys.modules['path_planning'] = path_planning
        return pickle.loads(self.robot.get_cur_human_graph())

    def elapseTime(self, p_num, timer_dict):
        start_time = timer()
        while (timer() - start_time < self.time_limit):
            pass
        print("Exiting elapseTime...")
        timer_dict[p_num] = timer() - start_time

    # plan a path to execute
    def plan(self):

        # if the human has diverged from the desired path, replan
        if self.human_position not in self.desired_path.vertex_keys:
            print("ROBOT:  Replanning...")

            found_sol = False
            maxed = False
            level = 0
            old_size = 0
            self.previous_paths = []
            self.time_spent = 0

            # loop plan until a solution is found or the abstraction is maxed
            while not found_sol and not maxed:


                start = timer()

                # simplify for certain level
                print("ROBOT:  Running on level: ", level)
                #TODO: Doesn't work if we don't use abstraction. Fix abstract_graph code to be the full graph if self.abstract is False
                new_size = self.simplifyWorld(old_size, level=self.max_level if not self.abstract else level)
                level += 1

                # check to see if abstraction has changed sizes; if not, stop
                if old_size == new_size:
                    maxed = True
                else:
                    old_size = new_size

                # find best solution for the current abstraction level
                # and save to self.desired_path and self.mitigation_path
                self.desired_path = PlanningPath(vertex_keys=[], distance=0, cost=0, obstacles={})
                self.mitigation_path = PlanningPath(vertex_keys=[], distance=0, cost=0, obstacles={})
                self.desired_path_abstract = PlanningPath(vertex_keys=[], distance=0, cost=0, obstacles={})
                self.mitigation_path_pos = 0
                found_sol = self.findSolution(self.human_position)

                if found_sol == -1:
                    found_sol = False
                    break

                end = timer()
                self.time_spent += end - start
                print("ROBOT:  Took: ", end - start)

                if self.time_spent > self.time_limit:
                    print("ROBOT: Ran out of time...")
                    break

            return found_sol
        else:
            return True

    def findSolution(self, start_key):
            # generate the expected human path
            human_path = path_planning.a_star(self.abstract_graph, start_key, self.goal_keys)
            human_real_path = path_planning.abstract_to_full_path(self.real_graph, human_path)
            print("ROBOT:  Human path cost: ", human_real_path.total_cost)

            if human_real_path.total_cost >= self.cost_limit:
                # loop until a solution is found or the sampling limit is hit
                found_sol = False
                for sample_num in range(self.num_samples):
                    print("ROBOT:  Sample number: ", sample_num+1)
                
                    start = timer()
                    # find a sampling of paths that fits constraints (cost_limit)
                    current_cost = self.robot.get_human_damage()
                    sample_paths = path_planning.find_paths(self.abstract_graph, start_key, self.goal_keys, self.sample_size, current_cost, self.cost_limit, self.time_spent, self.time_limit)
                    for sample_path in sample_paths:
                        if sample_path not in self.previous_paths:
                            self.previous_paths.append(sample_path)
                        else:
                            sample_paths.remove(sample_path)
                    print("ROBOT: Finished sampling...")
                    end = timer()
                    self.time_spent += end - start
                    if self.time_spent > self.time_limit:
                        print("ROBOT: Ran out of time...")
                        return False

                    # sort list by total cost
                    sample_paths.sort(key=lambda x: x.total_cost, reverse=False)

                    for sample_path in sample_paths:
                        start = timer()

                        # find the locations for obstacles for the sampled path
                        obstacle_list = []
                        copy_graph = copy.deepcopy(self.abstract_graph)
                        copy_path = copy.deepcopy(sample_path)
                        obstacle_list = self.findObstaclePlacements(copy_graph, copy_path, human_path)

                        # check if there is a solvable mitigation path for obstacle list                
                        if len(obstacle_list) > 0:
                            # find the mitigation path for the obstacle list
                            found_sol = self.planMitigationPath(obstacle_list, start_key)

                            end = timer()
                            self.time_spent += end - start
                            if self.time_spent > self.time_limit:
                                print("ROBOT: Ran out of time...")
                                return False

                            # if valid, generate the desired path for the human given obstacles
                            if found_sol:
                                # get real graph representation of path to set desired_path
                                full_path = path_planning.abstract_to_full_path(self.real_graph, sample_path)
                                self.desired_path = copy.deepcopy(full_path)
                                self.desired_path_abstract = copy.deepcopy(sample_path)

                                print("ROBOT: desired_path: ", self.desired_path.vertex_keys)
                                print("ROBOT: obstacles: ", obstacle_list)
                                break

                    if not found_sol:
                        print("ROBOT:  No solution...")
                    else:
                        break
            else:
                self.desired_path = copy.deepcopy(human_real_path)
                found_sol = True

            return found_sol

    # finds the obstacles to place that forces the human on the desired path
    # recursively checks the human's predicted route after each obstacle to generate list
    def findObstaclePlacements(self, copy_graph, desired_path, human_path):
        # initialize variable for search
        obstacle_list = []
        len_path = len(desired_path.vertex_keys)
        cur_key = -1
        next_key = -1
        predicted_key = -1

        # iterate along path and generate needed obstacles based off of weighted cost
        for i in range(len_path):
            # set the current key
            cur_key = desired_path.vertex_keys[i]

            # set the next keys
            if i < len_path-1:
                next_key = desired_path.vertex_keys[i+1]
                try:
                    predicted_key = human_path.vertex_keys[i+1]
                except:
                    obstacle_list = []
                    break
            else:
                next_key = -1
                predicted_key = -1

            repeat = True
            new_obstacles = []
            while repeat:
                repeat = False
                # generate weighted cost of each neighbor
                costs = {}
                cur_neighbors = copy_graph.get_vertex(cur_key).get_neighbors().keys()
                for neighbor in cur_neighbors:

                    # make sure not to create obstacles forward along the desired path
                    if neighbor != next_key:
                        # get possible human path
                        possible_human_path = self.getHumanPathByDirection(copy_graph, cur_key, neighbor, cur_neighbors)
                        # human_path is sometimes empty list
                        if len(possible_human_path.vertex_keys) > 0:
                            full_possible_human_path = path_planning.abstract_to_full_path(self.real_graph, possible_human_path)

                            if neighbor == predicted_key:  # predicted path
                                costs[neighbor] = 1 #full_possible_human_path.total_cost #(self.human_optimality_prob) * full_possible_human_path.total_cost
                            else:  # unpredicted path
                                costs[neighbor] = 0 #full_possible_human_path.total_cost #(1 - self.human_optimality_prob) * full_possible_human_path.total_cost

                cur_path = PlanningPath()
                prev_vertex = self.abstract_graph.get_vertex(desired_path.vertex_keys[0])
                for j in range(1, i):
                    cur_vertex = self.abstract_graph.get_vertex(desired_path.vertex_keys[j])
                    info = prev_vertex.get_neighbors()[cur_vertex.key]
                    edge_dist = info[1]
                    edge_cost = info[2]
                    cur_path.add_vertex(prev_vertex.key, new_distance=edge_dist, new_cost=edge_cost)
                    prev_vertex = self.abstract_graph.get_vertex(desired_path.vertex_keys[j])

                cur_cost = cur_path.total_cost

                for key, cost in costs.items():
                    predicted_cost = cost + cur_cost
                    if predicted_cost > self.cost_limit:
                        new_obstacles.append(key)
                        self.removeEdgeFromGivenGraph(copy_graph, cur_key, key)
                        repeat = True

                # recompute the human's path with new obstacles and get new predicted_key
                human_path = path_planning.a_star(copy_graph, cur_key, self.goal_keys)
                if repeat and len(human_path.vertex_keys) > 0:
                    predicted_key = human_path.vertex_keys[1]
                else:
                    predicted_key = -1

            # add tuple of obstacles
            if len(new_obstacles) > 0:
                obstacle_list.append((cur_key, new_obstacles))

            # invalid because no valid human path
            if len(human_path.vertex_keys) < 1 and cur_key not in self.goal_keys:
                # print("ROBOT:  No human path to goal...")
                obstacle_list = []
                break

            # keep building the human path from the start for divergence checking
            if i > 0:
                human_path.vertex_keys = desired_path.vertex_keys[0:i] + human_path.vertex_keys

        return obstacle_list

    # get the human's predicted path in a certain direction
    def getHumanPathByDirection(self, graph, cur_key, next_key, neighbors):
        # create a new copy to add temporary obstacles to
        copy_graph = copy.deepcopy(graph)

        # force path_planning to generate human path in given direction to accumulate cost
        # by removing other neighbors
        for temp_key in neighbors:
            if temp_key != next_key:
                self.removeEdgeFromGivenGraph(copy_graph, cur_key, temp_key)

        # generate the cost by using a_star (human model)
        return path_planning.a_star(copy_graph, cur_key, self.goal_keys)


    # finds the point at which the human will diverge from the desired path
    # this is done by looking the the predicted human path and comparing
    # it with the desired path
    def findDivergence(self, desired_path, human_path):
        key_from = -1
        key_to = -1

        # iterate through desired path and check for divergence
        for i in range(len(desired_path)):
            key_desired = desired_path[i]
            key_human = human_path[i]

            # if the desired key doesn't match the human key then return
            # the human key and the previous human key
            if key_desired != key_human:
                key_from = human_path[i-1]
                key_to = key_human
                break

        return key_from, key_to

    def planMitigationPath(self, obstacle_list, human_position):
        found_sol = False
        robot_position = self.real_graph.get_key((self.robot.posx, self.robot.posy))

        real_copy = copy.deepcopy(self.real_graph)
        human_copy = copy.deepcopy(self.human_graph)

        # iterate through all the obstacles in the list and find the mitigation paths
        first = True
        for obstacle in obstacle_list:
            obstacle_key = obstacle[0]
            
            robot_path_to_obstacle = path_planning.a_star(real_copy, robot_position, [obstacle_key])
            human_path_to_obstacle = path_planning.a_star(human_copy, human_position, [obstacle_key])

            # check to see if the robot can get their before the human on the first obstacle
            if first:
                if robot_path_to_obstacle.distance < self.robot_speed * human_path_to_obstacle.distance:
                    first = False
                    found_sol = True
                    print("ROBOT:  Found solution!")
                else:
                    break #if human closer to first obstacle in list, this plan isn't feasible

            if found_sol:
                # remove edge from (add obstacle to) copy worlds
                for next_key in obstacle[1]:
                    self.removeEdgeFromGivenGraph(real_copy, obstacle_key, next_key)
                    self.removeEdgeFromGivenGraph(human_copy, obstacle_key, next_key)

                # add vertices to mitigation path
                for key in robot_path_to_obstacle.vertex_keys:

                    if first or robot_position != key:
                        # add vertex to path
                        self.mitigation_path.add_vertex(key, obstacles=[])
                        
                        # encode obstacle into vertex that needs obstacle placement
                        if key == obstacle_key:
                            self.mitigation_path.add_obstacle(key, pos=len(self.mitigation_path.vertex_keys)-1, obstacle=obstacle)

                # reset the robot position
                robot_position = obstacle_key

        return found_sol

    def move(self):
            # check sim to find allowance to move
            can_move = self.robot.can_robot_move()
            if not can_move:
                print("ROBOT:  Waiting...")
                time.sleep(1)
            else:
                mitigation_path_size = len(self.mitigation_path.vertex_keys)
                if mitigation_path_size > 0 and self.mitigation_path_pos < mitigation_path_size:

                    # move given number of times by speed
                    for cur_move in range(self.robot_speed):
                        # check to make sure there is a valid move
                        if self.mitigation_path_pos < mitigation_path_size:
                            # pull out vertex info (skip first location)
                            vtx_key = self.mitigation_path.vertex_keys[self.mitigation_path_pos]

                            # move to next position in path
                            print("ROBOT:  Moving to vertex: ", vtx_key)
                            self.move_helper(self.real_graph.get_vertex(vtx_key))

                            # try to place obstacle
                            new_obstacles = self.mitigation_path.obstacles[(vtx_key, self.mitigation_path_pos)]
                            for new_obstacle in new_obstacles:
                                if new_obstacle != None:
                                    cur_key = new_obstacle[0]
                                    copy_list = copy.deepcopy(new_obstacle[1])
                                    for next_key in copy_list:
                                        wait = self.will_block_human(cur_key, next_key)
                                        if wait == -1:
                                            return
                                        elif wait:
                                            print("ROBOT:  Waiting...")
                                            return

                                        print("ROBOT:  Placing obstacle...")
                                        self.removeEdgeFromRealGraph(key_a=cur_key, key_b=next_key)
                                        new_obstacle[1].remove(next_key)
                            
                            self.mitigation_path_pos += 1
                else:
                    print("ROBOT:  Nothing to do...")

    def removeDesiredPathFirstEntry(self):
        try:
            del(self.desired_path.vertex_keys[0])
        except:
            x = 0

    def will_block_human(self, cur_key, next_key):
        print("ROBOT: Checking if will block human...")

        try:
            human_pos = self.desired_path.vertex_keys.index(self.human_position)
        except:
            print("ROBOT:  Human off of desired path...")
            return -1

        for i in range(len(self.desired_path_abstract.vertex_keys)-1):
            key_a = self.desired_path_abstract.vertex_keys[i]
            key_b = self.desired_path_abstract.vertex_keys[i+1]

            if key_b == cur_key and key_a == next_key:
                vertex_pos = self.desired_path.vertex_keys.index(key_b)
                if human_pos < vertex_pos:
                    print("ROBOT: Will block human")
                    return True

        print("ROBOT: Won't block human")
        return False
        


    def move_helper(self, vertex):
        (x, y) = vertex.get_xy(self.world_size)
        direction = (x - self.robot.posx, y - self.robot.posy)

        # check for success
        msg = ""

        # heading: 0=E, 90=N, 180=W, 270=S

        # east
        if direction == (1, 0):
            if self.heading == 0: # E
                msg = self.robot.move_forward()
            elif self.heading == 90: # N
                self.robot.move_right()
                msg = self.robot.move_forward()
            elif self.heading == 180: # W
                self.robot.move_right()
                self.robot.move_right()
                msg = self.robot.move_forward()
            elif self.heading == 270: # S
                self.robot.move_left()
                msg = self.robot.move_forward()

            self.heading = 0

            if msg == "OK": self.robot.posx += 1

        # north
        elif direction == (0, 1):
            if self.heading == 0: # E
                self.robot.move_left()
                msg = self.robot.move_forward()
            elif self.heading == 90: # N
                msg = self.robot.move_forward()
            elif self.heading == 180: # W
                self.robot.move_right()
                msg = self.robot.move_forward()
            elif self.heading == 270: # S
                self.robot.move_left()
                self.robot.move_left()
                msg = self.robot.move_forward()

            self.heading = 90

            if msg == "OK": self.robot.posy += 1

        # west
        elif direction == (-1, 0):
            if self.heading == 0: # E
                self.robot.move_left()
                self.robot.move_left()
                msg = self.robot.move_forward()
            elif self.heading == 90: # N
                self.robot.move_left()
                msg = self.robot.move_forward()
            elif self.heading == 180: # W
                msg = self.robot.move_forward()
            elif self.heading == 270: # S
                self.robot.move_right()
                msg = self.robot.move_forward()

            self.heading = 180

            if msg == "OK": self.robot.posx -= 1

        # south
        elif direction == (0, -1):
            if self.heading == 0: # E
                self.robot.move_right()
                msg = self.robot.move_forward()
            elif self.heading == 90: # N
                self.robot.move_left()
                self.robot.move_left()
                msg = self.robot.move_forward()
            elif self.heading == 180: # W
                self.robot.move_left()
                msg = self.robot.move_forward()
            elif self.heading == 270: # S
                msg = self.robot.move_forward()

            self.heading = 270

            if msg == "OK": self.robot.posy -= 1


    # given two keys in the abstract graph, this removes the keys from
    # real_graph and propagates the change to the sim
    def removeEdgeFromRealGraph(self, key_a, key_b):
        # convert from abstract to real
        vertex_a_abstract = self.abstract_graph.get_vertex(key_a)
        vertex_a_real = self.real_graph.get_vertex(key_a)

        real_neighbors = vertex_a_real.get_neighbors()
        abstract_neighbors = vertex_a_abstract.get_neighbors()

        abstract_direction = 0
        for key, info in abstract_neighbors.items():
            if key == key_b:
                abstract_direction = info[0]

        real_neighbor_key = -1
        for key, info in real_neighbors.items():
            if info[0] == abstract_direction:
                real_neighbor_key = key

        # remove from local real and abstract worlds
        self.removeEdgeFromGivenGraph(self.real_graph, key_a, real_neighbor_key)
        self.removeEdgeFromGivenGraph(self.abstract_graph, key_a, key_b)

        # remove from real world in sim
        self.robot.remove_edge(key_a, real_neighbor_key)

    # bidirectional removal of and edge given the graph and keys
    def removeEdgeFromGivenGraph(self, graph, key_a, key_b):
        self.removeSingleEdgeFromGivenGraph(graph, key_a, key_b)
        self.removeSingleEdgeFromGivenGraph(graph, key_b, key_a)

    # removes the edge in a single direction
    def removeSingleEdgeFromGivenGraph(self, graph, from_key, to_key):
        # pull out neighbors of from vertex
        neighbors_from = graph.get_vertex(from_key).get_neighbors()

        # remove neighbor with matching key
        for key in neighbors_from.keys():
            if key == to_key:
                del(neighbors_from[key])
                break

    # creates the abstract representaion of the world
    # self.real_graph -> self.abstract_graph
    def simplifyWorld(self, world_size, level):
        # first level that just pulls out intersections
        if level == 0:
            # initialize empty graph
            self.abstract_graph = Graph()
            self.abstract_graph.world_size = self.world_size
            # generate the intial set of vertices
            key_list = self.generateInitialVertices()
            # generate the new edges between vertices
            self.generateEdges(key_list)

        # other levels which adds in intermediate vertices
        else:
            # set distance limit for generating new vertices
            distance_limit = 5 - level
            if distance_limit < 1:
                distance_limit = 1
            # generate new vertices between current vertices
            key_list = self.generateIntermediateVertices(distance_limit)
            # generate the new edges between vertices
            self.generateEdges(key_list)

        # show and count current vertices
        size = 0
        for vertex in self.abstract_graph:
            size += 1
            x, y = vertex.get_xy(self.world_size)
            if self.show_abstraction: self.robot.modify_cell_look(x, y, "Door")

        return size

    # add vertices with a choice-value > 2 (intersections) AND reward vertices AND human position
    def generateInitialVertices(self):
        key_list = []
        for vertex in self.real_graph:
            if len(vertex.get_neighbors()) > 2 or vertex.cell_type == "Reward" or vertex.key == self.human_position:
                # create new vertex
                copy_vertex = copy.deepcopy(vertex)

                # add to key list for edge generation
                key_list.append(vertex.key)

                # clear neighbors and add to abstract_graph
                copy_vertex.neighbor_list = {}
                self.abstract_graph.add_vertex(copy_vertex)

        return key_list

    # creates new vertices between previous vertices given a distance limit
    def generateIntermediateVertices(self, distance_limit):
        # pull out the current vertex keys to find new neighbors for
        start_vertices = []
        for key in self.abstract_graph.get_vertices():
            start_vertices.append(key)

        # keep track of new vertex keys to add
        key_list = []

        # iterate through current vertex keys to find neighbors
        for start_key in start_vertices:
            # pull out current vertex to search, copy neighbors, and clear neighbors
            start_vertex = self.abstract_graph.get_vertex(start_key)
            abstract_neighbors = copy.deepcopy(start_vertex.get_neighbors())
            start_vertex.neighbor_list = {}

            # iterate through current neighbors and find intermediate vertices along the paths between
            for end_info in abstract_neighbors.values():
                # pull out the neighbor distance
                abstract_distance = end_info[1]

                # check to see if the vertex has already been completed and if the distance is great enough
                if abstract_distance > distance_limit:
                    # pull out the neighbor direction and the real neighbors
                    abstract_direction = end_info[0]
                    real_neighbors = self.real_graph.get_vertex(start_key).get_neighbors()

                    # iterate through the real neighbors to find the new, intermediate neighbor
                    for real_key, real_info in real_neighbors.items():
                        # pull out the real direction
                        real_direction = real_info[0]

                        # check to make sure the directions match for the neighbors
                        if real_direction == abstract_direction:
                            # create new vertex
                            max_depth = int(abstract_distance/2)
                            if max_depth == 0:
                                max_depth += 1

                            new_key = self.findAbstractNeighbor(start_key, real_key, cur_depth=1, max_depth=max_depth)

                            # error check
                            if new_key == -1:
                                print("ROBOT:  ERROR")
                            else:
                                # make deep copy of the new vertex
                                new_vertex = copy.deepcopy(self.real_graph.get_vertex(new_key))

                                # add to key list for edge generation
                                key_list.append(new_key)

                                # clear neighbors and add to abstract_graph
                                new_vertex.neighbor_list = {}
                                self.abstract_graph.add_vertex(new_vertex)

        # add other vertices to key list for edge generation
        for vertex in self.abstract_graph:
            key_list.append(vertex.key)

        return key_list

    # generates the edges between vertices given a list of vertex keys
    def generateEdges(self, key_list):
        # iterate through list of keys creating edges for each one
        for cur_key in key_list:
            # copy neighbor list
            real_neighbors = self.real_graph.get_vertex(cur_key).get_neighbors()

            # iterate through real neighbors to build edges with direction, distance, and valuation
            for neighbor_key, neighbor_info in real_neighbors.items():
                # find info for new edge
                new_key, new_distance, new_cost = self.findEdgeInfo(cur_key, neighbor_key, distance=0, cost=0)

                # make sure the key is valid
                if new_key != -1:
                    # pull out the neighbor direction
                    direction = neighbor_info[0]

                    # add the edge to the abstract graph
                    self.abstract_graph.add_edge(cur_key, new_key, direction, new_distance, new_cost)

    # recurses through path from vertex with key_a to max depth or another already defined vertex (whichever comes first)
    # returns a tuple = (key, distance, value) that represents the edge
    def findEdgeInfo(self, key_a, key_b, distance, cost):
        # pull out current vertex
        cur_vertex = self.real_graph.get_vertex(key_b)

        if key_b in self.abstract_graph.get_vertices():
            # if the key is already a vertex, return the vertex or the max depth has been reached
            # with the distance and value up to that point in the recursion
            distance += 1
            cost += cur_vertex.cost
            return (key_b, distance, cost)
        else:
            # else keep recursing until either a vertex or deadend is found
            neighbors = cur_vertex.get_neighbors()
            if len(neighbors) > 1:
                for key_c in neighbors.keys():
                    # make sure not to recurse back the way we came (a -> b -> c)
                    if key_c != key_a:
                        distance += 1
                        cost += cur_vertex.cost
                        return self.findEdgeInfo(key_b, key_c, distance, cost)
            else:
                # return a bad key to signal deadend
                return (-1, 0, 0)

    # recurses to create a new neighbor at the max depth
    # given the keys to move between
    def findAbstractNeighbor(self, key_a, key_b, cur_depth, max_depth):
        if cur_depth == max_depth:
            return key_b
        else:
            # else keep recursing until either a vertex or deadend is found
            cur_vertex = self.real_graph.get_vertex(key_b)
            neighbors = cur_vertex.get_neighbors()
            if len(neighbors) > 1:
                for key_c in neighbors.keys():
                    # make sure not to recurse back the way we came (a -> b -> c)
                    if key_c != key_a:
                        cur_depth += 1
                        return self.findAbstractNeighbor(key_b, key_c, cur_depth, max_depth)
            else:
                # return a bad key to signal deadend
                return -1

if __name__ == "__main__":
    Agent = PlanningAgent()
    Agent.run()
