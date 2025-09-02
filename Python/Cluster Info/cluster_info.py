#!/usr/bin/env python

from pyhesity import *
import argparse
import codecs
import json
from datetime import datetime

parser = argparse.ArgumentParser()
parser.add_argument('-v', '--vip', type=str, default='helios.cohesity.com')
parser.add_argument('-u', '--username', type=str, default='helios')
parser.add_argument('-i', '--useApiKey', action='store_true')
parser.add_argument('-mcm', '--mcm', action='store_true')


args = parser.parse_args()

vip = args.vip
username = args.username
mcm = args.mcm
useApiKey = args.useApiKey

# authentication =========================================================
apiauth(vip=vip, username=username, useApiKey=useApiKey)

# exit if not authenticated
if apiconnected() is False:
    print('authentication failed')
    exit(1)

# end authentication =====================================================

#Date and Time
now = datetime.now()
datetimestring = now.strftime("%m/%d/%Y %I:%M %p")
dateString = now.strftime("%Y-%m-%d")

#Cluster File
outfile = 'cluster_info-%s.csv' % dateString

f = codecs.open(outfile, 'w')
f.write('Cluster,Cluster ID,Type,Node Count,Install Date,Timezone,Version,Encryption,Redundancy,Erasure Coding,EC Post Processing,DNS 1,DNS 2,SMTP Enabled,SMTP Server,SMTP Sender,NTP Server,NTP Auth Enabled,NTP Auth Key ID,SSO,Cluster Audit Log Days,Filer Audit Log Days,Apps Network,Critical Alert Email,Custom Roles,Custom Users,Banner\n')
report = []

#GFLAG File
gflagfile = 'cluster_info_gflags-%s.csv' % dateString
gf = codecs.open(gflagfile, 'w', 'utf-8')
gf.write('Cluster,Service Name,Flag Name,Flag Value,Reason\n')
gflagreport = []

#Apps File
appsfile = 'cluster_info_apps-%s.csv' % dateString
af = codecs.open(appsfile, 'w', 'utf-8')
af.write('Cluster,App Name,Running Instances\n')
appsreport = []

#Nodes File
nodesfile = 'cluster_info_nodes-%s.csv' % dateString
nf = codecs.open(nodesfile, 'w', 'utf-8')
nf.write('Cluster,Node,Type,ID,Node IP,Node IPMI IP\n')
nodesreport = []

#Get Clusters
clusters = api('get', 'cluster-mgmt/info',mcmv2=True)
clusters = clusters['cohesityClusters']

#Get info for each cluster
for cluster in clusters:

    #Skip Cluster if not connected to Helios
    if cluster['isConnectedToHelios'] == False:
        print(cluster['clusterName'],"Not Connected to Helios")
        continue
    
    print(cluster['clusterName'])

    #Connect to Cluster
    heliosCluster (cluster['clusterName'])

    #Cluster Info
    clusterinfo = api('get', 'cluster?fetchStats=true')
    if clusterinfo is None:
        print("API Error for", cluster['clusterName'], "...skipping")
        continue
    version = clusterinfo['clusterSoftwareVersion'].split('_r')[0]
    nodecount = clusterinfo['nodeCount']
    installmsecs = clusterinfo['createdTimeMsecs']
    installusecs = installmsecs * 1000
    installdate = usecsToDate (installusecs)
    loginbanner = api('get', 'banners')
    loginbanner = loginbanner['content']
    loginbanner = "".join(loginbanner.splitlines())
    timezone = clusterinfo['timezone']
    clusterauditinfo = clusterinfo['clusterAuditLogConfig']
    clusterauditretention = clusterauditinfo['retentionPeriodDays']
    filerauditinfo = clusterinfo['filerAuditLogConfig']
    filerauditretention = clusterauditinfo['retentionPeriodDays']
    dnsServers = clusterinfo['dnsServerIps']
    if len(dnsServers) > 1:
        dns1 = dnsServers[0]
        dns2 = dnsServers[1]
    if len(dnsServers) == 1:
        dns1 = dnsServers[0]
        dns2 = "NA"
    appsSubnet = clusterinfo['appsSubnet']
    appsip = appsSubnet['ip']
    appsbits = appsSubnet['netmaskBits']
    appsnetwork = f"{appsip}/{appsbits}"

    #SMTP Info
    smtpinfo = api('get', '/smtpServer')
    if smtpinfo == 'null\n':
        smtpenabled = "NA"
        smtpserver = "NA"
        smtpsender = "NA"
    if smtpinfo != 'null\n':
        smtpserver = smtpinfo['server']
        smtpdisabled = smtpinfo['disableSmtp']
        if smtpdisabled == False:
            smtpenabled = True
        if smtpdisabled == True:
            smtpenabled = False
        smtpsender = smtpinfo['senderEmailAddress']

    #NTP Info
    ntpinfo = api('get', '/ntpServers')
    ntpserver = ntpinfo['ntpServers'][0]
    if 'ntpAuthenticationEnabled' in ntpinfo:
        ntpauthenabled = ntpinfo['ntpAuthenticationEnabled']
        if ntpauthenabled == True:
            ntpauthinfo = ntpinfo['ntpServerAuthInfo']
            ntpauthserver = ntpauthinfo[0]
            ntpauthkeyid = ntpauthserver['ntpServerAuthKeyId']
    else:
        ntpauthenabled = False
        ntpauthkeyid = "NA"

    #SSO Info
    ssoinfo = api('get', 'idps?allUnderHierarchy=true')
    if len(ssoinfo) == 0:
        ssoname = "NA"
    else:
        ssoinfo = ssoinfo[0]
        ssoname = ssoinfo['name']

    #Storage Domains
    sd = api('get', 'storage-domains?matchPartialNames=false&includeTenants=true&includeStats=true', v=2)
    sd = sd['storageDomains'][0]
    sdpolicy = sd['storagePolicy']
    diskfailstolerated = (sdpolicy['numDiskFailuresTolerated'])
    nodefailstolerated = (sdpolicy['numNodeFailuresTolerated'])
    redundancy = f"{diskfailstolerated}" +"D:" + f"{nodefailstolerated}" +"N"
    if 'erasureCodingParams' in sdpolicy:
        numDataStripes = sdpolicy['erasureCodingParams']['numDataStripes']
        numCodedStripes = sdpolicy['erasureCodingParams']['numCodedStripes']
        ec = f"{numDataStripes}" + ":" + f"{numCodedStripes}"
        ecinlineEnabled = sdpolicy['erasureCodingParams']['inlineEnabled']
        if ecinlineEnabled == False:
            ecpostprocess = "True"
        if ecinlineEnabled == True:
            ecpostprocess = "False"
    else:
        ec = "NA"
        ecpostprocess = "NA"

    #Cluster Notifications
    clusteralertnotifcations = api('get', 'alertNotificationRules')
    for n in clusteralertnotifcations:
        if 'severities' in n:
            severities = n['severities']
            sevstring = ", ".join(severities)
            if sevstring == 'kCritical':
                emailinfo = n['emailDeliveryTargets'][0]
                alertemailto = emailinfo['emailAddress']
            else:
                alertemailto = "NA"
    if 'alertemailto' not in locals():
        alertemailto = "NA"

    #Roles
    roles = api('get', 'roles')
    customroles = [r for r in roles if r['isCustomRole'] == True]
    customrolecount= len(customroles)

    #Users
    users = api('get', 'users')
    customusers = [u for u in users if u['username'] != 'admin' and not (u['username'].startswith('cohesity_ui_support'))]
    customusercount = len(customusers)

    #add all data to cluster report
    report.append(str('%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s' % (clusterinfo['name'],clusterinfo['id'],clusterinfo['clusterType'],nodecount,installdate,timezone,version,clusterinfo['aesEncryptionMode'],redundancy,ec,ecpostprocess,dns1,dns2,smtpenabled,smtpserver,smtpsender,ntpserver,ntpauthenabled,ntpauthkeyid,ssoname,clusterauditretention,filerauditretention,appsnetwork,alertemailto,customrolecount,customusercount,loginbanner)))

    #GFLAGS
    flags = api('get', '/clusters/gflag')
    for flag in flags:
        servicename = flag['serviceName']
        if 'gflags' in flag:
            gflags = flag['gflags']
            customgflags = [g for g in gflags if not g['reason'].startswith('Auto') and not g['reason'].startswith('Maybe')]
            for customgflag in customgflags:
                flagname = customgflag['name']
                flagvalue = customgflag['value']
                reason = customgflag['reason']
                flagvalue = flagvalue.replace(',', ';;')
                gflagreport.append(str('%s,%s,%s,%s,%s' % (clusterinfo['name'],servicename, flagname, flagvalue, reason)))

    #APPS
    appsmode = api('get', 'cluster/appSettings')
    if appsmode['marketplaceAppsMode'] == 'kDisabled':
        appsreport.append(str('%s,%s' % (clusterinfo['name'],'Apps Disabled')))
    
    if appsmode['marketplaceAppsMode'] == 'kBareMetal':
        apps = api('get', 'apps')
        if 'error' in apps:
            appsreport.append(str('%s,%s' % (clusterinfo['name'],'Internal Error. Check Athena')))
        else:
            for app in apps:
                if len(app['metadata']) == 0:
                    continue
                appname =app['metadata']['name']
                if 'installState' in app:
                    appinstances = api('get', 'appInstances')
                    runningapps = [i for i in appinstances if i['appName'] == appname and i['state'] == 'kRunning']
                    totalinstances = len(runningapps)
                    appsreport.append(str('%s,%s,%s' % (clusterinfo['name'],appname,totalinstances)))
                else:
                    appsreport.append(str('%s,%s,%s' % (clusterinfo['name'],appname,'Not Installed')))
    
    #NODES
    nodes = api('get', 'nodes')
    if clusterinfo['clusterType'] == 'kPhysical':
        ipmiinfo = api('get', '/nexus/ipmi/cluster_get_lan_info')
        ipminodeinfo = ipmiinfo['nodesIpmiInfo']
    else:
        ipminodeinfo = "NA"
    
    for node in nodes:
        nodeid = node['id']
        nodeip = node['ip']
        hostname = node['hostName']
        nodetype = node['productModel']
        if ipminodeinfo != "NA":
            for nodeips in ipminodeinfo:
                if nodeips['nodeIp'] == nodeip:
                    nodeipmiip = nodeips['nodeIpmiIp']
        else:
            nodeipmiip = "NA"
        nodesreport.append(str('%s,%s,%s,%s,%s,%s' % (cluster['clusterName'],hostname,nodetype,nodeid,nodeip,nodeipmiip)))

#write Cluster Info to report
for item in sorted(report):
    f.write('%s\n' % item)
f.close()
print('\nCluster Output saved to %s\n' % outfile)

#write gflags to report
for flags in sorted(gflagreport):
    gf.write ('%s\n' % flags)
gf.close()
print('\nGFLAG Output saved to %s\n' % gflagfile)

#write Apps to report
for app in sorted(appsreport):
    af.write ('%s\n' % app)
af.close()
print('\nApps Output saved to %s\n' % appsfile)

#write Nodes to report
for nodes in sorted(nodesreport):
    nf.write ('%s\n' % nodes)
nf.close()
print('\nNodes Output saved to %s\n' % nodesfile)
