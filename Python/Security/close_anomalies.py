#!/usr/bin/env python
"""Close Anti-Ransomware Anomaly Incidences"""

### import pyhesity wrapper module
from pyhesity import *
from datetime import datetime, timedelta
import time

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
parser.add_argument('-emfa', '--emailmfacode', action='store_true')
parser.add_argument('-o', '--olderthan', type=int, default=None)
parser.add_argument('-s', '--strength', type=int, default=None)
parser.add_argument('-e', '--entity', type=str, default=None)
parser.add_argument('-r', '--resolve', action='store_true')

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
olderthan = args.olderthan
strength = args.strength
entity = args.entity
resolve = args.resolve

#Dates
now = datetime.now()
dateString = now.strftime("%Y-%m-%d")
currentdatemsecs = int(now.timestamp() * 1000)
ninetydaysago = now - timedelta(days=90)
ninetydaysagosecs = time.mktime(ninetydaysago.timetuple())
ninetydaysagomsecs = int(ninetydaysagosecs * 1000)

#Check if Older Than or Strength was given
if olderthan is None and strength is None:
    print('Either Older Than or Strength is required (Can optionally supply both)')
    exit(1)


# authenticate
apiauth(vip=vip, username=username, domain=domain, password=password, useApiKey=useApiKey, helios=mcm, prompt=(not noprompt))

# exit if not authenticated
if apiconnected() is False:
    print('authentication failed')
    exit(1)

#get anomaly incidents
incidents = api('get', 'argus/api/v1/public/incidences?shieldTypes=ANTI_RANSOMWARE&startTimeMsecs=%s&endTimeMsecs=%s' % (ninetydaysagomsecs, currentdatemsecs), mcm=True)
incidenttotal = incidents['total']
incidences = incidents['incidences']

#filter by entity
if entity is not None:
    incidences = [i for i in incidences if i['antiRansomwareDetails']['entityName'].lower() == entity.lower()]
    if not incidences:
        print ('%s not found' % entity)
        exit (1)

#filter by strength
if strength is not None:
    incidences = [i for i in incidences if i['antiRansomwareDetails']['anomalyStrength'] <= strength]

#filter by older than
if olderthan is not None:
    olderthandate = now - timedelta(days=olderthan)
    olderthansecs = time.mktime(olderthandate.timetuple())
    olderthanmsecs = int(olderthansecs * 1000)
    incidences = [i for i in incidences if i['incidenceTimeMsecs'] <= olderthanmsecs]

#total records
totaltoclose = len(incidences)
if totaltoclose == 0:
    print("No incidences matched criteria")
    exit(1)

#Display Headings
print("\nEntity\tDate\tStrength\tID\n")

#Display Results
for i in incidences:
    timestamp = i['incidenceTimeMsecs'] / 1000
    datestamp = datetime.fromtimestamp(timestamp)
    print('%s \t%s\t%s\t%s\n' % (i['antiRansomwareDetails']['entityName'].lower(), datestamp, i['antiRansomwareDetails']['anomalyStrength'], i['id']))
print("Closing the above %s incidences if -r was specified\n" % totaltoclose)

#Set Resoultion State
resolution = {
    "alert_state": "Resolved"
}

#Resolve Incident(s)
if resolve:
    for i in incidences:
        id = i['id']
        print(id)
        resolved = api ('put', 'alert-service/alerts/%s/state' % id, resolution, mcmv2=True)
      
