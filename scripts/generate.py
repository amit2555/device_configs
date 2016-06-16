#!/usr/bin/python

#--------------------------------------------------
# Python script to generate configs for entire
# 2-tier Clos fabrics. The template is based on
# Cisco IOS. It uses MongoDB as IPAM database.
#
# Usage:
#    generate.py -p <pod_name> -y <site_yaml>
#
#--------------------------------------------------

import sys
import argparse
import jinja2
import yaml
import netaddr
import logging
from pymongo import MongoClient
from collections import defaultdict


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Pod_Device(object):
    def __init__(self,device,pod):
        self.device = device 
        self.pod = pod

    def allocate_ip(self):
        self._create_hostname()
        self._get_db_connection()
        if self.device.startswith("leaf"):
            self._allocate_interconnects()
        self._allocate_loopback()
        self._allocate_oob()
        return None

    def generate_configs(self):
        #self._create_hostname()
        self._assign_interconnects()
        self._assign_loopback()
        self._assign_oob()

        if self.device.startswith("leaf"):
            self._leaf_neighbor_interconnects()

        self._get_ibgp_neighbors()
        self._close_db_connection()
        return None

    def _get_db_connection(self):
        self.conn = MongoClient("mongodb://localhost",port=27017)
        self.db = self.conn.ipam
        return self.db            

    def _close_db_connection(self):
       self.conn.close()

    def _create_hostname(self):
        self.hostname = self.pod.site[0] + self.pod.site[-1] + '-' + self.pod.name + '-' + self.device
        return None
                
    def _assign_interconnects(self):
        leaf_uplinks = ['GigabitEthernet1/0','GigabitEthernet2/0']
        spine_downlinks = ['GigabitEthernet1/0','GigabitEthernet2/0','GigabitEthernet3/0','GigabitEthernet4/0']
        query = {"a_end": self.device}

        cursor = self.db.interconnects.find(query) 
        ip_addresses = list()
        descriptions = list()
        for entry in cursor:
            # Assign IP only if one of ends is a Spine device
            if entry["a_end"].startswith("spine") or entry["b_end"].startswith("spine"):
                ip_addresses.append(entry["_id"])
                descriptions.append(entry["description"])
        if self.device.startswith("leaf"):
            self.intf_ip_mapping = zip(leaf_uplinks,ip_addresses,descriptions)
        else:
            self.intf_ip_mapping = zip(spine_downlinks,ip_addresses,descriptions)
        return None


    def _allocate_interconnects(self):
        for spine in self.pod.spines:
            prefix = self.pod.interconnect_subnets.pop(0)
            ip_addresses = list(netaddr.IPNetwork(prefix))
            self.db.interconnects.update({"_id":str(ip_addresses[0])},{"_id":str(ip_addresses[0]),"pod":self.pod.name,"site":self.pod.site,"a_end":self.device,"b_end":spine,"description":self.device + " to " + spine}, upsert=True)
            self.db.interconnects.update({"_id":str(ip_addresses[1])},{"_id":str(ip_addresses[1]),"pod":self.pod.name,"site":self.pod.site,"a_end":spine,"b_end":self.device,"description":spine + " to " + self.device}, upsert=True)

        return None


    def _leaf_neighbor_interconnects(self):
        self.neighbors = defaultdict(dict)
        leaf_downlinks = {3:'GigabitEthernet3/0',4:'GigabitEthernet4/0',5:'GigabitEthernet5/0',6:'GigabitEthernet6/0'}

        if self.pod.vars['bgp']['neighbors']:
            for neighbor,attributes in self.pod.vars['bgp']['neighbors'].iteritems():

                #Convert [1,2] to ['leaf1','leaf2']
                leafs = [ 'leaf' + str(leaf_node) for leaf_node in attributes['leaf_nodes'] ]

                #Check if the device is listed in leafs
                if self.device in leafs:    
                    prefix = self.pod.interconnect_subnets.pop(-1)
                    ip_addresses = list(netaddr.IPNetwork(prefix))
                    self.db.interconnects.update({"_id":str(ip_addresses[0])},{"_id":str(ip_addresses[0]),"pod":self.pod.name,"site":self.pod.site,"a_end":self.device,"b_end":neighbor,"description":self.device + " to " + neighbor}, upsert=True)
                    self.db.interconnects.update({"_id":str(ip_addresses[1])},{"_id":str(ip_addresses[1]),"pod":self.pod.name,"site":self.pod.site,"a_end":neighbor,"b_end":self.device,"description":neighbor + " to " + self.device}, upsert=True)

                    lag = attributes['lag']         
                    asn = attributes['asn']         
                    lag_members = list()

                    for interface in attributes['interfaces']:
                        member = leaf_downlinks[interface]                       
                        description = self.device + " to " + neighbor 
                        lag_members.append((member,description)) 
                    self.neighbors[neighbor] = { 'lag': lag, 'lag_members': lag_members, 'lag_ip': str(ip_addresses[0]),'asn':asn, 'remote_ip': str(ip_addresses[1])}
         
        return None

 
    def _allocate_loopback(self):
        loopback_addresses = list(netaddr.IPNetwork(self.pod.loopback_subnets.pop(0)))   
        self.db.loopbacks.update({"_id":str(loopback_addresses[0])},{"_id":str(loopback_addresses[0]),"pod":self.pod.name,"site":self.pod.site,"device_name":self.device,"family":"ios","hostname":self.hostname}, upsert=True)
        return None

    def _assign_loopback(self):
        query = {'device_name': self.device}
        loopback = self.db.loopbacks.find_one(query)
        self.loopback = loopback['_id']
        return None

    def _allocate_oob(self):
        oob_addresses = list(netaddr.IPNetwork(self.pod.oob_subnets.pop(0)))   
        self.db.oobs.update({"_id":str(oob_addresses[0])},
			    {"_id":str(oob_addresses[0]),
			     "pod":self.pod.name,
			     "site":self.pod.site,
			     "device_name":self.device,
			     "family":"ios",
			     "hostname":self.hostname}, 
			     upsert=True)
        return None

    def _assign_oob(self):
        query = {'device_name': self.device}
        oob = self.db.oobs.find_one(query)
        self.oob = oob['_id']
        return None

    def _get_ibgp_neighbors(self):
        self.ibgp = dict()

        for device in self.pod.devices:
            if self.device != device:
                query = {'device_name':device}
                device_ip = self.db.loopbacks.find_one(query)
                self.ibgp.update({device_ip['_id']:device})

        return None


class Pod(object):
    def __init__(self,name,loopback_prefix,interconnect_prefix,oob_prefix):
        self.name = name
        self.loopback_prefix = loopback_prefix
        self.interconnect_prefix = interconnect_prefix
        self.oob_prefix = oob_prefix
        self._interconnect_subnets()
        self._loopback_subnets()
        self._oob_subnets()

    def _interconnect_subnets(self):
        # All /31 subnets for interconnects
        self.interconnect_subnets = list(netaddr.IPNetwork(self.interconnect_prefix).subnet(31))

    def _loopback_subnets(self):
        # All /32 subnets for loopback
        self.loopback_subnets = list(netaddr.IPNetwork(self.loopback_prefix).subnet(32))

    def _oob_subnets(self):
        # All /32 subnets for oob
        self.oob_subnets = list(netaddr.IPNetwork(self.oob_prefix).subnet(32))
        # Remove Network(first) and Broadcast(last) addresses
        self.oob_subnets.pop(0)
        self.oob_subnets.pop()
        return None

def parse_arguments(args):
    parser = argparse.ArgumentParser()
    parser.add_argument('-p','--pod_name',required=True,help='Pod name eg. pod1')
    parser.add_argument('-y','--yaml_file',required=True,help='Variables filename')
    results = parser.parse_args(args)
    return results    


def main():
    args = parse_arguments(sys.argv[1:])
    yaml_file = args.yaml_file
    pod_name = args.pod_name.lower()

    vars = yaml.load(open('yaml_configs/'+ yaml_file).read())
    template = jinja2.Template(open('templates/site.tmpl').read())

    if vars['pods']:
        globals = vars['globals']
        pod_vars = vars['pods'][pod_name]

        leafs = [ 'leaf' + str(leaf_id) for leaf_id in range(1, pod_vars['leaf_count'] + 1) ]
        spines = [ 'spine' + str(spine_id) for spine_id in range(1, pod_vars['spine_count'] + 1) ]
        
        pod = Pod(pod_name,pod_vars['loopback_prefix'],
			   pod_vars['interconnect_prefix'],
			   pod_vars['oob_prefix']) 
        pod.site = globals['site']
        pod.spines = spines 
        pod.leafs = leafs         # "leafs" is deliberatly spelled this way
        pod.devices = pod.leafs + pod.spines

        pod.vars = pod_vars

        instances = list()

        for device in pod.devices:
            d = Pod_Device(device,pod)                        
            d.allocate_ip()
            instances.append(d)

        for device_instance in instances:
            device_instance.generate_configs()
            config = template.render(device = device_instance, globals = globals)
            logger.info("Config generated successfully for device {}".format(device_instance.hostname))
            with open('configs/' + device_instance.hostname + '.txt','w') as f:
                f.write(config)
        return None


if __name__ == "__main__":
    main()
