#!/usr/bin/python

#------------------------------------------------------
# These are unit test like checks/tests that will ensure
# - devices are in healthy state
# - configs are generated correctly
# - all OSPF neighbors are Up
# - all BGP neighbors are Up
#------------------------------------------------------

import re
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

@pytest.fixture(scope='session')
def filenames():
    files = glob.glob("../configs/*.txt")
    return files


@pytest.mark.parametrize("device", 
			  loopbacks())
def test_bgp_neighbors_configured(device):
    """Check BGP neighbors more than (total # of leafs+spines - 1) """
    assert len(tasks.get_bgp_neighbors(device).keys()) >= 5 

@pytest.mark.parametrize("device", 
			  loopbacks())
def test_device_traffic_more_than_threshold(device):
    """Check device is taking traffic """
    pytest.skip("WIP")
    assert tasks.get_device_traffic(device) > 50

@pytest.mark.parametrize("device", 
			  loopbacks())
def test_bgp_neighbors_state_is_established(device):
    """Check all IBGP neighbors are in Established state """
    for neighbor in tasks.get_bgp_neighbors_state(device):
        if neighbor['peergroup'] == 'IBGP':
            assert neighbor['state'] == 'Established'

@pytest.mark.parametrize("filename",
			  filenames())
def test_check_bgp_neighbors_in_configs_generated(filename):
    """Check BGP neighbors configured in config """
   
    with open(filename) as f:
        config = f.read()

    # Identifying IBGP peers in generated config
    PEER_RE = re.compile(r'neighbor (?P<peer>\S+) peer-group IBGP')
    peers_in_config = { peer.group('peer') for peer in re.finditer(PEER_RE,config) }

    #Assert number of IBGP peers on device = sum(leafs+spines-1)
    assert len(peers_in_config) == 5

@pytest.mark.parametrize("device",
			 loopbacks())
def test_check_ospf_neighbors_count(device):
    """Test OSPF neighbors count is 2(spines) or 4(leafs) """
    assert len(tasks.get_ospf_neighbors(device)) == 2 or 4

@pytest.mark.parametrize("device",
			 loopbacks())
def test_check_ospf_neighbors_state(device):
    """Test OSPF neighbors state is FULL """
    for neighbor in tasks.get_ospf_neighbors(device):
        assert neighbor["state"] == "FULL"

