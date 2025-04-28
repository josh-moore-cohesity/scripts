#!/usr/bin/env python
"""Audit Helios User API Keys"""

# version 2025.04.24

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

#Date and Time
now = datetime.now()
datetimestring = now.strftime("%m/%d/%Y %I:%M %p")
dateString = now.strftime("%Y-%m-%d")


# Define outfile
outfile = 'apikey_audit-%s.csv' % dateString
f = codecs.open(outfile, 'w')

# Add headings to outfile
f.write("Username,Action,Name,Type,Date\n")

#Define Report
report = []

auditlog = api('get', 'audit-logs?searchString=api%20key&actions=create%2Cdelete&count=5000', mcmv2=True)
auditlog = (auditlog['auditLogs'])

for audit in auditlog:
    username = audit['username']
    action = audit['action']
    entityname = audit['entityName']
    entitytype = audit['entityType']
    timestamp = usecsToDate(audit['timestampUsecs'])

    print('%s,%s,%s,%s,%s' %(username, action, entityname, entitytype, timestamp))

    report.append(str('%s,%s,%s,%s,%s' %(username, action, entityname, entitytype, timestamp)))

#write results to file        
for item in report:
    f.write('%s\n' % item)

f.close()
print('\nOutput saved to %s\n' % outfile)
