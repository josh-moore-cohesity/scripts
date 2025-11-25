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
parser.add_argument('-np', '--noprompt', action='store_true')
parser.add_argument('-m', '--mfacode', type=str, default=None)
parser.add_argument('-e', '--emailmfacode', action='store_true')
parser.add_argument('-c', '--clustername', nargs='+', type=str, default=None)
parser.add_argument('-cl', '--clusters', type=str, default=None)

args = parser.parse_args()

vip = args.vip
username = args.username
mcm = args.mcm
useApiKey = args.useApiKey
noprompt = args.noprompt
mfacode = args.mfacode
emailmfacode = args.emailmfacode
clustername = args.clustername
clusterlist = args.clusters

# authentication =========================================================
apiauth(vip=vip, username=username, useApiKey=useApiKey, helios=mcm, prompt=(not noprompt), mfaCode=mfacode, emailMfaCode=emailmfacode)

# exit if not authenticated
if apiconnected() is False:
    print('authentication failed')
    exit(1)

# end authentication =====================================================

#Date and Time
now = datetime.now()
datetimestring = now.strftime("%m/%d/%Y %I:%M %p")
dateString = now.strftime("%Y-%m-%d")

# gather server list
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

# Combine list of clusters
clusternames = gatherList(clustername, clusterlist, name='clusters')

#Apps File
appsfile = 'datahawk-app-status-%s.csv' % dateString
af = codecs.open(appsfile, 'w', 'utf-8')
af.write('Cluster,App Name,Installed,State,Health Status,Health Detail\n')
appsreport = []

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

    print(cluster)

    #Connect to Cluster
    heliosCluster (cluster)

    #Cluster Info
    clusterinfo = api('get', 'cluster')
    if clusterinfo is None:
        print("API Error for", cluster, "...skipping")
        continue

    #Get Apps
    installstate = "Not Installed"
    appsmode = api('get', 'cluster/appSettings')
    if appsmode['marketplaceAppsMode'] == 'kDisabled':
        print('Apps Disabled')
        appsreport.append(str('%s,%s' % (clusterinfo['name'],'Apps Disabled')))
        continue

    #Filter for DataHawk App and get details    
    if appsmode['marketplaceAppsMode'] == 'kBareMetal':
        apps = api('get', 'apps')
        datahawkapp = [a for a in apps if a['metadata'] and a['metadata']['name'] == 'DataHawk Engines']

        for dhapp in datahawkapp:
            if 'installState' in dhapp:
                installstate = dhapp['installState']

        #Get DH App Instances
        appinstances = api('get', 'appInstances')
        runningapps = [i for i in appinstances if i['appName'] == 'DataHawk Engines' and i['state'] != 'kTerminated']
        totalinstances = len(runningapps)
        if totalinstances > 0:
            for runningapp in runningapps:
                appname = runningapp['appName']
                appstate = runningapp['state']
                healthstatus = runningapp['healthStatus']
                healthDetail = runningapp['healthDetail']
                appsreport.append(str('%s,%s,%s,%s,%s,%s' % (clusterinfo['name'],appname,installstate,appstate,healthstatus,healthDetail)))
                if healthstatus != 'kHealthy':
                    print('%s,%s,%s' % (appname,healthstatus,healthDetail))
        else:
            appname = "DataHawk Engines"
            print('%s,%s,%s' % (appname,installstate,'Not Running'))
            appsreport.append(str('%s,%s,%s,%s' % (clusterinfo['name'],appname,installstate,'Not Running')))

#write Apps to report
for app in sorted(appsreport):
    af.write ('%s\n' % app)
af.close()
print('\nApps Output saved to %s\n' % appsfile)
