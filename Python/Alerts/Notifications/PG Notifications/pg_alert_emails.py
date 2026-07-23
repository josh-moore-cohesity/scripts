#!/usr/bin/env python
"""Script Overview"""

### import pyhesity wrapper module
from pyhesity import *
from datetime import datetime
import os
import csv

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
parser.add_argument('-outputpath', '--outputpath', type=str, default='./Results')

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
outputpath = args.outputpath

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
clusternames = gatherList(clustername, clusterlist, name='clusters', required=False)


#Date and Time
now = datetime.now()
datetimestring = now.strftime("%m/%d/%Y %I:%M %p")
dateString = now.strftime("%Y-%m-%d")

# authenticate
apiauth(vip=vip, username=username, domain=domain, password=password, useApiKey=useApiKey, helios=mcm, prompt=(not noprompt), mfaCode=mfacode, emailMfaCode=emailmfacode)


# exit if not authenticated
if apiconnected() is False:
    print('authentication failed')
    exit(1)

# end authentication =====================================================

#Get Clusters
if len(clusternames) > 0:
    clusternames = clusternames
else:
    clusters = api('get', 'cluster-mgmt/info',mcmv2=True)
    clusters = clusters['cohesityClusters']
    clusters = [c for c in clusters if c['isConnectedToHelios'] == True]
    clusternames = []
    for cluster in clusters:
        clusternames.append(cluster['clusterName'])


report = []

for clustername in clusternames:
    heliosCluster(clustername)
    print(clustername)

    if LAST_API_ERROR() != 'OK':
        continue

    #Code starts here
    pgs = api('get', 'data-protect/protection-groups?isDeleted=false&includeTenants=true', v=2)
    pgs = (pgs or {}).get('protectionGroups') or []

    for pg in pgs:
        pgname = pg.get('name', '')
        environment = pg.get('environment', '')
        alertPolicy = pg.get('alertPolicy') or {}
        alertTargets = alertPolicy.get('alertTargets', []) or []
        backupRunStatus = ','.join(alertPolicy.get('backupRunStatus', []) or [])
        allEmails = ','.join([t.get('emailAddress', '') for t in alertTargets])
        print('  %s (%s) -> %s' % (pgname, environment, allEmails))
        report.append([clustername, pgname, environment, pg.get('id', ''), backupRunStatus, allEmails])

# write report
if not os.path.isdir(outputpath):
    os.makedirs(outputpath)

outfile = os.path.join(outputpath, 'pg_alert_emails-%s.csv' % dateString)
with open(outfile, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['Cluster', 'Protection Group', 'Environment', 'PG ID', 'Alert On', 'Alert Recipients'])
    writer.writerows(report)

print('\nFound %d protection group(s)' % len(report))
print('Report written to %s' % outfile)
