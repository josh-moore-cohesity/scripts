#!/usr/bin/env python
"""Clone one or more SQL databases from a Cohesity protection job"""

### import pyhesity wrapper module
from pyhesity import *
import time

### command line arguments
import argparse
parser = argparse.ArgumentParser()
# authentication
parser.add_argument('-v', '--vip', type=str, default='helios.cohesity.com')
parser.add_argument('-u', '--username', type=str, default='helios')
parser.add_argument('-d', '--domain', type=str, default='local')
parser.add_argument('-i', '--useApiKey', action='store_true')
parser.add_argument('-pwd', '--password', type=str, default=None)
parser.add_argument('-np', '--noprompt', action='store_true')
parser.add_argument('-t', '--tenant', type=str, default=None)
parser.add_argument('-mcm', '--mcm', action='store_true')
parser.add_argument('-m', '--mfacode', type=str, default=None)
parser.add_argument('-e', '--emailmfacode', action='store_true')
parser.add_argument('-c', '--clustername', type=str, default=None)
# source/target selection
parser.add_argument('-ss', '--sourceserver', type=str, required=True)
parser.add_argument('-sd', '--sourcedb', nargs='+', type=str, default=None)
parser.add_argument('-sl', '--sourcedblist', type=str, default=None)
parser.add_argument('-ts', '--targetserver', type=str, default=None)
parser.add_argument('-p', '--prefix', type=str, default='')
parser.add_argument('-sx', '--suffix', type=str, default='')
parser.add_argument('-ti', '--targetinstance', type=str, default='MSSQLSERVER')
parser.add_argument('-lt', '--logtime', type=str, default=None, help="point in time log replay like '2019-09-29 17:51:01'")
parser.add_argument('-nl', '--nologs', action='store_true')
parser.add_argument('-latest', '--latest', action='store_true')
parser.add_argument('-dbg', '--debug', action='store_true')

args = parser.parse_args()

vip = args.vip
username = args.username
domain = args.domain
useapikey = args.useApiKey
password = args.password
noprompt = args.noprompt
tenant = args.tenant
mcm = args.mcm
mfacode = args.mfacode
emailmfacode = args.emailmfacode
clustername = args.clustername

sourceserver = args.sourceserver
sourcedb = args.sourcedb
sourcedblist = args.sourcedblist
targetserver = args.targetserver if args.targetserver is not None else sourceserver
prefix = args.prefix
suffix = args.suffix
targetinstance = args.targetinstance
logtime = args.logtime
nologs = args.nologs
latest = args.latest
debug = args.debug


# gather database name list from command line params and/or file
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
        print('No %s specified' % name)
        exit(1)
    return sorted(set(items))


dbnames = gatherList(sourcedb, sourcedblist, name='databases', required=True)

# authenticate
apiauth(vip=vip, username=username, domain=domain, password=password, useApiKey=useapikey,
        helios=mcm, prompt=(not noprompt), mfaCode=mfacode, emailMfaCode=emailmfacode, tenantId=tenant)

# exit if not authenticated
if apiconnected() is False:
    print('Not authenticated')
    exit(1)

# select helios/mcm managed cluster
if mcm or vip.lower() == 'helios.cohesity.com':
    if clustername:
        heliosCluster(clustername)
        if LAST_API_ERROR() != 'OK':
            exit(1)
    else:
        print('Please provide -c/--clustername when connecting through Helios')
        exit(1)

for dbname in dbnames:

    # search for database to clone
    searchresults = api('get', '/searchvms?environment=SQL&entityTypes=kSQL&entityTypes=kVMware&vmName=%s&runTypes=kRegular,kFull' % dbname)

    # handle source instance name e.g. instance/dbname
    if '/' in dbname:
        dbname = dbname.split('/')[1]

    # narrow the search results to the correct source server
    dbresults = []
    if searchresults is not None and 'vms' in searchresults:
        dbresults = [vm for vm in searchresults['vms'] if sourceserver in vm['vmDocument'].get('objectAliases', [])]
    if not dbresults:
        print('Server %s Not Found' % sourceserver)
        exit(1)

    # narrow the search results to the correct source database
    dbresults = [vm for vm in dbresults if vm['vmDocument']['objectId']['entity']['sqlEntity']['databaseName'] == dbname]
    if not dbresults:
        print('Database %s Not Found' % dbname)
        continue

    # gather all versions from all matching results
    dbversions = []
    for dbresult in dbresults:
        for version in dbresult['vmDocument']['versions']:
            version['vmDocument'] = dbresult['vmDocument']
            version['registeredSource'] = dbresult['registeredSource']
            dbversions.append(version)
    dbversions = sorted(dbversions, key=lambda v: v['instanceId']['jobStartTimeUsecs'], reverse=True)

    # if there are multiple results (e.g. old/new jobs?) select the one with the newest snapshot
    latestdb = max(dbresults, key=lambda db: db['vmDocument']['versions'][0]['snapshotTimestampUsecs'])
    if latestdb is None:
        print('Database %s Not Found' % dbname)
        continue

    latestdbdoc = dbversions[0]['vmDocument']

    # identify physical or vm
    entitytype = latestdb['registeredSource']['type']

    # search for source and target servers
    entities = api('get', '/appEntities?appEnvType=3&envType=%s' % entitytype)
    ownerid = latestdbdoc['objectId']['entity']['sqlEntity']['ownerId']
    targetentitymatches = [e for e in entities if e['appEntity']['entity']['displayName'] == targetserver]

    if not targetentitymatches:
        print('Target Server %s Not Found' % targetserver)
        exit(1)
    targetentity = targetentitymatches[0]

    dbid = latestdbdoc['objectId']['entity']['id']

    # handle log replay
    versionnum = 0
    validlogtime = False
    uselogtime = False
    latestusecs = 0
    oldestusecs = 0
    logusecs = None
    logstart = None
    logend = None

    if logtime or latest:
        if logtime:
            logusecs = dateToUsecs(logtime)
            logusecsdaystart = dbversions[-1]['instanceId']['jobStartTimeUsecs']
            logdaystart = '%s 00:00:00' % logtime.split(' ')[0]
            logusecsdayend = dateToUsecs(logdaystart) + 86399000000
            dbversions = [v for v in dbversions if v['snapshotTimestampUsecs'] < (logusecs + 60000000)]
        elif latest:
            logusecsdayend = dateToUsecs()

        for version in dbversions:
            if latest:
                logusecsdaystart = version['snapshotTimestampUsecs']
            snapshottimestampusecs = version['snapshotTimestampUsecs']
            oldestusecs = snapshottimestampusecs
            timerangequery = {
                'endTimeUsecs': logusecsdayend,
                'protectionSourceId': dbid,
                'environment': 'kSQL',
                'jobUids': [
                    {
                        'clusterId': version['vmDocument']['objectId']['jobUid']['clusterId'],
                        'clusterIncarnationId': version['vmDocument']['objectId']['jobUid']['clusterIncarnationId'],
                        'id': version['vmDocument']['objectId']['jobUid']['objectId']
                    }
                ],
                'startTimeUsecs': logusecsdaystart
            }
            pointsfortimerange = api('post', 'restore/pointsForTimeRange', timerangequery)
            if pointsfortimerange is not None and 'timeRanges' in pointsfortimerange:
                # log backups available
                for timerange in pointsfortimerange['timeRanges']:
                    logstart = timerange['startTimeUsecs']
                    logend = timerange['endTimeUsecs']
                    if latestusecs == 0:
                        latestusecs = logend - 1000000
                    if latest:
                        logusecs = logend - 1000000
                    if (logusecs - 1000000) <= snapshottimestampusecs or snapshottimestampusecs >= (logusecs + 1000000):
                        validlogtime = True
                        uselogtime = False
                        break
                    elif logstart <= logusecs <= logend and logusecs >= (snapshottimestampusecs - 1000000):
                        validlogtime = True
                        uselogtime = True
                        break
            else:
                # no log backups available
                for snapshot in (pointsfortimerange or {}).get('fullSnapshotInfo', []):
                    if latestusecs == 0:
                        latestusecs = snapshot['restoreInfo']['startTimeUsecs']
                    if logtime:
                        if snapshot['restoreInfo']['startTimeUsecs'] <= (logusecs + 60000000):
                            validlogtime = True
                            uselogtime = False
                            break
                    elif latest:
                        validlogtime = True
                        uselogtime = False
                        break
            if latestusecs == 0:
                latestusecs = oldestusecs
            if validlogtime:
                break
            versionnum += 1

        if not validlogtime:
            print('log time is out of range')
            print('Valid range is %s to %s' % (usecsToDate(oldestusecs), usecsToDate(latestusecs)))
            exit(1)

    if validlogtime is False:
        versionnum = 0

    taskname = 'CloneSQL-%s-%s-%s%s%s' % (targetserver, targetinstance, prefix, dbname, suffix)

    # create new clone task (RestoreAppArg Object)
    clonetask = {
        'name': taskname,
        'action': 'kCloneApp',
        'restoreAppParams': {
            'type': 3,
            'ownerRestoreInfo': {
                'ownerObject': {
                    'attemptNum': dbversions[versionnum]['instanceId']['attemptNum'],
                    'jobUid': dbversions[versionnum]['vmDocument']['objectId']['jobUid'],
                    'jobId': dbversions[versionnum]['vmDocument']['objectId']['jobId'],
                    'jobInstanceId': dbversions[versionnum]['instanceId']['jobInstanceId'],
                    'startTimeUsecs': dbversions[versionnum]['instanceId']['jobStartTimeUsecs'],
                    'entity': {
                        'id': ownerid
                    }
                },
                'ownerRestoreParams': {
                    'action': 'kCloneVMs',
                    'powerStateConfig': {}
                },
                'performRestore': False
            },
            'restoreAppObjectVec': [
                {
                    'appEntity': dbversions[versionnum]['vmDocument']['objectId']['entity'],
                    'restoreParams': {
                        'sqlRestoreParams': {
                            'captureTailLogs': False,
                            'instanceName': targetinstance,
                            'newDatabaseName': '%s%s%s' % (prefix, dbname, suffix)
                        },
                        'targetHost': targetentity['appEntity']['entity'],
                        'targetHostParentSource': {
                            'id': targetentity['appEntity']['entity']['parentId']
                        }
                    }
                }
            ]
        }
    }

    # apply log replay time
    if validlogtime is True:
        if not nologs and uselogtime is True:
            clonetask['restoreAppParams']['restoreAppObjectVec'][0]['restoreParams']['sqlRestoreParams']['restoreTimeSecs'] = int(logusecs / 1000000)
    else:
        if logtime:
            print('LogTime of %s is out of range' % logtime)
            print('Available range is %s to %s' % (usecsToDate(logstart), usecsToDate(logend)))
            continue

    if debug:
        display(clonetask)
        exit(0)

    # execute the clone task (post /cloneApplication api call)
    response = api('post', '/cloneApplication', clonetask)

    if response:
        taskid = response['restoreTask']['performRestoreTaskState']['base']['taskId']
        print('Cloning %s to %s as %s (task name: %s)' % (dbname, targetserver, '%s%s%s' % (prefix, dbname, suffix), taskname))
    else:
        print('No Response')
        continue

    status = 'started'
    finishedstates = ('kCanceled', 'kSuccess', 'kFailure')
    publicstatus = None
    while status != 'completed':
        task = api('get', '/restoretasks/%s' % taskid)
        publicstatus = task['restoreTask']['performRestoreTaskState']['base']['publicStatus']
        if publicstatus in finishedstates:
            status = 'completed'
        else:
            time.sleep(3)
    print('Clone task completed with status: %s' % publicstatus)
    if publicstatus == 'kFailure':
        print('Error Message: %s' % task['restoreTask']['performRestoreTaskState']['base']['error']['errorMsg'])

exit(0)
