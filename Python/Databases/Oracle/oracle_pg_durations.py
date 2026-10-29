#!/usr/bin/env python
"""Graph Oracle Protection Runs"""

### import pyhesity wrapper module
from pyhesity import *
from datetime import datetime
import plotly.express as px
import pandas as pd
from io import StringIO
import csv
import json
import time
from plotly.subplots import make_subplots
import plotly.graph_objects as go

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
parser.add_argument('-j', '--jobname', nargs='+', type=str, default=None)
parser.add_argument('-jl', '--joblist', type=str, default=None)
parser.add_argument('-daysback', '--daysback', type=int, default=30)
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
jobname = args.jobname
joblist = args.joblist
daysback = args.daysback
debug = args.debug

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

runTypeNames = {'kRegular': 'Incremental', 'kFull': 'Full', 'kLog': 'Log'}

# get database names in a (v2) run: database objects if present, otherwise all object names
def getDbNames(run):
    objects = [o['object'] for o in run.get('objects', []) if 'object' in o]
    dbs = [o for o in objects if o.get('objectType') == 'kDatabase']
    names = []
    for o in (dbs if len(dbs) > 0 else objects):
        if o.get('name') and o['name'] not in names:
            names.append(o['name'])
    return sorted(names, key=lambda n: n.lower())

# get an object's own snapshot/archive info (local snapshot if present, otherwise the first archive target)
def getObjectInfo(o):
    snap = (o.get('localSnapshotInfo') or {}).get('snapshotInfo')
    if snap is not None:
        return snap
    results = (o.get('archivalInfo') or {}).get('archivalTargetResults') or []
    if len(results) > 0:
        return results[0]
    return None

# get list of clusters
clusternames = gatherList(clustername, clusterlist, name='clusters', required=True)

#Date
now = datetime.now()
dateString = now.strftime("%Y-%m-%d")

# authenticate
apiauth(vip=vip, username=username, domain=domain, password=password, useApiKey=useApiKey, helios=mcm, prompt=(not noprompt), mfaCode=mfacode, emailMfaCode=emailmfacode)

# exit if not authenticated
if apiconnected() is False:
    print('authentication failed')
    exit(1)

# end authentication =====================================================

# csv output: one row per run, all clusters
csvfile = 'oracle_pg_durations-%s.csv' % dateString
csvrows = []

# csv output: one row per database per run, all clusters
dbcsvfile = 'oracle_db_durations-%s.csv' % dateString
dbcsvrows = []

for clustername in clusternames:
    heliosCluster(clustername)
    print(clustername)

    if LAST_API_ERROR() != 'OK':
        continue
        #exit(1)

    fig_divs = []
    jobs = api('get', 'protectionJobs?environments=kOracle&isDeleted=False&isActive=True')
    # map v1 job id to v2 protection group id (clusterId:incarnationId:jobId)
    v2pgs = api('get', 'data-protect/protection-groups?environments=kOracle&isDeleted=false&isActive=true', v=2)
    v2pgids = {}
    if v2pgs is not None and 'protectionGroups' in v2pgs:
        v2pgids = {int(pg['id'].split(':')[-1]): pg['id'] for pg in v2pgs['protectionGroups']}
    if len(jobs) == 0 or jobs == None:
        print("No Oracle Jobs Found on %s" % clustername)
    for job in jobs:
        jobid = job['id']
        jobname = job['name']
        sourceids = job['sourceIds']
        print(jobname)
        daysBackUsecs = timeAgo(daysback, 'days')

        # csv rows: all run types (full, incremental, log) using v2 runs for per-database detail
        if jobid in v2pgids:
            for run in getRuns(v2pgids[jobid], startTimeUsecs=daysBackUsecs, includeObjectDetails=True, includeDeleted=True):
                # local backup info, or the archive target for direct-to-archive groups
                info = run.get('localBackupInfo')
                infosource = 'localBackupInfo'
                if info is None:
                    results = run.get('archivalInfo', {}).get('archivalTargetResults', [])
                    if len(results) == 0:
                        continue
                    info = results[0]
                    infosource = 'archivalInfo.archivalTargetResults[0]'
                if 'endTimeUsecs' not in info or info['startTimeUsecs'] < daysBackUsecs:
                    continue
                if debug is True:
                    # dump the first completed run's structure for troubleshooting, then exit
                    print('\nrun keys: %s' % list(run.keys()))
                    print('\nrun info (%s):\n%s' % (infosource, json.dumps(info, indent=2)))
                    print('\nobjects in run (%s):' % len(run.get('objects', [])))
                    for o in run.get('objects', []):
                        ob = o.get('object', {})
                        print('  id=%s type=%s env=%s name=%s sourceId=%s children=%s' % (ob.get('id'), ob.get('objectType'), ob.get('environment'), ob.get('name'), ob.get('sourceId'), None if ob.get('childObjects') is None else len(ob['childObjects'])))
                    dbobjs = [o for o in run.get('objects', []) if o.get('object', {}).get('objectType') != 'kOracleRACCluster']
                    print('\nfirst non-cluster object:\n%s' % json.dumps(dbobjs[0] if len(dbobjs) > 0 else None, indent=2))
                    print('\nsource tree (id, name, keys) for %s:' % jobname)
                    def dumpSources(nodes, depth=0):
                        for node in nodes or []:
                            ps = node.get('protectionSource', {})
                            print('  %s%s  %s  %s' % ('    ' * depth, ps.get('id'), ps.get('name'), [k for k in ps.keys() if k not in ('id', 'name')]))
                            dumpSources(node.get('nodes'), depth + 1)
                    dumpSources(api('get', 'protectionSources?environment=kOracle'))
                    v1runs = [r for r in (api('get', 'protectionRuns?jobId=%s&numRuns=5' % jobid) or []) if 'backupRun' in r and r['backupRun'].get('status') != 'kRunning']
                    if len(v1runs) > 0:
                        print('\nv1 run backupRun keys: %s' % list(v1runs[0]['backupRun'].keys()))
                        print('\nv1 sourceBackupStatus[0]:\n%s' % json.dumps(v1runs[0]['backupRun'].get('sourceBackupStatus', [None])[0], indent=2))
                    exit()
                csvrows.append([
                    clustername,
                    jobname,
                    run.get('protectionGroupInstanceId', run['id'].split(':')[-1]),
                    runTypeNames.get(info.get('runType'), info.get('runType')),
                    usecsToDate(info['startTimeUsecs']),
                    usecsToDate(info['endTimeUsecs']),
                    round(((info['endTimeUsecs'] - info['startTimeUsecs']) / 1000000) / 60, 2),
                    round(info.get('localSnapshotStats', info.get('stats', {})).get('bytesRead', 0) / 1024 / 1024 / 1024, 2),
                    '; '.join(getDbNames(run))
                ])

                # per-database rows: the source (host) is in the same run's objects, matched by sourceId
                runid = run.get('protectionGroupInstanceId', run['id'].split(':')[-1])
                runobjectnames = {o['object']['id']: o['object'].get('name') for o in run.get('objects', []) if 'object' in o}
                for o in run.get('objects', []):
                    ob = o.get('object', {})
                    if ob.get('objectType') != 'kDatabase':
                        continue
                    dbinfo = getObjectInfo(o)
                    if dbinfo is None or 'endTimeUsecs' not in dbinfo:
                        dbinfo = info
                    dbstart = dbinfo.get('startTimeUsecs', info['startTimeUsecs'])
                    dbend = dbinfo.get('endTimeUsecs', info['endTimeUsecs'])
                    dbstats = dbinfo.get('stats', {})
                    dbcsvrows.append([
                        clustername,
                        runobjectnames.get(ob.get('sourceId')) or ob.get('sourceId'),
                        ob.get('name'),
                        runid,
                        runTypeNames.get(info.get('runType'), info.get('runType')),
                        usecsToDate(dbstart),
                        usecsToDate(dbend),
                        round(((dbend - dbstart) / 1000000) / 60, 2),
                        round(dbstats.get('bytesRead', 0) / 1024 / 1024, 2)
                    ])

        runs = api('get', 'protectionRuns?jobId=%s&startTimeUsecs=%s&runTypes=kRegular&numRuns=1000' % (jobid,daysBackUsecs))
        if len(runs) == 0:
            print("No Runs Found for job %s" % jobname)
            continue

        completedruns = [r for r in runs if 'backupRun' in r and r['backupRun'].get('status') != 'kRunning']
        
        report = []
        runstats = []
        

        for run in completedruns:
            starttimeusecs = run['backupRun']['stats']['startTimeUsecs']
            starttime = usecsToDate(starttimeusecs)
            endtimeusecs = run['backupRun']['stats']['endTimeUsecs']
            endtime = usecsToDate(endtimeusecs)
            durationusecs = endtimeusecs - starttimeusecs
            durationminutes = round((durationusecs / 1000000) / 60)
            gbytesread = round(run['backupRun']['stats']['totalBytesReadFromSource'] / 1024 / 1024 / 1024)
            runstats.append(durationminutes)
            report.append('%s,%s,%s,%s,%s' % (clustername,jobname,starttime,durationminutes,gbytesread))
        
        avgruntime = sum(runstats) / len(runstats)
        csv_string = "\n".join(report)
        print("%s Average Run Time: %s Minutes (%s Total Runs)" % (jobname, round(avgruntime),len(runstats)))

        # Use pandas to read the string as if it were a CSV file
        df = pd.read_csv(
            StringIO(csv_string),
            header=None,
            names=['cluster_info', 'pg', 'date_time', 'duration', 'gbytesread']
        )

        # Convert the 'date_time' column to a proper datetime format
        df['date_time'] = pd.to_datetime(df['date_time'])

        # Sort the data by date and time to ensure the line chart is plotted correctly
        df = df.sort_values(by='date_time')

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(
            go.Scatter(x=df['date_time'], y=df['duration'], name='Duration', line=dict(color='purple'), mode='lines+markers'), secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(x=df['date_time'], y=df['gbytesread'], name='GB Read', line=dict(color='orange'), mode='lines+markers'), secondary_y=True
        )

        fig.update_layout(
            title_text='%s - %s days \n%s' % (jobname,daysback,sourceids)
        )

        fig.update_xaxes(title_text="Date")

        fig.update_yaxes(title_text="<b>Duration (Minutes)</b>", secondary_y=False)
        fig.update_yaxes(title_text="<b>GB Read</b>", secondary_y=True)

        fig_divs.append(fig.to_html(full_html=False))

    #Create HTML File    
    header = '%s - Oracle PG Duration Trends' % clustername.upper()
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Job Run Time Trends</title>
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    </head>
    <body>
        <h1>{}</h1>
        {}
    </body>
    </html>
    """.format(header,"\n".join(fig_divs))

    with open("%s-job_duration_trends.html" % clustername, "w", encoding="utf-8") as f:
            f.write(html_content)

# write csv file
with open(csvfile, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['Cluster Name', 'Protection Group', 'Run ID', 'Run Type', 'Run Start', 'Run End', 'Duration (Minutes)', 'GB Read', 'Databases'])
    writer.writerows(csvrows)
print('\nCSV output saved to %s' % csvfile)

# write per-database csv file
with open(dbcsvfile, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['Cluster Name', 'Source Name', 'Database', 'Run ID', 'Run Type', 'Start Time', 'End Time', 'Duration (Minutes)', 'Data Read (MiB)'])
    writer.writerows(dbcsvrows)
print('Per-database CSV output saved to %s' % dbcsvfile)

