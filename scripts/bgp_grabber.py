#!/usr/bin/python

#-------------------------------------------------------
# Python script used for unit testing in Jenkins.
# The script will identify IBGP neighbors from the config
# files generated and compare with IBGP neighbors on live
# devices.
#-------------------------------------------------------

import re
import glob
import sys
import logging
from pymongo import MongoClient
from automation import tasks


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Pod_Device(object):
    def __init__(self,name):
        self.name = name

    def get_peers_from_config(self,filename):

        with open(filename) as f:
            config = f.read()

        # Identifying IBGP peers in generated config
        PEER_RE = re.compile(r'neighbor (?P<peer>\S+) peer-group IBGP')

        self.peers_in_config = { peer.group('peer') for peer in re.finditer(PEER_RE,config) }
        return None

    def get_peers_from_device(self):
        conn = MongoClient("mongodb://localhost",port=27017)
        db = conn.ipam
        query = {"hostname":self.name}

        matching = db.loopbacks.find_one(query)
        if matching:
            loopback_ip = matching["_id"]
            self.peers_on_device = [ neighbor for neighbor in tasks.get_bgp_neighbors(loopback_ip) ]
           
        return None 


def main():

    files = glob.glob("configs/*.txt")

    # Get hostname from config file name
    devices = [ filename.split("/")[1].rstrip(".txt") for filename in files ]

    for device,filename in zip(devices,files):
        d = Pod_Device(device)
        d.get_peers_from_config(filename)
        d.get_peers_from_device()
  
        # Comparing IBGP peers in config with BGP peers configured on device  
        if len(d.peers_in_config) > 0:
            if len(d.peers_on_device) < len(d.peers_in_config):
                sys.exit(-1)
            else:
                logger.info("Device {} : OK".format(device))
        else:
            sys.exit(-1) 
            

if __name__ == "__main__":
    main()


