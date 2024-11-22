#!/usr/bin/env python
"""List Protection Jobs for python"""

# usage: ./jobList.py -v mycluster -u myuser -d mydomain.net [ -s defaultStorageDomain ] [ -e vmware ]

# import pyhesity wrapper module
from pyhesity import *
import json

# command line arguments
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('-v', '--vip', type=str, default='helios.cohesity.com')
parser.add_argument('-u', '--username', type=str, default='helios')
parser.add_argument('-d', '--domain', type=str, default='local')  # (optional) domain - defaults to local
parser.add_argument('-c', '--clustername', action='append', type=str, default=None)
parser.add_argument('-cl', '--clusters', type=str, default=None)
parser.add_argument('-mcm', '--mcm', action='store_true')
parser.add_argument('-i', '--useApiKey', action='store_true')
parser.add_argument('-pwd', '--password', type=str, default=None)
parser.add_argument('-np', '--noprompt', action='store_true')
parser.add_argument('-e', '--environment', type=str, default=None)


args = parser.parse_args()

vip = args.vip
username = args.username
domain = args.domain
clustername = args.clustername
clusterlist = args.clusters
mcm = args.mcm
useApiKey = args.useApiKey
password = args.password
noprompt = args.noprompt
environment = args.environment

# gather list function
def gatherList(param=None, filename=None, name='items', required=True):
    items = []
    if param is not None:
        for item in param:
            items.append(item)
    if filename is not None:
        f = open(filename, 'r')
        items += [s.strip() for s in f.readlines() if s.strip() != '']
        f.close()
    if required is True and len(items) == 0:
        print('no %s specified' % name)
        exit()
    return items


# get list of clusters
clusternames = gatherList(clustername, clusterlist, name='clusters', required=True)

# authentication =========================================================
# demand clustername if connecting to helios or mcm
if (mcm or vip.lower() == 'helios.cohesity.com') and clusternames is None:
    print('-c, --clustername is required when connecting to Helios or MCM')
    exit(1)

# authenticate
apiauth(vip=vip, username=username, domain=domain, password=password, useApiKey=useApiKey, helios=mcm, prompt=(not noprompt))

# exit if not authenticated
if apiconnected() is False:
    print('authentication failed')
    exit(1)

# if connected to helios or mcm, select access cluster
for cluster in clusternames:
    if mcm or vip.lower() == 'helios.cohesity.com':
    
       heliosCluster(cluster)
       print (cluster)
    if LAST_API_ERROR() != 'OK':
        exit(1)
# end authentication =====================================================

jobs = api('get', 'data-protect/protection-groups?isActive=True', v=2)
jobs = list(jobs.values())

for job in jobs:
    for item in job:
        if environment is None or item['environment'][1:].lower() == environment.lower():
            #print(item['name'])
                if item['environment'] == 'kVMware':
                    vmparams = item['vmwareParams']['objects']
                    #vmparams = list(vmparams.values())
                    vmautoprotecttotal = len(vmparams)
                    #print(vmautoprotecttotal)
                    print('%s (%s) (%s %s) (%s %s)' % (item['name'], item['environment'], 'Objects:', item['numProtectedObjects'],'Auto Protected:',vmautoprotecttotal))
                else:
                    print('%s (%s) (%s %s)' % (item['name'],item['environment'], 'Objects:', item['numProtectedObjects']))
