#!/usr/bin/env python
"""protect VMware VMs Using Python"""

### import pyhesity wrapper module
from pyhesity import *

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
parser.add_argument('-n', '--vmname', action='append', type=str)
parser.add_argument('-l', '--vmlist', type=str)
parser.add_argument('-vc', '--vcentername', type=str, default=None)


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
vmname = args.vmname
vmlist = args.vmlist
vcentername = args.vcentername


# Functions
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

def getnodes(obj, parentid=0):
    """gather list of VMs and parent/child relationships"""
    global nodes
    global nodeParents
    nodes.append(obj)
    if parentid not in nodeParents.keys():
        nodeParents[parentid] = []
    if obj['protectionSource']['id'] not in nodeParents.keys():
        nodeParents[obj['protectionSource']['id']] = nodeParents[parentid] + [parentid]
    else:
        nodeParents[obj['protectionSource']['id']] = list(set(nodeParents[parentid] + [parentid] + nodeParents[obj['protectionSource']['id']]))
    if 'nodes' in obj:
        for node in obj['nodes']:
            getnodes(node, obj['protectionSource']['id'])

def removeexclude(node, job, reason):
    """add exclusions to protection job"""
    if node['protectionSource']['id'] in job['excludeSourceIds']:
        job['excludeSourceIds'].remove(node['protectionSource']['id'])
        print("   Removing %s from exclusions (%s)" % (node['protectionSource']['name'], reason))

# end functions =========================================

vmnames = gatherList(vmname, vmlist, name='VMs', required=True)


# authenticate
apiauth(vip=vip, username=username, domain=domain, password=password, useApiKey=useApiKey, helios=mcm, prompt=(not noprompt))

# exit if not authenticated
if apiconnected() is False:
    print('authentication failed')
    exit(1)

# end authentication =====================================================

clusters = api('get', 'cluster-mgmt/info',mcmv2=True)
clusters = clusters['cohesityClusters']

for cluster in clusters:
    #Skip Cluster if not connected to Helios
    if cluster['isConnectedToHelios'] == False:
        print(cluster['clusterName'],"Not Connected to Helios")
        continue
    
    print(cluster['clusterName'])

    #Connect to Cluster
    heliosCluster (cluster['clusterName'])

    clusterid = api('get', 'cluster')['id']

    for job in api('get', 'protectionJobs?isDeleted=false'):
        origclusterid = int(job['policyId'].split(':')[0])

        if job['environment'] == 'kVMware' and origclusterid == clusterid:
            print("looking for exclusions in job: %s..." % job['name'])

            parentId = job['parentSourceId']

            # get source info (vCenter)
            parentSource = api('get', 'protectionSources?allUnderHierarchy=true&excludeTypes=kResourcePool&id=%s&includeEntityPermissionInfo=true&includeVMFolders=true' % parentId)[0]

            # gather list of VMs and parent/child relationships
            nodes = []
            parents = []
            nodeParents = {}
            getnodes(parentSource)

            # apply VM exclusion rules
            if 'excludeSourceIds' in job:
                for sourceId in job['excludeSourceIds']:
                    for node in nodes:

                        # if vm (node) is a child of the container (sourceId)
                        if sourceId in [node['protectionSource']['id']]:
                            # if vm name matches an exclusion rule
                            for vmname in vmnames:
                                if vmname.lower() in node['protectionSource']['name'].lower():
                                    removeexclude(node, job, 'Name Match')

                            
                # update job with new exclusions
                updatedJob = api('put', 'protectionJobs/%s' % job['id'], job)
              
