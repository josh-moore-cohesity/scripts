#!/usr/bin/env python
"""Script Overview"""

### import pyhesity wrapper module
from pyhesity import *
from datetime import datetime
import json
import os

### command line arguments
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('-v', '--vip', type=str, default='helios.cohesity.com')
parser.add_argument('-u', '--username', type=str, default='helios')
parser.add_argument('-d', '--domain', type=str, default='local')
parser.add_argument('-sc', '--clustername', nargs='+', type=str, default=None)
parser.add_argument('-tc', '--targetclustername', type=str, default=None)
parser.add_argument('-cl', '--clusters', type=str, default=None)
parser.add_argument('-mcm', '--mcm', action='store_true')
parser.add_argument('-i', '--useApiKey', action='store_true')
parser.add_argument('-pwd', '--password', type=str, default=None)
parser.add_argument('-np', '--noprompt', action='store_true')
parser.add_argument('-m', '--mfacode', type=str, default=None)
parser.add_argument('-e', '--emailmfacode', action='store_true')
parser.add_argument('-newpass', '--newpassword', type=str, default=None)  # password for local user
parser.add_argument('-o', '--outputpath', type=str, default='./configExports')
parser.add_argument('-env', '--environment', type=str, default=None)
parser.add_argument('-preview', '--preview', action='store_true')

args = parser.parse_args()

vip = args.vip
username = args.username
domain = args.domain
clustername = args.clustername
targetclustername = args.targetclustername
clusterlist = args.clusters
mcm = args.mcm
useApiKey = args.useApiKey
password = args.password
noprompt = args.noprompt
mfacode = args.mfacode
emailmfacode = args.emailmfacode
newpassword = args.newpassword
outputpath = args.outputpath
environment = args.environment
preview = args.preview

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



# authentication =========================================================

if(mcm or vip.lower() != 'helios.cohesity.com'):
    clusternames = []
    clusternames.append(vip)

# Get cluster name or cluster list if connecting to helios or mcm
elif (mcm or vip.lower() == 'helios.cohesity.com'):
    clusternames = gatherList(clustername, clusterlist, name='clusters', required=True)


apiauth(vip=vip, username=username, useApiKey=useApiKey, helios=mcm, prompt=(not noprompt), mfaCode=mfacode, emailMfaCode=emailmfacode)

# exit if not authenticated
if apiconnected() is False:
    print('authentication failed')
    exit(1)

# end authentication =====================================================

#Date
now = datetime.now()
dateString = now.strftime("%Y-%m-%d")


for clustername in clusternames:
    print(clustername)
    # if connected to helios or mcm, select access cluster
    if mcm or vip.lower() == 'helios.cohesity.com':
        heliosCluster(targetclustername)
    if LAST_API_ERROR() != 'OK':
        continue
    thisclusterpath = "%s/%s" % (outputpath,clustername)

    #PGs to import
    pgs_output_file = os.path.join(thisclusterpath, 'protectionGroups.json')

    with open(pgs_output_file, 'r') as file:
        pgs_payload = json.load(file)

    

    currentpgs = api('get', 'data-protect/protection-groups?allUnderHierarchy=true', v=2)
    currentpgs = currentpgs['protectionGroups']
    storagedomains = api ('get', 'storage-domains?matchPartialNames=false&includeTenants=true&includeStats=true', v=2)
    storagedomains = storagedomains['storageDomains']
    defaultdomain = [d for d in storagedomains if d['name'] == 'DefaultStorageDomain']
    defaultdomainid = defaultdomain[0]['id']

    for pg in pgs_payload['protectionGroups']:
        pg['storageDomainId'] = defaultdomainid
        if environment is not None:
            if pg['environment'] != environment or pg['name'] == 'One-time':
                #print("PG %s is not %s" % (pg['name'],environment))
                continue
        localpg= [p for p in currentpgs if p['name'].lower() == pg['name'].lower()]
        if len(localpg) == 0:
            print('Adding PG %s' % pg['name'])
            if not preview:
                newpg= api('post', 'data-protect/protection-groups', pg, v=2)

        else:
            print('PG %s already exists...' % pg['name'])
