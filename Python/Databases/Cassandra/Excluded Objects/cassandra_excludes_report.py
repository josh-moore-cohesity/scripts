#!/usr/bin/env python
"""List Cassandra Excluded Objects"""

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
outfile = 'cassanda_pg_excludes-%s.csv' % dateString
f = codecs.open(outfile, 'w')
f.write('Cluster,PG Name,Custom Source Name,Primary Host,Selected DC,Exclude Type,Exclude Name\n')
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
    jobs = api('get', '/backupjobs')

    cassandrajobs = [j for j in jobs if int(j['backupJob']['type']) == 38]
    
    if not cassandrajobs:
        print("No Cassandra PGs found on Cluster %s" % cluster['name'])
        continue
    
    for pg in cassandrajobs:
        pgexcludes = []
        pgname = pg['backupJob']['name']
        print(pgname)
        pgid = pg['backupJob']['jobId']
        sourceid = pg['backupJob']['parentSource']['id']
        customSourceName = pg['backupJob']['parentSource']['customName']
        paused = pg['backupJob']['isPaused']
        primaryhost = pg['backupJob']['parentSource']['cassandraEntity']['clusterInfo']['primaryHost']
        try:
            selecteddc = pg['backupJob']['envBackupParams']['nosqlBackupJobParams']['cassandraBackupJobParams']['selectedDataCenterVec'][0]
        except:
            selecteddc = "All"
        try:
            excludeinfo = pg['backupJob']['excludeSources']
        except:
            excludeinfo = None
     
        if excludeinfo is not None:
            excludeentities = [e for e in excludeinfo]
            for e in excludeentities:
                entity = (e['entities'][0])
                cassandraexcludeentity = entity['cassandraEntity']
                type = cassandraexcludeentity['type']
                if type == 1:
                    excludetype = "Keyspace"
                if type == 2:
                    excludetype = "Table"
                excludename = cassandraexcludeentity['name']
                pgexcludes.append(str('%s,%s,%s,%s,%s,%s,%s' %(cluster['name'],pgname,customSourceName,primaryhost,selecteddc,excludetype,excludename)))
        else:
            excludetype = "NA"
            excludename = "NA"
            pgexcludes.append(str('%s,%s,%s,%s,%s,%s,%s' %(cluster['name'],pgname,customSourceName,primaryhost,selecteddc,excludetype,excludename)))
        
        for item in sorted(pgexcludes):
            f.write('%s\n' % item)

    f.close
    print('\nOutput saved to %s\n' % outfile)
