#!/usr/bin/env python
"""Get List of Excluded VMs from each Backup Job"""

# usage: ./get_excluded_vms.py -v helios.cohesity.com -i -c clustername

# import pyhesity wrapper module
from pyhesity import *
from datetime import datetime
import codecs
import os

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
parser.add_argument('-outputpath', '--outputpath', type=str, default='./ExcludedVMs')

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
outputpath = args.outputpath

#DATE
now = datetime.now()
datetimestring = now.strftime("%m/%d/%Y %I:%M %p")
dateString = now.strftime("%Y-%m-%d-%I-%M-%S")

if excludeRules is None:
    excludeRules = []

# functions =============================================

# gather list function
def gatherList(param=None, filename=None, name='items'):
    items = []
    if param is not None:
        for item in param:
            items.append(item)
    if filename is not None:
        f = open(filename, 'r')
        items += [s.strip() for s in f.readlines() if s.strip() != '']
        f.close()
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

# Define outfile
outpath = "%s" % (outputpath)
os.makedirs(outpath, exist_ok=True)

if(clusterlist is not None):
    outfile = os.path.join(outpath, 'excluded-vms-%s-%s.csv' % (dateString, clusterlist))
else:
    outfile = os.path.join(outpath, 'excluded-vms-%s.csv' % dateString)
                           
f = codecs.open(outfile, 'w')

# Add headings to outfile
f.write("Cluster Name,Job Name,VM Name\n")

# end functions =========================================

# get list of clusters
clusternames = gatherList(clustername, clusterlist, name='clusters')

# authenticate

apiauth(vip=vip, username=username, domain=domain, password=password, useApiKey=useApiKey, helios=mcm, prompt=(not noprompt))

# end authentication =====================================================

# exit if not authenticated
if apiconnected() is False:
    print('authentication failed')
    exit(1)

#Get Clusters
if len(clusternames) > 0:
    clusternames = clusternames
else:
    clusters = api('get', 'cluster-mgmt/info',mcmv2=True)
    clusters = clusters['cohesityClusters']
    clusters = [c for c in clusters if c['isConnectedToHelios'] == True]
    clusternames = []
    for cluster in clusters:
        clusternames.append(cluster['clusterName'])

#Get info for each cluster
for cluster in clusternames:
    heliosCluster('-')
    if mcm or vip.lower() == 'helios.cohesity.com':
        
        print (cluster)
        
        #Connect to Cluster
        heliosCluster(cluster)
       
    if LAST_API_ERROR() != 'OK':
        continue

    #Cluster Info
    clusterinfo = api('get', 'cluster')
    if clusterinfo is None:
        print("API Error for", cluster, "...skipping")
        continue
    #Get Cluster ID
    clusterid = clusterinfo['id']

    #Define Exclude List
    excludedvms = []

    #Get Jobs
    jobs = api('get', 'protectionJobs?isDeleted=false')
    if 'error' in jobs:
        job_error_message = jobs['error'].replace('\n', '')
        print("Error Getting Jobs on %s" % cluster)
        continue
    for job in jobs:
        origclusterid = int(job['policyId'].split(':')[0])

        if job['environment'] == 'kVMware' and origclusterid == clusterid:
            print("looking for exclusions in job: %s..." % job['name'])

            parentId = job['parentSourceId']
            
            # get source info (vCenter)
            parentSource = api('get', 'protectionSources?allUnderHierarchy=true&excludeTypes=kResourcePool&id=%s&includeEntityPermissionInfo=true&includeVMFolders=true' % parentId)
            if parentSource is None:
                print("Error Getting Parent Source on %s for Job %s..skipping" % (cluster,job['name']))
                continue
            parentSource = parentSource[0]
            # gather list of VMs and parent/child relationships
            nodes = []
            parents = []
            nodeParents = {}
            getnodes(parentSource)
            
            #Get Excluded VM Info
            if 'excludeSourceIds' in job:
                for excludedid in job['excludeSourceIds']:
                    for node in nodes:
                        if excludedid in [node['protectionSource']['id']]:
                            excludedvms.append(str('%s,%s,%s' %(cluster,job['name'],node['protectionSource']['name'])))
                            print(str('%s,%s,%s' %(cluster,job['name'],node['protectionSource']['name'])))
                excludedvms = list(set(excludedvms))

    #write results to file        
    for item in sorted(excludedvms):
        f.write('%s\n' % item)

f.close()
print('\nOutput saved to %s\n' % outfile)
