#!/usr/bin/env python
"""Graph Oracle Protection Runs"""

### import pyhesity wrapper module
from pyhesity import *
from datetime import datetime
import plotly.express as px
import pandas as pd
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
    # active Oracle protection groups (v2 id is clusterId:incarnationId:jobId)
    v2pgs = api('get', 'data-protect/protection-groups?environments=kOracle&isDeleted=false&isActive=true', v=2)
    pgs = []
    if v2pgs is not None and 'protectionGroups' in v2pgs:
        pgs = v2pgs['protectionGroups']
    if len(pgs) == 0:
        print("No Oracle Jobs Found on %s" % clustername)
    for pg in pgs:
        pgid = pg['id']
        jobname = pg['name']
        print(jobname)
        daysBackUsecs = timeAgo(daysback, 'days')

        # source and database names in the PG, collected from the runs (used for the graph title)
        pgsources = []
        pgdbs = []

        # incremental runs for the graph: (start time, duration minutes, GB read)
        graphrows = []

        # csv rows: all run types (full, incremental, log) using v2 runs for per-database detail
        for run in getRuns(pgid, startTimeUsecs=daysBackUsecs, includeObjectDetails=True, includeDeleted=True):
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
                exit()
            runid = run.get('protectionGroupInstanceId', run['id'].split(':')[-1])
            runtype = runTypeNames.get(info.get('runType'), info.get('runType'))
            durationminutes = round(((info['endTimeUsecs'] - info['startTimeUsecs']) / 1000000) / 60, 2)
            gbytesread = round(info.get('localSnapshotStats', info.get('stats', {})).get('bytesRead', 0) / 1024 / 1024 / 1024, 2)
            csvrows.append([
                clustername,
                jobname,
                runid,
                runtype,
                usecsToDate(info['startTimeUsecs']),
                usecsToDate(info['endTimeUsecs']),
                durationminutes,
                gbytesread,
                '; '.join(getDbNames(run))
            ])
            if info.get('runType') == 'kRegular':
                graphrows.append((usecsToDate(info['startTimeUsecs']), durationminutes, gbytesread))

            # per-database rows: the source (host) is in the same run's objects, matched by sourceId
            runobjectnames = {o['object']['id']: o['object'].get('name') for o in run.get('objects', []) if 'object' in o}
            for o in run.get('objects', []):
                ob = o.get('object', {})
                if ob.get('objectType') != 'kDatabase':
                    continue
                sourcename = runobjectnames.get(ob.get('sourceId')) or ob.get('sourceId')
                if sourcename not in pgsources:
                    pgsources.append(sourcename)
                if ob.get('name') not in pgdbs:
                    pgdbs.append(ob.get('name'))
                dbinfo = getObjectInfo(o)
                if dbinfo is None or 'endTimeUsecs' not in dbinfo:
                    dbinfo = info
                dbstart = dbinfo.get('startTimeUsecs', info['startTimeUsecs'])
                dbend = dbinfo.get('endTimeUsecs', info['endTimeUsecs'])
                dbstats = dbinfo.get('stats', {})
                dbcsvrows.append([
                    clustername,
                    sourcename,
                    ob.get('name'),
                    runid,
                    runtype,
                    usecsToDate(dbstart),
                    usecsToDate(dbend),
                    round(((dbend - dbstart) / 1000000) / 60, 2),
                    round(dbstats.get('bytesRead', 0) / 1024 / 1024, 2)
                ])

        if len(graphrows) == 0:
            print("No Incremental Runs Found for job %s" % jobname)
            continue

        avgruntime = sum([r[1] for r in graphrows]) / len(graphrows)
        print("%s Average Run Time: %s Minutes (%s Total Runs)" % (jobname, round(avgruntime), len(graphrows)))

        df = pd.DataFrame(graphrows, columns=['date_time', 'duration', 'gbytesread'])

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
            title_text='%s - %s days<br>Source: %s<br>Databases: %s' % (jobname, daysback, ', '.join([str(s) for s in sorted(pgsources, key=lambda s: str(s).lower())]) or 'unknown', ', '.join([str(d) for d in sorted(pgdbs, key=lambda d: str(d).lower())]) or 'unknown')
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

