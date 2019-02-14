# Python 2 and 3 compatibility. Use Python 3 syntax
from __future__ import absolute_import, division, print_function
try:
    input = raw_input  # Python 3 style input()
except:
    pass

try:
    # Python 3 tkinter
    import tkinter.filedialog as fd
except:
    # Else Python 2 Tkinter
    import tkFileDialog as fd

# Setup imports
from grobot import GRobot
from random import randint
from path_planning import *
import path_planning
import pickle
import numpy as np
import copy
import time

class HumanAgent():

    def __init__(self, knowledge=1, optimal=True):
        # Initialise globals
        self.robot = GRobot("HumanAgent", colour="yellow")
        self.heading = 90 #0=forward, 90 = right, 180 = down, 270 = left
        self.path = []
        self.knowledge = knowledge
        self.optimal = optimal
        self.optimality_constant = 0.2
        self.reward_removal_constant = 0.5
        self.real_graph = None

        # get file name from simulator
        file_name = self.robot.get_cur_file()

        # import world
        self.world = pickle.load(open(file_name, 'rb'))
        self.world_size = len(self.world)

        # Erase hazards and (some) rewards from memory
        self.reward_states = []
        self.empty_states = []
        for i in range(0, self.world_size):
            for j in range(0, self.world_size):
                cell_type = self.world[i][j]
                if cell_type == "Hazard":
                    # remove all hazard knowledge
                    self.world[i][j] = None
                elif cell_type == "Reward":
                    if self.knowledge == 0 and np.random.uniform() >= self.reward_removal_constant:
                        # remove rewards randomly
                        self.world[i][j] = None
                    else:
                        # save reward state for goal generation
                        self.reward_states.append((i,j))
                elif cell_type == None:
                    # save empy states for start generation
                    self.empty_states.append((i,j))

    def sendGraph(self):
        serialized_graph = pickle.dumps(copy.deepcopy(self.real_graph), protocol=2)
        self.robot._send(serialized_graph, "byte")

    def run(self):
        goal = self.plan()
        self.move(goal)

    def plan(self):
        # generate graph world
        self.real_graph = Graph()
        self.real_graph.setup_graph(self.world, self.world_size)
        self.sendGraph()

        # generate start and goal states
        start_x, start_y = self.empty_states[randint(0, len(self.empty_states)-1)]
        goal_x, goal_y = self.reward_states[randint(0, len(self.reward_states)-1)]

        # build start info
        xy = (start_x, start_y)
        start_key = self.real_graph.get_key(xy)
        start = self.real_graph.get_vertex(start_key)
        print("Start: " + str(xy))

        # build goal info
        xy = (goal_x, goal_y)
        goal_key = self.real_graph.get_key(xy)
        goal = self.real_graph.get_vertex(goal_key)
        print("Goal: " + str(xy))

        # recreate robot with 
        self.robot = GRobot("HumanAgent", posx=start_x, posy=start_y, colour="yellow")

        #path plan with A*
        self.path = a_star(self.real_graph, start, goal)

        return goal

    def move(self, goal):
        i = 1
        goal_pose = goal.get_xy(self.world_size)
        while (self.robot.posx, self.robot.posy) != goal_pose:
            
            # check sim to find allowance to move
            can_move = False
            while not can_move:
                can_move = self.robot.can_human_move()
                if not can_move:
                    print("Waiting to move...")
                    time.sleep(1)

            valid, changed = self.robot.look()
            
            # found new world knowledge
            if changed:
                print("New world knowledge!")
                # update world knowledge
                self.real_graph = self.getHumanGraph()

                # reset position and find new path
                i = 0
                xy = (self.robot.posx, self.robot.posy)
                start = self.real_graph.get_vertex(self.real_graph.get_key(xy))
                start.parent = -1
                self.path = a_star(self.real_graph, start, goal)

            # if making a random move, rerun A*
            if self.optimal == False and np.random.uniform() <= self.optimality_constant:
                print("Random Move")
                coord = (self.robot.posx + np.random.randint(-1, 1), self.robot.posy + np.random.randint(-1, 1))
                self.move_helper(coord)

                # reset position and find new path
                i = 0
                xy = (self.robot.posx, self.robot.posy)
                start = self.real_graph.get_vertex(self.real_graph.get_key(xy))
                start.parent = -1
                self.path = a_star(self.real_graph, start, goal)

            else:
                coord = self.path[i]
                self.move_helper(coord)
                i += 1

    def getHumanGraph(self):
        sys.modules['path_planning'] = path_planning
        return pickle.loads(self.robot.get_cur_human_graph())

    def move_helper(self, coord):
        (x, y) = coord
        direction = (x - self.robot.posx, y - self.robot.posy)
        print("Current, Intended:", (self.robot.posx, self.robot.posy), (x, y))

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


if __name__ == "__main__":
    # sys.argv: 0=name, 1=knowledge, 2=optimal
    # Agent = HumanAgent(sys.argv[1], sys.argv[2])
    Agent = HumanAgent()
    Agent.run()
