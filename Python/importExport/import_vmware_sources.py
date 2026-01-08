#!/usr/bin/env python
"""Script Overview"""

### import pyhesity wrapper module
from pyhesity import *
from datetime import datetime
import json
import os
import getpass

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
parser.add_argument('-o', '--outputpath', type=str, default='./configExports')

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
outputpath = args.outputpath

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

# authentication =========================================================

if(mcm or vip.lower() != 'helios.cohesity.com'):
    clusternames = []
    clusternames.append(vip)

# Get cluster name or cluster list if connecting to helios or mcm
elif (mcm or vip.lower() == 'helios.cohesity.com'):
    clusternames = gatherList(clustername, clusterlist, name='clusters', required=True)


apiauth(vip=vip, username=username, useApiKey=useApiKey, helios=mcm, prompt=(not noprompt), mfaCode=mfacode, emailMfaCode=emailmfacode)

# exit if not authenticated
if apiconnected() is False:
    print('authentication failed')
    exit(1)

# end authentication =====================================================

#Date
now = datetime.now()
dateString = now.strftime("%Y-%m-%d")


for clustername in clusternames:
    print(clustername)
    # if connected to helios or mcm, select access cluster
    if mcm or vip.lower() == 'helios.cohesity.com':
        heliosCluster(clustername)
    if LAST_API_ERROR() != 'OK':
        continue
    thisclusterpath = "%s/%s" % (outputpath,clustername)

    #Sources
    sources_output_file = os.path.join(thisclusterpath, 'sources.json')

    with open(sources_output_file, 'r') as file:
        sources_payload = json.load(file)

    currentsources = api('get', 'protectionSources?registrationInfo?includeEntityPermissionInfo=true&environments=kVMware')

    for source in sources_payload:
        if source['protectionSource']['environment'] == "kVMware":
            vcenterusername = source['registrationInfo']['username']
            vcentername = source['protectionSource']['name']
            vcenterendpoint = source['registrationInfo']['accessInfo']['endpoint']
            vmwaretype = source['protectionSource']['vmWareProtectionSource']['type']
            if vmwaretype == "kStandaloneHost":
                type = 10
            if vmwaretype == "kVCenter":
                type = 1
            print(vcentername)
            print(type)

            currentsource = [s for s in currentsources if s['protectionSource']['name'].lower() == vcentername.lower()]

            if len(currentsource) == 0:
                vcenterpassword = getpass.getpass("Enter the password for %s: " % vcenterusername)
                vCenterParams = {
                        "entity": {
                            "type": 1,
                            "vmwareEntity": {
                                "type": type
                            }
                        },
                        "entityInfo": {
                            "endpoint": vcenterendpoint,
                            "type": 1,
                            "credentials": {
                                "username": vcenterusername,
                                "password": vcenterpassword
                            }
                        },
                        "registeredEntityParams": {
                            "isSpaceThresholdEnabled": False,
                            "spaceUsagePolicy": {},
                            "throttlingPolicy": {
                                "isThrottlingEnabled": False,
                                "isDatastoreStreamsConfigEnabled": False,
                                "datastoreStreamsConfig": {}
                            },
                            "vmwareParams": {}
                        }
                    }
                print('Adding Source %s' % vcentername)
                newsource = api('post', '/backupsources', vCenterParams)

            else:
                print('Source %s already exists...' % vcentername)
