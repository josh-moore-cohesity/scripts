#!/usr/bin/env python
"""Script Overview"""

### import pyhesity wrapper module
from pyhesity import *
from datetime import datetime
import os

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
parser.add_argument('-outputpath', '--outputpath', type=str, default='./DatalockStatus')
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
outputpath = args.outputpath

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
clusternames = gatherList(clustername, clusterlist, name='clusters', required=False)

#Date
now = datetime.now()
dateString = now.strftime("%Y-%m-%d")

# authenticate
apiauth(vip=vip, username=username, domain=domain, password=password, useApiKey=useApiKey, helios=mcm, prompt=(not noprompt), mfaCode=mfacode, emailMfaCode=emailmfacode)


# exit if not authenticated
if apiconnected() is False:
    print('authentication failed')
    exit(1)

# end authentication =====================================================

#Get Clusters
if len(clusternames) > 0:
    clusternames = clusternames
else:
    clusters = api('get', 'cluster-mgmt/info',mcmv2=True)
    clusters = clusters['cohesityClusters']
    clusters = [c for c in clusters if c['isConnectedToHelios'] == True]
    clusternames = []
    for cluster in clusters:
        clusternames.append(cluster['clusterName'])

# prepare csv output
if not os.path.exists(outputpath):
    os.makedirs(outputpath)
csvFileName = os.path.join(outputpath, 'datalock-status-%s.csv' % dateString)
csv = open(csvFileName, 'w')
csv.write('Cluster,Policy,Datalock\n')

print('%-25s  %-40s  %s' % ('Cluster', 'Policy', 'Datalock'))
print('%-25s  %-40s  %s' % ('-' * 25, '-' * 40, '-' * 8))

for clustername in clusternames:
    heliosCluster(clustername)

    if LAST_API_ERROR() != 'OK':
        continue

    policies = api('get', 'data-protect/policies?includeTenants=false&includeStats=true&excludeLinkedPolicies=false', v=2)

    for policy in (policies.get('policies', []) if policies else []):
        # only report policies that are actually in use
        if policy.get('numProtectionGroups', 0) <= 0 and policy.get('numProtectedObjects', 0) <= 0:
            continue

        name = policy.get('name', 'unknown')

        # datalock is configured if the regular retention has a dataLockConfig
        dataLockConfig = policy.get('backupPolicy', {}).get('regular', {}).get('retention', {}).get('dataLockConfig')
        datalock = 'Yes' if dataLockConfig else 'No'

        # only report policies without datalock configured
        if datalock == 'No':
            print('%-25s  %-40s  %s' % (clustername, name, datalock))
            csv.write('"%s","%s","%s"\n' % (clustername, name, datalock))

csv.close()
print('\noutput saved to %s' % csvFileName)
