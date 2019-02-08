#! /usr/bin/python3
#  Copyright 2015 Mick Walters <Mick Walters> M.L.Walters@herts.ac.uk
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
# Version 0.1 Sept 2015
# Version 1.0 Nov 2015
# Version 1.1 Jan 2016 - Fixed socket bug, contributed by Jamie Hollaway
#

# Python 2 and 3 compatibility
from __future__ import absolute_import, division, print_function
try:
      input=raw_input # Python 3 style input()
except:
      pass

import socket
from time import sleep
import atexit
import sys

hostname="localhost" # Set to Tutors PC IP address to shown on Projector etc?
port = 9001          # Possibility of various clients running own robots
                     # in the simulator in future?


class GRobot():

    def __init__(self, rname="anon", posx=1, posy=1, colour="red", rshape="None"):
        self.rname=rname
        self.posx=posx
        self.posy=posy
        self.colour=colour
        self.rshape=rshape
        msg = "N "+str(rname)+" "+str(posx)+" "+str(posy)+" "+colour+" "+rshape
        self._send(msg)

    def _send(self, msg):
        # Send message and get respose from Simulator
        try:
            # The simulator IP is on localhost, maybe to remote PC later?
            if type(msg)==str:
                self.tcpSock=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                # Repeated runs can sometimes hang up here, because
                # the socket hasn't been released by the kernel
                # So this tells the socket to reuse the old one if it exists
                self.tcpSock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.tcpSock.connect ((hostname, port))# (hostname,portno))
                self.tcpSock.send(msg.encode('utf-8'))

                tries=1
                rmsg=""
                while rmsg=="" and tries > 0:
                    rmsg = rmsg + self.tcpSock.recv(100).decode('utf-8')
                    if rmsg!="":tries -= 1
                self.tcpSock.close()
            else:
                rmsg = "msg type error"
            if rmsg == "": rmsg = "Warning: Receieved Data error"
        except:
            print("Cannot connect to simulator")
            print("Please make sure Simulator is running")
            exit()

            

        return rmsg

    def init(self, xpos=1, ypos=1):
        self.xpos=xpos
        self.ypos=ypos
        return self._send("N " + self.rname+" "+str(self.xpos)+" "+str(self.ypos)+" "+self.colour+" "+ self.rshape)

    def right(self):
        return self._send("R "+ self.rname+" ")

    def left(self):
        return self._send("L " + self.rname+" ")

    def look(self):
        msg = self._send("S " + self.rname)
        return eval(msg)

    def forward(self):
        return self._send("F " + self.rname)

    def getFile(self):
        msg = self._send("G " + self.rname)
        return msg.encode("utf-8")

    def modifyCellLook(self, x, y, cell_type):
        return self._send("M " + self.rname + " " + str(x) + " " + str(y) + " " + cell_type)



def demo():
    # print() used to show return value from method/function calls
    fred=GRobot("fred", 1, 1)
    bill=GRobot("bill", 1, 1, "green")
    print("Fred forward", fred.forward())
    print("Bill forward",bill.forward())
    print("Fred right", fred.right())
    print("Bill right", bill.right())
    count = 12
    while count > 0:
        print("Fred looks at:", fred.look())
        print("Fred forward",fred.forward())
        print("Bill looks at:", bill.look())
        print ("Bill forward",bill.forward())
        count -= 1
    print("Fred looks forward at", fred.look()[2])
    print("Bill looks forward at", bill.look()[2])

def demo2():
    arthur=GRobot("arthur", 1, 4, "blue")
    ted=GRobot("ted", 4, 4, "yellow")
    print("Arthur forward", arthur.forward())
    print("Ted forward",ted.forward())
    print("Arthur right", arthur.right())
    print("Ted right", ted.right())
    count = 12
    while count > 0:
        print("Arthur looks at: ", arthur.look())
        print("Arthur forward",arthur.forward())
        print("Ted looks at:", ted.look())
        print ("Ted forward",ted.forward())
        count -= 1
    print("Arthur looks at:", arthur.look())
    print("ted looks at:", ted.look())

if __name__ == "__main__":
    demo()
    print("Finished")

