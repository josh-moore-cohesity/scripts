#!/usr/bin/env python
"""Script Overview"""

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
parser.add_argument('-s', '--status', type=str, choices=['all', 'succeeded', 'failed', 'running', 'canceled'],default='All')

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
f.write("Cluster, Task Name, Start Time, End Time, Run Time, Status, % Complete, Estimated Time Remaining, Warnings, Messages\n")

def find_last_occurrence_of_text(text_list, search_text):
    """
    Finds the last occurrence of a specified text within a list of strings.

    Args:
        text_list (list): A list of strings to search within.
        search_text (str): The text to search for.

    Returns:
        str or None: The last found string containing the search_text,
                     or None if the text is not found in any string.
    """
    for item in reversed(text_list):
        if search_text in item:
            return item
    return None


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
        starttimetodate = datetime.fromtimestamp(recovery['startTimeUsecs'] / 1_000_000)
        try:
            endtime = usecsToDate(recovery['endTimeUsecs'])
            endtimetodate = datetime.fromtimestamp(recovery['endTimeUsecs'] / 1_000_000)
            runtime = endtimetodate - starttimetodate
            runtime = str(runtime)
            runtime = runtime.replace(",", " -")
        except:
            endtime = ''
            runtime = now - starttimetodate
            runtime = str(runtime)
            runtime = runtime.replace(",", " -")
        currentstatus = recovery['status']
        messages = recovery['messages']
        messages = (str(messages).replace(",", "-"))
        cassandraparms = recovery['cassandraParams']
        recovercassandraparams = cassandraparms['recoverCassandraParams']
        warnings = recovercassandraparams['warnings']
        progresstaskid = recovery['progressTaskId']
        progressmonitor = api('get', '/progressMonitors?taskPathVec=%s&excludeSubTasks=false&includeFinishedTasks=true&includeEventLogs=true&fetchLogsMaxLevel=0' % progresstaskid)
        progressmonitor = progressmonitor['resultGroupVec'][0]['taskVec'][0]
        percentcomplete = progressmonitor['progress']['percentFinished']
        pulselog = progressmonitor['progress']['eventVec']
        for entry in reversed(pulselog):
            if "map" in entry['eventMsg']:
                last_map_entry = entry
                break
        print(last_map_entry['eventMsg'])
        #for index, item in enumerate(pulselog):
        #    print(f"Index: {index}, Value: {item}")
        try:
            expectedremainingsecs = progressmonitor['progress']['expectedTimeRemainingSecs']
            expectedremaininghours = round(expectedremainingsecs/60/60,2)
        except:
            expectedremaininghours = '0'
        results = {"Name": name, "Start Time": starttime, "End Time": endtime, "Run Time": runtime, "Status": currentstatus, "Percent Complete": percentcomplete,"Estimated Hours Remaining": expectedremaininghours, "Warnings": warnings, "Messages": messages}
        report.append(str('%s,%s,%s,%s,%s,%s,%s,%s,%s,%s' % (cluster,name,starttime,endtime,runtime,currentstatus,percentcomplete,expectedremaininghours,warnings,messages)))
        for key, value in results.items():
            print(f"{key}: {value}\n")

#Save to File
for record in (report):
    f.write ('%s\n' % record)
f.close()
print('\nOutput saved to %s\n' % outfile)
