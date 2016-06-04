#!/usr/bin/python

#-------------------------------------------------------
# Python script used for traffic shift away and back 
# from device.
# The script will apply/remove max-metric on OSPF and 
# MAINTENANCE route-map on IBGP peer-group.
#-------------------------------------------------------

import logging
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
    if matching:
        ip = matching["_id"]

    conn.close()
    return ip


def shift_away(device,asn):
    loopback_ip = _get_loopback(device)

    commands = ['router ospf 1',
                'max-metric router-lsa external-lsa include-stub summary-lsa'] 

    commands.append("router bgp {}".format(asn))
    commands.append("neighbor IBGP route-map MAINTENANCE in")
    commands.append("neighbor IBGP route-map MAINTENANCE out")
    commands.append("do copy running-config startup-config")

    response = tasks.apply_config(loopback_ip,commands)

    if not response:
        return False

    logger.info("Traffic has been drained from device {}.".format(device))
    return True

 
def shift_back(device,asn):
    loopback_ip = _get_loopback(device)

    commands = ['router ospf 1',
                'no max-metric router-lsa'] 

    commands.append("router bgp {}".format(asn))
    commands.append("no neighbor IBGP route-map MAINTENANCE in")
    commands.append("no neighbor IBGP route-map MAINTENANCE out")
    commands.append("do copy running-config startup-config")

    response = tasks.apply_config(loopback_ip,commands)

    if not response:
        return False

    logger.info("Traffic has been restored to device {}.".format(device))
    return True
 
