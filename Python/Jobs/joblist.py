#!/usr/bin/env python
"""List Protection Jobs for python"""

# usage: ./jobList.py -v mycluster -u myuser -d mydomain.net [ -s defaultStorageDomain ] [ -e vmware ]

# import pyhesity wrapper module
from pyhesity import *

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
parser.add_argument('-s', '--storagedomain', type=str, default=None)
parser.add_argument('-e', '--environment', type=str, default=None)
parser.add_argument('-p', '--paused', action='store_true')

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
storagedomain = args.storagedomain
environment = args.environment
paused = args.paused

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

    sd = []
    if storagedomain is not None:
        sd = [s for s in api('get', 'viewBoxes') if s['name'].lower() == storagedomain.lower()]
        if len(sd) > 0:
            sd = sd[0]
        else:
            print('Storage Domain %s not found' % storagedomain)
            exit(1)

    # find protection job
    jobs = sorted(api('get', 'protectionJobs'), key=lambda j: j['name'])

    for job in jobs:
        if storagedomain is None or sd['id'] == job['viewBoxId']:
            if environment is None or job['environment'][1:].lower() == environment.lower():
                if not paused or ('isPaused' in job and job['isPaused'] is True):
                    objectcount = len(job['sourceIds'])
                    print('%s (%s) (%s %s)' % (job['name'], job['environment'][1:], 'Objects:', objectcount))
                    print ('')
