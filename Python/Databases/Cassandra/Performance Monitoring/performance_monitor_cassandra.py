#!/usr/bin/env python
"""Monitor Performance of an Active Cassandra DSE Backup"""

### import pyhesity wrapper module
from pyhesity import *
from datetime import datetime, timedelta
import time
import os
import subprocess
import codecs

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
parser.add_argument('-pg', '--protectiongroup', type=str, required=True)
parser.add_argument('-runtime', '--runtime', type=int, default='5')
parser.add_argument('-interval', '--interval', type=int, default='10')

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
pgname = args.protectiongroup
runtime = args.runtime
interval = args.interval

end_time = datetime.now() + timedelta(minutes=runtime)

#Date
now = datetime.now()
dateString = now.strftime("%Y-%m-%d")
datetimestring = now.strftime("%m/%d/%Y %I:%M %p")

# authenticate
apiauth(vip=vip, username=username, domain=domain, password=password, useApiKey=useApiKey, helios=mcm, prompt=(not noprompt), mfaCode=mfacode, emailMfaCode=emailmfacode)


# exit if not authenticated
if apiconnected() is False:
    print('authentication failed')
    exit(1)

# end authentication =====================================================


report = []

pgs = api('get', 'data-protect/protection-groups', v=2)
pgs = pgs['protectionGroups']

pg = [p for p in pgs if p['name'] == pgname][0]

pgid = pg['id']
print("\nPGID: %s" % pgid)
runs = api('get', 'data-protect/protection-groups/%s/runs?includeObjectDetails=true' % pgid, v=2)

runs = runs['runs']
print("\nTotal Runs: %s" % len(runs))

activerun = [r for r in runs if r['localBackupInfo']['status'] == "Running"]

if len(activerun) == 0:
    print("No Active Run Found for PG %s" % pgname)
    exit(1)

exportfile = 'cassandra-pg-performance-%s-%s.csv' % (pgname,dateString)
f = codecs.open(exportfile, 'w', 'utf-8')

activerun = activerun[0]


activerunid = activerun['id']
print("\nActive Run ID: %s" % activerunid)
#display(activerun)
taskinfo = activerun['objects'][0]['localSnapshotInfo']['snapshotInfo']['progressTaskId']

runtaskpath = activerun['localBackupInfo']['progressTaskId']
print("\nRun Task Path: %s" % runtaskpath)

pulselog = api('get', 'data-protect/runs/%s/progress?runTaskPath=%s&objects=180&objectTaskPaths=%s&includeEventLogs=true' % (activerunid, runtaskpath,taskinfo), v=2)

pulselogevents = pulselog['localRun']['objects'][0]['events']
print("\nPulse Log Events Length: %s" % len(pulselogevents))

viewinfo = [e for e in pulselogevents if 'Backup will write to view' in e['message']]
print("\nView Info: %s" % viewinfo)

viewmessage = viewinfo[0]['message']
print("\nView Message: %s" % viewmessage)

viewname = viewmessage.split(':', 1)[1].strip()
print("\nView Name: %s" %viewname)

views = api('get', 'views?includeInternalViews=true')

views = views['views']
print("\nTotal Views: %s" % len(views))

thisview = [v for v in views if v['name'] == viewname][0]
print("\nThis View: %s" % thisview['name'])
viewid = thisview['viewId']

print("\n",viewid)

cmd = (
    "allssh.sh links -dump-width 1024 http://127.0.0.1:11111/ | egrep -A40 'View Stats Averaged over 60 secs' | egrep 'MiBps|KiBps' | egrep -i '%s:Backup'" % viewid
)

while datetime.now() < end_time:
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(result.stdout)
    report.append(result.stdout)
    time.sleep(interval)

#Save to File
for record in (report):
    f.write ('%s\n' % record)
f.close()
