#!/usr/bin/env python
"""List the files and folders that were restored by a Cohesity recovery"""

### import pyhesity wrapper module
from pyhesity import *
from datetime import datetime
from urllib.parse import quote
import argparse
import base64
import codecs
import csv
import json
import os
import re
import time

### command line arguments
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
parser.add_argument('-r', '--recoveryid', type=str, default=None)
parser.add_argument('-n', '--recoveryname', type=str, default=None)
parser.add_argument('-p', '--path', type=str, default=None)
parser.add_argument('-a', '--attemptnum', type=int, default=0)
parser.add_argument('-showraw', '--showraw', action='store_true')
parser.add_argument('-outputpath', '--outputpath', type=str, default='./Results')

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
recoveryid = args.recoveryid
recoveryname = args.recoveryname
startpath = args.path
attemptnum = args.attemptnum
showraw = args.showraw
outputpath = args.outputpath

if recoveryid is None and recoveryname is None:
    print('-r (--recoveryid) or -n (--recoveryname) is required')
    exit(1)


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

# authenticate
apiauth(vip=vip, username=username, domain=domain, password=password, useApiKey=useApiKey, helios=mcm, prompt=(not noprompt), mfaCode=mfacode, emailMfaCode=emailmfacode)

# exit if not authenticated
if apiconnected() is False:
    print('authentication failed')
    exit(1)

# end authentication =====================================================

os.makedirs(outputpath, exist_ok=True)
errorPattern = re.compile(r'error|fail|warn|skip|unable|denied', re.IGNORECASE)


def safeName(text):
    return re.sub(r'[^A-Za-z0-9_.-]+', '_', text)


def findRecovery():
    """return the recovery matching -r or -n on the current cluster"""
    if recoveryid is not None:
        recovery = api('get', 'data-protect/recoveries/%s' % quote(recoveryid, safe=':'), v=2, quiet=True)
        if recovery is not None and 'id' in recovery:
            return recovery
    recoveries = api('get', 'data-protect/recoveries', v=2, quiet=True)
    if recoveries is None or 'recoveries' not in recoveries:
        return None
    for recovery in recoveries['recoveries']:
        if recoveryid is not None and recovery['id'] == recoveryid:
            return recovery
        if recoveryname is not None and recovery['name'].lower() == recoveryname.lower():
            return recovery
    return None


def findAll(node, key, found=None):
    """collect every value stored under key anywhere in the recovery json"""
    if found is None:
        found = []
    if isinstance(node, dict):
        for k, v in node.items():
            if k == key:
                found.append(v)
            findAll(v, key, found)
    elif isinstance(node, list):
        for v in node:
            findAll(v, key, found)
    return found


def findObjects(node, found=None):
    """collect every object entry that carries a snapshotId"""
    if found is None:
        found = []
    if isinstance(node, dict):
        if 'snapshotId' in node and 'objectInfo' in node:
            found.append(node)
        for v in node.values():
            findObjects(v, found)
    elif isinstance(node, list):
        for v in node:
            findObjects(v, found)
    return found


def findOptions(node, parent=None, found=None):
    """collect every restore options block (the one holding overwriteExistingFile) with its parent key"""
    if found is None:
        found = []
    if isinstance(node, dict):
        if 'overwriteExistingFile' in node:
            found.append((parent, node))
        for k, v in node.items():
            findOptions(v, k, found)
    elif isinstance(node, list):
        for v in node:
            findOptions(v, parent, found)
    return found


def decodeSnapshotId(snapshotId):
    """snapshotId is base64 json: cluster, incarnation, job, run instance, run start, object"""
    padded = snapshotId + '=' * (-len(snapshotId) % 4)
    decoded = json.loads(base64.b64decode(padded))
    return {k[2:]: v for k, v in decoded.items()}


def pick(info, keys, default=None):
    for key in keys:
        if info is not None and key in info:
            return info[key]
    return default


def listDirectory(instance, path):
    """return all entries in one snapshot directory, or None on error"""
    entries = []
    cookie = None
    while True:
        uri = '/vm/directoryList?%s&dirPath=%s&statFileEntries=true' % (instance, quote(path, safe=''))
        if cookie is not None:
            uri += '&cookie=%s' % quote(str(cookie), safe='')
        # retry transient failures (timeouts, session hiccups, non-json replies)
        result = None
        for attempt in range(4):
            result = api('get', uri, quiet=True)
            if isinstance(result, dict):
                break
            if result is not None:
                print('    error listing %s (attempt %s): %s' % (path, attempt + 1, str(LAST_API_ERROR())[:300]))
            time.sleep(2 * (attempt + 1))
        if showraw is True and len(entries) == 0:
            print(json.dumps(result, indent=2)[:3000])
        if not isinstance(result, dict):
            return None
        entries += result.get('entries', [])
        newcookie = result.get('cookie', None)
        if not newcookie or newcookie == cookie:
            break
        cookie = newcookie
    return entries


def walkSnapshot(obj, startPaths, writer):
    """walk the snapshot under each start path and write every file to the csv"""
    ids = decodeSnapshotId(obj['snapshotId'])
    objectId = pick(obj['objectInfo'], ['id'])
    instance = 'attemptNum=%s&clusterId=%s&clusterIncarnationId=%s&entityId=%s&jobId=%s&jobInstanceId=%s&jobStartTimeUsecs=%s&jobUidObjectId=%s' % (
        attemptnum,
        ids['clusterId'],
        ids['clusterIncarnationId'],
        objectId,
        ids['jobId'],
        ids['jobInstanceId'],
        ids['runStartTimeUsecs'],
        ids['jobId'])
    snapshotDate = usecsToDate(ids['runStartTimeUsecs'])
    stack = list(startPaths)
    fileCount = 0
    dirCount = 0
    failedPaths = []
    while len(stack) > 0:
        path = stack.pop()
        entries = listDirectory(instance, path)
        if entries is None:
            failedPaths.append(path)
            print('    could not list %s (%s)' % (path, LAST_API_ERROR()))
            continue
        for entry in entries:
            name = entry.get('name', '')
            fullPath = entry.get('fullPath', path.rstrip('/') + '/' + name)
            entryType = entry.get('type', '')
            info = entry.get('statInfo') or entry.get('fstatInfo') or entry
            if 'Directory' in entryType:
                dirCount += 1
                stack.append(fullPath)
                continue
            fileCount += 1
            modified = pick(info, ['lastModifiedTimeUsecs', 'mtimeUsecs', 'modificationTimeUsecs', 'lastModifiedTime'])
            if isinstance(modified, int) and modified > 0:
                modified = usecsToDate(modified)
            writer.writerow([obj['objectInfo'].get('name', ''), fullPath, entryType[1:] if entryType.startswith('k') else entryType, pick(info, ['size', 'fileSize', 'sizeBytes'], ''), modified or '', snapshotDate])
            if fileCount % 5000 == 0:
                print('    %s files listed...' % fileCount)
    return fileCount, dirCount, failedPaths


def getEvents(recovery):
    """pull error / warning style events from the recovery progress task"""
    taskId = recovery.get('progressTaskId', None)
    if taskId is None:
        return []
    progress = api('get', '/progressMonitors?taskPathVec=%s&includeFinishedTasks=true&excludeSubTasks=false' % taskId, quiet=True)
    events = []
    if progress is None:
        return events
    for group in progress.get('resultGroupVec', []):
        for task in group.get('taskVec', []):
            for event in task.get('progress', {}).get('eventVec', []):
                message = event.get('eventMsg', '')
                if errorPattern.search(message.replace('skip finalize as false', '')):
                    events.append([usecsToDate(event.get('timestampSecs', 0) * 1000000), task.get('taskPath', ''), message])
    return events


def processRecovery(cluster, recovery):
    print('    %s (%s) %s' % (recovery['name'], recovery['recoveryAction'], recovery['status']))
    base = os.path.join(outputpath, '%s-%s' % (safeName(cluster), safeName(recovery['name'])))

    # recovery summary and restore options (overwrite, attributes, continue on error)
    stats = recovery.get('aggregatedStats') or {}
    settings = [
        ['Recovery Name', recovery['name']],
        ['Recovery Id', recovery['id']],
        ['Recovery Action', recovery['recoveryAction']],
        ['Status', recovery['status']],
        ['Requested By', (recovery.get('creationInfo') or {}).get('userName', '')],
        ['Start Time', usecsToDate(recovery['startTimeUsecs']) if 'startTimeUsecs' in recovery else ''],
        ['End Time', usecsToDate(recovery['endTimeUsecs']) if 'endTimeUsecs' in recovery else ''],
        ['Bytes Transferred', stats.get('transferredBytes', '')]]
    targets = {'originalSourceConfig': 'Original location', 'newSourceConfig': 'Alternate location'}
    for parent, options in findOptions(recovery):
        settings.append(['Restore Target', targets.get(parent, parent)])
        for key, value in options.items():
            if not isinstance(value, (dict, list)):
                settings.append([key, value])
    settingsFile = base + '-recovery-settings.csv'
    with codecs.open(settingsFile, 'w', 'utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Setting', 'Value'])
        writer.writerows(settings)
    for setting, value in settings:
        if setting not in ('Recovery Id', 'Bytes Transferred'):
            print('      %s: %s' % (setting, value))
    print('    recovery settings saved to %s' % settingsFile)

    # paths requested for a file / folder restore
    requested = findAll(recovery, 'filesAndFolders')
    requestedPaths = []
    for group in requested:
        for item in group:
            requestedPaths.append(item)
    if len(requestedPaths) > 0:
        requestedFile = base + '-requested-paths.csv'
        with codecs.open(requestedFile, 'w', 'utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Absolute Path', 'Destination Directory', 'Is Directory'])
            for item in requestedPaths:
                writer.writerow([item.get('absolutePath', ''), item.get('destinationDir', ''), item.get('isDirectory', '')])
        print('    requested paths saved to %s' % requestedFile)

    # enumerate the snapshot that was restored from
    objects = findObjects(recovery)
    if len(objects) == 0:
        print('    no snapshots found in this recovery')
    else:
        filesFile = base + '-restored-files.csv'
        # write to a temp file so a failed run never overwrites a complete list
        with codecs.open(filesFile + '.partial', 'w', 'utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Object', 'File Path', 'Type', 'Size (Bytes)', 'Last Modified', 'Snapshot Date'])
            for obj in objects:
                if startpath is not None:
                    startPaths = [startpath]
                elif len(requestedPaths) > 0:
                    startPaths = [p['absolutePath'] for p in requestedPaths]
                else:
                    startPaths = ['/']
                print('    listing snapshot of %s from %s' % (obj['objectInfo'].get('name', ''), ', '.join(startPaths)))
                fileCount, dirCount, failedPaths = walkSnapshot(obj, startPaths, writer)
                print('    %s files in %s folders' % (fileCount, dirCount))
                if len(failedPaths) > 0:
                    print('    WARNING: %s paths could not be listed - list is incomplete' % len(failedPaths))
        os.replace(filesFile + '.partial', filesFile)
        print('    restored files saved to %s' % filesFile)

    # errors and warnings recorded by the restore task
    events = getEvents(recovery)
    eventsFile = base + '-events.csv'
    if len(events) > 0:
        with codecs.open(eventsFile, 'w', 'utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Time', 'Task', 'Message'])
            writer.writerows(events)
        print('    %s error / warning events saved to %s' % (len(events), eventsFile))
    else:
        print('    no error or warning events in the restore task')


#Get Clusters
if len(clusternames) == 0:
    clusters = api('get', 'cluster-mgmt/info', mcmv2=True)
    clusters = clusters['cohesityClusters']
    clusters = [c for c in clusters if c['isConnectedToHelios'] is True]
    clusternames = [c['clusterName'] for c in clusters]

found = False
for cluster in clusternames:
    heliosCluster(cluster)
    print(cluster)

    if LAST_API_ERROR() != 'OK':
        continue

    recovery = findRecovery()
    if recovery is None:
        continue

    found = True
    processRecovery(cluster, recovery)
    break

if found is False:
    print('recovery not found on any cluster')
    exit(1)
