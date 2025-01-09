#!/usr/bin/env python

from pyhesity import *
import argparse
import codecs

parser = argparse.ArgumentParser()
parser.add_argument('-v', '--vip', type=str, default='helios.cohesity.com')
parser.add_argument('-u', '--username', type=str, default='helios')
parser.add_argument('-i', '--useApiKey', action='store_true')
parser.add_argument('-mcm', '--mcm', action='store_true')
parser.add_argument('-o', '--objectname', action='append', type=str, default=None)
parser.add_argument('-ol', '--objectlist', type=str, default=None)

args = parser.parse_args()

vip = args.vip
username = args.username
mcm = args.mcm
useApiKey = args.useApiKey
objectname = args.objectname
objectlist = args.objectlist

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
objectnames = gatherList(objectname, objectlist, name='Objects', required=True)

# authentication =========================================================
apiauth(vip=vip, username=username, useApiKey=useApiKey)

# exit if not authenticated
if apiconnected() is False:
    print('authentication failed')
    exit(1)

# end authentication =====================================================

#get clusters
clusters = api('get', 'cluster-mgmt/info',mcmv2=True)
clusters = clusters['cohesityClusters']

# outfile
outfile = 'protection_audit.csv'
f = codecs.open(outfile, 'w')

# headings
f.write('Object,Cluster,Protection Group,Backup Type,Policy,Retention,Total Snapshots,Oldest Snapshot, Newest Snapshot\n')

report = []

#Get details for objects
for object in objectnames:
    print("Getting Details for", object)

    stats = api('get', 'data-protect/search/objects?searchString=%s&includeTenants=true&count=5' %object, v=2)
    stats = [s for s in stats['objects']]
    for stat in stats:
       opi = stat['objectProtectionInfos']
       for o in opi:
           if o['protectionGroups'] is not None:
            primarybackup = (o['protectionGroups'])
            environment = stat['environment']
            objectid = o['objectId']
            cluster = ([c for c in clusters if c['clusterId'] == o['clusterId']])
            for c in cluster:
                clustername = c['clusterName']
    primarybackup = primarybackup[0]
    pgname = primarybackup['name']
    policyname = primarybackup['policyName']

    #Connect to Object's Primary Cluster
    heliosCluster (clustername)
    policy = api('get', 'data-protect/policies?policyNames=%s' %policyname, v=2)
    policy = policy['policies']
    for p in policy:
        retention = p['backupPolicy']['regular']['retention']
        duration = retention['duration']
        unit = retention['unit']
        fullretention = str(duration) + " " + unit
    snapshots = api('get', 'data-protect/objects/%s/snapshots?runTypes=kRegular&orrunTypes=kFull' % objectid, v=2)
    snapshots = [s for s in snapshots['snapshots']]
    snapcount = len(snapshots)
    latestsnapshot = snapshots[-1]
    oldestsnapshot = snapshots[0]
    latestsnapshotdate = usecsToDate (latestsnapshot['runStartTimeUsecs'])
    oldestsnapshotdate = usecsToDate (oldestsnapshot['runStartTimeUsecs'])
    print(object,clustername,pgname,environment,policyname,fullretention,snapcount,oldestsnapshotdate,latestsnapshotdate)
    report.append(str('%s,%s,%s,%s,%s,%s,%s,%s,%s' % (object,clustername,pgname,environment,policyname,fullretention,snapcount,oldestsnapshotdate,latestsnapshotdate)))

    #Disconnect from Object's Primary Cluster
    heliosCluster('-')

#write results to report
for item in sorted(report):
    f.write('%s\n' % item)

f.close()
print('\nOutput saved to %s\n' % outfile)
