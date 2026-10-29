#!/usr/bin/env python
"""Match Helios SSO User Cluster Access"""

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
parser.add_argument('-m', '--mfacode', type=str, default=None)
parser.add_argument('-e', '--emailmfacode', action='store_true')
parser.add_argument('-matchuser', '--matchuser', type=str, required=True)
parser.add_argument('-touser', '--touser', nargs='+', type=str, default=None)
parser.add_argument('-touserlist', '--touserlist', type=str, default=None)
parser.add_argument('-preview', '--preview', action='store_true')

args = parser.parse_args()

vip = args.vip
username = args.username
domain = args.domain
useApiKey = args.useApiKey
password = args.password
noprompt = args.noprompt
mfacode = args.mfacode
emailmfacode = args.emailmfacode
matchuser = args.matchuser
touser = args.touser
touserlist = args.touserlist
preview = args.preview

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

# get list of users to update
tousers = gatherList(touser, touserlist, name='users to update (-touser or -touserlist)', required=True)

# authenticate
apiauth(vip=vip, username=username, domain=domain, password=password, useApiKey=useApiKey, prompt=(not noprompt), mfaCode=mfacode, emailMfaCode=emailmfacode)

# exit if not authenticated
if apiconnected() is False:
    print('authentication failed')
    exit(1)

# end authentication =====================================================

# get clusters
clusterinfo = api('get', 'cluster-mgmt/info', mcmv2=True)
clusterinfo = clusterinfo['cohesityClusters']

# get IDP (SSO) users
idpusers = api('get', 'idps/principals', mcmv2=True)
idpusers = idpusers['principals']

# describe a user's cluster access list as cluster names
def clusterNames(clusterids):
    if clusterids == ['-1:-1']:
        return ['all clusters']
    names = []
    for clusterid in clusterids:
        record = next((c for c in clusterinfo if c['clusterId'] == int(clusterid.split(':')[0])), None)
        names.append(record['clusterName'] if record is not None else clusterid)
    return sorted(names, key=lambda n: n.lower())

# find the user to match
matchidpuser = next((u for u in idpusers if u.get('name', '').lower() == matchuser.lower()), None)
if matchidpuser is None:
    print('Match user %s not found' % matchuser)
    exit(1)

if preview is True:
    print('PREVIEW: no changes will be made\n')

matchclusters = list(matchidpuser['clusters'])
print('%s has access to: %s' % (matchidpuser['name'], ', '.join(clusterNames(matchclusters))))
print('')

issues = []

for user in tousers:
    idpuser = next((u for u in idpusers if u.get('name', '').lower() == user.lower()), None)
    if idpuser is None:
        print('User %s not found' % user)
        issues.append(user)
        continue

    if idpuser['sid'] == matchidpuser['sid']:
        print('%s is the match user, skipping' % idpuser['name'])
        continue

    if set(idpuser['clusters']) == set(matchclusters):
        print('%s already matches' % idpuser['name'])
        continue

    # describe what will change
    before = clusterNames(idpuser['clusters'])
    after = clusterNames(matchclusters)
    added = [c for c in after if c not in before]
    removed = [c for c in before if c not in after]
    print('%s %s' % ('Would update' if preview is True else 'Updating', idpuser['name']))
    if len(added) > 0:
        print('    adding: %s' % ', '.join(added))
    if len(removed) > 0:
        print('    removing: %s' % ', '.join(removed))

    # API call to update user (skipped in preview mode)
    if preview is True:
        continue
    idpuser['clusters'] = list(matchclusters)
    api('put', 'idps/principals/%s' % idpuser['sid'], idpuser, mcmv2=True)

if len(issues) > 0:
    print('\nThe following users were not found:\n')
    for user in issues:
        print(user)
