#!/usr/bin/env python
"""Get Postgres DB Details Per Cluster"""

### import pyhesity wrapper module
from pyhesity import *
from datetime import datetime

### command line arguments
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('-v', '--vip', type=str, default='helios.cohesity.com')
parser.add_argument('-u', '--username', type=str, default='helios')
parser.add_argument('-d', '--domain', type=str, default='local')
parser.add_argument('-c', '--clustername', nargs='+', type=str, default=None)
parser.add_argument('-cl', '--clusters', type=str, default=None)
parser.add_argument('-mcm', '--mcm', action='store_true')
parser.add_argument('-i', '--useApiKey', action='store_true')
parser.add_argument('-pwd', '--password', type=str, default=None)
parser.add_argument('-np', '--noprompt', action='store_true')
parser.add_argument('-m', '--mfacode', type=str, default=None)
parser.add_argument('-e', '--emailmfacode', action='store_true')

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
mfacode = args.mfacode
emailmfacode = args.emailmfacode

# gather server list
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

#Date
now = datetime.now()
dateString = now.strftime("%Y-%m-%d")

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

# end authentication =====================================================

if clusternames[0] == "all":
    clusters = api('get', 'cluster-mgmt/info',mcmv2=True)
    clusters = clusters['cohesityClusters']
    clusters = [c for c in clusters if c['isConnectedToHelios'] == True]

    clusternames = []

    for cluster in clusters:
        clustername = cluster['clusterName']
        clusternames.append(clustername)

report = []

for cluster in clusternames:
    if mcm or vip.lower() == 'helios.cohesity.com':
    # if connected to helios or mcm, select access cluster
       heliosCluster(cluster)
       print (cluster)
    if LAST_API_ERROR() != 'OK':
        exit(1)

    firewallinfo = api('get', '/nexus/firewall/list')

    for profile in firewallinfo['entry']['attachments']:
        if profile['profile'] == "Reporting database":
            if profile['action'] == "allow":
                print("Reporting Database firewall already allowed on cluster %s" % cluster)
                continue
            profile['action'] = "allow"
            firewallinfo['updateAttachment'] = True
            print("Enabling Reporting Database Firewall (Allow)")
            result = api('put', '/nexus/v1/firewall/update', firewallinfo)
          
