#!/usr/bin/env python
"""Report the Helios clusters a user has access to"""

# version 2026.11.18

### import pyhesity wrapper module
from pyhesity import *

### command line arguments
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('-v', '--vip', type=str, default='helios.cohesity.com')
parser.add_argument('-u', '--username', type=str, default='helios')
parser.add_argument('-d', '--domain', type=str, default='local')
parser.add_argument('-i', '--useApiKey', action='store_true')
parser.add_argument('-pwd', '--password', type=str, default=None)
parser.add_argument('-np', '--noprompt', action='store_true')
parser.add_argument('-mcm', '--mcm', action='store_true')
parser.add_argument('-m', '--mfacode', type=str, default=None)
parser.add_argument('-e', '--emailmfacode', action='store_true')
parser.add_argument('-user', '--user', type=str, default=None)
parser.add_argument('-c', '-cluster', '--cluster', action='append', default=None)
parser.add_argument('-clusterlist', '--clusterlist', type=str, default=None)

args = parser.parse_args()

vip = args.vip
username = args.username
domain = args.domain
useApiKey = args.useApiKey
password = args.password
noprompt = args.noprompt
mcm = args.mcm
mfacode = args.mfacode
emailmfacode = args.emailmfacode
finduser = args.user.strip() if args.user else None

# build list of clusters to report on (-cluster may repeat or be comma separated; -clusterlist is a text file, 1 cluster per line)
findclusters = []
for entry in (args.cluster or []):
    findclusters += [e.strip() for e in entry.split(',') if e.strip()]
if args.clusterlist:
    try:
        with open(args.clusterlist, 'r') as cl:
            findclusters += [line.strip() for line in cl if line.strip() and not line.strip().startswith('#')]
    except IOError:
        print("Unable to read cluster list file %s" % args.clusterlist)
        exit(1)
findclusters = list(dict.fromkeys(findclusters))

if not finduser and len(findclusters) == 0:
    print("specify -user (report clusters a user can access) and/or -cluster/-clusterlist (report users with access to a cluster)")
    exit(1)

# authenticate
apiauth(vip=vip, username=username, domain=domain, password=password, useApiKey=useApiKey, helios=mcm, prompt=(not noprompt), mfaCode=mfacode, emailMfaCode=emailmfacode)

# exit if not authenticated
if apiconnected() is False:
    print('authentication failed')
    exit(1)

# end authentication =====================================================

# get all users and all clusters registered to Helios
users = api('get', 'users', mcm=True)
clusters = api('get', 'cluster-mgmt/info', mcmv2=True)
clusters = clusters['cohesityClusters']
totalclusters = len(clusters)

# '-c all' expands to every cluster currently connected to Helios
if any(name.lower() == 'all' for name in findclusters):
    connectednames = [c['clusterName'] for c in clusters if c.get('isConnectedToHelios') is True]
    skipped = totalclusters - len(connectednames)
    if skipped > 0:
        print('skipping %s cluster(s) not connected to Helios' % skipped)
    # replace 'all' with connected clusters, keeping any explicitly named clusters (de-duplicated)
    findclusters = [n for n in findclusters if n.lower() != 'all'] + connectednames
    findclusters = list(dict.fromkeys(findclusters))

def hasAccess(user, cluster):
    clusteraccess = user.get('clusterIdentifiers', [])
    # clusterId of -1 means access to all clusters
    return any(c['clusterId'] in (-1, cluster['clusterId']) for c in clusteraccess)


# report clusters accessible to a user =====================================
if finduser:
    # match on username or user@domain
    matches = [u for u in users if finduser.lower() in (u['username'].lower(), ('%s@%s' % (u['username'], u['domain'])).lower())]

    if len(matches) == 0:
        print("User '%s' not found" % finduser)
        if len(findclusters) == 0:
            exit(1)

    for user in matches:
        accessibleclusters = [c['clusterName'] for c in clusters if hasAccess(user, c)]
        print('\nUser %s (%s) has access to %s/%s clusters' % (user['username'], user['domain'], len(accessibleclusters), totalclusters))
        if len(accessibleclusters) > 0:
            print('')
            for clustername in sorted(accessibleclusters, key=str.lower):
                print('  %s' % clustername)

# report users (and roles) with access to a cluster ========================
csvrows = []
for name in findclusters:
    cluster = next((c for c in clusters if c['clusterName'].lower() == name.lower()), None)
    if cluster is None:
        print("\nCluster '%s' not found" % name)
        continue

    clusterusers = [u for u in users if hasAccess(u, cluster)]
    print('\nCluster %s has %s/%s users with access' % (cluster['clusterName'], len(clusterusers), len(users)))
    if len(clusterusers) > 0:
        print('')
        rows = []
        for u in sorted(clusterusers, key=lambda u: (u['username'].lower(), u['domain'].lower())):
            rows.append(('%s (%s)' % (u['username'], u['domain']), ', '.join(u.get('roles', []))))
            csvrows.append([cluster['clusterName'], u['username'], u['domain'], '; '.join(u.get('roles', []))])
        width = max(len(r[0]) for r in rows)
        for r in rows:
            print('  %s  %s' % (r[0].ljust(width), r[1]))

# write cluster report to csv (one line per cluster/user)
if len(findclusters) > 0:
    import csv
    from datetime import datetime
    dateString = datetime.now().strftime("%Y-%m-%d")
    if len(findclusters) == 1:
        # single cluster: include its name in the file name (use the name as registered in Helios when found)
        found = next((c['clusterName'] for c in clusters if c['clusterName'].lower() == findclusters[0].lower()), findclusters[0])
        safename = ''.join(ch if (ch.isalnum() or ch in '-_.') else '_' for ch in found)
        outfile = 'cluster_users-%s-%s.csv' % (safename, dateString)
    else:
        outfile = 'cluster_users-%s.csv' % dateString
    with open(outfile, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Cluster', 'User', 'Domain', 'Role'])
        writer.writerows(csvrows)
    print('\nOutput saved to %s' % outfile)

print('')
