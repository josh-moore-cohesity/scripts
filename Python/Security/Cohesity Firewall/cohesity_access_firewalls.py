#!/usr/bin/env python
"""Script Overview"""

### import pyhesity wrapper module
from pyhesity import *
from datetime import datetime
import csv
import os

# =====================================================================
# Approved "Client's IPSET" entries for the Management and SSH profiles
# =====================================================================

# Applies to ALL clusters
BASE_APPROVED = [
    '10.52.22.83',
    '10.52.78.60',
    '10.52.144.80',
    '10.228.24.150',
    '10.228.162.82',
    '10.228.98.32',
    '10.52.168.39',
    '10.228.1.11',
    '10.52.42.25',
    '10.228.166.34',
    '10.52.69.32',
    '10.228.171.43',
    '10.231.150.31',
    '10.53.155.21',
    '10.229.95.122',
    '10.249.227.99',
    '10.249.227.16',
]

# Additional entries required ONLY on clusters whose name matches *atl-lz1*
ATL_EXTRA = [
    '10.63.15.71',
    '10.63.15.101',
    '10.63.15.102',
    '10.63.15.103',
    '10.63.15.104',
]

# Additional entries required ONLY on clusters whose name matches *las-lz1*
LAS_EXTRA = [
    '10.231.12.77',
    '10.231.12.101',
    '10.231.12.102',
    '10.231.12.103',
    '10.231.12.104',
]

# Firewall profiles (applications) to check
PROFILES_TO_CHECK = ['Management', 'SSH']


def _normalize_name(s):
    """lowercase and strip separators so 'LAS LZ1-CL1' == 'LAS-LZ1-CL1'"""
    return s.lower().replace(' ', '').replace('_', '').replace('-', '')


def name_contains(clustername, fragment):
    """substring match, ignoring case and separators (so *atl-az1* == 'atlaz1')"""
    return _normalize_name(fragment) in _normalize_name(clustername)


def approved_for_cluster(clustername):
    """Return the approved IP set for a given cluster name."""
    approved = set(BASE_APPROVED)
    if name_contains(clustername, 'atl-lz1'):
        approved.update(ATL_EXTRA)
    if name_contains(clustername, 'las-lz1'):
        approved.update(LAS_EXTRA)
    return approved


def normalize_ip(entry):
    """Strip a /32 host suffix so '10.0.0.1/32' compares equal to '10.0.0.1'."""
    entry = entry.strip()
    if entry.endswith('/32'):
        entry = entry[:-3]
    return entry

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
parser.add_argument('-outputpath', '--outputpath', type=str, default='./Firewall')

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


# collect discrepancy rows across all clusters
discrepancies = []

for clustername in clusternames:
    heliosCluster(clustername)
    print(clustername)

    if LAST_API_ERROR() != 'OK':
        print('  ! could not access cluster (%s)' % LAST_API_ERROR())
        continue

    approved = approved_for_cluster(clustername)

    firewallinfo = api('get', '/nexus/firewall/list')
    if firewallinfo is None or 'entry' not in firewallinfo:
        print('  ! no firewall data returned')
        continue

    entry = firewallinfo['entry']
    attachments = entry.get('attachments') or []

    # build a name->subnets lookup for named ipsets (fallback if attachment has no subnets)
    ipset_lookup = {}
    for ipset in (entry.get('ipsets') or []):
        ipset_lookup[ipset['name']] = ipset.get('subnets') or []

    for profile_name in PROFILES_TO_CHECK:
        attachment = next((a for a in attachments if a.get('profile') == profile_name), None)

        if attachment is None:
            print('  %s: no attachment found' % profile_name)
            continue

        # resolve the effective "Client's IPSET" for this profile
        subnets = attachment.get('subnets')
        if not subnets:
            # fall back to resolving any named ipsets attached
            subnets = []
            for ipset_name in (attachment.get('ipsetNames') or []):
                subnets.extend(ipset_lookup.get(ipset_name, []))

        # no restriction at all == "All"
        if not subnets:
            print('  %s: Client IPSET is "All" (unrestricted) -- DISCREPANCY' % profile_name)
            discrepancies.append({
                'cluster': clustername,
                'application': profile_name,
                'discrepancy': 'Client IPSET is "All" (unrestricted)',
                'entry': 'ALL',
            })
            continue

        actual = set(normalize_ip(s) for s in subnets)

        unexpected = sorted(actual - approved)   # present but not approved
        missing = sorted(approved - actual)      # approved but not present

        if not unexpected and not missing:
            print('  %s: OK (%d entries match)' % (profile_name, len(actual)))
            continue

        for ip in unexpected:
            print('  %s: UNEXPECTED entry %s' % (profile_name, ip))
            discrepancies.append({
                'cluster': clustername,
                'application': profile_name,
                'discrepancy': 'Unexpected (not in approved list)',
                'entry': ip,
            })
        for ip in missing:
            print('  %s: MISSING entry %s' % (profile_name, ip))
            discrepancies.append({
                'cluster': clustername,
                'application': profile_name,
                'discrepancy': 'Missing (approved but not present)',
                'entry': ip,
            })

# =====================================================================
# write results
# =====================================================================
if not os.path.exists(outputpath):
    os.makedirs(outputpath)

outfile = os.path.join(outputpath, 'firewall-ipset-discrepancies-%s.csv' % dateString)
with open(outfile, 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['Cluster', 'Application', 'Discrepancy', 'Entry'])
    for d in discrepancies:
        writer.writerow([d['cluster'], d['application'], d['discrepancy'], d['entry']])

print('')
if discrepancies:
    print('%d discrepancies found across the checked clusters' % len(discrepancies))
else:
    print('No discrepancies found -- all Management/SSH IPSETs match the approved list')
print('results written to %s' % outfile)
