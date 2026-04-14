#!/usr/bin/env python
"""Get Registered Agent Details"""

### import pyhesity wrapper module
from pyhesity import *
from datetime import datetime
import codecs
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

outfile = 'agent-summary-%s.csv' % dateString
f = codecs.open(outfile, 'w')
f.write('Cluster Name,Host,OS Type, Health,Cluster Version,Agent Version,Upgradability,Certficate Issuer,Certificate Status,Certificate Expiry,Port\n')
report = []

#get cluster list if clusters is set to all
if clusternames[0] == "all":
    clusters = api('get', 'cluster-mgmt/info',mcmv2=True)
    clusters = clusters['cohesityClusters']
    connectedclusters = [c for c in clusters if c['isConnectedToHelios'] == True]
    disconnectedclusters = [c for c in clusters if c['isConnectedToHelios'] == False]

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

for clustername in clusterlist:
    heliosCluster(clustername)
    print(clustername)

    if LAST_API_ERROR() != 'OK':
        continue
    
    clusterinfo = api('get', 'cluster')
    if clusterinfo is None:
        print("Error Running API on Cluster")
        report.append('%s,API Error' % clustername)
        continue
    clusterversion = clusterinfo.get('clusterSoftwareVersion')

    agents = api('get', 'reports/agents')

    if agents is None or len(agents) == 0:
        print("No Agents Registered")
        report.append('%s,No Agents Registered' % clustername)
        continue

    for agent in agents:
        ostype = agent.get('hostOsType')
        hostip = agent.get('hostIp')
        agentversion = agent.get('version')
        health = agent.get('healthStatus')
        upgradability = agent.get('upgradability')
        certissuer = agent.get('certificateIssuer')
        certstatus = agent.get('certificateStatus')
        certexpiry = usecsToDateTime(agent.get('certificateExpiryTimeUsecs'))
        agentport = agent.get('agentPort')
        report.append(str('%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s') % (clustername,hostip,ostype,health,clusterversion,agentversion,upgradability,certissuer,certstatus,certexpiry,agentport))

for item in report:
    f.write('%s\n' % item)

f.close()
print('\nOutput saved to %s\n' % outfile)
