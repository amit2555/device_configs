#!/usr/bin/python

#-------------------------------------------------------
# Python script used for unit testing in Jenkins.
# The script will identify IBGP neighbors from the config
# files generated and compare with IBGP neighbors on live
# devices.
#-------------------------------------------------------

import re
import glob
from pymongo import MongoClient
from automation import tasks


class Pod_Device(object):
    def __init__(self,name):
        self.name = name

    def get_neighbors_from_config(self,filename):

        with open(filename) as f:
            config = f.read()

        # Identifying IBGP neighbors in generated config
        NEIGHBOR_RE = re.compile(r'neighbor (?P<neighbor>\S+) peer-group IBGP')

        self.neighbors_in_config = { neighbor.group('neighbor') for neighbor in re.finditer(NEIGHBOR_RE,config) }
        #print neighbors_in_config
        return None

    def get_neighbors_from_device(self):
        conn = MongoClient("mongodb://localhost",port=27017)
        db = conn.ipam
        query = {"device_name":self.name}

        matching = db.loopbacks.find_one(query)

        if matching:
            loopback_ip = matching["_id"]
            self.neighbors_on_device = [ neighbor for neighbor in tasks.get_bgp_neighbors(loopback_ip) ]
           
        return None 

def main():

    files = glob.glob("configs/*.txt")
    #print files

    # Get hostname from config file name
    devices = [ filename.split("/")[1].rstrip(".txt") for filename in files ]

    for device,filename in zip(devices,files):
        d = Pod_Device(device)
        d.get_neighbors_from_config(filename)
        d.get_neighbors_from_device()
   
        if len(d.neighbors_in_config) <= len(d.neighbors_from_device):
            sys.exit(-1) 
            

if __name__ == "__main__":
    main()


