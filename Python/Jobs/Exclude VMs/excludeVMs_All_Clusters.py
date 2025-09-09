#!/usr/bin/env python
"""Apply Exclusion Rules to VM Autoprotect Protection Job"""

# usage: ./excludeVMs.py -v helios.cohesity.com -i -xt -x sql -x ora -x rhel

# import pyhesity wrapper module
from pyhesity import *
import codecs
from datetime import datetime
import re

# command line arguments
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('-v', '--vip', type=str, default='helios.cohesity.com')
parser.add_argument('-u', '--username', type=str, default='helios')
parser.add_argument('-i', '--useApiKey', action='store_true')
parser.add_argument('-p', '--password', type=str, default=None)
parser.add_argument('-d', '--domain', type=str, default='local')
parser.add_argument('-x', '--exclude', action='append', type=str)
parser.add_argument('-vl', '--excludelist', type=str)
parser.add_argument('-xt', '--excludeTemplates', action='store_true')
parser.add_argument('-np', '--noprompt', action='store_true')
parser.add_argument('-mcm', '--mcm', action='store_true')
parser.add_argument('-m', '--mfacode', type=str, default=None)
parser.add_argument('-e', '--emailmfacode', action='store_true')

args = parser.parse_args()

vip = args.vip                 # cluster name/ip
username = args.username       # username to connect to cluster
domain = args.domain           # domain of username (e.g. local, or AD domain)
excludeTemplates = args.excludeTemplates  # boolean exclude templates or not
excludeRules = args.exclude    # list of substrings to exclude
excludelist = args.excludelist
useApiKey = args.useApiKey
password = args.password
noprompt = args.noprompt
mcm = args.mcm
mfacode = args.mfacode
emailmfacode = args.emailmfacode


#DATE
now = datetime.now()
datetimestring = now.strftime("%m/%d/%Y %I:%M %p")
dateString = now.strftime("%Y-%m-%d-%I-%M-%S")


# functions =============================================

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

# end functions =========================================

vmnames = gatherList(excludeRules, excludelist, name='VMs', required=True)
totalvms = len(vmnames)
# authenticate
apiauth(vip=vip, username=username, domain=domain, password=password, useApiKey=useApiKey, helios=mcm, prompt=(not noprompt))

# exit if not authenticated
if apiconnected() is False:
    print('authentication failed')
    exit(1)

# end authentication =====================================================

# Define outfile
if(excludelist is not None):
    outfile = 'excluded-vms-%s-%s.csv' % (dateString, excludelist)
else:
    outfile = 'excluded-vms-%s.csv' % dateString
f = codecs.open(outfile, 'w')

clusters = api('get', 'cluster-mgmt/info',mcmv2=True)
clusters = clusters['cohesityClusters']

count = 0
for vm in vmnames:
    report = []
    count +=1
    print("\nLooking to exclude %s (%s / %s)" % (vm, count, totalvms))
    stats = api('get', 'data-protect/search/objects?searchString=%s&includeTenants=true' % vm, v=2)
    stats = [s for s in stats['objects']]
    
    if(len(stats)) == 0:
       print("No data found for", vm)
       continue

    for stat in stats:
       actualname = stat['name']
       opi = stat['objectProtectionInfos']
       for o in opi:         
           if o['protectionGroups'] is not None:
            primarybackup = (o['protectionGroups'])
            environment = stat['environment']
            objectid = o['objectId']
            sourceid = o['sourceId']
            primarybackup = primarybackup[0]
            pgname = primarybackup['name']
            policyname = primarybackup['policyName']
            cluster = ([c for c in clusters if c['clusterId'] == o['clusterId']])
            
            for c in sorted(cluster):
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

                    if job['parentSourceId'] == sourceid and origclusterid == clusterid and job['name'] == pgname:                
                        print("Adding exclusion for %s in job: %s" % (vm, job['name']))
                        if 'excludeSourceIds' not in job:
                            job['excludeSourceIds'] = []
                        job['excludeSourceIds'].append(objectid)
                    # update job with new exclusions
                        updatedJob = api('put', 'protectionJobs/%s' % job['id'], job)
                        report.append('%s,%s,%s, Excluded' % (actualname,clustername,job['name']))

    for item in report:
        f.write('%s\n' % item)
    
    print("\nDone searching for %s" % vm)
    heliosCluster('-')
   
f.close()
print('\nOutput saved to %s\n' % outfile)
