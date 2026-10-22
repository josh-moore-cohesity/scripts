#!/usr/bin/env python
"""Decommission VMware, GCP, Azure and AWS VMs and physical servers from Cohesity protection.

For each object name supplied, this script uses Helios global search to find the
cluster and protection group(s) the object is protected in, connects to that
cluster via Helios and then:

  * removes the object from its protection group(s)
      - VMware / GCP / Azure / AWS VM: removed from the PG object list (or added to the PG's excluded
        objects when it is protected through a folder/tag/auto-protect parent)
      - Physical server: removed from the file/volume PG object list
  * unregisters the source - physical servers only. The vCenter / cloud source is never
    unregistered when decommissioning a VM.

Existing snapshots are not deleted. A PG that would be left with no objects is not
modified unless -deleteemptypg is specified (the PG is then deleted, keeping its
snapshots).

Requires a Helios connection (run with -mcm).

Examples:
    python decomission_object.py -mcm -o myvm01 -o physhost01
    python decomission_object.py -mcm -ol decom_list.txt
    # Preview only, no changes made:
    python decomission_object.py -mcm -ol decom_list.txt -dr
    # Skip the per-object confirmation prompt:
    python decomission_object.py -mcm -ol decom_list.txt -y
    # Restrict to specific clusters when a name exists on more than one:
    python decomission_object.py -mcm -o myvm01 -c coh-p-wtc-bo-cl1
"""

### import pyhesity wrapper module
from pyhesity import *
from datetime import datetime
import codecs
import re
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
parser.add_argument('-o', '--objectname', action='append', type=str, default=None)
parser.add_argument('-ol', '--objectlist', type=str, default=None)
parser.add_argument('-dr', '--dryrun', action='store_true')
parser.add_argument('-y', '--yes', action='store_true')
parser.add_argument('-deleteemptypg', '--deleteemptypg', action='store_true')
parser.add_argument('-outputpath', '--outputpath', type=str, default='./Decommission')

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
objectname = args.objectname
objectlist = args.objectlist
dryrun = args.dryrun
yes = args.yes
deleteemptypg = args.deleteemptypg
outputpath = args.outputpath

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

# get list of objects to decommission
objectnames = gatherList(objectname, objectlist, name='objects', required=True)

# optional list of clusters to restrict the search to
clusternames = gatherList(clustername, clusterlist, name='clusters', required=False)
clusterfilter = [c.lower() for c in clusternames]

# supported object environments
ENV_LABELS = {'kVMware': 'VMware VM', 'kGCP': 'GCP VM', 'kAzure': 'Azure VM', 'kAWS': 'AWS VM', 'kPhysical': 'physical server'}
SUPPORTED_ENVS = list(ENV_LABELS.keys())
# cloud environments: PG environment -> PG params key
CLOUD_PARAMS = {'kGCP': 'gcpParams', 'kAzure': 'azureParams', 'kAWS': 'awsParams'}
CLOUD_SOURCES = {'kGCP': 'GCP', 'kAzure': 'Azure', 'kAWS': 'AWS'}

# Fix special characters in object name that need additional info in URL search string
# i.e. add "25" after a % in a name
def add_chars_after_match(text, pattern, chars_to_add):
    return re.sub(pattern, r'\g<0>' + chars_to_add, text)

# api calls return None, 'error' or {'error': ...} on failure (a 204 on success does not set LAST_ERROR to OK)
def apifailed(result):
    return result is None or result == 'error' or (isinstance(result, dict) and 'error' in result)

# Date and Time
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

# gather all Helios clusters (maps clusterId -> clusterName)
clusterinfo = api('get', 'cluster-mgmt/info', mcmv2=True)
if clusterinfo is None or 'cohesityClusters' not in clusterinfo:
    print('unable to retrieve cluster list from Helios (did you connect with -mcm?)')
    exit(1)
allclusters = clusterinfo['cohesityClusters']

# outfile
os.makedirs(outputpath, exist_ok=True)
if objectlist is not None:
    outfile = os.path.join(outputpath, '%s-%s.csv' % (os.path.basename(objectlist), dateString))
else:
    outfile = os.path.join(outputpath, 'decommission-%s.csv' % dateString)
report = []

def log(obj, cluster, env, pg, action, result):
    report.append('%s,%s,%s,%s,%s,%s' % (obj, cluster, env, pg, action, result))

# find the list of objects a PG protects, and the key used to exclude objects from it
# returns (objects list, params dict holding excludeObjectIds or None) - None if environment unsupported
def getPgObjects(pg):
    env = pg.get('environment')
    if env == 'kVMware':
        params = pg.get('vmwareParams')
        if params is None:
            return None, None
        if params.get('objects') is None:
            params['objects'] = []
        return params['objects'], params
    if env in CLOUD_PARAMS:
        params = pg.get(CLOUD_PARAMS[env])
        if not isinstance(params, dict):
            return None, None
        # objects may sit directly in the params or in a nested protection type params dict
        holder = params
        if 'objects' not in params:
            nested = [v for k, v in params.items() if isinstance(v, dict) and k.endswith('ProtectionTypeParams')]
            withobjects = [v for v in nested if 'objects' in v]
            if len(withobjects) > 0:
                holder = withobjects[0]
            elif len(nested) == 1:
                holder = nested[0]
        if holder.get('objects') is None:
            holder['objects'] = []
        return holder['objects'], holder
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

# remove one object from one PG. returns a result string for the report
def removeFromPg(pgid, pgname, objectId, objname):
    pg = api('get', 'data-protect/protection-groups/%s' % pgid, v=2)
    if apifailed(pg) or not isinstance(pg, dict):
        print('    unable to get protection group "%s"' % pgname)
        return 'Error getting PG'

    pgobjects, vmwareparams = getPgObjects(pg)
    if pgobjects is None:
        print('    protection group "%s" is %s - not supported by this script, skipping' % (pgname, pg.get('environment')))
        return 'Unsupported PG type %s' % pg.get('environment')

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
            # PG would be left empty
            if not deleteemptypg:
                print('    %s is the last object in "%s" - not modified (use -deleteemptypg to delete the PG)' % (objname, pgname))
                return 'Last object in PG - not modified'
            if dryrun:
                print('    [DRY RUN] would delete protection group "%s" (%s is its last object)' % (pgname, objname))
                return 'DRY RUN - would delete PG'
            print('    deleting protection group "%s" (%s is its last object)' % (pgname, objname))
            result = api('delete', 'data-protect/protection-groups/%s?deleteSnapshots=false' % pgid, v=2)
            if apifailed(result):
                print('    failed to delete "%s": %s' % (pgname, LAST_API_ERROR()))
                return 'Error deleting PG'
            return 'PG deleted (last object)'
        action = 'remove %s from' % objname
        pgobjects[:] = remaining
    elif vmwareparams is not None:
        # VM is protected through a parent (folder/tag/project/auto-protect) - exclude it instead
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
        return 'Error updating PG'
    return 'Removed' if len(explicit) > 0 else 'Excluded'

# unregister a physical server. returns a result string for the report
def unregisterPhysical(objectId, objname, cname):
    regs = api('get', 'protectionSources/registrationInfo?environments=kPhysical')
    rootnodes = []
    if not apifailed(regs) and isinstance(regs, dict):
        rootnodes = regs.get('rootNodes') or []
    reg = [r for r in rootnodes if r['rootNode']['id'] == objectId]
    if len(reg) == 0:
        print('    %s is not a registered physical source on %s, nothing to unregister' % (objname, cname))
        return 'Not a registered source'
    if dryrun:
        print('    [DRY RUN] would unregister physical source %s (id %s)' % (objname, objectId))
        return 'DRY RUN - would unregister'
    print('    unregistering physical source %s (id %s)' % (objname, objectId))
    result = api('delete', 'protectionSources/%s' % objectId)
    if apifailed(result):
        print('    failed to unregister %s: %s' % (objname, LAST_API_ERROR()))
        return 'Error unregistering'
    return 'Unregistered'

if dryrun:
    print('\n*** DRY RUN - no changes will be made ***')

for objname in objectnames:
    print('\nSearching for %s...' % objname)

    # Helios global search for the object
    search = api('get', 'data-protect/search/objects?searchString=%s&includeTenants=true' % add_chars_after_match(objname, '%', '25'), v=2)
    if apifailed(search) or 'objects' not in search or search['objects'] is None:
        print('  no results found for %s' % objname)
        log(objname, '', '', '', 'Search', 'Not found')
        continue

    # exact (case-insensitive) VMware / physical name matches only
    matches = [o for o in search['objects']
               if o.get('name', '').lower() == objname.lower() and o.get('environment') in SUPPORTED_ENVS]
    if len(matches) == 0:
        print('  %s not found as a VMware, GCP, Azure or AWS VM or physical server' % objname)
        log(objname, '', '', '', 'Search', 'Not found as VMware, GCP, Azure or AWS VM or physical server')
        continue

    # build the work list: one entry per cluster / object id
    targets = []
    for obj in matches:
        env = obj['environment']
        for opi in (obj.get('objectProtectionInfos') or []):
            clusterId = opi.get('clusterId')
            objectId = opi.get('objectId')
            if objectId is None:
                continue
            pgs = opi.get('protectionGroups') or []
            if len(pgs) == 0 and env != 'kPhysical':
                continue

            cmatch = [c for c in allclusters if c['clusterId'] == clusterId]
            if len(cmatch) == 0:
                print('  cluster id %s (for %s) is not registered in Helios, skipping' % (clusterId, objname))
                continue
            cname = cmatch[0]['clusterName']
            if clusterfilter and cname.lower() not in clusterfilter:
                continue
            if cmatch[0].get('isConnectedToHelios') is False:
                print('  %s is on %s which is disconnected from Helios, skipping' % (objname, cname))
                log(objname, cname, env, '', 'Connect', 'Cluster disconnected')
                continue
            targets.append({'env': env, 'cname': cname, 'objectId': objectId, 'pgs': pgs})

    if len(targets) == 0:
        print('  nothing to decommission for %s' % objname)
        log(objname, '', '', '', 'Search', 'No protection found')
        continue

    for t in targets:
        env = t['env']
        cname = t['cname']
        objectId = t['objectId']
        pgs = t['pgs']
        pgnames = ', '.join([p['name'] for p in pgs]) if len(pgs) > 0 else '(none)'

        print('  %s (%s) on %s - protection groups: %s' % (objname, ENV_LABELS[env], cname, pgnames))
        if env == 'kPhysical':
            print('    physical server will be unregistered after PG removal')
        elif env in CLOUD_SOURCES:
            print('    %s source will NOT be unregistered' % CLOUD_SOURCES[env])
        else:
            print('    vCenter source will NOT be unregistered')

        # confirm before changing anything
        if not dryrun and not yes:
            answer = input('    Decommission %s on %s? (y/N): ' % (objname, cname))
            if answer.strip().lower() not in ['y', 'yes']:
                print('    skipped')
                log(objname, cname, env, pgnames, 'Confirm', 'Skipped by user')
                continue

        # connect to the object's cluster via Helios
        heliosCluster(cname)
        if LAST_API_ERROR() != 'OK':
            print('    unable to connect to %s, skipping' % cname)
            log(objname, cname, env, pgnames, 'Connect', 'Unable to connect')
            continue

        pgfailed = False
        for pg in pgs:
            result = removeFromPg(pg['id'], pg['name'], objectId, objname)
            log(objname, cname, env, pg['name'], 'Remove from PG', result)
            if result.startswith('Error') or result.startswith('Last object') or result.startswith('Unsupported'):
                pgfailed = True

        if env == 'kPhysical':
            if pgfailed:
                print('    not unregistering %s - it is still protected by a protection group' % objname)
                log(objname, cname, env, '', 'Unregister', 'Skipped - PG removal incomplete')
            else:
                log(objname, cname, env, '', 'Unregister', unregisterPhysical(objectId, objname, cname))

        # done with this cluster; clear the access header before the next
        heliosCluster('-')

# write results to report
f = codecs.open(outfile, 'w')
f.write('Object,Cluster,Environment,Protection Group,Action,Result\n')
for item in report:
    f.write('%s\n' % item)
f.write('\n\nThis report (decomission_object.py) was run %s%s' % (datetimestring, ' (DRY RUN)' if dryrun else ''))
f.close()
print('\nOutput saved to %s\n' % outfile)
