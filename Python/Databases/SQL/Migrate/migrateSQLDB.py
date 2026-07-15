#!/usr/bin/env python
"""Initiate, sync, finalize, cancel or list SQL database migrations"""

### import pyhesity wrapper module
from pyhesity import *
from datetime import datetime
import re

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
parser.add_argument('-ss', '--sourceserver', type=str, default='')
parser.add_argument('-sd', '--sourcedb', action='append', type=str)
parser.add_argument('-si', '--sourceinstance', type=str, default=None)
parser.add_argument('-sl', '--sourcedblist', type=str, default=None)
parser.add_argument('-ts', '--targetserver', type=str, default='')
parser.add_argument('-td', '--targetdb', type=str, default='')
parser.add_argument('-ow', '--overwrite', action='store_true')
parser.add_argument('-mf', '--mdffolder', type=str, default=None)
parser.add_argument('-lf', '--ldffolder', type=str, default=None)
parser.add_argument('-nf', '--ndffolders', action='append', type=str, help="format: '.*pattern.ndf=D:\\path'")
parser.add_argument('-ti', '--targetinstance', type=str, default=None)
parser.add_argument('-nr', '--norecovery', action='store_true')
parser.add_argument('-kc', '--keepcdc', action='store_true')
parser.add_argument('-sp', '--showpaths', action='store_true')
parser.add_argument('-usp', '--usesourcepaths', action='store_true')
parser.add_argument('-ms', '--manualsync', action='store_true')
# mode
parser.add_argument('-init', '--init', action='store_true')
parser.add_argument('-sync', '--sync', action='store_true')
parser.add_argument('-fin', '--finalize', action='store_true')
parser.add_argument('-x', '--cancel', action='store_true')
# filters (sync/finalize/cancel/list modes)
parser.add_argument('-sa', '--showall', action='store_true')
parser.add_argument('-db', '--daysback', type=int, default=30)
parser.add_argument('-n', '--name', type=str, default='')
parser.add_argument('-f', '--filter', type=str, default='')
parser.add_argument('-id', '--id', type=str, default='')
parser.add_argument('-rt', '--returntaskids', action='store_true')
parser.add_argument('-dbg', '--debug', action='store_true', help='dump raw JSON of matched migrations and exit')

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
sourceinstance = args.sourceinstance
sourcedblist = args.sourcedblist
targetserver = args.targetserver
targetdb = args.targetdb
mdffolder = args.mdffolder
ldffolder = args.ldffolder if args.ldffolder is not None else args.mdffolder
targetinstance = args.targetinstance
norecovery = args.norecovery
keepcdc = args.keepcdc
showpaths = args.showpaths
usesourcepaths = args.usesourcepaths
manualsync = args.manualsync
init = args.init
sync = args.sync
finalize = args.finalize
cancel = args.cancel
showall = args.showall
daysback = args.daysback
name = args.name
namefilter = args.filter
id = args.id
returntaskids = args.returntaskids


# gather list from command line params and file
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
        exit()
    return sorted(set(items))


sourcedbs = gatherList(sourcedb, sourcedblist, name='sourceDBs', required=False)
if not sourcedbs:
    sourcedbs = ['']

migrationcount = 0

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

# demand parameters for init mode
if init or showpaths:
    if sourceserver == '':
        print('-ss/--sourceserver is required')
        exit(1)
    if not sourcedbs or sourcedbs == ['']:
        print('-sd/--sourcedb is required')
        exit(1)
if init:
    if targetserver == '':
        print('-ts/--targetserver is required')
        exit(1)

# handle alternate secondary data file locations
secondaryfilelocationtemplate = []
if args.ndffolders:
    for entry in args.ndffolders:
        (filepattern, targetdirectory) = entry.split('=', 1)
        secondaryfilelocationtemplate.append({'filePattern': filepattern, 'targetDirectory': targetdirectory})

isautosyncenabled = not manualsync

notargetdbspecified = True
if targetdb != '':
    notargetdbspecified = False
    if len(sourcedbs) > 1:
        print('-td/--targetdb not supported with multiple DBs')
        exit()

taskids = []
sourcenames = {}
entities = None
daysbackusecs = timeAgo(daysback, 'days')

allmigrations = []
tasks = []
if not init:
    recoveries = api('get', 'data-protect/recoveries?snapshotEnvironments=kSQL&recoveryActions=RecoverApps&startTimeUsecs=%s' % daysbackusecs, v=2)
    if recoveries is not None and 'recoveries' in recoveries:
        allmigrations = recoveries['recoveries']
    if not showall:
        allmigrations = [m for m in allmigrations if m['status'] in ('OnHold', 'Running')]
    tasks = api('get', '/restoretasks?restoreTypes=kRestoreApp&startTimeUsecs=%s' % daysbackusecs)
    if tasks is None:
        tasks = []

sqlsources = api('get', 'protectionSources/registrationInfo?environments=kSQL')
sqlsource = None
if sourceserver != '':
    matches = [n for n in sqlsources.get('rootNodes', []) if n.get('rootNode', {}).get('name', '').lower() == sourceserver.lower()]
    if not matches:
        print('sourceServer %s not found' % sourceserver)
        exit()
    sqlsource = matches[0]

for s in sourcedbs:
    thissourcedb = str(s)
    if len(sourcedbs) > 1:
        targetdb = thissourcedb
    if targetdb == '':
        targetdb = thissourcedb

    # handle source instance name e.g. instance/dbname
    if '/' in thissourcedb:
        if targetdb == thissourcedb:
            targetdb = thissourcedb.split('/')[1]
        (sourceinstance, thissourcedb) = thissourcedb.split('/')
    elif not sourceinstance:
        sourceinstance = 'MSSQLSERVER'

    if init or showpaths:
        # search for database to clone
        searchresults = api('get', '/searchvms?environment=SQL&entityTypes=kSQL&entityTypes=kVMware&vmName=%s/%s' % (sourceinstance, thissourcedb))

        # narrow the search results to the correct source server
        dbresults = []
        if searchresults is not None and 'vms' in searchresults:
            dbresults = [vm for vm in searchresults['vms']
                         if sourceserver in vm['vmDocument'].get('objectAliases', [])
                         and vm['vmDocument']['objectId']['entity']['sqlEntity']['databaseName'] == thissourcedb
                         and vm['vmDocument']['objectName'] == '%s/%s' % (sourceinstance, thissourcedb)]

        if not dbresults:
            print('Database %s/%s on Server %s Not Found' % (sourceinstance, thissourcedb, sourceserver))
            continue

        # if there are multiple results (e.g. old/new jobs?) select the one with the newest snapshot
        latestdb = max(dbresults, key=lambda db: db['vmDocument']['versions'][0]['snapshotTimestampUsecs'])

        if showpaths:
            print("\n{0:<30}{1:<15}{2}".format('logicalName', 'Size (MiB)', 'fullPath'))
            print("{0:<30}{1:<15}{2}".format('-----------', '----------', '--------'))
            for f in latestdb['vmDocument']['objectId']['entity']['sqlEntity']['dbFileInfoVec']:
                print("{0:<30}{1:<15.2f}{2}".format(f['logicalName'], f['sizeBytes'] / (1024 * 1024), f['fullPath']))

            print("\nExample Restore Path Parameters:\n")

            ndffolderexample = ''
            mdffolderexample = ''
            ldffolderexample = ''
            for f in latestdb['vmDocument']['objectId']['entity']['sqlEntity']['dbFileInfoVec']:
                filename = f['fullPath'].split('/')[-1].split('\\')[-1]
                filepath = f['fullPath'].rsplit('/', 1)[0].rsplit('\\', 1)[0].replace('/', '\\')
                extension = '.' + filename.split('.')[-1]
                if f['type'] == 0:
                    if mdffolderexample == '' and extension == '.mdf':
                        mdffolderexample = filepath
                    else:
                        ndffolderexample += "-nf '.*%s=%s' " % (filename, filepath)
                else:
                    if ldffolderexample == '':
                        ldffolderexample = filepath
            print("-mdffolder %s -ldffolder %s %s\n" % (mdffolderexample, ldffolderexample, ndffolderexample))
            continue

        # identify physical or vm
        entitytype = latestdb['registeredSource']['type']

        # search for source server
        if entities is None:
            entities = api('get', '/appEntities?appEnvType=3&envType=%s' % entitytype)

        ownerid = latestdb['vmDocument']['objectId']['entity']['sqlEntity']['ownerId']

        versionnum = 0
        dbversions = latestdb['vmDocument']['versions']

        restoretaskname = "Migrate-%s_%s_%s_%s" % (sourceserver, sourceinstance, s, datetime.now().strftime('%b_%d_%Y_%H-%M%p'))

        secondaryfilelocation = list(secondaryfilelocationtemplate)

        # create new clone task (RestoreAppArg Object)
        restoretask = {
            "name": restoretaskname,
            'action': 'kRecoverApp',
            'restoreAppParams': {
                'type': 3,
                'ownerRestoreInfo': {
                    "ownerObject": {
                        "attemptNum": dbversions[versionnum]['instanceId']['attemptNum'],
                        "jobUid": latestdb['vmDocument']['objectId']['jobUid'],
                        "jobId": latestdb['vmDocument']['objectId']['jobId'],
                        "jobInstanceId": dbversions[versionnum]['instanceId']['jobInstanceId'],
                        "startTimeUsecs": dbversions[versionnum]['instanceId']['jobStartTimeUsecs'],
                        "entity": {
                            "id": ownerid
                        }
                    },
                    'ownerRestoreParams': {
                        'action': 'kRecoverVMs',
                        'powerStateConfig': {}
                    },
                    'performRestore': False
                },
                'restoreAppObjectVec': [
                    {
                        "appEntity": latestdb['vmDocument']['objectId']['entity'],
                        'restoreParams': {
                            'sqlRestoreParams': {
                                'captureTailLogs': False,
                                'secondaryDataFileDestinationVec': [],
                                'alternateLocationParams': {},
                                "isAutoSyncEnabled": isautosyncenabled,
                                "isMultiStageRestore": True
                            }
                        }
                    }
                ]
            }
        }

        # noRecovery
        if norecovery:
            restoretask['restoreAppParams']['restoreAppObjectVec'][0]['restoreParams']['sqlRestoreParams']['withNoRecovery'] = True

        # keepCDC
        if keepcdc:
            restoretask['restoreAppParams']['restoreAppObjectVec'][0]['restoreParams']['sqlRestoreParams']['keepCdc'] = True

        # alt location params
        if usesourcepaths:
            mdffolderfound = False
            ldffolderfound = False
            for datafile in latestdb['vmDocument']['objectId']['entity']['sqlEntity']['dbFileInfoVec']:
                path = datafile['fullPath'][:datafile['fullPath'].rfind('\\')]
                if datafile['type'] == 0:
                    if mdffolderfound is False:
                        mdffolder = path
                        mdffolderfound = True
                    else:
                        secondaryfilelocation.append({'filePattern': datafile['fullPath'], 'targetDirectory': path})
                if datafile['type'] == 1:
                    if ldffolderfound is False:
                        ldffolder = path
                        ldffolderfound = True

        if init:
            if not targetinstance:
                targetinstance = 'MSSQLSERVER'
            if not mdffolder:
                print('-mf/--mdffolder must be specified when restoring to a new database name or different target server')
                exit()
            sqlrestoreparams = restoretask['restoreAppParams']['restoreAppObjectVec'][0]['restoreParams']['sqlRestoreParams']
            sqlrestoreparams['dataFileDestination'] = mdffolder
            sqlrestoreparams['logFileDestination'] = ldffolder
            sqlrestoreparams['secondaryDataFileDestinationVec'] = secondaryfilelocation
            sqlrestoreparams['newDatabaseName'] = targetdb

            # search for target server
            targetentitymatches = [e for e in entities if e['appEntity']['entity']['displayName'].lower() == targetserver.lower()]
            if not targetentitymatches:
                print('Target Server Not Found')
                exit(1)
            targetentity = targetentitymatches[0]
            restoretask['restoreAppParams']['restoreAppObjectVec'][0]['restoreParams']['targetHost'] = targetentity['appEntity']['entity']
            restoretask['restoreAppParams']['restoreAppObjectVec'][0]['restoreParams']['targetHostParentSource'] = {'id': targetentity['appEntity']['entity']['parentId']}
            sqlrestoreparams['instanceName'] = targetinstance if targetinstance else 'MSSQLSERVER'

            # execute the recovery task (post /recoverApplication api call)
            response = api('post', '/recoverApplication', restoretask)

            if response:
                print('Initiating migration of %s/%s to %s/%s/%s' % (sourceinstance, thissourcedb, targetserver, targetinstance, targetdb))
                continue
            else:
                print('An error occured')
                continue

    if allmigrations and not init:
        migrations = allmigrations
        if name != '':
            migrations = [m for m in migrations if m['name'].lower() == name.lower()]
        if id != '':
            migrations = [m for m in migrations if m['id'] == id]
        if namefilter != '':
            migrations = [m for m in migrations if re.search(namefilter, m['name'], re.IGNORECASE)]

        def recoverappparams(migration):
            rap = migration['mssqlParams'].get('recoverAppParams')
            if isinstance(rap, dict):
                return [rap]
            return rap or [{}]

        def gettargetdbname(rapitem):
            # newSourceConfig only carries a database name when the recovery renamed the DB;
            # an unrenamed migration keeps the source database name (from objectInfo.name)
            newsourceconfig = rapitem.get('sqlTargetParams', {}).get('newSourceConfig', {})
            dbname = newsourceconfig.get('databaseName') or newsourceconfig.get('newDatabaseName') or rapitem.get('sqlTargetParams', {}).get('newDatabaseName')
            if dbname:
                return dbname
            objectinfoname = rapitem.get('objectInfo', {}).get('name', '')
            if '/' in objectinfoname:
                return objectinfoname.split('/', 1)[1]
            return objectinfoname

        if thissourcedb != '':
            filtered = []
            for m in migrations:
                rap = recoverappparams(m)
                if 'objects' in m['mssqlParams'] and m['mssqlParams']['objects'][0]['objectInfo']['name'].lower() == '%s/%s' % (sourceinstance.lower(), thissourcedb.lower()):
                    filtered.append(m)
                elif 'objectInfo' in rap[0] and rap[0]['objectInfo']['name'].lower() == '%s/%s' % (sourceinstance.lower(), thissourcedb.lower()):
                    filtered.append(m)
            migrations = filtered

        if sourceserver != '':
            filtered = []
            for m in migrations:
                rap = recoverappparams(m)
                if 'objects' in m['mssqlParams'] and sqlsource is not None and m['mssqlParams']['objects'][0]['objectInfo']['sourceId'] == sqlsource['rootNode']['id']:
                    filtered.append(m)
                elif 'objectInfo' in rap[0] and rap[0].get('hostInfo', {}).get('name', '').lower() == sourceserver.lower():
                    filtered.append(m)
            migrations = filtered

        if targetdb != '' or targetserver != '':
            if '/' in targetdb:
                (thistargetinstance, thistargetdb) = targetdb.split('/')
            else:
                thistargetdb = targetdb
                thistargetinstance = None
            if targetinstance:
                thistargetinstance = targetinstance
            elif not thistargetinstance:
                thistargetinstance = 'MSSQLSERVER'

            if targetserver != '':
                filtered = []
                for m in migrations:
                    rap = recoverappparams(m)
                    if rap[0].get('sqlTargetParams', {}).get('newSourceConfig', {}).get('host', {}).get('name', '').lower() == targetserver.lower():
                        filtered.append(m)
                migrations = filtered

            if notargetdbspecified is False:
                filtered = []
                for m in migrations:
                    rap = recoverappparams(m)
                    newsourceconfig = rap[0].get('sqlTargetParams', {}).get('newSourceConfig', {})
                    if newsourceconfig.get('instanceName', '').lower() == thistargetinstance.lower() and gettargetdbname(rap[0]).lower() == thistargetdb.lower():
                        filtered.append(m)
                migrations = filtered

        if migrations:
            migrations = sorted(migrations, key=lambda m: m['id'], reverse=True)
            if returntaskids:
                taskids += [m['id'] for m in migrations]
                continue
            if args.debug:
                for m in migrations:
                    display(m)
                exit()

        for migration in migrations:
            migrationcount += 1
            mtaskid = int(migration['id'].split(':')[2])
            mtaskmatches = [t for t in tasks if t['restoreTask']['performRestoreTaskState']['base']['taskId'] == mtaskid]
            mtask = mtaskmatches[0] if mtaskmatches else None
            msnapshotusecs = None
            subtasks = []
            if mtask is not None:
                subtasks = mtask['restoreTask'].get('restoreSubTaskWrapperProtoVec', [])
            if len(subtasks) > 0:
                msnapshotusecs = subtasks[-1]['performRestoreTaskState']['restoreAppTaskState']['restoreAppParams']['ownerRestoreInfo']['ownerObject']['startTimeUsecs']

            rap = recoverappparams(migration)
            newsourceconfig = rap[0].get('sqlTargetParams', {}).get('newSourceConfig', {})
            mtargethost = newsourceconfig.get('host', {}).get('name')
            mtargetinstance = newsourceconfig.get('instanceName')
            mtargetdb = gettargetdbname(rap[0])

            if 'objects' in migration['mssqlParams']:
                msourcedb = migration['mssqlParams']['objects'][0]['objectInfo']['name']
                msourceid = str(migration['mssqlParams']['objects'][0]['objectInfo']['sourceId'])
                if msourceid in sourcenames:
                    msourcehost = sourcenames[msourceid]
                else:
                    hostsearch = api('get', '/searchvms?entityIds=%s' % msourceid)
                    msourcehost = hostsearch['vms'][0]['vmDocument']['objectAliases'][0]
                    sourcenames[msourceid] = msourcehost
            elif 'objectInfo' in rap[0]:
                msourcedb = rap[0]['objectInfo']['name']
                msourcehost = rap[0].get('hostInfo', {}).get('name')
            else:
                msourcedb = None
                msourcehost = None

            if len(subtasks) > 0:
                print('\nTask Name: %s' % migration['name'])
                print('  Task ID: %s' % migration['id'])
                print('Source DB: %s/%s' % (msourcehost, msourcedb))
                print('Target DB: %s/%s/%s' % (mtargethost, mtargetinstance, mtargetdb))
                print('   Status: %s' % migration['status'])
                print('Synced To: %s' % usecsToDate(msnapshotusecs))

            if len(subtasks) > 0 and 'warnings' in subtasks[0]['performRestoreTaskState']['base'] and subtasks[0]['performRestoreTaskState']['base']['warnings']:
                print('  Warning: %s' % subtasks[0]['performRestoreTaskState']['base']['warnings'][0]['errorMsg'])

            if sync:
                if migration['status'] == 'OnHold':
                    print('Performing Sync...')
                    api('put', 'restore/recover', {'restoreTaskId': mtaskid, 'sqlOptions': 'kUpdate'}, quiet=True)
                else:
                    print("Can't sync now (%s)" % migration['status'])

            if finalize:
                if migration['status'] == 'OnHold':
                    print('Finalizing...')
                    api('put', 'restore/recover', {'restoreTaskId': mtaskid, 'sqlOptions': 'kFinalize'}, quiet=True)
                else:
                    print("Can't finalize now (%s)" % migration['status'])

            if cancel:
                if migration['status'] in ('OnHold', 'Running'):
                    print('Cancelling...')
                    api('put', 'restore/tasks/cancel/%s' % mtaskid, quiet=True)

if returntaskids and not init:
    for taskid in taskids:
        print(taskid)
    exit()

print('')
if migrationcount == 0 and not init:
    print('No migrations found\n')
