#!/usr/bin/env python
"""Protection Job Monitor for python"""

# version 2024.12.03

### import pyhesity wrapper module
from pyhesity import *
from datetime import datetime
from datetime import timedelta
import codecs

### command line arguments
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('-v', '--vip', type=str, default='helios.cohesity.com')
parser.add_argument('-u', '--username', type=str, default='helios')
parser.add_argument('-d', '--domain', type=str, default='local')
parser.add_argument('-i', '--useApiKey', action='store_true')
parser.add_argument('-p', '--password', type=str, default=None)
parser.add_argument('-np', '--noprompt', action='store_true')
parser.add_argument('-mcm', '--mcm', action='store_true')
parser.add_argument('-c', '--clustername', action='append', type=str, default=None)
parser.add_argument('-cl', '--clusters', type=str, default=None)
parser.add_argument('-m', '--mfacode', type=str, default=None)
parser.add_argument('-e', '--emailmfacode', action='store_true')
parser.add_argument('-j', '--jobname', action='append', type=str)
parser.add_argument('-n', '--numruns', type=int, default=10)
parser.add_argument('-s', '--showobjects', action='store_true')

args = parser.parse_args()

vip = args.vip
username = args.username
domain = args.domain
useApiKey = args.useApiKey
password = args.password
noprompt = args.noprompt
clustername = args.clustername
clusterlist = args.clusters
mcm = args.mcm
mfacode = args.mfacode
emailmfacode = args.emailmfacode
jobnames = args.jobname
numruns = args.numruns
showobjects = args.showobjects

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


# get list of clusters
clusternames = gatherList(clustername, clusterlist, name='clusters', required=True)

# authentication =========================================================
# demand clustername if connecting to helios or mcm
if (mcm or vip.lower() == 'helios.cohesity.com') and clusternames is None:
    print('-c, --clustername is required when connecting to Helios or MCM')
    exit(1)

# authenticate
apiauth(vip=vip, username=username, domain=domain, password=password, useApiKey=useApiKey, helios=mcm, prompt=(not noprompt))

# exit if not authenticated
if apiconnected() is False:
    print('authentication failed')
    exit(1)

# Define outfile
now = datetime.now()
dateString = now.strftime("%Y-%m-%d")
#outfile = 'runningjobs-%s-%s.csv' % (cluster['name'], dateString)
outfile = 'runningjobs-%s.csv' % (dateString)
f = codecs.open(outfile, 'w')

# Add headings to outfile
f.write("Cluster Name,Job Name,Run Type,Start Time,Run Time,% Complete,Object\n")

#Define Report
report = []

# if connected to helios or mcm, select access cluster
for cluster in clusternames:
    if mcm or vip.lower() == 'helios.cohesity.com':
    
       heliosCluster(cluster)
       print ("\n",cluster)
    if LAST_API_ERROR() != 'OK':
        exit(1)
# end authentication =====================================================
    
    #Get Cluster Info
    cluster = api('get', 'cluster')
    
    #Get Running Jobs
    runningjobs = api('get', 'data-protect/protection-groups?useCachedData=false&lastRunLocalBackupStatus=Running&isDeleted=false&includeTenants=true&includeLastRunInfo=true', v=2)
    
    #Get Job Run Details if there are running jobs
    if(runningjobs['protectionGroups'] != None):

        #Get Runs currently running for each Job and progress for each object
        for job in runningjobs['protectionGroups']:
            jobid = job['id'].split(":")[2]
            runs = api('get', 'protectionRuns?jobId=%s' % (jobid))
            runs = [r for r in runs if r['backupRun']['status'] == 'kRunning']
            print("\n", len(runs),"runs in progress for job", job['name'])
            for run in runs:
                    status = run['backupRun']['status']
                    runtype = run['backupRun']['runType']
                    startTime = usecsToDate(run['backupRun']['stats']['startTimeUsecs'])
                    startTime = datetime.strptime(startTime,'%Y-%m-%d %H:%M:%S')
                    runtime = str(now - startTime).split(".")[0]
                    print("\n",runtype,"Running for", runtime)
                    try:
                            progressTotal = 0
                            sourceCount = len(run['backupRun']['sourceBackupStatus'])
                            for source in sorted(run['backupRun']['sourceBackupStatus'], key=lambda source: source['source']['name'].lower()):
                                sourceName = source['source']['name']
                                progressPath = source['progressMonitorTaskPath']
                                progressMonitor = api('get', '/progressMonitors?taskPathVec=%s&includeFinishedTasks=true&excludeSubTasks=false' % progressPath)
                                thisProgress = progressMonitor['resultGroupVec'][0]['taskVec'][0]['progress']['percentFinished']
                                progressTotal += thisProgress
                                percentComplete = int(round(progressTotal / sourceCount))
                                if showobjects is True:
                                    if thisProgress < 100:
                                        #print(duration)
                                        print('\n%s    %s:  %s%% completed\t%s' % (job['name'],startTime, int(round(thisProgress)), sourceName))
                                        report.append(str('%s, %s, %s, %s, %s, %s%%,\t%s' %(cluster['name'],job['name'],runtype,startTime,runtime, int(round(thisProgress)), sourceName)))
                                if showobjects is not True:
                                    print('\n%s' % job['name'])
                                    print('    %s: %s%%\tcompleted' % (startTime, percentComplete))
                    except Exception:
                        pass


       
    #if no jobs running
    else: print("No Running Jobs on cluster")

#write results to file        
for item in sorted(report):
    f.write('%s\n' % item)

f.close()
print('\nOutput saved to %s\n' % outfile)
