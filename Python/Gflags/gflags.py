#!/usr/bin/env python
"""list gflags with python"""

# import pyhesity wrapper module
from pyhesity import *
import codecs
from time import sleep
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
parser.add_argument('-k', '--useApiKey', action='store_true')
parser.add_argument('-pwd', '--password', type=str, default=None)
parser.add_argument('-np', '--noprompt', action='store_true')
parser.add_argument('-m', '--mfacode', type=str, default=None)
parser.add_argument('-em', '--emailmfacode', action='store_true')
parser.add_argument('-s', '--servicename', type=str, default=None)
parser.add_argument('-n', '--flagname', type=str, default=None)
parser.add_argument('-f', '--flagvalue', type=str, default=None)
parser.add_argument('-r', '--reason', type=str, default=None)
parser.add_argument('-e', '--effectivenow', action='store_true')
parser.add_argument('-clear', '--clear', action='store_true')
parser.add_argument('-i', '--importfile', type=str, default=None)
parser.add_argument('-x', '--restartservices', action='store_true')

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
servicename = args.servicename
flagname = args.flagname
flagvalue = args.flagvalue
reason = args.reason
effectivenow = args.effectivenow
importfile = args.importfile
clear = args.clear
restartservices = args.restartservices

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

# authentication =========================================================
# demand clustername if connecting to helios or mcm
if (mcm or vip.lower() == 'helios.cohesity.com') and clusternames is None:
    print('-c, --clustername is required when connecting to Helios or MCM')
    exit(1)

# authenticate
apiauth(vip=vip, username=username, domain=domain, password=password, useApiKey=useApiKey, helios=mcm, prompt=(not noprompt), mfaCode=mfacode, emailMfaCode=emailmfacode)

# exit if not authenticated
if apiconnected() is False:
    print('authentication failed')
    exit(1)


# end authentication =====================================================

#Date and Time
now = datetime.now()
datetimestring = now.strftime("%m/%d/%Y %I:%M %p")
dateString = now.strftime("%Y-%m-%d")

report = []

#get cluster list if clusters is set to all
if clusternames[0] == "all":
    clusters = api('get', 'cluster-mgmt/info',mcmv2=True)
    clusters = clusters['cohesityClusters']
    connectedclusters = [c for c in clusters if c['isConnectedToHelios'] == True]
    disconnectedclusters = [c for c in clusters if c['isConnectedToHelios'] == False]

    exportfile = 'all-cluster-gflags-%s.csv' % dateString
    f = codecs.open(exportfile, 'w', 'utf-8')
    f.write('Cluster,Service Name,Flag Name,Flag Value,Reason\n')
    
    if len(disconnectedclusters) > 0:
        for cluster in disconnectedclusters:
            clustername = cluster['clusterName']
            report.append('%s,Disconnected From Helios' % clustername)

    clusterlist = []

    for cluster in connectedclusters:
        clustername = cluster['clusterName']
        clusterlist.append(clustername)

#else use specified clusters
else:
    clusterlist = clusternames


for cluster in clusterlist:
    # if connected to helios or mcm, select access cluster
    print(cluster)
        # set gflags export file
    if clusternames[0] != "all":
        exportfile = 'gflags-%s.csv' % cluster
        f = codecs.open(exportfile, 'w', 'utf-8')
        f.write('Cluster,Service Name,Flag Name,Flag Value,Reason\n')

    if mcm or vip.lower() == 'helios.cohesity.com':
        heliosCluster(cluster)

    if LAST_API_ERROR() != 'OK':
        f.write('%s,Disconnected From Helios' % cluster)
        f.close()
        print('\nGflags saved to %s\n' % exportfile)
        continue
    
    localcluster = api('get', 'cluster')

    if localcluster == None:
        print("API Error On Cluster")
        report.append('%s,Server API Error' % cluster)
        continue
    
    def setGflag(servicename, flagname, reason, flagvalue=None):

        if clear is True:
            print('Clearing %s: %s' % (servicename, flagname))
            gflag = {
                'serviceName': servicename,
                'gflags': [
                    {
                        'name': flagname,
                        'clear': True,
                        'reason': reason
                    }
                ],
                'effectiveNow': False
            }
        else:
            print('Setting %s: %s = %s' % (servicename, flagname, flagvalue))
            gflag = {
                'serviceName': servicename,
                'gflags': [
                    {
                        'name': flagname,
                        'value': flagvalue,
                        'reason': reason
                    }
                ],
                'effectiveNow': False
            }
        if effectivenow:
            gflag['effectiveNow'] = True
        response = api('put', '/clusters/gflag', gflag)
        sleep(1)


    servicestorestart = []
    servicescantrestart = []

    # set a flag
    if flagvalue is not None or clear is True:
        if servicename is None or flagname is None or reason is None:
            print('-servicename, -flagname, -flagvalue and -reason are all required to set a gflag')
            exit()
        else:
            setGflag(servicename=servicename, flagname=flagname, flagvalue=flagvalue, reason=reason)
            servicestorestart.append(servicename[1:].lower())

    # import gflags fom export file
    flagdata = []
    if importfile is not None:
        fi = codecs.open(importfile, 'r', 'utf-8')
        flagdata += [s.strip() for s in fi.readlines() if s.strip() != '']
        fi.close()
        for flag in flagdata:
            (importservicename, importflagname, importflagvalue, importreason) = flag.split(',', 3)
            importflagvalue = importflagvalue.replace(';;', ',')
            print(importservicename,importflagname,importflagvalue,importreason)
            setGflag(servicename=importservicename, flagname=importflagname, flagvalue=importflagvalue, reason=importreason)
            if importservicename.lower() != 'nexus':
                servicestorestart.append(importservicename[1:].lower())
            else:
                servicescantrestart.append(importservicename[1:].lower())


    # get currrent flags
    flags = api('get', '/clusters/gflag')
    print('\nCurrent GFlags:')

    for service in flags:
        currentservicename = service['serviceName']
        print('\n%s:' % currentservicename)
        if 'gflags' in service:
            gflags = service['gflags']
            customgflags = [g for g in gflags if not g['reason'].startswith('Auto') and not g['reason'].startswith('Maybe')]
            for gflag in customgflags:
                currentflagname = gflag['name']
                currentflagvalue = gflag['value']
                currentreason = gflag['reason']
                print('    %s: %s (%s)' % (currentflagname, currentflagvalue, currentreason))
                currentflagvalue = currentflagvalue.replace(',', ';;')
                report.append('%s,%s,%s,%s,%s' % (cluster, currentservicename, currentflagname, currentflagvalue, currentreason))


    #Restart Services  
    if restartservices is True:
        print('\nRestarting required services...\n')
        restartParams = {
            "clusterId": cluster['id'],
            "services": list(set(servicestorestart))
        }
        response = api('post', '/nexus/cluster/restart', restartParams)

    if restartservices is True and len(servicescantrestart) > 0:
        print('\nCant restart services: %s\n' % ', '.join(servicescantrestart))
    print('\nGflags saved to %s\n' % exportfile)


#Save to File
for record in (report):
    f.write ('%s\n' % record)
f.close()
