#!/usr/bin/env python
"""List Cassandra Protected Objects"""

# import pyhesity wrapper module
from pyhesity import *
from datetime import datetime
import codecs

# command line arguments
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('-v', '--vip', type=str, default='helios.cohesity.com')
parser.add_argument('-u', '--username', type=str, default='helios')
parser.add_argument('-d', '--domain', type=str, default='local')
parser.add_argument('-i', '--useApiKey', action='store_true')
parser.add_argument('-p', '--password', type=str, default=None)
parser.add_argument('-np', '--noprompt', action='store_true')
parser.add_argument('-mcm', '--mcm', action='store_true')
parser.add_argument('-c', '--clustername', nargs='+', type=str, default=None)
parser.add_argument('-cl', '--clusters', type=str, default=None)
parser.add_argument('-m', '--mfacode', type=str, default=None)
parser.add_argument('-e', '--emailmfacode', action='store_true')

args = parser.parse_args()

vip = args.vip
username = args.username
domain = args.domain
useApiKey = args.useApiKey
password = args.password
noprompt = args.noprompt
clustername = args.clustername
clusterlist = args.clusters
mcm = args.mcm
mfacode = args.mfacode
emailmfacode = args.emailmfacode


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

# outfile
now = datetime.now()
dateString = now.strftime("%Y-%m-%d")
outfile = 'cassanda_protected_summary-%s.csv' % dateString
f = codecs.open(outfile, 'w')
f.write('Cluster,PG Name,Primary Host,Custom Name,Source Id, Protected Table Count, Unprotected Table Count, Excluded Keyspace Count,Paused, Consumption GB\n')
report = []

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

# if connected to helios or mcm, select access cluster
for cluster in clusternames:
    if mcm or vip.lower() == 'helios.cohesity.com':
    
       heliosCluster(cluster)
       print (cluster)
    if LAST_API_ERROR() != 'OK':
        exit(1)

    # Get Cluster Info
    cluster = api('get', 'cluster')

    print('\nGathering Job Info from %s...\n' % cluster['name'])
    #Get PGs on cluster
    jobs = api('get', 'data-protect/protection-groups?environments=kCassandra', v=2)
    pgs = jobs['protectionGroups']
    
    #skip cluster if no Cassandra PGs found
    if not pgs:
        print("No Cassandra PGs found on Cluster %s" % cluster['name'])
        continue

    #Get PG Details
    for pg in pgs:
        jobname = pg['name']
        jobid = pg['id'].split(':')[2]
        sourceid = pg['cassandraParams']['sourceId']
        customSourceName = pg['cassandraParams']['customSourceName']
        paused = pg['isPaused']
        if pg['cassandraParams']['excludeObjectIds']:
            excludes = len(pg['cassandraParams']['excludeObjectIds'])
        else:
            excludes = "0"

    #Get Source Info
        protectedsummary = api('get', '/backupsources?allUnderHierarchy=false&entityId=%s' % sourceid)
        protectedobjectcount = protectedsummary['entityHierarchy']['aggregatedProtectedInfoVec'][0]['numEntities']
        unprotectedobjectcount = protectedsummary['entityHierarchy']['aggregatedUnprotectedInfoVec'][0]['numEntities']
        clusterhost = protectedsummary['entityHierarchy']['entity']['cassandraEntity']['name']
        
        pgstats = api('get', 'stats/consumers?consumerType=kProtectionRuns&consumerIdList=%s' % jobid)
        pgconsumption = round(pgstats['statsList'][0]['stats']['storageConsumedBytes']/1024/1024/1024, 2)

        #Post Results
        print(jobname, customSourceName, protectedobjectcount, paused, pgconsumption)
        report.append(str('%s,%s,%s,%s,%s,%s,%s,%s,%s,%s' % (clustername[0], jobname, clusterhost, customSourceName, sourceid, protectedobjectcount, unprotectedobjectcount, excludes ,paused, pgconsumption)))

#Save to File
for record in (report):
    f.write ('%s\n' % record)
f.close()
print('\nReport saved to %s\n' % outfile)
