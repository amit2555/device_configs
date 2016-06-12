#!/usr/bin/python

#------------------------------------------------------
# These are unit test like checks/tests that will ensure
# - devices are in healthy state
# - configs are generated correctly
# - all OSPF neighbors are Up
# - all BGP neighbors are Up
#------------------------------------------------------

import glob
import pytest
from automation import tasks
from pymongo import MongoClient


@pytest.fixture(scope='session')
def loopbacks():
    files = glob.glob("../configs/*.txt")
    devices = [ filename.split("/")[2].rstrip(".txt") for filename in files ]

    conn = MongoClient("mongodb://localhost",port=27017)
    db = conn.ipam
    loopback_ips = list()
   
    for device in devices:
        query = {"hostname": device}
        loopback_ips.append(db.loopbacks.find_one(query)["_id"])

    conn.close()
    return loopback_ips


@pytest.mark.parametrize("device", loopbacks())
def test_bgp_neighbors_configured_atleast_5(device):
    """Check BGP neighbors more than (total # of leafs+spines - 1) """
    assert len(tasks.get_bgp_neighbors(device).keys()) >= 5 

@pytest.mark.parametrize("device", loopbacks())
def test_device_traffic_more_than_threshold(device):
    """Check device is taking traffic """
    assert tasks.get_device_traffic(device) > 50


