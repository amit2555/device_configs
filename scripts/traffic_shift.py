#!/usr/bin/python

#-------------------------------------------------------
# Python script used for traffic shift away and back 
# from device.
# The script will apply/remove max-metric on OSPF and 
# MAINTENANCE route-map on peer-groups to external
# neighbors.
#-------------------------------------------------------

import logging
import time
from pymongo import MongoClient
from automation import tasks


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TrafficShiftError(Exception):
    def __init__(self, msg):
        super(TrafficShiftError, self).__init__(msg)
        self.message = msg


def _get_loopback(device):
    conn = MongoClient("mongodb://localhost",port=27017)
    db = conn.ipam
    query = {"hostname":device}

    matching = db.loopbacks.find_one(query)
    ip = matching["_id"]

    conn.close()
    return ip

def _get_commands(loopback_ip,asn,state=None):

    commands = list()
    commands = ["router ospf 1"]

    if state == "away":
        commands.append("max-metric router-lsa external-lsa include-stub summary-lsa")
    elif state == "back":
        commands.append("no max-metric router-lsa")

    commands.append("router bgp {}".format(asn))

    #Get BGP peer-groups from device
    peergroups = tasks.get_bgp_peergroups(loopback_ip)

    for peergroup in peergroups:
        if peergroup != "IBGP":
            if state == "away":
                commands.append("neighbor {} route-map MAINTENANCE in".format(peergroup))
                commands.append("neighbor {} route-map MAINTENANCE out".format(peergroup))
            elif state == "back":
                commands.append("no neighbor {} route-map MAINTENANCE in".format(peergroup))
                commands.append("no neighbor {} route-map MAINTENANCE out".format(peergroup))
 
    commands.append("do copy running-config startup-config")
    return commands


def shift_away(device,asn):
    """
    Applies max-metric to OSPF and MAINTENANCE route-map to BGP.
    """

    loopback_ip = _get_loopback(device)
    commands = _get_commands(loopback_ip,asn,state="away")

    tasks.apply_config(loopback_ip,commands)
    logger.info("Shift away config applied to device {}".format(device))

    threshold = 100
    count = 1
 
    while count <= 3:
        time.sleep(5)
        #Get device traffic levels
        pps = tasks.get_device_traffic(loopback_ip)

        if pps > threshold:
            logger.info("## Attempt: {} - Traffic NOT drained from device {} ##\n".format(count,device))
            count += 1
        else:
    	    logger.info("Traffic has been drained from device {}".format(device))
            return True

    logger.info("Traffic not drained from device {} - currently {} packets/sec".format(device,pps))
    return False

 
def shift_back(device,asn):
    """
    Removes max-metric from OSPF and MAINTENANCE route-map from BGP.
    """

    loopback_ip = _get_loopback(device)
    commands = _get_commands(loopback_ip,asn,state="back")

    tasks.apply_config(loopback_ip,commands)
    logger.info("Shift back config applied to device {}".format(device))

    threshold = 100
    count = 1

    while count <= 3:
        time.sleep(5)
        pps = tasks.get_device_traffic(loopback_ip)

        if pps < threshold:
            logger.info("## Attempt: {} - Traffic not restored to device {} ##\n".format(count, device))
            count += 1
        else:
            logger.info("Traffic restored to device {}".format(device))
            return True
   
    logger.info("Traffic not restored to device {} - currently {} packets/sec".format(device,pps))
    return False
 
