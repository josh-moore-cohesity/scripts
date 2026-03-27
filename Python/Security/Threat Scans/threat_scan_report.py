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
parser.add_argument('-nt', '--newerthan', type=int, default=None)
parser.add_argument('-ot', '--olderthan', type=int, default=None)

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
#get threat scans
scans = api('get', 'argus/api/v1/public/ioc/scans', mcm=True)

scandetails = scans['scans']
scandetails = [s for s in scandetails if 'lastRun' in s and 'endTimeUsecs' in s['lastRun']]

if newerthan is not None:
    newerthandate = now - timedelta(days=newerthan)
    newerthandateusecs = dateToUsecs(newerthandate)
    scandetails = [s for s in scandetails if s['lastRun']['startTimeUsecs'] >= newerthandateusecs]

if olderthan is not None:
    olderthandate = now - timedelta(days=olderthan)
    olderthandateusecs = dateToUsecs(olderthandate)
    scandetails = [s for s in scandetails if s['lastRun']['startTimeUsecs'] <= olderthandateusecs]

if len(scandetails) == 0:
    print("No Scans Found in Selected Range")
    exit(0)

#Scan Detail Outfile
outfile = 'threat_scans-%s.csv' % dateString
f = codecs.open(outfile, 'w')
f.write('Scan Name,Object,File Path, File Hash,Snapshot Date,Threat Family,Threat Category,Severity\n')
report = []
summaryreport = []

#Summary Outfile
summaryfile = 'threat_scans_summary-%s.csv' % dateString
sf = codecs.open(summaryfile, 'w')
sf.write ('Start Time,End Time, Duration,Cluster,Scanned,Total,Scan Method,OS,ScanId,RunId,Threat Feed, Threats,Unique Files,Error\n')

for scan in scandetails:
    scanname = scan['name']
    print(scanname)
    scanid = scan['id']

    #Duration Info
    scanstarttime = usecsToDateTime(scan['lastRun']['startTimeUsecs'])
    scanendtime = usecsToDateTime(scan['lastRun']['endTimeUsecs'])
    duration = scanendtime - scanstarttime
    duration = str(duration).split('.')[0]
    scanstarttime = scanstarttime.strftime("%Y-%m-%d %H:%M")
    scanendtime = scanendtime.strftime("%Y-%m-%d %H:%M")
    
    #Cluster
    clusterid = int((scan['lastRun']['objects'][0]['object']['id']).split(":")[0])
    cluster = [c for c in clusters if c['clusterId'] == clusterid]
    clustername = cluster[0]['clusterName']

    #Object Counts
    scannedobjects = scan['lastRun']['stats']['scannedObjectCount']
    totalobjects = scan['lastRun']['stats']['totalObjectCount']

    #Scan Method
    scanmethod = scan['scanMethod']

    #OS Manual Field
    os = ""

    #Run ID
    runid = scan['lastRun']['id']

    #Threat Feed
    if scan['detectionType']['builtInThreats'] == True:
        threatfeed = "Default"
    else:
        threatfeed = "Non Default"
    
    #Snapshots Affected
    snapshotsaffected = scan['lastRun']['stats']['affectedSnapshotCount']

    #Unique Files
    uniquefiles = scan['lastRun']['stats']['affectedFilesCount']

    #Error Message
    errormessage = scan['lastRun']['health'].get('message')

    summaryreport.append(str('%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s') % (scanstarttime,scanendtime,duration,clustername,scannedobjects,totalobjects,scanmethod,os,scanid,runid,threatfeed,snapshotsaffected,uniquefiles,errormessage))
    #Affected Files
    affectedfiles = api('get', 'argus/api/v1/public/ioc/scans/%s/affected-files?pageSize=10' % scanid, mcm=True)

    try:
        affectedfiles = affectedfiles['affectedFiles']
        for file in affectedfiles:
            objectname = file['object']['name']
            report.append(str('%s,%s,%s,%s,%s,%s,%s,%s') % (scanname,objectname,file['filePath'],file['fileHash'],usecsToDateTime(file['snapshotStartTimeUsecs']),file['threatFamily'],file['threatCategory'],file['severity']))
    except:
        objects = scan['objects']
        for object in objects:
            objectname = object['object']['name']
            report.append(str('%s,%s,No Files Found') % (scanname,objectname))
        continue

for item in report:
    f.write('%s\n' % item)

f.close()
print('\nOutput saved to %s\n' % outfile)

for item in summaryreport:
    sf.write('%s\n' % item)

sf.close()
print('\nSummary saved to %s\n' % summaryfile)
