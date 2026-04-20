#!/usr/bin/env python
"""Report Threat Scan Results"""

### import pyhesity wrapper module
from pyhesity import *
from datetime import datetime,timedelta
import codecs

### command line arguments
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
parser.add_argument('-nt', '--newerthan', type=int, default=30)
parser.add_argument('-ot', '--olderthan', type=int, default=0)

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
newerthan = args.newerthan
olderthan = args.olderthan

#Date Time Format Function
def fmt_timedelta_d_hms(td: timedelta) -> str:
    total = int(td.total_seconds())  # truncates fractional part
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{days}:{hours:02d}:{minutes:02d}:{seconds:02d}"

#Date
now = datetime.now()
dateString = now.strftime("%Y-%m-%d")

# authenticate
apiauth(vip=vip, username=username, domain=domain, password=password, useApiKey=useApiKey, helios=mcm, prompt=(not noprompt))

# exit if not authenticated
if apiconnected() is False:
    print('authentication failed')
    exit(1)

#Clusters
clusters = api('get', 'cluster-mgmt/info',mcmv2=True)
clusters = clusters['cohesityClusters']

#Set Older than and Newer Than Dates
newerthandate = now - timedelta(days=newerthan)
newerthandateusecs = dateToUsecs(newerthandate)
newerthandatemsecs = newerthandateusecs // 1000

olderthandate = now - timedelta(days=olderthan)
olderthandateusecs = dateToUsecs(olderthandate)
olderthandatemsecs = olderthandateusecs // 1000

#get threat scans
scans = api('get', 'argus/api/v1/public/ioc/scans?startTimeMsecs=%s&endTimeMsecs=%s' % (newerthandatemsecs,olderthandatemsecs), mcm=True)
#scans = api('get', 'argus/api/v1/public/ioc/scans', mcm=True)
scandetails = scans['scans']
scanstats = scans['stats']

#Scan Detail Outfile
outfile = 'threat_scans-details-%s.csv' % dateString
f = codecs.open(outfile, 'w')
f.write('Scan Name,Start Time,Object,File Path, File Hash,Snapshot Date,Threat Family,Threat Category,Severity\n')
report = []
summaryreport = []

#Summary Outfile
summaryfile = 'threat_scans_summary-%s.csv' % dateString
sf = codecs.open(summaryfile, 'w')
sf.write ('Scan Name,Start Time,End Time, Duration,Cluster,Scanned,Total,Scan Method,OS,ScanId,RunId,Threat Feed, Threats,Unique Files,Error\n')

for scan in scandetails:
    scanname = scan['name']
    scanid = scan['id']
    print(scanname)

    runs = api('get', 'argus/api/v1/public/ioc/scans/%s/runs?startTimeMsecs=%s&endTimeMsecs=%s&pageSize=100' % (scanid,newerthandatemsecs,olderthandatemsecs), mcm=True)

    runs = runs['runs']

    for run in runs:

        #Duration Info
        scanstarttime = usecsToDateTime(run['startTimeUsecs'])

        end_usecs = run.get('endTimeUsecs')
        if not end_usecs:
            continue

        scanendtime = usecsToDateTime(end_usecs)

        duration = scanendtime - scanstarttime
        duration = fmt_timedelta_d_hms(duration)

        scanstarttime = scanstarttime.strftime("%Y-%m-%d %H:%M")
        scanendtime = scanendtime.strftime("%Y-%m-%d %H:%M")
    
        #Cluster
        clusterid = int((run['objects'][0]['object']['id']).split(":")[0])
        cluster = [c for c in clusters if c['clusterId'] == clusterid]
        clustername = cluster[0]['clusterName']

        #Object Counts
        scannedobjects = run['stats']['scannedObjectCount']
        totalobjects = run['stats']['totalObjectCount']

        #Scan Method
        scanmethod = run['objects'][0]['scanMethod']

        #OS Manual Field
        os = ""

        #Run ID
        runid = run['id']

        #Threat Feed
        if scan['detectionType']['builtInThreats'] == True:
            threatfeed = "Default"
        else:
            threatfeed = "Non Default"
    
        #Snapshots Affected
        snapshotsaffected = run['stats']['affectedSnapshotCount']

        #Unique Files
        uniquefiles = run['stats']['affectedFilesCount']

        #Error Message
        errormessage = run['health'].get('message')

        summaryreport.append(str('%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s') % (scanname,scanstarttime,scanendtime,duration,clustername,scannedobjects,totalobjects,scanmethod,os,scanid,runid,threatfeed,snapshotsaffected,uniquefiles,errormessage))
    
        #Affected Files
        affectedfiles = api('get', 'argus/api/v1/public/ioc/scans/%s/runs/%s/affected-files?pageSize=10' % (scanid,runid), mcm=True)

        try:
            affectedfiles = affectedfiles['affectedFiles']
            for file in affectedfiles:
                objectname = file['object']['name']
                report.append(str('%s,%s,%s,%s,%s,%s,%s,%s,%s') % (scanname,scanstarttime,objectname,file['filePath'],file['fileHash'],usecsToDateTime(file['snapshotStartTimeUsecs']),file['threatFamily'],file['threatCategory'],file['severity']))
        except:
            objects = scan['objects']
            for object in objects:
                objectname = object['object']['name']
                report.append(str('%s,%s,%s,No Files Found') % (scanname,scanstarttime,objectname))
            continue

for item in report:
    f.write('%s\n' % item)

f.close()
print('\nOutput saved to %s\n' % outfile)

for item in summaryreport:
    sf.write('%s\n' % item)

sf.close()
print('\nSummary saved to %s\n' % summaryfile)
