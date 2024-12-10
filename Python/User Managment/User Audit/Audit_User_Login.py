#!/usr/bin/env python
"""Protection Job Monitor for python"""

# version 2024.12.10

### import pyhesity wrapper module
from pyhesity import *
import codecs

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

# authentication =========================================================

# authenticate
apiauth(vip=vip, username=username, domain=domain, password=password, useApiKey=useApiKey, helios=mcm, prompt=(not noprompt))

# exit if not authenticated
if apiconnected() is False:
    print('authentication failed')
    exit(1)

# end authentication =====================================================

# Define outfile
outfile = 'user_audit.csv'
f = codecs.open(outfile, 'w')

# Add headings to outfile
f.write("Username,Domain,Last Login,Role\n")

#Define Report
report = []

users = api('get', 'users', mcm=True)

print(len(users), "users")

auditlog = api('get', 'audit-logs?actions=login&count=5000', mcmv2=True )

auditlog = (auditlog['auditLogs'])

print(len(auditlog), "total records")

oldestrecord = auditlog[-1]
oldestdatestamp = usecsToDate(oldestrecord['timestampUsecs'])
print("Oldest record is", oldestdatestamp)

for user in users:
    username = user['username']
    role = user['roles']
    role = str(role)[1:-1].strip('\'')
    domain = user['domain']
    logins = [record for record in auditlog if record['username'] == username and record['sourceType'] == 'helios']
    lastlogin = [login for login in logins]
    #print(username,len(lastlogin))
    if len(lastlogin) > 0:
        print('%s,%s,%s,%s' %(username, domain,usecsToDate (lastlogin[0]['timestampUsecs']),role))
        report.append(str('%s,%s,%s,%s' %(username, domain,usecsToDate (lastlogin[0]['timestampUsecs']),role)))
    if len(lastlogin) == 0:
        print('%s,%s,%s,%s' %(username, domain,"NA",role))
        report.append(str('%s,%s,%s,%s' %(username, domain,"NA",role)))

#write results to file        
for item in sorted(report):
    f.write('%s\n' % item)

f.close()
print('\nOutput saved to %s\n' % outfile)