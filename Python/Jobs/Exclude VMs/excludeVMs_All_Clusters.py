#!/usr/bin/env python
"""Exclude VMware VMs and physical servers from their protection groups (all Helios clusters)

For each name or wildcard pattern supplied, this script uses Helios global search to find the
matching objects, then connects to the cluster that protects each object and updates the
protection group(s) using the v2 protection group API (data-protect/protection-groups).

Only these object / protection group types are touched:
  * VMware VMs (kVMware)
      - protected through a folder / tag / auto-protect parent: the VM is added to the PG's excludeObjectIds
      - listed explicitly in the PG: the VM is removed from the PG object list
  * Physical servers (kPhysical)
      - physical file/volume PGs have no exclusion list, so the server is removed from the PG object list

Anything else the search returns (Cassandra, SQL, Oracle, NAS, etc.) is ignored, even if a wildcard
matches its name, and any protection group that is not a VMware or Physical PG is skipped.
Replicated protection groups (isActive=false) are skipped. A PG that would be left with no objects
is not modified. Existing snapshots are not deleted.

Requires a Helios connection (run with -mcm).

usage: ./excludeVMs_AllClusters.py -v helios.cohesity.com -i -mcm -x sql -x ora -x rhel
wildcards are supported (quote them in your shell): -x 'server1*' -x '*sql*' -x 'web0?'
preview only, no changes made: add -dr
"""

# import pyhesity wrapper module
from pyhesity import *
import codecs
from datetime import datetime
import re
import os
import fnmatch
from urllib.parse import quote

# command line arguments
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('-v', '--vip', type=str, default='helios.cohesity.com')
parser.add_argument('-u', '--username', type=str, default='helios')
parser.add_argument('-i', '--useApiKey', action='store_true')
parser.add_argument('-p', '--password', type=str, default=None)
parser.add_argument('-d', '--domain', type=str, default='local')
parser.add_argument('-x', '--exclude', action='append', type=str)
parser.add_argument('-vl', '--excludelist', type=str)
parser.add_argument('-xt', '--excludeTemplates', action='store_true')  # accepted for compatibility, not used
parser.add_argument('-np', '--noprompt', action='store_true')
parser.add_argument('-mcm', '--mcm', action='store_true')
parser.add_argument('-m', '--mfacode', type=str, default=None)
parser.add_argument('-e', '--emailmfacode', action='store_true')
parser.add_argument('-dr', '--dryrun', action='store_true')
parser.add_argument('-outputpath', '--outputpath', type=str, default='./ExcludeVMs')

args = parser.parse_args()

vip = args.vip                 # cluster name/ip
username = args.username       # username to connect to cluster
domain = args.domain           # domain of username (e.g. local, or AD domain)
excludeRules = args.exclude    # list of names / wildcard patterns to exclude
excludelist = args.excludelist
useApiKey = args.useApiKey
password = args.password
noprompt = args.noprompt
mcm = args.mcm
mfacode = args.mfacode
emailmfacode = args.emailmfacode
dryrun = args.dryrun
outputpath = args.outputpath

# DATE
now = datetime.now()
dateString = now.strftime("%Y-%m-%d-%I-%M-%S")

# only these object environments (and protection group environments) are ever modified
ENV_LABELS = {'kVMware': 'VMware VM', 'kPhysical': 'physical server'}


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


# get the search term to send to the API for a name or wildcard pattern
def searchTerm(pattern):
    # the search API does substring matching, so use the longest literal piece of the pattern
    pieces = re.split(r'[*?\[\]]', pattern)
    return max(pieces, key=len)


# case-insensitive match of an object name against a name or wildcard pattern (* ? [seq])
def nameMatches(name, pattern):
    return fnmatch.fnmatchcase(name.lower(), pattern.lower())


# api calls return None, 'error' or {'error': ...} on failure (a 204 on success does not set LAST_ERROR to OK)
def apifailed(result):
    return result is None or result == 'error' or (isinstance(result, dict) and 'error' in result)


# write one line to the csv report as it happens
def log(obj, cluster, env, pg, result):
    # keep the csv well formed when a result carries an api error message
    result = re.sub(r'\s+', ' ', str(result)).replace(',', ';')
    f.write('%s,%s,%s,%s,%s\n' % (obj, cluster, env, pg, result))
    f.flush()


# find the list of objects a PG protects and the params dict holding excludeObjectIds (VMware only)
# returns (None, None) for any PG type this script does not support
def getPgObjects(pg):
    env = pg.get('environment')
    if env == 'kVMware':
        params = pg.get('vmwareParams')
        if params is None:
            return None, None
        if params.get('objects') is None:
            params['objects'] = []
        return params['objects'], params
    if env == 'kPhysical':
        params = pg.get('physicalParams') or {}
        ptype = params.get('protectionType')
        typeparams = params.get('fileProtectionTypeParams') if ptype == 'kFile' else params.get('volumeProtectionTypeParams')
        if typeparams is None:
            return None, None
        if typeparams.get('objects') is None:
            typeparams['objects'] = []
        return typeparams['objects'], None
    return None, None


# exclude one object from one protection group (v2 API). returns a result string for the report
def excludeFromPg(pgid, pgname, objectId, objname):
    pg = api('get', 'data-protect/protection-groups/%s' % pgid, v=2)
    if apifailed(pg) or not isinstance(pg, dict):
        print('    unable to get protection group "%s"' % pgname)
        return 'Error getting PG: %s' % LAST_API_ERROR()

    # a PG with isActive=false is a replica of a PG on another cluster - leave it alone
    if pg.get('isActive') is False:
        print('    protection group "%s" is a replicated (inactive) PG - skipping' % pgname)
        return 'Skipped - replicated PG'

    # never modify anything but VMware / Physical protection groups
    if pg.get('environment') not in ENV_LABELS:
        print('    protection group "%s" is %s - not a VMware or Physical PG, skipping' % (pgname, pg.get('environment')))
        return 'Skipped - unsupported PG type %s' % pg.get('environment')

    pgobjects, vmwareparams = getPgObjects(pg)
    if pgobjects is None:
        print('    protection group "%s" has no usable object list, skipping' % pgname)
        return 'Skipped - no object list in PG'

    explicit = [o for o in pgobjects if o.get('id') == objectId]
    excluded = []
    if vmwareparams is not None:
        excluded = vmwareparams.get('excludeObjectIds') or []
        if objectId in excluded:
            print('    %s is already excluded from "%s"' % (objname, pgname))
            return 'Already excluded'

    if len(explicit) > 0:
        remaining = [o for o in pgobjects if o.get('id') != objectId]
        if len(remaining) == 0:
            print('    %s is the last object in "%s" - not modified' % (objname, pgname))
            return 'Last object in PG - not modified'
        action = 'remove %s from' % objname
        pgobjects[:] = remaining
    elif vmwareparams is not None:
        # VM is protected through a parent (folder/tag/auto-protect) - exclude it instead
        action = 'exclude %s (auto-protected) from' % objname
        excluded.append(objectId)
        vmwareparams['excludeObjectIds'] = excluded
    else:
        print('    %s is not in the object list of "%s"' % (objname, pgname))
        return 'Not in PG object list'

    if dryrun:
        print('    [DRY RUN] would %s protection group "%s"' % (action, pgname))
        return 'DRY RUN - would update PG'

    print('    %s protection group "%s"' % (action, pgname))
    result = api('put', 'data-protect/protection-groups/%s' % pgid, pg, v=2)
    if apifailed(result):
        print('    failed to update "%s": %s' % (pgname, LAST_API_ERROR()))
        return 'Error updating PG: %s' % LAST_API_ERROR()
    return 'Removed from PG' if len(explicit) > 0 else 'Excluded'

# end functions =========================================


vmnames = gatherList(excludeRules, excludelist, name='VMs', required=True)
totalvms = len(vmnames)

# authenticate
apiauth(vip=vip, username=username, domain=domain, password=password, useApiKey=useApiKey, helios=mcm, prompt=(not noprompt), mfaCode=mfacode, emailMfaCode=emailmfacode)

# exit if not authenticated
if apiconnected() is False:
    print('authentication failed')
    exit(1)

# end authentication =====================================================

# Define outfile
os.makedirs(outputpath, exist_ok=True)
if excludelist is not None:
    listname = os.path.splitext(os.path.basename(excludelist))[0]
    outfile = os.path.join(outputpath, 'excluded-vms-%s-%s.csv' % (dateString, listname))
else:
    outfile = os.path.join(outputpath, 'excluded-vms-%s.csv' % dateString)

f = codecs.open(outfile, 'w')
f.write('Object,Cluster,Environment,Protection Group,Result\n')

clusterinfo = api('get', 'cluster-mgmt/info', mcmv2=True)
if clusterinfo is None or 'cohesityClusters' not in clusterinfo:
    print('unable to retrieve cluster list from Helios (did you connect with -mcm?)')
    exit(1)
clusters = clusterinfo['cohesityClusters']

if dryrun:
    print('\n*** DRY RUN - no changes will be made ***')

count = 0
for vm in vmnames:
    count += 1
    print("\nLooking to exclude %s (%s / %s)" % (vm, count, totalvms))
    term = searchTerm(vm)
    if term == '':
        print("Pattern %s has no searchable text, skipping" % vm)
        log(vm, '', '', '', 'Skipped - pattern has no searchable text')
        continue

    search = api('get', 'data-protect/search/objects?searchString=%s&includeTenants=true' % quote(term), v=2)
    if apifailed(search) or search.get('objects') is None:
        print("No data found for", vm)
        log(vm, '', '', '', 'Not found')
        continue

    # only VMware VMs and physical servers - anything else the pattern matches is ignored
    named = [s for s in search['objects'] if nameMatches(s['name'], vm)]
    stats = [s for s in named if s.get('environment') in ENV_LABELS]
    ignored = [s for s in named if s.get('environment') not in ENV_LABELS]
    if len(ignored) > 0:
        envs = sorted(set([str(s.get('environment')) for s in ignored]))
        print("  ignoring %s matching object(s) that are not VMware VMs or physical servers (%s)" % (len(ignored), ', '.join(envs)))

    if len(stats) == 0:
        print("No VMware VM or physical server found for", vm)
        log(vm, '', '', '', 'No VMware VM or physical server match')
        continue

    for stat in stats:
        actualname = stat['name']
        environment = stat['environment']
        for o in (stat.get('objectProtectionInfos') or []):
            objectid = o.get('objectId')
            if objectid is None:
                print('No Object ID Found for %s' % actualname)
                log(actualname, '', environment, '', 'Object ID Not Found')
                continue

            # only active (primary) protection groups - replicated PGs (isActive=false) are ignored
            pgs = [p for p in (o.get('protectionGroups') or []) if p.get('isActive') is not False]
            if len(pgs) == 0:
                continue

            cluster = [c for c in clusters if c['clusterId'] == o.get('clusterId')]
            if len(cluster) == 0:
                print('Cluster id %s (for %s) is not registered in Helios, skipping' % (o.get('clusterId'), actualname))
                log(actualname, str(o.get('clusterId')), environment, '', 'Cluster not registered in Helios')
                continue
            clustername = cluster[0]['clusterName']
            if cluster[0].get('isConnectedToHelios') is False:
                print('Unable to Get PG INFO (%s Disconnected)' % clustername)
                log(actualname, clustername, environment, '', 'Cluster Disconnected')
                continue

            print("\n %s (%s) on %s" % (actualname, ENV_LABELS[environment], clustername))
            heliosCluster(clustername)
            if LAST_API_ERROR() != 'OK':
                print('    unable to connect to %s, skipping' % clustername)
                log(actualname, clustername, environment, '', 'Unable to connect')
                continue

            for pg in pgs:
                result = excludeFromPg(pg['id'], pg['name'], objectid, actualname)
                log(actualname, clustername, environment, pg['name'], result)

            # done with this cluster; clear the access header before the next
            heliosCluster('-')

    print("\nDone searching for %s" % vm)

f.close()
print('\nOutput saved to %s\n' % outfile)
