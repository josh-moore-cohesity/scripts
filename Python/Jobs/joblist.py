#!/usr/bin/env python
"""List Protection Jobs for python"""

# usage: ./jobList.py -v mycluster -u myuser -d mydomain.net [ -s defaultStorageDomain ] [ -e vmware ]

# import pyhesity wrapper module
from pyhesity import *
import json
from datetime import time, datetime, timedelta
import codecs

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
parser.add_argument('-j', '--jobname', type=str, default=None)
parser.add_argument('-paused', '--paused', action='store_true')

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
jobname = args.jobname
ispaused = args.paused

#Date
now = datetime.now()
dateString = now.strftime("%Y-%m-%d")

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

#Create Outfile
outfile = 'pg_summary-%s.csv' % dateString
f = codecs.open(outfile, 'w')
f.write('Cluster,Job Name,Paused,Start Time,Environment,Total Objects, AutoProtect Objects\n')

report = []

if clustername == ['all']:
    clusternames = []
    clusters = api('get', 'cluster-mgmt/info',mcmv2=True)
    allclusters = clusters['cohesityClusters']
    for cluster in allclusters:
        if cluster['isConnectedToHelios'] == False:
            print(cluster['clusterName'],"Not Connected to Helios")
            report.append('%s,Disconnected From Helios' % cluster['clusterName'])
            continue
        clusternames.append(cluster['clusterName'])



# if connected to helios or mcm, select access cluster
for cluster in clusternames:
    if mcm or vip.lower() == 'helios.cohesity.com':
    
       heliosCluster(cluster)

    if LAST_API_ERROR() != 'OK':
        exit(1)
# end authentication =====================================================

    jobs = api('get', 'data-protect/protection-groups?isActive=True&useCachedData=false', v=2)
    jobs = jobs['protectionGroups']
    if jobs is None:
        continue

    if ispaused:
        jobs = [j for j in jobs if j['isPaused'] == True]

    if jobname:
        jobs = [j for j in jobs if jobname.lower() in j['name'].lower() ]

    for job in jobs:
        starttime = job['startTime']
        starttimeobject = time(hour=starttime['hour'], minute=starttime['minute'])
        paused = job['isPaused']
        if 'numProtectedObjects' not in job:
            job['numProtectedObjects'] = "NA"
        if environment is None or job['environment'][1:].lower() == environment.lower():
                if job['environment'] == 'kVMware':
                    vmparams = job['vmwareParams']['objects']
                    vmautoprotecttotal = len(vmparams)
                    print('%s %s (Paused: %s) (%s) (%s) (%s %s) (%s %s)' % (cluster,job['name'],paused,starttimeobject,job['environment'], 'Objects:', job['numProtectedObjects'],'Auto Protected:',vmautoprotecttotal))
                    report.append('%s,%s,%s,%s,%s,%s,%s' % (cluster,job['name'],paused,starttimeobject,job['environment'],job['numProtectedObjects'],vmautoprotecttotal))                
                else:
                    print('%s %s (Paused: %s) (%s) (%s) (%s %s)' % (cluster,job['name'],paused,starttimeobject, job['environment'], 'Objects:', job['numProtectedObjects']))
                    report.append('%s,%s,%s,%s,%s,%s' % (cluster,job['name'],paused,starttimeobject,job['environment'],job['numProtectedObjects']))

for item in report:
    f.write('%s\n' % item)

f.close()
print('\nOutput saved to %s\n' % outfile)
