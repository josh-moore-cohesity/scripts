#!/usr/bin/env python
"""Register a remote cluster replication partnership between two clusters (via Helios)"""

### usage: ./register_remote_cluster.py -lc ClusterA -lu admin -rc ClusterB -ru admin

### usage: ./register_remote_cluster.py -lc ClusterA -lu admin -lsd DefaultStorageDomain \
#                                        -rc ClusterB -ru admin -rsd DefaultStorageDomain

### import pyhesity wrapper module
from pyhesity import *
import getpass

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

parser.add_argument('-lc', '--localcluster', type=str, required=True)          # local cluster name (as registered in Helios)
parser.add_argument('-lu', '--localusername', type=str, required=True)         # local cluster admin username
parser.add_argument('-ld', '--localdomain', type=str, default='local')         # local cluster admin user domain
parser.add_argument('-lp', '--localpassword', type=str, default=None)          # local cluster admin password
parser.add_argument('-lsd', '--localstoragedomain', type=str, default='DefaultStorageDomain')

parser.add_argument('-rc', '--remotecluster', type=str, required=True)         # remote cluster name (as registered in Helios)
parser.add_argument('-ru', '--remoteusername', type=str, required=True)        # remote cluster admin username
parser.add_argument('-rd', '--remotedomain', type=str, default='local')        # remote cluster admin user domain
parser.add_argument('-rp', '--remotepassword', type=str, default=None)         # remote cluster admin password
parser.add_argument('-rsd', '--remotestoragedomain', type=str, default='DefaultStorageDomain')

parser.add_argument('-ra', '--remoteaccess', action='store_true')              # enable remote access

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

localClusterName = args.localcluster
localUsername = args.localusername
localDomain = args.localdomain
localPassword = args.localpassword
localStorageDomain = args.localstoragedomain

remoteClusterName = args.remotecluster
remoteUsername = args.remoteusername
remoteDomain = args.remotedomain
remotePassword = args.remotepassword
remoteStorageDomain = args.remotestoragedomain

remoteAccess = args.remoteaccess

# look up a storage domain by name, falling back to the cluster's only storage domain if there's no match
def getStorageDomain(name, clustername):
    storageDomains = api('get', 'storage-domains?matchPartialNames=false&includeTenants=true&includeStats=true', v=2)
    storageDomains = storageDomains['storageDomains'] if storageDomains else []
    match = [d for d in storageDomains if d['name'].lower() == name.lower()]
    if match:
        return match[0]['id'], match[0]['name']
    if len(storageDomains) == 1:
        print('storage domain "%s" not found on %s, using "%s" instead' % (name, clustername, storageDomains[0]['name']))
        return storageDomains[0]['id'], storageDomains[0]['name']
    print('storage domain "%s" not found on %s' % (name, clustername))
    print('available storage domains: %s' % ', '.join(sorted(d['name'] for d in storageDomains)))
    exit(1)

# authenticate
apiauth(vip=vip, username=username, domain=domain, password=password, useApiKey=useApiKey, helios=mcm, prompt=(not noprompt), mfaCode=mfacode, emailMfaCode=emailmfacode)

# exit if not authenticated
if apiconnected() is False:
    print('authentication failed')
    exit(1)

# end authentication =====================================================

### cluster admin credentials are used to establish the replication trust,
### independent of the Helios login used above, so prompt if not supplied
if localPassword is None:
    localPassword = getpass.getpass("Enter password for %s\\%s on %s: " % (localDomain, localUsername, localClusterName))

if remotePassword is None:
    remotePassword = getpass.getpass("Enter password for %s\\%s on %s: " % (remoteDomain, remoteUsername, remoteClusterName))

### gather local cluster info
heliosCluster(localClusterName)
if LAST_API_ERROR() != 'OK':
    print('%s not connected to Helios' % localClusterName)
    exit(1)
localClusterInfo = api('get', 'cluster')
localStorageDomainId, localStorageDomain = getStorageDomain(localStorageDomain, localClusterName)
localNodeIp = api('get', 'nodes')[0]['ip']

### gather remote cluster info
heliosCluster(remoteClusterName)
if LAST_API_ERROR() != 'OK':
    print('%s not connected to Helios' % remoteClusterName)
    exit(1)
remoteClusterInfo = api('get', 'cluster')
remoteStorageDomainId, remoteStorageDomain = getStorageDomain(remoteStorageDomain, remoteClusterName)
remoteNodeIp = api('get', 'nodes')[0]['ip']

### add remoteCluster as partner on localCluster
localToRemote = {
    'name': remoteClusterInfo['name'],
    'clusterIncarnationId': remoteClusterInfo['incarnationId'],
    'clusterId': remoteClusterInfo['id'],
    'remoteIps': [
        remoteNodeIp
    ],
    'allEndpointsReachable': True,
    'viewBoxPairInfo': [
        {
            'localViewBoxId': localStorageDomainId,
            'localViewBoxName': localStorageDomain,
            'remoteViewBoxId': remoteStorageDomainId,
            'remoteViewBoxName': remoteStorageDomain
        }
    ],
    'userName': remoteUsername,
    'password': remotePassword,
    'compressionEnabled': True,
    'purposeReplication': True,
    'purposeRemoteAccess': False
}

### add localCluster as partner on remoteCluster
remoteToLocal = {
    'name': localClusterInfo['name'],
    'clusterIncarnationId': localClusterInfo['incarnationId'],
    'clusterId': localClusterInfo['id'],
    'remoteIps': [
        localNodeIp
    ],
    'allEndpointsReachable': True,
    'viewBoxPairInfo': [
        {
            'localViewBoxId': remoteStorageDomainId,
            'localViewBoxName': remoteStorageDomain,
            'remoteViewBoxId': localStorageDomainId,
            'remoteViewBoxName': localStorageDomain
        }
    ],
    'userName': localUsername,
    'password': localPassword,
    'compressionEnabled': True,
    'purposeReplication': True,
    'purposeRemoteAccess': False
}

if remoteAccess:
    localToRemote['purposeRemoteAccess'] = True
    remoteToLocal['purposeRemoteAccess'] = True

### join clusters (routed through Helios to whichever cluster is currently selected)
print('Adding replication partnership %s <- %s' % (localClusterInfo['name'], remoteClusterInfo['name']))
heliosCluster(remoteClusterName)
remotePartner = api('post', 'remoteClusters', remoteToLocal)

print('Adding replication partnership %s -> %s' % (localClusterInfo['name'], remoteClusterInfo['name']))
heliosCluster(localClusterName)
localPartner = api('post', 'remoteClusters', localToRemote)
