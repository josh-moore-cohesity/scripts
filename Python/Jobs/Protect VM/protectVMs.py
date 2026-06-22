#!/usr/bin/env python
"""protect VMware VMs Using Python"""

### import pyhesity wrapper module
from pyhesity import *

### command line arguments
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('-v', '--vip', type=str, default='helios.cohesity.com')
parser.add_argument('-u', '--username', type=str, default='helios')
parser.add_argument('-d', '--domain', type=str, default='local')
parser.add_argument('-c', '--clustername', type=str, default=None)
parser.add_argument('-mcm', '--mcm', action='store_true')
parser.add_argument('-i', '--useApiKey', action='store_true')
parser.add_argument('-pwd', '--password', type=str, default=None)
parser.add_argument('-np', '--noprompt', action='store_true')
parser.add_argument('-m', '--mfacode', type=str, default=None)
parser.add_argument('-e', '--emailmfacode', action='store_true')
parser.add_argument('-j', '--jobname', type=str, required=True)
parser.add_argument('-n', '--vmname', action='append', type=str)
parser.add_argument('-l', '--vmlist', type=str)
parser.add_argument('-vc', '--vcentername', type=str, default=None)
parser.add_argument('-sd', '--storagedomain', type=str, default='DefaultStorageDomain')
parser.add_argument('-p', '--policyname', type=str, default=None)
parser.add_argument('-tz', '--timezone', type=str, default='US/Eastern')
parser.add_argument('-st', '--starttime', type=str, default='21:00')
parser.add_argument('-is', '--incrementalsla', type=int, default=60)
parser.add_argument('-fs', '--fullsla', type=int, default=120)
parser.add_argument('-z', '--pause', action='store_true')
parser.add_argument('-ei', '--enableindexing', action='store_true')
parser.add_argument('-di', '--disableindexing', action='store_true')
parser.add_argument('-ea', '--emailalerts', type=str, action='append', default=None)
# Indexing path arguments
parser.add_argument('-ip', '--includepath', type=str, action='append', default=None)
parser.add_argument('-ep', '--excludepath', type=str, action='append', default=None)
parser.add_argument('-aip', '--addincludepath', type=str, action='append', default=None)
parser.add_argument('-aep', '--addexcludepath', type=str, action='append', default=None)
parser.add_argument('-rip', '--removeincludepath', type=str, action='append', default=None)
parser.add_argument('-rep', '--removeexcludepath', type=str, action='append', default=None)
parser.add_argument('-ud', '--usedefaults', action='store_true')

args = parser.parse_args()

vip = args.vip
username = args.username
domain = args.domain
clustername = args.clustername
mcm = args.mcm
useApiKey = args.useApiKey
password = args.password
noprompt = args.noprompt
mfacode = args.mfacode
emailmfacode = args.emailmfacode
jobname = args.jobname
vmname = args.vmname
vmlist = args.vmlist
vcentername = args.vcentername
storagedomain = args.storagedomain
policyname = args.policyname
starttime = args.starttime
timezone = args.timezone
incrementalsla = args.incrementalsla
fullsla = args.fullsla
pause = args.pause
enableindexing = args.enableindexing
disableindexing = args.disableindexing
emailalerts = args.emailalerts
includepaths = args.includepath
excludepaths = args.excludepath
addincludepaths = args.addincludepath
addexcludepaths = args.addexcludepath
removeincludepaths = args.removeincludepath
removeexcludepaths = args.removeexcludepath
usedefaults = args.usedefaults

# Default indexing exclude paths for new jobs
DEFAULT_EXCLUDE_PATHS = [
    "/$Recycle.Bin",
    "/Windows",
    "/Program Files",
    "/Program Files (x86)",
    "/ProgramData",
    "/System Volume Information",
    "/Users/*/AppData",
    "/Recovery",
    "/var",
    "/usr",
    "/sys",
    "/proc",
    "/lib",
    "/grub",
    "/grub2",
    "/opt/splunk",
    "/splunk"
]

DEFAULT_INCLUDE_PATHS = ["/"]

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


def updateIndexingPolicy(job):
    """Apply any indexing policy changes to the job dict in place."""

    # Ensure the indexingPolicy key exists (it should on any fetched job, but be safe)
    if 'indexingPolicy' not in job['vmwareParams']:
        job['vmwareParams']['indexingPolicy'] = {
            "enableIndexing": False,
            "includePaths": list(DEFAULT_INCLUDE_PATHS),
            "excludePaths": list(DEFAULT_EXCLUDE_PATHS)
        }

    policy = job['vmwareParams']['indexingPolicy']
    
    if usedefaults:
        policy['includePaths'] = list(DEFAULT_INCLUDE_PATHS)
        policy['excludePaths'] = list(DEFAULT_EXCLUDE_PATHS)
        print('    includePaths/excludePaths reset to defaults')

        
    # Toggle indexing on/off
    if enableindexing:
        policy['enableIndexing'] = True
        print('    indexing enabled')
    if disableindexing:
        policy['enableIndexing'] = False
        print('    indexing disabled')

    # Full replace of include/exclude paths
    if includepaths is not None:
        policy['includePaths'] = includepaths
        print('    includePaths set to: %s' % includepaths)

    if excludepaths is not None:
        policy['excludePaths'] = excludepaths
        print('    excludePaths set to: %s' % excludepaths)

    # Additive changes to include paths
    if addincludepaths is not None:
        for p in addincludepaths:
            if p not in policy['includePaths']:
                policy['includePaths'].append(p)
                print('    added includePath: %s' % p)
            else:
                print('    includePath already exists: %s' % p)

    # Additive changes to exclude paths
    if addexcludepaths is not None:
        for p in addexcludepaths:
            if p not in policy['excludePaths']:
                policy['excludePaths'].append(p)
                print('    added excludePath: %s' % p)
            else:
                print('    excludePath already exists: %s' % p)

    # Remove specific include paths
    if removeincludepaths is not None:
        for p in removeincludepaths:
            if p in policy['includePaths']:
                policy['includePaths'].remove(p)
                print('    removed includePath: %s' % p)
            else:
                print('    includePath not found (skipping): %s' % p)

    # Remove specific exclude paths
    if removeexcludepaths is not None:
        for p in removeexcludepaths:
            if p in policy['excludePaths']:
                policy['excludePaths'].remove(p)
                print('    removed excludePath: %s' % p)
            else:
                print('    excludePath not found (skipping): %s' % p)


vmnames = gatherList(vmname, vmlist, name='VMs', required=False)  # not required — may just be updating indexing

isPaused = True if pause else False
indexingEnabled = True if enableindexing else False

# authenticate
apiauth(vip=vip, username=username, domain=domain, password=password, useApiKey=useApiKey, helios=mcm, prompt=(not noprompt), emailMfaCode=emailmfacode, mfaCode=mfacode)

# if connected to helios or mcm, select access cluster
if mcm or vip.lower() == 'helios.cohesity.com':
    if clustername is not None:
        heliosCluster(clustername)
    else:
        print('-clustername is required when connecting to Helios or MCM')
        exit()

# exit if not authenticated
if apiconnected() is False:
    print('authentication failed')
    exit(1)

# get vCenter protection source
vcenters = api('get', 'protectionSources/rootNodes?environments=kVMware')

# find existing job
job = None
jobs = api('get', 'data-protect/protection-groups?environments=kVMware&isDeleted=false&isActive=true', v=2)
if jobs['protectionGroups'] is not None:
    jobs = [j for j in jobs['protectionGroups'] if j['name'].lower() == jobname.lower()]
    if jobs is not None and len(jobs) > 0:
        job = jobs[0]

if job is not None:
    newJob = False
    vcenter = [v for v in vcenters if v['protectionSource']['id'] == job['vmwareParams']['sourceId']][0]

    if emailalerts is not None and len(emailalerts) > 0:
        job['alertPolicy']['alertTargets'] = [
            {
                "emailAddress": e,
                "language": "en-us",
                "recipientType": "kTo"
            }
            for e in emailalerts
        ]

    # Apply indexing policy updates to existing job
    anyIndexingChange = any([
        enableindexing, disableindexing,
        includepaths, excludepaths,
        addincludepaths, addexcludepaths,
        removeincludepaths, removeexcludepaths,
        usedefaults
    ])
    if anyIndexingChange:
        print('Updating indexing policy for job %s' % jobname)
        updateIndexingPolicy(job)

else:
    # new job
    newJob = True

    if len(vmnames) == 0:
        print('No VMs specified — required for new jobs')
        exit(1)

    # get vcenter
    if vcentername is None:
        print('vcentername required')
        exit(1)
    else:
        vcenter = [v for v in vcenters if v['protectionSource']['name'].lower() == vcentername.lower()]
        if not vcenters or len(vcenters) == 0:
            print('vCenter %s not registered' % vcentername)
            exit(1)
        else:
            vcenter = vcenters[0]

    # get policy
    if policyname is None:
        print('Policy name required')
        exit(1)
    else:
        policy = [p for p in (api('get', 'data-protect/policies', v=2))['policies'] if p['name'].lower() == policyname.lower()]
        if policy is None or len(policy) == 0:
            print('Policy %s not found' % policyname)
            exit(1)
        else:
            policy = policy[0]

    # get storageDomain
    viewBox = [v for v in api('get', 'viewBoxes') if v['name'].lower() == storagedomain.lower()]
    if viewBox is None or len(viewBox) == 0:
        print('Storage Domain %s not found' % storagedomain)
        exit(1)
    else:
        viewBox = viewBox[0]

    # parse starttime
    try:
        (hour, minute) = starttime.split(':')
        hour = int(hour)
        minute = int(minute)
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            print('starttime is invalid!')
            exit(1)
    except Exception:
        print('starttime is invalid!')
        exit(1)

    # Build indexing policy for new job — respect overrides if provided
    newIncludePaths = includepaths if includepaths is not None else list(DEFAULT_INCLUDE_PATHS)
    newExcludePaths = excludepaths if excludepaths is not None else list(DEFAULT_EXCLUDE_PATHS)

    # new job params
    job = {
        "name": jobname,
        "environment": "kVMware",
        "isPaused": isPaused,
        "policyId": policy['id'],
        "priority": "kMedium",
        "storageDomainId": viewBox['id'],
        "description": "",
        "startTime": {
            "hour": hour,
            "minute": minute,
            "timeZone": timezone
        },
        "abortInBlackouts": False,
        "alertPolicy": {
            "backupRunStatus": [
                "kFailure", "kSlaViolation"
            ],
            "alertTargets": [{"emailAddress": emailalerts}]
        },
        "sla": [
            {
                "backupRunType": "kFull",
                "slaMinutes": fullsla
            },
            {
                "backupRunType": "kIncremental",
                "slaMinutes": incrementalsla
            }
        ],
        "qosPolicy": "kBackupHDD",
        "vmwareParams": {
            "sourceId": vcenter['protectionSource']['id'],
            "objects": [],
            "excludeObjectIds": [],
            "vmTagIds": [],
            "excludeVmTagIds": [],
            "appConsistentSnapshot": False,
            "fallbackToCrashConsistentSnapshot": False,
            "skipPhysicalRDMDisks": False,
            "globalExcludeDisks": [],
            "leverageHyperflexSnapshots": False,
            "leverageStorageSnapshots": False,
            "cloudMigration": False,
            "indexingPolicy": {
                "enableIndexing": indexingEnabled,
                "includePaths": newIncludePaths,
                "excludePaths": newExcludePaths
            }
        }
    }

    # Apply additive/removal path changes on top of new job defaults
    updateIndexingPolicy(job)


# Add VMs if specified
if len(vmnames) > 0:
    vms = api('get', 'protectionSources/virtualMachines?id=%s' % vcenter['protectionSource']['id'])
    for thisvmname in vmnames:
        thisvm = [v for v in vms if v['name'].lower() == thisvmname.lower()]
        if thisvm is not None and len(thisvm) > 0:
            thisvm = thisvm[0]
            if thisvm['id'] not in [o['id'] for o in job['vmwareParams']['objects']]:
                newobject = {
                    "excludeDisks": None,
                    "id": thisvm['id'],
                    "name": thisvm['name'],
                    "isAutoprotected": False
                }
                job['vmwareParams']['objects'].append(newobject)
            print('    protecting %s' % thisvmname)
        else:
            print('    warning: %s not found' % thisvmname)

# create or update job
if newJob is True:
    print('Creating protection job %s' % jobname)
    result = api('post', 'data-protect/protection-groups', job, v=2)
else:
    print('Updating protection job %s' % jobname)
    result = api('put', 'data-protect/protection-groups/%s' % job['id'], job, v=2)
