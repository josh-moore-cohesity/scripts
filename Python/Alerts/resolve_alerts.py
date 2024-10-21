#!/usr/bin/env python
"""Resolve alerts using Python"""

### import pyhesity wrapper module
from pyhesity import *
from datetime import datetime

### command line arguments
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('-v', '--vip', type=str, default='helios.cohesity.com')
parser.add_argument('-u', '--username', type=str, default='helios')
parser.add_argument('-d', '--domain', type=str, default='local')
parser.add_argument('-c', '--clustername', action='append', type=str, default=None)
parser.add_argument('-cl', '--clusters', type=str, default=None)
parser.add_argument('-mcm', '--mcm', action='store_true')
parser.add_argument('-k', '--useApiKey', action='store_true')
parser.add_argument('-pwd', '--password', type=str, default=None)
parser.add_argument('-np', '--noprompt', action='store_true')
parser.add_argument('-s', '--severity', type=str, default=None)
parser.add_argument('-t', '--alerttype', type=int, default=None)
parser.add_argument('-r', '--resolution', type=str, default=None)
parser.add_argument('-o', '--olderthan', type=int, default=0)

args = parser.parse_args()

vip = args.vip            # cluster name/ip
username = args.username  # username to connect to cluster
domain = args.domain      # domain of username (e.g. local, or AD domain)
clustername = args.clustername
clusterlist = args.clusters
mcm = args.mcm
useApiKey = args.useApiKey
password = args.password
noprompt = args.noprompt
severity = args.severity
alerttype = args.alerttype
resolution = args.resolution
olderthan = args.olderthan

olderthanUsecs = timeAgo(olderthan, 'days')
now = datetime.now()
nowUsecs = dateToUsecs(now.strftime("%Y-%m-%d %H:%M:%S"))

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

# if connected to helios or mcm, select access cluster
for cluster in clusternames:
    if mcm or vip.lower() == 'helios.cohesity.com':
    
       heliosCluster(cluster)
       print (cluster)
    if LAST_API_ERROR() != 'OK':
        exit(1)
# end authentication =====================================================


    alerts = api('get', 'alerts?maxAlerts=1000')

    alerts = [a for a in alerts if a['alertState'] != 'kResolved']

    if severity is not None:
         alerts = [a for a in alerts if a['severity'].lower() == severity.lower()]

    if alerttype is not None:
        alerts = [a for a in alerts if a['alertType'] == alerttype]

    if olderthan is not None:
        alerts = [a for a in alerts if a['latestTimestampUsecs'] < olderthanUsecs]

    alertcount = len(alerts)
    print("Total", alertcount)

    alertIds = [a['id'] for a in alerts]

    for alert in alerts:
        print('%s\t%s\t%s' % (alert['alertType'], alert['severity'], alert['alertDocument']['alertDescription']))

    if resolution is not None:
        alertResolution = {
            "alertIdList": alertIds,
            "resolutionDetails": {
                "resolutionDetails": resolution,
                "resolutionSummary": resolution
            }



        }
    
        result = api ('post', 'alertResolutions', alertResolution)
