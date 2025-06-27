#!/usr/bin/env python
"""Audit Helios User Logins"""

# version 2025.03.12

### import pyhesity wrapper module
from pyhesity import *
import codecs
from datetime import datetime

### command line arguments
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('-v', '--vip', type=str, default='helios.cohesity.com')
parser.add_argument('-u', '--username', type=str, default='helios')
parser.add_argument('-d', '--domain', type=str, default='local')
parser.add_argument('-i', '--useApiKey', action='store_true')
parser.add_argument('-p', '--password', type=str, default=None)
parser.add_argument('-np', '--noprompt', action='store_true')
parser.add_argument('-mcm', '--mcm', action='store_true')
parser.add_argument('-m', '--mfacode', type=str, default=None)
parser.add_argument('-e', '--emailmfacode', action='store_true')
parser.add_argument('-y', '--days', type=int)

args = parser.parse_args()

vip = args.vip
username = args.username
domain = args.domain
useApiKey = args.useApiKey
password = args.password
noprompt = args.noprompt
mcm = args.mcm
mfacode = args.mfacode
emailmfacode = args.emailmfacode
days = args.days

# authentication =========================================================

# authenticate
apiauth(vip=vip, username=username, domain=domain, password=password, useApiKey=useApiKey, helios=mcm, prompt=(not noprompt))

# exit if not authenticated
if apiconnected() is False:
    print('authentication failed')
    exit(1)

# end authentication =====================================================

#Date and Time
now = datetime.now()
datetimestring = now.strftime("%m/%d/%Y %I:%M %p")
dateString = now.strftime("%Y-%m-%d")

# Define outfile
outfile = 'user_audit-%s.csv' % dateString
f = codecs.open(outfile, 'w')

# Add headings to outfile
f.write("Username,Domain,Last Login,Last Logout,Role,Total Clusters,Accessible Clusters\n")

#Define Report
report = []

#Get Users
users = api('get', 'users', mcm=True)
print(len(users), "users")

#Get Clusters
clusters = api('get', 'cluster-mgmt/info',mcmv2=True)
clusters = clusters['cohesityClusters']

if days:
    #set start time
    daysBackUsecs = timeAgo(days, 'days')
    auditlog = api('get', 'audit-logs?startTimeUsecs=%s&actions=login%%2Clogout&count=5000' % (daysBackUsecs), mcmv2=True )
else:
    #get all records
    auditlog = api('get', 'audit-logs?actions=login%2Clogout&count=5000', mcmv2=True )

auditlog = (auditlog['auditLogs'])

print(len(auditlog), "total records")

#report oldest record
oldestrecord = auditlog[-1]
oldestdatestamp = usecsToDate(oldestrecord['timestampUsecs'])
print("Oldest record is", oldestdatestamp)

#get user info
for user in users:
    username = user['username']
    accesibleclusters = []
    role = user['roles']
    role = str(role)[1:-1].strip('\'')
    domain = user['domain']
    logins = [record for record in auditlog if record['username'] == username and record['domain'] == domain.lower() and record['action'] == 'Login']
    logouts = [record for record in auditlog if record['username'] == username and record['domain'] == domain.lower() and record['action'] == 'Logout']
    loginrecords = [login for login in logins]
    logoutrecords = [logout for logout in logouts]
    clusteraccess = [c for c in user['clusterIdentifiers']]
    totalclusters = len(clusters)
    if clusteraccess[0]['clusterId'] == -1:
        accessibleclustercount = len(clusters)
        for cluster in clusters:
            accesibleclusters.append(cluster['clusterName'])
    else:
        accessibleclustercount = len(user['clusterIdentifiers'])
        for cluster in clusteraccess:
            clusterid = cluster['clusterId']
            clustername = [c for c in clusters if clusterid == c['clusterId']]
            for name in clustername:
                accesibleclusters.append(name['clusterName'])

    accesibleclusters = ",".join(accesibleclusters)

    if len(logins) > 0:
        lastlogin = usecsToDate (logins[0]['timestampUsecs'])
        
    if len(logins) == 0:
        lastlogin = "NA"
    
    if len(logouts) > 0:
        lastlogout = usecsToDate (logouts[0]['timestampUsecs'])
        
    if len(logouts) == 0:
        lastlogout = "NA"
    
    print('%s,%s,%s,%s,%s,%s,%s' %(username,domain,lastlogin,lastlogout,role,totalclusters,accessibleclustercount))

    report.append(str('%s,%s,%s,%s,%s,%s,%s,%s' %(username,domain,lastlogin,lastlogout,role,totalclusters,accessibleclustercount, accesibleclusters)))

#write results to file        
for item in sorted(report):
    f.write('%s\n' % item)

f.close()
print('\nOutput saved to %s\n' % outfile)
