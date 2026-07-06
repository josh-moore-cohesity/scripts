#!/usr/bin/env python
"""Script Overview"""

### import pyhesity wrapper module
from pyhesity import *
from datetime import datetime

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
parser.add_argument('-ea', '--emailalerts', type=str, action='append', default=None)

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
emailalerts = args.emailalerts

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
    
    #Get PGs
    pgs = api('get', 'data-protect/protection-groups?environments=kVMware&isDeleted=false&isActive=true', v=2)    
    pgs = pgs['protectionGroups']

   #Update PG Alert Recipents
    for pg in pgs:
        pgname = pg['name']
        if emailalerts is not None and len(emailalerts) > 0:
            existingTargets = pg['alertPolicy'].get('alertTargets', [])
            existingEmails = [t['emailAddress'] for t in existingTargets]

            newTargets = [
                {
                    "emailAddress": e,
                    "language": "en-us",
                    "recipientType": "kTo"
                }
                for e in emailalerts
                if e not in existingEmails
            ]

            pg['alertPolicy']['alertTargets'] = existingTargets + newTargets
            
        print('Updating protection job %s' % pgname)
        result = api('put', 'data-protect/protection-groups/%s' % pg['id'], pg, v=2)
