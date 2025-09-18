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

#Create Outfile
outfile = 'threat_scans-%s.csv' % dateString
f = codecs.open(outfile, 'w')
f.write('Scan Name,Object,File Path, File Hash,Snapshot Date,Threat Family,Threat Category,Severity\n')
report = []

#get threat scans
scans = api('get', 'argus/api/v1/public/ioc/scans', mcm=True)

scandetails = scans['scans']

if newerthan is not None:
    newerthandate = now - timedelta(days=newerthan)
    newerthandateusecs = dateToUsecs(newerthandate)
    scandetails = [s for s in scandetails if s['lastRun']['startTimeUsecs'] >= newerthandateusecs]

if olderthan is not None:
    olderthandate = now - timedelta(days=olderthan)
    olderthandateusecs = dateToUsecs(olderthandate)
    scandetails = [s for s in scandetails if s['lastRun']['startTimeUsecs'] <= olderthandateusecs]

for scan in scandetails:
    scanname = scan['name']
    scanid = scan['id']
    print(scanname)
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
