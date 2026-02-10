#!/usr/bin/env python
"""Graph Oracle Protection Runs"""

### import pyhesity wrapper module
from pyhesity import *
from datetime import datetime
import plotly.express as px
import pandas as pd
from io import StringIO
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



for clustername in clusternames:
    heliosCluster(clustername)
    print(clustername)

    if LAST_API_ERROR() != 'OK':
        continue
        #exit(1)

    fig_divs = []
    sources = api('get', 'protectionSources?environment=kOracle')
    jobs = api('get', 'protectionJobs?environments=kOracle&isDeleted=False&isActive=True')
    if len(jobs) == 0 or jobs == None:
        print("No Oracle Jobs Found on %s" % clustername)
    for job in jobs:
        jobid = job['id']
        jobname = job['name']
        sourceids = job['sourceIds']
        print(jobname)
        daysBackUsecs = timeAgo(daysback, 'days')
        
        runs = api('get', 'protectionRuns?jobId=%s&startTimeUsecs=%s&runTypes=kRegular&numRuns=1000' % (jobid,daysBackUsecs))
        if len(runs) == 0:
            print("No Runs Found for job %s" % jobname)
            continue
        #print(runs)
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
