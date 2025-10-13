#!/usr/bin/env python

from pyhesity import *
import argparse
import codecs
from datetime import datetime
import re
from collections import defaultdict

parser = argparse.ArgumentParser()
parser.add_argument('-v', '--vip', type=str, default='helios.cohesity.com')
parser.add_argument('-u', '--username', type=str, default='helios')
parser.add_argument('-i', '--useApiKey', action='store_true')
parser.add_argument('-mcm', '--mcm', action='store_true')
parser.add_argument('-np', '--noprompt', action='store_true')
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
noprompt = args.noprompt

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

#Fix special characters in VM name that need addtional info in URL search string
# I.E. Add "25" after a % in a vm name
def add_chars_after_match(text, pattern, chars_to_add):
        """
    Adds specified characters after each match of a pattern in a string.

    Args:
        text: The input string.
        pattern: The regular expression pattern to search for.
        chars_to_add: The characters to add after each match.

    Returns:
        The modified string with characters added after each match.
    """
        return re.sub(pattern, r'\g<0>' + chars_to_add, text)


# authentication =========================================================
apiauth(vip=vip, username=username, useApiKey=useApiKey, prompt=(not noprompt))

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
    pattern = "%"
    chars_to_add = "25"
    object = add_chars_after_match(object, pattern, chars_to_add)

    stats = api('get', 'data-protect/search/objects?searchString=%s&includeTenants=true' % object, v=2)
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
                try:
                    objectid = o['objectId']
                except:
                    print('No Object ID Found for %s' % actualname)
                    report.append(str('%s,Object ID Not Found' % actualname))
                    continue
                cluster = ([c for c in clusters if c['clusterId'] == o['clusterId']])
                for c in cluster:
                    clustername = c['clusterName']
                    connectedtohelios = c['isConnectedToHelios']
                primarybackup = primarybackup[0]
                pgname = primarybackup['name']
                policyname = primarybackup['policyName']

                #Connect to Object's Primary Cluster
                if connectedtohelios == False:
                    print('Unable to Get PG INFO (%s Disconnected)' % clustername)
                    report.append(str('%s,%s,%s,%s,%s,Cluster Disconnected' % (actualname,clustername,pgname,environment,policyname)))
                    continue
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
                    grouped_data = defaultdict(list)
                    if snapshots['snapshots'] is not None:
                        snapshots = [s for s in snapshots['snapshots']]
                        snapcount = len(snapshots)
                        for snapshot in snapshots:
                            grouped_data[snapshot['protectionGroupName']].append(snapshot['snapshotTimestampUsecs'])
                        snapsummary = {}

                        for group, times in grouped_data.items():
                            times.sort()
                            snapsummary[group] = [{
                                "oldest": times[0],
                                "newest": times[-1]
                            }]

                        for pg, records in snapsummary.items():
                            for record in records:
                                newestsnapshot = record['newest']
                                oldestsnapshot = record['oldest']
                                latestsnapshotdate = usecsToDate (newestsnapshot)
                                oldestsnapshotdate = usecsToDate (oldestsnapshot)

                            print(actualname,clustername,pg,environment,policyname,fullretention,snapcount,oldestsnapshotdate,latestsnapshotdate)
                            report.append(str('%s,%s,%s,%s,%s,%s,%s,%s,%s' % (actualname,clustername,pg,environment,policyname,fullretention,snapcount,oldestsnapshotdate,latestsnapshotdate)))
                    else:
                        snapcount = 0
                        print(actualname,clustername,pgname,environment,policyname,fullretention,snapcount)
                        report.append(str('%s,%s,%s,%s,%s,%s,%s' % (actualname,clustername,pgname,environment,policyname,fullretention,snapcount)))
                else:
                    print(actualname,clustername,pgname,environment,policyname,fullretention)
                    report.append(str('%s,%s,%s,%s,%s,%s' % (actualname,clustername,pgname,environment,policyname,fullretention)))

    #Disconnect from Object's Primary Cluster
    heliosCluster('-')

#write results to report
for item in sorted(report):
    f.write('%s\n' % item)
f.write('\n\nThis report (audit_protection.py) was run %s' % datetimestring)
f.close()
print('\nOutput saved to %s\n' % outfile)
