#!/usr/bin/env python
"""Apply Exclusion Rules to VM Autoprotect Protection Job"""

# usage: ./excludeVMs.py -v helios.cohesity.com -i -xt -x sql -x ora -x rhel

# import pyhesity wrapper module
from pyhesity import *

# command line arguments
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('-v', '--vip', type=str, default='helios.cohesity.com')
parser.add_argument('-u', '--username', type=str, default='helios')
parser.add_argument('-i', '--useApiKey', action='store_true')
parser.add_argument('-p', '--password', type=str, default=None)
parser.add_argument('-d', '--domain', type=str, default='local')
parser.add_argument('-x', '--exclude', action='append', type=str)
parser.add_argument('-xt', '--excludeTemplates', action='store_true')
parser.add_argument('-np', '--noprompt', action='store_true')
parser.add_argument('-mcm', '--mcm', action='store_true')
parser.add_argument('-m', '--mfacode', type=str, default=None)
parser.add_argument('-e', '--emailmfacode', action='store_true')
parser.add_argument('-c', '--clustername', action='append', type=str, default=None)
parser.add_argument('-cl', '--clusters', type=str, default=None)

args = parser.parse_args()

vip = args.vip                 # cluster name/ip
username = args.username       # username to connect to cluster
domain = args.domain           # domain of username (e.g. local, or AD domain)
excludeTemplates = args.excludeTemplates  # boolean exclude templates or not
excludeRules = args.exclude    # list of substrings to exclude
useApiKey = args.useApiKey
password = args.password
noprompt = args.noprompt
mcm = args.mcm
mfacode = args.mfacode
emailmfacode = args.emailmfacode
clustername = args.clustername
clusterlist = args.clusters

if excludeRules is None:
    excludeRules = []

# functions =============================================

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


def exclude(node, job, reason):
    """add exclusions to protection job"""
    if 'excludeSourceIds' not in job:
        job['excludeSourceIds'] = []
    if node['protectionSource']['id'] not in job['excludeSourceIds']:
        job['excludeSourceIds'].append(node['protectionSource']['id'])
        print("   adding %s to exclusions (%s)" % (node['protectionSource']['name'], reason))


# end functions =========================================

# get list of clusters
clusternames = gatherList(clustername, clusterlist, name='clusters', required=True)

# authenticate
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
            for sourceId in job['sourceIds']:
                for node in nodes:

                    # if vm (node) is a child of the container (sourceId)
                    if sourceId in nodeParents[node['protectionSource']['id']]:

                        # if vm is a template
                        if excludeTemplates is True and 'isVmTemplate' in node['protectionSource']['vmWareProtectionSource']:
                            if node['protectionSource']['vmWareProtectionSource']['isVmTemplate'] is True:
                                exclude(node, job, 'template')

                        # if vm name matches an exclusion rule
                        for excludeRule in excludeRules:
                            if excludeRule.lower() in node['protectionSource']['name'].lower():
                                exclude(node, job, 'rule match')

                        
            # update job with new exclusions
            updatedJob = api('put', 'protectionJobs/%s' % job['id'], job)
