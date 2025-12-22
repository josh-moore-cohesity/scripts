#!/usr/bin/env python
"""Script Overview"""

### import pyhesity wrapper module
from pyhesity import *
from datetime import datetime
import json
import os

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

# get list of clusters
clusternames = gatherList(clustername, clusterlist, name='clusters', required=True)

# authentication =========================================================
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
    heliosCluster(clustername)
    thisclusterpath = "%s/%s" % (outputpath,clustername)
    os.makedirs(thisclusterpath, exist_ok=True)
    
    #Cluster Summary and Config
    clusterconfig = api('get', 'cluster')

    #Summary
    summary = []
    summary_output_file = os.path.join(thisclusterpath, 'clusterSummary.txt')
    summary.append('Cluster Name: %s' % clusterconfig['name'])
    summary.append('Cluster ID: %s' % clusterconfig['id'])
    summary.append('Version: %s' % clusterconfig['clusterSoftwareVersion'])
    summary.append('Node Count: %s' % clusterconfig['nodeCount'])
    summary.append('Domain Names: %s' % ','.join(clusterconfig['domainNames']))
    summary.append('DNS Servers: %s' % ','.join(clusterconfig['dnsServerIps']))

    with open(summary_output_file, 'w') as f:
        for item in summary:
            f.write(str(item) + '\n')
    print(f"API data successfully saved to {summary_output_file}")

    #Cluster Config
    config_output_file = os.path.join(thisclusterpath, 'cluster_config.json')

    with open(config_output_file, 'w') as f:
        json.dump(clusterconfig, f, indent=4)
    print(f"API data successfully saved to {config_output_file}")

    #Storage Domains
    viewboxes = api('get', 'viewBoxes')
    viewboxes_output_file = os.path.join(thisclusterpath, 'storageDomains.json')

    with open(viewboxes_output_file, 'w') as f:
        json.dump(viewboxes, f, indent=4)
    print(f"API data successfully saved to {viewboxes_output_file}")

    #Cluster Partitions
    partitions = api('get', 'clusterPartitions')
    partitions_output_file = os.path.join(thisclusterpath, 'clusterPartitions.json')

    with open(partitions_output_file, 'w') as f:
        json.dump(partitions, f, indent=4)
    print(f"API data successfully saved to {partitions_output_file}")

    #SMTP Servers
    smtp = api('get', '/smtpServer')
    smtp_output_file = os.path.join(thisclusterpath, 'smtp.json')

    with open(smtp_output_file, 'w') as f:
        json.dump(smtp, f, indent=4)
    print(f"API data successfully saved to {smtp_output_file}")

    #SNMP
    snmp = api('get', '/snmp/config')
    snmp_output_file = os.path.join(thisclusterpath, 'snmp.json')

    with open(snmp_output_file, 'w') as f:
        json.dump(snmp, f, indent=4)
    print(f"API data successfully saved to {snmp_output_file}")

    #NETWORKING

    #Interface Groups
    interfacegroups = api('get', 'interfaceGroups')
    interfacegroups_output_file = os.path.join(thisclusterpath, 'interfaceGroups.json')

    with open(interfacegroups_output_file, 'w') as f:
        json.dump(interfacegroups, f, indent=4)
    print(f"API data successfully saved to {interfacegroups_output_file}")

    #VLANS
    vlans = api('get', 'vlans?skipPrimaryAndBondIface=true')
    vlans_output_file = os.path.join(thisclusterpath, 'vlans.json')

    with open(vlans_output_file, 'w') as f:
        json.dump(vlans, f, indent=4)
    print(f"API data successfully saved to {vlans_output_file}")

    #Hosts File
    hosts = api('get', '/nexus/cluster/get_hosts_file')
    hosts_output_file = os.path.join(thisclusterpath, 'hosts.json')

    with open(hosts_output_file, 'w') as f:
        json.dump(hosts, f, indent=4)
    print(f"API data successfully saved to {hosts_output_file}")

    #ACCESS MANAGEMENT

    #Active Directory
    activedirectory = api('get', 'activeDirectory')
    activedirectory_output_file = os.path.join(thisclusterpath, 'activeDirectory.json')

    with open(activedirectory_output_file, 'w') as f:
        json.dump(activedirectory, f, indent=4)
    print(f"API data successfully saved to {activedirectory_output_file}")

    #idps
    idps = api('get', 'idps?allUnderHierarchy=true')
    idps_output_file = os.path.join(thisclusterpath, 'idps.json')

    with open(idps_output_file, 'w') as f:
        json.dump(idps, f, indent=4)
    print(f"API data successfully saved to {idps_output_file}")

    #ldapProvider
    ldap = api('get', 'ldapProvider')
    ldap_output_file = os.path.join(thisclusterpath, 'ldap.json')

    with open(ldap_output_file, 'w') as f:
        json.dump(ldap, f, indent=4)
    print(f"API data successfully saved to {ldap_output_file}")

    #Roles
    roles = api('get', 'roles')
    roles_output_file = os.path.join(thisclusterpath, 'roles.json')

    with open(roles_output_file, 'w') as f:
        json.dump(roles, f, indent=4)
    print(f"API data successfully saved to {roles_output_file}")

    #Users
    users = api('get', 'users')
    users_output_file = os.path.join(thisclusterpath, 'users.json')

    with open(users_output_file, 'w') as f:
        json.dump(users, f, indent=4)
    print(f"API data successfully saved to {users_output_file}")

    #Groups
    groups = api('get', 'groups')
    groups_output_file = os.path.join(thisclusterpath, 'groups.json')

    with open(groups_output_file, 'w') as f:
        json.dump(groups, f, indent=4)
    print(f"API data successfully saved to {groups_output_file}")

    #COPY TARGETS

    #Remote Clusters
    remoteclusters = api('get', 'remoteClusters')
    remoteclusters_output_file = os.path.join(thisclusterpath, 'remoteClusters.json')

    with open(remoteclusters_output_file, 'w') as f:
        json.dump(remoteclusters, f, indent=4)
    print(f"API data successfully saved to {remoteclusters_output_file}")

    #Vaults
    vaults = api('get', 'vaults')
    vaults_output_file = os.path.join(thisclusterpath, 'vaults.json')

    with open(vaults_output_file, 'w') as f:
        json.dump(vaults, f, indent=4)
    print(f"API data successfully saved to {vaults_output_file}")

    #DATA PROTECTION

    #Sources
    sources = api('get', 'protectionSources?allUnderHierarchy=true')
    sources_output_file = os.path.join(thisclusterpath, 'sources.json')

    with open(sources_output_file, 'w') as f:
        json.dump(sources, f, indent=4)
    print(f"API data successfully saved to {sources_output_file}")

    #Policies
    policies = api('get', 'data-protect/policies?allUnderHierarchy=true', v=2)
    policies_output_file = os.path.join(thisclusterpath, 'policies.json')

    with open(policies_output_file, 'w') as f:
        json.dump(policies, f, indent=4)
    print(f"API data successfully saved to {policies_output_file}")

    #Protection Groups
    pgs = api('get', 'data-protect/protection-groups?allUnderHierarchy=true', v=2)
    pgs_output_file = os.path.join(thisclusterpath, 'protectionGroups.json')

    with open(pgs_output_file, 'w') as f:
        json.dump(pgs, f, indent=4)
    print(f"API data successfully saved to {pgs_output_file}")

    #FILE SERVICES

    #Views
    views = api('get', 'views?allUnderHierarchy=true')
    views_output_file = os.path.join(thisclusterpath, 'views.json')

    with open(views_output_file, 'w') as f:
        json.dump(views, f, indent=4)
    print(f"API data successfully saved to {views_output_file}")

    #Global Whitelist
    whitelist = api('get', 'externalClientSubnets')
    whitelist_output_file = os.path.join(thisclusterpath, 'globalWhitelist.json')

    with open(whitelist_output_file, 'w') as f:
        json.dump(whitelist, f, indent=4)
    print(f"API data successfully saved to {whitelist_output_file}")

    #Shares
    shares = api('get', 'shares')
    shares_output_file = os.path.join(thisclusterpath, 'shares.json')

    with open(shares_output_file, 'w') as f:
        json.dump(shares, f, indent=4)
    print(f"API data successfully saved to {shares_output_file}")
