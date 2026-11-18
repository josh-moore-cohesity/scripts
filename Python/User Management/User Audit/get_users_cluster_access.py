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
parser.add_argument('-user', '--user', type=str, required=True)

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
finduser = args.user.strip()

# authenticate
apiauth(vip=vip, username=username, domain=domain, password=password, useApiKey=useApiKey, helios=mcm, prompt=(not noprompt), mfaCode=mfacode, emailMfaCode=emailmfacode)

# exit if not authenticated
if apiconnected() is False:
    print('authentication failed')
    exit(1)

# end authentication =====================================================

# get users and find the requested one (match on username or user@domain)
users = api('get', 'users', mcm=True)
matches = [u for u in users if finduser.lower() in (u['username'].lower(), ('%s@%s' % (u['username'], u['domain'])).lower())]

if len(matches) == 0:
    print("User '%s' not found" % finduser)
    exit(1)

# get all clusters registered to Helios
clusters = api('get', 'cluster-mgmt/info', mcmv2=True)
clusters = clusters['cohesityClusters']
totalclusters = len(clusters)

for user in matches:
    accessibleclusters = []
    clusteraccess = user.get('clusterIdentifiers', [])

    # clusterId of -1 means access to all clusters
    if any(c['clusterId'] == -1 for c in clusteraccess):
        accessibleclusters = [c['clusterName'] for c in clusters]
    else:
        accessibleids = [c['clusterId'] for c in clusteraccess]
        accessibleclusters = [c['clusterName'] for c in clusters if c['clusterId'] in accessibleids]

    print('\nUser %s (%s) has access to %s/%s clusters' % (user['username'], user['domain'], len(accessibleclusters), totalclusters))
    if len(accessibleclusters) > 0:
        print('')
        for clustername in sorted(accessibleclusters, key=str.lower):
            print('  %s' % clustername)

print('')
