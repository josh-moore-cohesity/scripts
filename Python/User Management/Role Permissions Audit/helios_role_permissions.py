#!/usr/bin/env python

from pyhesity import *
import argparse
import codecs
from datetime import datetime
import re
from operator import itemgetter

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

now = datetime.now()
datetimestring = now.strftime("%m/%d/%Y %I:%M %p")
dateString = now.strftime("%Y-%m-%d")


# authenticate
apiauth(vip=vip, username=username, useApiKey=useApiKey, helios=mcm)

# exit if not authenticated
if apiconnected() is False:
    print('authentication failed')
    exit(1)

# end authentication =====================================================

# Define outfile
outfile = 'helios-roles-%s.csv' % dateString
f = codecs.open(outfile, 'w')

#Get Helios Roles
roles = api('get', 'roles', mcm=True)
privileges = api ('get', 'privileges', mcm=True)

#Define Report Lists
report = []
allrolenames = []

#Get list of role names
for role in roles:
    rolename = role['name']
    allrolenames.append(rolename)

allrolenames = sorted(allrolenames)
allrolenames = ",".join(allrolenames)

#Add Role Names to report (Will be CSV Header)
report.append('CATEGORY,PRIVILEGES,%s' % allrolenames)

#Check what roles have each privilege
for privilege in sorted(privileges, key=itemgetter('category')):
    hasprivilege = []
    for role in sorted(roles, key=itemgetter('name')):
        if privilege['name'] in role['privileges']:
            hasit = 'YES'
            hasprivilege.append(hasit)
        else:
            hasit = 'NO'
            hasprivilege.append(hasit)

    hasprivilege = ','.join(hasprivilege)
    report.append('%s,%s,%s' % (privilege['category'], privilege['name'], hasprivilege))

#Write to CSV
for record in (report):
    f.write ('%s\n' % record)

f.close()
print('\nOutput saved to %s\n' % outfile)
