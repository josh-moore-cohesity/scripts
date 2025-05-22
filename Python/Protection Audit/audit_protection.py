#!/usr/bin/env python

from pyhesity import *
import argparse
import codecs
from datetime import datetime

parser = argparse.ArgumentParser()
parser.add_argument('-v', '--vip', type=str, default='helios.cohesity.com')
parser.add_argument('-u', '--username', type=str, default='helios')
parser.add_argument('-i', '--useApiKey', action='store_true')
parser.add_argument('-mcm', '--mcm', action='store_true')
parser.add_argument('-o', '--objectname', action='append', type=str, default=None)
parser.add_argument('-ol', '--objectlist', type=str, default=None)
parser.add_argument('-showsnaps', '--showsnaps', action='store_true')


args = parser.parse_args()

vip = args.vip
username = args.username
mcm = args.mcm
useApiKey = args.useApiKey
objectname = args.objectname
objectlist = args.objectlist
showsnaps = args.showsnaps

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


# get list of objects
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

now = datetime.now()
datetimestring = now.strftime("%m/%d/%Y %I:%M %p")
dateString = now.strftime("%Y-%m-%d")

# outfile
if(objectlist is not None):
    outfile = '%s.csv' % objectlist
else:
    outfile = 'audit-protection-%s.csv' % dateString

f = codecs.open(outfile, 'w')

# headings
if showsnaps is True:
    f.write('Object,Cluster,Protection Group,Backup Type,Policy,Retention,Total Snapshots,Oldest Snapshot, Newest Snapshot\n')
else:
    f.write('Object,Cluster,Protection Group,Backup Type,Policy,Retention\n')
report = []

#Get details for objects
for object in objectnames:
    print("Getting Details for", object)

    stats = api('get', 'data-protect/search/objects?searchString=%s&includeTenants=true' %object, v=2)
    stats = [s for s in stats['objects']]

    if(len(stats)) == 0:
       print("No data found for", object)
       report.append(str('%s,%s' % (object, "NA")))
       continue

    for stat in stats:
       actualname = stat['name']
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
                
                if showsnaps is True:
                    snapshots = api('get', 'data-protect/objects/%s/snapshots?runTypes=kRegular&orrunTypes=kFull' % objectid, v=2)

                    if snapshots['snapshots'] is not None:
                        snapshots = [s for s in snapshots['snapshots']]
                        snapcount = len(snapshots)
                        latestsnapshot = snapshots[-1]
                        oldestsnapshot = snapshots[0]
                        latestsnapshotdate = usecsToDate (latestsnapshot['runStartTimeUsecs'])
                        oldestsnapshotdate = usecsToDate (oldestsnapshot['runStartTimeUsecs'])

                        print(actualname,clustername,pgname,environment,policyname,fullretention,snapcount,oldestsnapshotdate,latestsnapshotdate)
                        report.append(str('%s,%s,%s,%s,%s,%s,%s,%s,%s' % (actualname,clustername,pgname,environment,policyname,fullretention,snapcount,oldestsnapshotdate,latestsnapshotdate)))
                    else:
                        snapcount = 0
                        print(actualname,clustername,pgname,environment,policyname,fullretention,snapcount)
                        report.append(str('%s,%s,%s,%s,%s,%s,%s' % (actualname,clustername,pgname,environment,policyname,fullretention,snapcount)))
                else:
                    print(actualname,clustername,pgname,environment,policyname,fullretention)
                    report.append(str('%s,%s,%s,%s,%s,%s' % (actualname,clustername,pgname,environment,policyname,fullretention)))
            else:
                cluster = ([c for c in clusters if c['clusterId'] == o['clusterId']])
                for c in cluster:
                    clustername = c['clusterName']
                print("No data found for", actualname)    
                report.append(str('%s,%s,%s' % (actualname,clustername,"NA")))

    #Disconnect from Object's Primary Cluster
    heliosCluster('-')

#write results to report
for item in sorted(report):
    f.write('%s\n' % item)
f.write('\n\nThis report (audit_protection.py) was run %s' % datetimestring)
f.close()
print('\nOutput saved to %s\n' % outfile)
