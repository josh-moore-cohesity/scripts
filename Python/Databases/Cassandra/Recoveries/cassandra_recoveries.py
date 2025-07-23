#!/usr/bin/env python
"""Query Cassandra Recoveries"""

### import pyhesity wrapper module
from pyhesity import *
from datetime import datetime
import codecs

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
parser.add_argument('-days', '--daysback', type=int, default=7)
parser.add_argument('-s', '--status', type=str, choices=['all', 'succeeded', 'failed', 'running', 'canceled'],default='all')

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
daysback = args.daysback
status = args.status.capitalize()

daysbackusecs = timeAgo(daysback, 'days')
print(daysbackusecs)
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

# end authentication =====================================================

#Date
now = datetime.now()
dateString = now.strftime("%Y-%m-%d")

# Define outfile
outfile = 'recovery_details-%s.csv' % dateString
f = codecs.open(outfile, 'w')

# Add headings to outfile
f.write("Cluster, Task Name, Start Time, End Time, Status, % Complete, Warnings, Messages\n")

report = []

for cluster in clusternames:
    heliosCluster(cluster)
    recoveries = api('get', 'data-protect/recoveries?snapshotEnvironments=kCassandra&startTimeUsecs=%s' % daysbackusecs, v=2)
    recoveries = recoveries['recoveries']
    if status != 'All':
        recoveries = [r for r in recoveries if '%s' % status in r['status']]
    if recoveries == None:
        print('No Cassandra recovery found in last %s days' % daysback)
        continue
    for recovery in recoveries:
        name = recovery['name']
        starttime = usecsToDate(recovery['startTimeUsecs'])
        try:
            endtime = usecsToDate(recovery['endTimeUsecs'])
        except:
            endtime = ''
        currentstatus = recovery['status']
        messages = recovery['messages']
        cassandraparms = recovery['cassandraParams']
        recovercassandraparams = cassandraparms['recoverCassandraParams']
        warnings = recovercassandraparams['warnings']
        progresstaskid = recovery['progressTaskId']
        progressmonitor = api('get', '/progressMonitors?taskPathVec=%s&excludeSubTasks=false&includeFinishedTasks=true&includeEventLogs=true&fetchLogsMaxLevel=0' % progresstaskid)
        progressmonitor = progressmonitor['resultGroupVec'][0]['taskVec'][0]
        percentcomplete = progressmonitor['progress']['percentFinished']
        results = {"Name": name, "Start Time": starttime, "End Time": endtime, "Status": currentstatus, "Percent Complete": percentcomplete, "Warnings": warnings, "Messages": messages}
        report.append(str('%s,%s,%s,%s,%s,%s,%s,%s' % (cluster,name,starttime,endtime,currentstatus,percentcomplete,warnings,messages)))
        for key, value in results.items():
            print(f"{key}: {value}\n")

#Save to File
for record in (report):
    f.write ('%s\n' % record)
f.close()
print('\nOutput saved to %s\n' % outfile)
