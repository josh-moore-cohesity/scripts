#!/usr/bin/env python
"""Report VMs excluded from tag based protection groups (VMware and GCP)"""

# version 2026.10.20

### import pyhesity wrapper module
from pyhesity import *
from datetime import datetime
import codecs
import csv
import json
import os

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
parser.add_argument('-pg', '--protectiongroup', type=str, default=None)
parser.add_argument('-debug', '--debug', action='store_true')

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
debug = args.debug
pgname = args.protectiongroup

ENVIRONMENTS = ['kVMware', 'kGCP']


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


# flatten a tag id list (may be a list of lists)
def flattenIds(raw):
    ids = []
    for entry in (raw or []):
        if isinstance(entry, list):
            ids += entry
        else:
            ids.append(entry)
    return ids


# find the first value in a nested dict whose key contains all the given words
def findKey(obj, *words):
    if isinstance(obj, dict):
        for key, value in obj.items():
            if all(w in key.lower() for w in words) and value:
                return value
        for value in obj.values():
            found = findKey(value, *words)
            if found:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = findKey(value, *words)
            if found:
                return found
    return None


# walk a protection source tree collecting children and VMs (with their tags)
def walkTree(node, children, vms):
    ps = node.get('protectionSource') or {}
    nodeid = ps.get('id')
    if nodeid is None:
        for child in node.get('nodes', []):
            walkTree(child, children, vms)
        return
    children.setdefault(nodeid, [])
    for key, value in ps.items():
        if key.lower().endswith('protectionsource') and isinstance(value, dict) and value.get('type') == 'kVirtualMachine':
            tags = {}
            for t in value.get('tagAttributes') or []:
                if isinstance(t, dict) and t.get('id') is not None:
                    tags[t['id']] = t.get('name', str(t['id']))
            vms[nodeid] = {'name': ps.get('name', str(nodeid)), 'tags': tags}
    for child in node.get('nodes', []):
        childid = (child.get('protectionSource') or {}).get('id')
        if childid is not None:
            children[nodeid].append(childid)
        walkTree(child, children, vms)


# all VM ids at or below a source id
def descendantVMs(sourceid, children, vms):
    result = set()
    stack = [sourceid]
    while stack:
        n = stack.pop()
        if n in vms:
            result.add(n)
        stack += children.get(n, [])
    return result


# get list of clusters
clusternames = gatherList(clustername, clusterlist, name='clusters', required=False)

# Date and Time
now = datetime.now()
dateString = now.strftime("%Y-%m-%d")

# authenticate
apiauth(vip=vip, username=username, domain=domain, password=password, useApiKey=useApiKey, helios=mcm, prompt=(not noprompt), mfaCode=mfacode, emailMfaCode=emailmfacode)

# exit if not authenticated
if apiconnected() is False:
    print('authentication failed')
    exit(1)

# end authentication =====================================================

# Get Clusters
if len(clusternames) == 0:
    clusters = api('get', 'cluster-mgmt/info', mcmv2=True)
    clusters = clusters['cohesityClusters']
    clusters = [c for c in clusters if c['isConnectedToHelios'] is True]
    for cluster in clusters:
        clusternames.append(cluster['clusterName'])

# output file
if not os.path.exists(outputpath):
    os.makedirs(outputpath)
outfile = os.path.join(outputpath, 'vm-tag-exclusions-%s.csv' % dateString)

rows = []

for thiscluster in clusternames:
    heliosCluster(thiscluster)
    print(thiscluster)

    if LAST_API_ERROR() != 'OK':
        print('  skipping %s (connection error)' % thiscluster)
        continue

    # protection groups that have excluded tags
    pgs = api('get', 'data-protect/protection-groups?environments=%s&isDeleted=false' % ','.join(ENVIRONMENTS), v=2)
    pgs = [] if pgs is None else pgs.get('protectionGroups', [])
    tagpgs = []
    for pg in pgs:
        if pg.get('environment') not in ENVIRONMENTS:
            continue
        if pgname is not None and pg.get('name', '').lower() != pgname.lower():
            continue
        params = {}
        for key, value in pg.items():
            if key.lower().endswith('params') and isinstance(value, dict):
                params = value
        if debug:
            print('  DEBUG PG %s (%s) keys=%s' % (pg.get('name'), pg.get('environment'), sorted(pg.keys())))
            print('  DEBUG   params: %s' % json.dumps(params)[:2500])
        if len(flattenIds(findKey(params, 'exclude', 'tag'))) > 0:
            tagpgs.append((pg, params))

    if len(tagpgs) == 0:
        if pgname is not None:
            print("  protection group '%s' not found or has no tag exclusions" % pgname)
        else:
            print('  no tag exclusions found')
        continue

    # protection source trees (only for environments in use)
    children = {}
    vms = {}
    for env in set(pg['environment'] for pg, params in tagpgs):
        sources = api('get', 'protectionSources?environments=%s' % env)
        if isinstance(sources, dict):
            sources = sources.get('nodes') or sources.get('rootNodes') or []
        if debug:
            print('  DEBUG %s sources: %s root nodes' % (env, len(sources or [])))
            # dump the first VM node found (trimmed) to show where its tags live
            def firstvm(n):
                ps = n.get('protectionSource') or {}
                for key, value in ps.items():
                    if key.lower().endswith('protectionsource') and isinstance(value, dict) and value.get('type') == 'kVirtualMachine':
                        return n
                for c in n.get('nodes', []):
                    r = firstvm(c)
                    if r:
                        return r
            for root in sources or []:
                vmnode = firstvm(root)
                if vmnode:
                    vmnode = dict(vmnode)
                    vmnode.pop('nodes', None)
                    print('  DEBUG %s sample VM node: %s' % (env, json.dumps(vmnode)[:1500]))
                    break
        for root in sources or []:
            walkTree(root, children, vms)

    # tag id -> name
    tagnames = {}
    for vm in vms.values():
        tagnames.update(vm['tags'])
    if debug:
        print('  DEBUG %s VMs found in source trees, %s distinct tags: %s' % (len(vms), len(tagnames), tagnames))

    print('')
    print('  PG Name | Tag | VM Count')
    print('')
    for pg, params in sorted(tagpgs, key=lambda p: p[0]['name'].lower()):
        # VMs in scope of the group: the registered source (or selected objects)
        scoperoots = [params.get('sourceId')] if params.get('sourceId') is not None else [o.get('id') for o in params.get('objects', []) if o.get('id') is not None]
        if len(scoperoots) > 0:
            scope = set()
            for oid in scoperoots:
                scope |= descendantVMs(oid, children, vms)
        else:
            scope = set(vms.keys())
        candidates = scope
        objectexcluded = set()
        includegroups = params.get('vmTagIds')
        objectids = scoperoots

        if debug:
            print('  DEBUG %s: scope=%s VMs, candidates=%s, objectexcluded=%s, objectids=%s, includegroups=%s' % (pg['name'], len(scope), len(candidates), len(objectexcluded), objectids, includegroups))

        for tagid in sorted(set(flattenIds(findKey(params, 'exclude', 'tag')))):
            tagname = tagnames.get(tagid, 'tag id %s' % tagid)
            excluded = sorted([vms[v]['name'] for v in candidates if tagid in vms[v]['tags']], key=str.lower)
            # one row per VM (a single row with no VM if the tag matched none)
            for vmname in (excluded or ['']):
                rows.append([thiscluster, pg['name'], pg['environment'], tagname, len(excluded), vmname])
            print('  %s | %s | %s VMs' % (pg['name'], tagname, len(excluded)))
            for vmname in excluded:
                print('    %s' % vmname)
            print('')

# write results
with codecs.open(outfile, 'w', 'utf-8') as f:
    writer = csv.writer(f, lineterminator='\n')
    writer.writerow(['Cluster', 'Protection Group', 'Environment', 'Excluded Tag', 'Excluded VM Count', 'Excluded VM'])
    for row in rows:
        writer.writerow(row)

print('\nOutput saved to %s\n' % outfile)
