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
parser.add_argument('-add', '--add', type=str, action='append', default=None)
parser.add_argument('-remove', '--remove', type=str, action='append', default=None)
parser.add_argument('-pglist', '--pglist', type=str, default=None)

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
addEmails = args.add or []
removeEmails = args.remove or []
pglistfile = args.pglist

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

# load csv of clustername,pgname pairs to restrict -add/-remove to
def loadPgList(filename):
    if filename is None:
        return None
    pairs = set()
    with open(filename, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 2 or row[0].strip() == '':
                continue
            pairs.add((row[0].strip().lower(), row[1].strip().lower()))
    if len(pairs) == 0:
        print('no protection groups found in %s' % filename)
        exit()
    return pairs

pgList = loadPgList(pglistfile)

# get list of clusters
clusternames = gatherList(clustername, clusterlist, name='clusters', required=False)

# if no clusters were explicitly given, narrow to the clusters referenced in -pglist
if len(clusternames) == 0 and pgList is not None:
    clusternames = sorted(set(pair[0] for pair in pgList))


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

        inScope = pgList is None or (clustername.lower(), pgname.lower()) in pgList
        modifying = len(addEmails) > 0 or len(removeEmails) > 0
        changed = False

        if modifying and inScope:
            if len(removeEmails) > 0:
                keptTargets = [t for t in alertTargets if t.get('emailAddress') not in removeEmails]
                if len(keptTargets) != len(alertTargets):
                    changed = True
                alertTargets = keptTargets

            if len(addEmails) > 0:
                existingEmails = [t.get('emailAddress') for t in alertTargets]
                newTargets = [
                    {
                        "emailAddress": e,
                        "language": "en-us",
                        "recipientType": "kTo"
                    }
                    for e in addEmails
                    if e not in existingEmails
                ]
                if len(newTargets) > 0:
                    changed = True
                alertTargets = alertTargets + newTargets

            if changed:
                pg['alertPolicy']['alertTargets'] = alertTargets
                print('  updating %s' % pgname)
                api('put', 'data-protect/protection-groups/%s' % pg.get('id', ''), pg, v=2)
                if LAST_API_ERROR() != 'OK':
                    print('  *** failed to update %s: %s' % (pgname, LAST_API_ERROR()))

        allEmails = ','.join([t.get('emailAddress', '') for t in alertTargets])
        if not modifying or changed:
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
