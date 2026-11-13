#!/usr/bin/env python
"""Apply Exclusion Rules to a VMware Protection Group

Uses the v2 protection group API (data-protect/protection-groups). Only VMware (kVMware)
protection groups are modified, and only VMs (not folders, hosts, etc.) are added to the
protection group's excluded objects. Replicated protection groups (isActive=false) are skipped.
"""

# usage: ./excludeVMs.py -v mycluster -i -j 'VM Backup' -xt -x sql -x ora
# preview only, no changes made: add -dr

# import pyhesity wrapper module
from pyhesity import *
from urllib.parse import quote

# command line arguments
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('-v', '--vip', type=str, default='helios.cohesity.com')
parser.add_argument('-u', '--username', type=str, default='helios')
parser.add_argument('-i', '--useApiKey', action='store_true')
parser.add_argument('-p', '--password', type=str, default=None)
parser.add_argument('-d', '--domain', type=str, default='local')
parser.add_argument('-j', '--jobname', type=str, required=True)
parser.add_argument('-x', '--exclude', action='append', type=str)
parser.add_argument('-xt', '--excludeTemplates', action='store_true')
parser.add_argument('-np', '--noprompt', action='store_true')
parser.add_argument('-mcm', '--mcm', action='store_true')
parser.add_argument('-m', '--mfacode', type=str, default=None)
parser.add_argument('-e', '--emailmfacode', action='store_true')
parser.add_argument('-c', '--clustername', action='append', type=str, default=None)
parser.add_argument('-cl', '--clusters', type=str, default=None)
parser.add_argument('-dr', '--dryrun', action='store_true')

args = parser.parse_args()

vip = args.vip                 # cluster name/ip
username = args.username       # username to connect to cluster
domain = args.domain           # domain of username (e.g. local, or AD domain)
jobname = args.jobname         # name of protection group
excludeTemplates = args.excludeTemplates  # boolean exclude templates or not
excludeRules = args.exclude    # list of substrings to exclude
useApiKey = args.useApiKey
password = args.password
noprompt = args.noprompt
mcm = args.mcm
mfacode = args.mfacode
emailmfacode = args.emailmfacode
clustername = args.clustername
clusterlist = args.clusters
dryrun = args.dryrun

if excludeRules is None:
    excludeRules = []

usingHelios = mcm or vip.lower() == 'helios.cohesity.com'

# functions =============================================


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


# api calls return None, 'error' or {'error': ...} on failure (a 204 on success does not set LAST_ERROR to OK)
def apifailed(result):
    return result is None or result == 'error' or (isinstance(result, dict) and 'error' in result)


def getnodes(obj, nodes, nodeParents, parentid=0):
    """gather list of VMs and parent/child relationships"""
    nodes.append(obj)
    if parentid not in nodeParents.keys():
        nodeParents[parentid] = []
    if obj['protectionSource']['id'] not in nodeParents.keys():
        nodeParents[obj['protectionSource']['id']] = nodeParents[parentid] + [parentid]
    else:
        nodeParents[obj['protectionSource']['id']] = list(set(nodeParents[parentid] + [parentid] + nodeParents[obj['protectionSource']['id']]))
    if 'nodes' in obj:
        for node in obj['nodes']:
            getnodes(node, nodes, nodeParents, obj['protectionSource']['id'])


def isVm(node):
    """only virtual machines are ever excluded (not folders, hosts, clusters, etc.)"""
    return (node['protectionSource'].get('vmWareProtectionSource') or {}).get('type') == 'kVirtualMachine'


def excludeInPg(pgid, pgname):
    """apply the exclusion rules to one VMware protection group (v2 API)"""
    pg = api('get', 'data-protect/protection-groups/%s' % pgid, v=2)
    if apifailed(pg) or not isinstance(pg, dict):
        print('   unable to get protection group "%s": %s' % (pgname, LAST_API_ERROR()))
        return

    # a PG with isActive=false is a replica of a PG on another cluster - leave it alone
    if pg.get('isActive') is False:
        print('   protection group "%s" is a replicated (inactive) PG - skipping' % pgname)
        return

    # never modify anything but VMware protection groups
    if pg.get('environment') != 'kVMware':
        print('   protection group "%s" is %s - not a VMware PG, skipping' % (pgname, pg.get('environment')))
        return

    params = pg.get('vmwareParams')
    if params is None or not params.get('objects') or params.get('sourceId') is None:
        print('   protection group "%s" has no objects (folders/VMs) to search, skipping' % pgname)
        return

    containerIds = [o['id'] for o in params['objects']]

    # get source info (vCenter)
    parentSource = api('get', 'protectionSources?allUnderHierarchy=true&excludeTypes=kResourcePool&id=%s&includeEntityPermissionInfo=true&includeVMFolders=true' % params['sourceId'])
    if apifailed(parentSource) or len(parentSource) == 0:
        print('   unable to get vCenter inventory for "%s": %s' % (pgname, LAST_API_ERROR()))
        return

    # gather list of VMs and parent/child relationships
    nodes = []
    nodeParents = {}
    getnodes(parentSource[0], nodes, nodeParents)

    excluded = params.get('excludeObjectIds') or []
    added = 0

    for node in nodes:
        nodeId = node['protectionSource']['id']
        nodeName = node['protectionSource']['name']

        # VMs that are a child of one of the PG's objects (folders, tags, hosts, etc.)
        if not isVm(node) or not any(c in nodeParents[nodeId] for c in containerIds):
            continue
        if nodeId in excluded:
            continue

        reason = None
        # if vm is a template
        if excludeTemplates is True and node['protectionSource']['vmWareProtectionSource'].get('isVmTemplate') is True:
            reason = 'template'
        # if vm name matches an exclusion rule
        for excludeRule in excludeRules:
            if excludeRule.lower() in nodeName.lower():
                reason = 'rule match'

        if reason is not None:
            excluded.append(nodeId)
            added += 1
            print("   adding %s to exclusions (%s)" % (nodeName, reason))

    if added == 0:
        print('   no new exclusions for "%s"' % pgname)
        return

    if dryrun:
        print('   [DRY RUN] would exclude %s VM(s) in protection group "%s"' % (added, pgname))
        return

    # update protection group with new exclusions
    params['excludeObjectIds'] = excluded
    result = api('put', 'data-protect/protection-groups/%s' % pgid, pg, v=2)
    if apifailed(result):
        print('   failed to update "%s": %s' % (pgname, LAST_API_ERROR()))
    else:
        print('   updated protection group "%s" (%s VM(s) excluded)' % (pgname, added))

# end functions =========================================


# get list of clusters
clusternames = gatherList(clustername, clusterlist, name='clusters', required=usingHelios)

# authenticate
apiauth(vip=vip, username=username, domain=domain, password=password, useApiKey=useApiKey, helios=mcm, prompt=(not noprompt), mfaCode=mfacode, emailMfaCode=emailmfacode)

# exit if not authenticated
if apiconnected() is False:
    print('authentication failed')
    exit(1)

# end authentication =====================================================

if dryrun:
    print('\n*** DRY RUN - no changes will be made ***')

# if connected to helios or mcm, select access cluster
for cluster in (clusternames if usingHelios else [vip]):
    if usingHelios:
        heliosCluster(cluster)
        if LAST_API_ERROR() != 'OK':
            print('unable to connect to %s, skipping' % cluster)
            continue
    print('\n%s' % cluster)

    # find the protection group by name (VMware, active PGs only)
    result = api('get', 'data-protect/protection-groups?names=%s&environments=kVMware&isDeleted=false' % quote(jobname), v=2)
    pgs = []
    if not apifailed(result) and result.get('protectionGroups'):
        pgs = [p for p in result['protectionGroups'] if p['name'].lower() == jobname.lower() and p.get('isActive') is not False and p.get('environment') == 'kVMware']
    if len(pgs) == 0:
        print("   VMware protection group '%s' not found" % jobname)
        continue

    for pg in pgs:
        excludeInPg(pg['id'], pg['name'])

if usingHelios:
    heliosCluster('-')
