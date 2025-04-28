#!/usr/bin/env python

from pyhesity import *
import argparse
import codecs
from datetime import datetime

parser = argparse.ArgumentParser()
parser.add_argument('-v', '--vip', type=str, default='helios.cohesity.com')
parser.add_argument('-u', '--username', type=str, default='helios')
parser.add_argument('-i', '--useApiKey', action='store_true')
parser.add_argument('-mcm', '--mcm', action='store_true')
parser.add_argument('-c', '--clustername', nargs='+', type=str, default=None)
parser.add_argument('-ol', '--clusterlist', type=str, default=None)
parser.add_argument('-un', '--usernames', nargs='+', type=str, default=None)
parser.add_argument('-ul', '--userlist', type=str, default=None)
parser.add_argument('-a', '--action', type=str, default='query', choices=['add', 'remove', 'query'])

args = parser.parse_args()

vip = args.vip
username = args.username
mcm = args.mcm
useApiKey = args.useApiKey
clustername = args.clustername
clusterlist = args.clusterlist
usernames = args.usernames
userlist = args.userlist
action = args.action

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
clusternames = gatherList(clustername, clusterlist, name='Clusters', required=True)

# get list of users
usernames = gatherList(usernames, userlist, name='Users', required=True)

#Exit if Removing all clusters from a user was attempted.
if clusternames == ['all'] and action == 'remove':
    print("Cannot Remove All Clusters from a user")
    exit()

# authentication =========================================================
apiauth(vip=vip, username=username, useApiKey=useApiKey)

# exit if not authenticated
if apiconnected() is False:
    print('authentication failed')
    exit(1)

# end authentication =====================================================

#Get Clusters
clusterinfo = api('get', 'cluster-mgmt/info',mcmv2=True)
clusterinfo = clusterinfo['cohesityClusters']

#Capture all Cluster IDs
clusterids = []
for cluster in clusterinfo:
    clusterid = cluster['clusterId']
    clusterincid = cluster['clusterIncarnationId']
    clusterids.append('%s:%s' % (clusterid, clusterincid))

#Get IDP(SSO) Users
idpusers = api('get', 'idps/principals', mcmv2=True)
idpusers = idpusers['principals']

for user in usernames:
    idpuser = [u for u in idpusers  if u['name'] == user][0]
    if not idpuser:
       print("User %s not found" % user)
       continue

    #Query Cluster Access
    if action == "query":
        if idpuser['clusters'] == ['-1:-1']:
            print("%s has all cluster access" % (user))
        else:
            print("%s has access to:" % idpuser['name'])
            userclusters = idpuser['clusters']

            for cluster in userclusters:
                clusterid = cluster.split(':')[0]
                for record in clusterinfo:
                    if record['clusterId'] == int(clusterid):
                        print(record['clusterName'])
        continue

    #Skip if adding "all" clusters and user already has "all" cluster access
    if idpuser['clusters'] == ['-1:-1'] and action == "add":
        print("%s already has all cluster access" % idpuser['name'])
        continue

    #Set user sid
    usersid = idpuser['sid']

    #Add all clusters to user if clusters = all
    if clusternames == ['all'] and action == "add":
        print("Adding all clusters for", idpuser['name'])
        idpuser['clusters'] = ['-1:-1']
    
    #Add/Remove individual clusters to/from user
    else:
        for cluster in clusternames:
            try:
                newcluster = [c for c in clusterinfo if c['clusterName'].lower() == cluster.lower()][0]
            except:
                print("Cluster %s not found" % cluster)
                continue
            if len(newcluster) == 0:
                print("Cluster %s not found" % cluster)
                continue
            newclusterid = newcluster['clusterId']
            newclusterincid = newcluster['clusterIncarnationId']
            
            #Add Cluster(s) to User
            if action == "add" and ('%s:%s' % (newclusterid, newclusterincid)) not in idpuser['clusters']:
                print("Adding %s for %s" % (cluster, idpuser['name']))
                idpuser['clusters'].append('%s:%s' % (newclusterid, newclusterincid))

            if action == "add" and ('%s:%s' % (newclusterid, newclusterincid)) in idpuser['clusters']:
                print("%s already has access to %s" % (idpuser['name'], cluster))
                continue
    
            #Remove Cluster from User
            if action == "remove":
                #If going from "all" clusters to specific clusters
                if idpuser['clusters'] == ['-1:-1']:
                    idpuser['clusters'].remove('-1:-1')
                    for id in clusterids:
                        idpuser['clusters'].append(id)
                if ('%s:%s' % (newclusterid, newclusterincid)) not in idpuser['clusters']:
                    print("Cluster %s not in %s Access List" % (cluster, idpuser['name']))
                    continue
                print("Removing %s from %s" % (cluster, idpuser['name']))
                idpuser['clusters'].remove('%s:%s' % (newclusterid, newclusterincid))    
                print(idpuser['clusters'])

    #API Call to update User
    api('put', 'idps/principals/%s' % usersid, idpuser, mcmv2=True)
