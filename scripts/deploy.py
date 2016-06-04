#!/usr/bin/python

#-------------------------------------------------------
# Python script used to deploy configuration to devices.
# The script will -
# 1. drain traffic from the device
# 2. apply latest config to the device 
# 3. restore traffic back onto the device
#-------------------------------------------------------

import sys
import glob
import logging
from pymongo import MongoClient
from automation import tasks
from traffic_shift import shift_away,shift_back


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Pod_Device(object):
    def __init__(self,name):
        self.name = name
        self.loopback = self._get_loopback_ip()

    def _get_loopback_ip(self):
        conn = MongoClient("mongodb://localhost",port=27017)
        db = conn.ipam
        query = {"hostname":self.name}

        matching = db.loopbacks.find_one(query)
        loopback_ip = matching.get("_id",None)

        conn.close()
        return loopback_ip

    def _get_asn(self):
        self.asn = tasks.get_bgp_asn(self.loopback)

    def shift_traffic_away(self):
        response = shift_away(self.loopback,self.asn)
        return response

    def shift_traffic_back(self):
        response = shift_back(self.loopback,self.asn)
        return response




def main():

    files = glob.glob("configs/*.txt")

    # Get hostname from config file name
    devices = [ filename.split("/")[1].rstrip(".txt") for filename in files ]

    for device,filename in zip(devices,files):
        d = Pod_Device(device)
        logger.info("Initiating shift away on device {}".format(device))
        result = d.shift_traffic_away()
        if result:
            logger.info("Applying latest config to device {}".format(device))

            logger.info("Initiating shift back on device {}".format(device))
            result = d.shift_traffic_back()
        else:
            sys.exit(-1)


if __name__ == "__main__":
    main()
    
