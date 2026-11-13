#!/usr/bin/env python
"""Remove Manually Added Excludes for VMware VMs (all Helios clusters)

Uses the v2 protection group API (data-protect/protection-groups). Only VMware (kVMware)
objects and protection groups are touched. Names are matched exactly (case-insensitive) unless
they contain wildcards (* ? [seq]). Replicated protection groups (isActive=false) are skipped.

usage: ./remove_vm_exclude_all_clusters.py -v helios.cohesity.com -i -mcm -n server1 -n 'web0*'
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
parser.add_argument('-d', '--domain', type=str, default='local')
parser.add_argument('-mcm', '--mcm', action='store_true')
parser.add_argument('-i', '--useApiKey', action='store_true')
parser.add_argument('-pwd', '--password', type=str, default=None)
parser.add_argument('-np', '--noprompt', action='store_true')
parser.add_argument('-m', '--mfacode', type=str, default=None)
parser.add_argument('-e', '--emailmfacode', action='store_true')
parser.add_argument('-n', '--vmname', action='append', type=str)
parser.add_argument('-vl', '--vmlist', type=str)
parser.add_argument('-vc', '--vcentername', type=str, default=None)
parser.add_argument('-dr', '--dryrun', action='store_true')
parser.add_argument('-outputpath', '--outputpath', type=str, default='./RemoveExcludes')

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
vmname = args.vmname
vmlist = args.vmlist
vcentername = args.vcentername
dryrun = args.dryrun
outputpath = args.outputpath

# DATE
now = datetime.now()
dateString = now.strftime("%Y-%m-%d-%I-%M-%S")

# Functions =============================================


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
def log(obj, cluster, pg, result):
    # keep the csv well formed when a result carries an api error message
    result = re.sub(r'\s+', ' ', str(result)).replace(',', ';')
    f.write('%s,%s,%s,%s\n' % (obj, cluster, pg, result))
    f.flush()


# active VMware protection groups on the cluster we are connected to (full definitions, cached per cluster)
pgCache = {}


def getVmwarePgs(cname):
    if cname not in pgCache:
        pgCache[cname] = None
        result = api('get', 'data-protect/protection-groups?environments=kVMware&isDeleted=false', v=2)
        if not apifailed(result):
            full = []
            for p in (result.get('protectionGroups') or []):
                if p.get('isActive') is False or p.get('environment') != 'kVMware':
                    continue
                pg = api('get', 'data-protect/protection-groups/%s' % p['id'], v=2)
                if not apifailed(pg) and isinstance(pg, dict):
                    full.append(pg)
            pgCache[cname] = full
    return pgCache[cname]

# end functions =========================================


vmnames = gatherList(vmname, vmlist, name='VMs', required=True)
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
if vmlist is not None:
    listname = os.path.splitext(os.path.basename(vmlist))[0]
    outfile = os.path.join(outputpath, 'removed-excluded-vms-%s-%s.csv' % (dateString, listname))
else:
    outfile = os.path.join(outputpath, 'removed-excluded-vms-%s.csv' % dateString)

f = codecs.open(outfile, 'w')
f.write('Object,Cluster,Protection Group,Result\n')

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
    print("\nChecking excludes for %s (%s / %s)" % (vm, count, totalvms))
    term = searchTerm(vm)
    if term == '':
        print("Pattern %s has no searchable text, skipping" % vm)
        log(vm, '', '', 'Skipped - pattern has no searchable text')
        continue

    search = api('get', 'data-protect/search/objects?searchString=%s&includeTenants=true' % quote(term), v=2)
    if apifailed(search) or search.get('objects') is None:
        print("No data found for", vm)
        log(vm, '', '', 'Not found')
        continue

    # only VMware VMs - anything else the pattern matches is ignored
    named = [s for s in search['objects'] if nameMatches(s['name'], vm)]
    stats = [s for s in named if s.get('environment') == 'kVMware']
    if len(named) > len(stats):
        print("  ignoring %s matching object(s) that are not VMware VMs" % (len(named) - len(stats)))
    if len(stats) == 0:
        print("No VMware VM found for", vm)
        log(vm, '', '', 'No VMware VM match')
        continue

    for stat in stats:
        actualname = stat['name']
        for o in (stat.get('objectProtectionInfos') or []):
            objectid = o.get('objectId')
            if objectid is None:
                print('No Object ID Found for %s' % actualname)
                log(actualname, '', '', 'Object ID Not Found')
                continue
            sourceid = o.get('sourceId')

            cluster = [c for c in clusters if c['clusterId'] == o.get('clusterId')]
            if len(cluster) == 0:
                print('Cluster id %s (for %s) is not registered in Helios, skipping' % (o.get('clusterId'), actualname))
                log(actualname, str(o.get('clusterId')), '', 'Cluster not registered in Helios')
                continue
            clustername = cluster[0]['clusterName']

            # Connect to Object's Primary Cluster
            if cluster[0].get('isConnectedToHelios') is False:
                print('Unable to Get PG INFO (%s Disconnected)' % clustername)
                log(actualname, clustername, '', 'Cluster Disconnected')
                continue

            print("\n %s (%s)" % (clustername, actualname))
            heliosCluster(clustername)
            if LAST_API_ERROR() != 'OK':
                print('    unable to connect to %s, skipping' % clustername)
                log(actualname, clustername, '', 'Unable to connect')
                continue

            pgs = getVmwarePgs(clustername)
            if pgs is None:
                print("Error Getting PGs on %s: %s" % (clustername, LAST_API_ERROR()))
                log(actualname, clustername, '', 'Error getting PGs')
                heliosCluster('-')
                continue

            for pg in pgs:
                params = pg.get('vmwareParams') or {}

                # same vCenter as the object (and the requested vCenter, if specified)
                if sourceid is not None and params.get('sourceId') != sourceid:
                    continue
                if vcentername is not None and str(params.get('sourceName', '')).lower() != vcentername.lower():
                    continue

                excluded = params.get('excludeObjectIds') or []
                if objectid not in excluded:
                    continue

                print("looking for exclusions in protection group: %s" % pg['name'])
                if dryrun:
                    print("   [DRY RUN] would remove %s from exclusions" % actualname)
                    log(actualname, clustername, pg['name'], 'DRY RUN - would remove exclusion')
                    continue

                print("   Removing %s from exclusions" % actualname)
                params['excludeObjectIds'] = [x for x in excluded if x != objectid]
                result = api('put', 'data-protect/protection-groups/%s' % pg['id'], pg, v=2)
                if apifailed(result):
                    print("   failed to update %s: %s" % (pg['name'], LAST_API_ERROR()))
                    params['excludeObjectIds'] = excluded
                    log(actualname, clustername, pg['name'], 'Error updating PG: %s' % LAST_API_ERROR())
                else:
                    log(actualname, clustername, pg['name'], 'Exclusion Removed')

            heliosCluster('-')

    print("\nDone searching for %s" % vm)

f.close()
print('\nOutput saved to %s\n' % outfile)
