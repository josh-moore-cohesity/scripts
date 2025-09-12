#!/usr/bin/env python
"""protect VMware VMs Using Python"""

### import pyhesity wrapper module
from pyhesity import *
import codecs
from datetime import datetime
import re

### command line arguments
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('-v', '--vip', type=str, default='helios.cohesity.com')
parser.add_argument('-u', '--username', type=str, default='helios')
parser.add_argument('-d', '--domain', type=str, default='local')
parser.add_argument('-mcm', '--mcm', action='store_true')
parser.add_argument('-i', '--useApiKey', action='store_true')
parser.add_argument('-pwd', '--password', type=str, default=None)
parser.add_argument('-np', '--noprompt', action='store_true')
parser.add_argument('-m', '--mfacode', type=str, default=None)
parser.add_argument('-e', '--emailmfacode', action='store_true')
parser.add_argument('-n', '--vmname', action='append', type=str)
parser.add_argument('-vl', '--vmlist', type=str)
parser.add_argument('-vc', '--vcentername', type=str, default=None)


args = parser.parse_args()

vip = args.vip
username = args.username
domain = args.domain
mcm = args.mcm
useApiKey = args.useApiKey
password = args.password
noprompt = args.noprompt
mfacode = args.mfacode
emailmfacode = args.emailmfacode
vmname = args.vmname
vmlist = args.vmlist
vcentername = args.vcentername

#DATE
now = datetime.now()
datetimestring = now.strftime("%m/%d/%Y %I:%M %p")
dateString = now.strftime("%Y-%m-%d-%I-%M-%S")

# Functions
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

# end functions =========================================

vmnames = gatherList(vmname, vmlist, name='VMs', required=True)
totalvms = len(vmnames)

# authenticate
apiauth(vip=vip, username=username, domain=domain, password=password, useApiKey=useApiKey, helios=mcm, prompt=(not noprompt))

# exit if not authenticated
if apiconnected() is False:
    print('authentication failed')
    exit(1)

# end authentication =====================================================

# Define outfile
if(vmlist is not None):
    outfile = 'removed-excluded-vms-%s-%s.csv' % (dateString, vmlist)
else:
    outfile = 'removed-excluded-vms-%s.csv' % dateString
f = codecs.open(outfile, 'w')

clusters = api('get', 'cluster-mgmt/info',mcmv2=True)
clusters = clusters['cohesityClusters']

count = 0
for vm in vmnames:
    report = []
    count +=1
    print("\nChecking excludes for %s (%s / %s)" % (vm, count, totalvms))
    stats = api('get', 'data-protect/search/objects?searchString=%s&includeTenants=true' % vm, v=2)
    stats = [s for s in stats['objects']]

    if(len(stats)) == 0:
       print("No data found for", vm)
       continue

    for stat in stats:
        actualname = stat['name']
        opi = stat['objectProtectionInfos']
        for o in opi:
            environment = stat['environment']
            objectid = o['objectId']
            sourceid = o['sourceId']
            cluster = ([c for c in clusters if c['clusterId'] == o['clusterId']])
            for c in cluster:
                    clustername = c['clusterName']
                    connectedtohelios = c['isConnectedToHelios']
                    
                    #Connect to Object's Primary Cluster
                    if connectedtohelios == False:
                        print('Unable to Get PG INFO (%s Disconnected)' % clustername)
                        report.append(str('%s,%s, Cluster Disconnected' % (actualname,clustername)))
                        continue
                    
                    print("\n %s" % clustername)
                    heliosCluster (clustername)

                    clusterid = api('get', 'cluster')['id']
                    
                    for job in api('get', 'protectionJobs?isDeleted=false'):
                        origclusterid = int(job['policyId'].split(':')[0])

                        if job['parentSourceId'] == sourceid and origclusterid == clusterid:
                            print("looking for exclusions in job: %s" % job['name'])
                            if 'excludeSourceIds' in job:
                                if objectid in job['excludeSourceIds']:
                                    job['excludeSourceIds'].remove(objectid)
                                    print("   Removing %s from exclusions" % actualname)

                                    # update job
                                    updatedJob = api('put', 'protectionJobs/%s' % job['id'], job)
                                    report.append('%s,%s,%s, Exclusion Removed' % (actualname,clustername,job['name']))
    for item in report:
        f.write('%s\n' % item)
    print("\nDone searching for %s" % vm)
    heliosCluster('-')

f.close()
print('\nOutput saved to %s\n' % outfile)
