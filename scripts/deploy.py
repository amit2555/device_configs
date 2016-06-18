#!/usr/bin/python

#-------------------------------------------------------
# Python script used to deploy configuration to devices.
# The script will -
# 1. drain traffic from the device
# 2. get a diff
# 3. apply latest config to the device 
# 4. restore traffic back onto the device
#-------------------------------------------------------

import os
import sys
import glob
import logging
from pymongo import MongoClient
from automation import tasks
from traffic_shift import TrafficShiftError,shift_away,shift_back


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Pod_Device(object):
    def __init__(self,name):
        self.name = name
        self.loopback = self._get_loopback_ip()
        self.asn = self._get_asn()

    def _get_loopback_ip(self):
        conn = MongoClient("mongodb://localhost",port=27017)
        db = conn.ipam
        query = {"hostname":self.name}

        matching = db.loopbacks.find_one(query)
        loopback_ip = matching.get("_id",None)

        conn.close()
        return loopback_ip

    def _get_asn(self):
        asn = tasks.get_bgp_asn(self.loopback)
        return asn
  
    def shift_traffic_away(self):
        response = shift_away(self.name,self.asn)
        return response

    def shift_traffic_back(self):
        response = shift_back(self.name,self.asn)
        return response

    def replace_running_config(self,filename):
        response = tasks.config_replace(self.loopback, 
			"scp://amit:amit@10.1.1.50/{}".format(os.path.abspath(filename)))
        return response

    def get_diff(self, filename):
        diffs = tasks.get_config_diff(self.loopback, "system:running-config", 
                      "scp://amit:amit@10.1.1.50/{}".format(os.path.abspath(filename)))
        logger.info("\n {}".format(diffs))
        return None


def main():

    files = glob.glob("configs/*.txt")

    # Get hostnames from config file names
    devices = [ filename.split("/")[1].rstrip(".txt") for filename in files ]

    for device,filename in zip(devices,files):
        d = Pod_Device(device)
        logger.info("\n==== {} ====".format(device.upper()))

        away_result = d.shift_traffic_away()

        if away_result:

            logger.info("\n==== Generating diff between running-config and generated config ====")
	    d.get_diff(filename)

            logger.info("\n==== Replacing running-config with generated config ====")
            deploy_result = d.replace_running_config(filename)
            logger.info("\n==== Config applied to device {} ====".format(device))

            logger.info("\n==== Restoring traffic back ====")
            back_result = d.shift_traffic_back()

            if not back_result:
                raise TrafficShiftError("Traffic shift back failed on device {}".format(device)) 
        else:
            raise TrafficShiftError("Traffic shift away failed on device {}".format(device)) 

        logger.info("==================================================")

    logger.info("All devices updated successfully.")


if __name__ == "__main__":
    main()
    
