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
parser.add_argument('-priv', '--privilege', type=str, default=None, required=True)
parser.add_argument('-showroles', '--showroles', action='store_true')
parser.add_argument('-showusers', '--showusers', action='store_true')

args = parser.parse_args()

vip = args.vip
username = args.username
mcm = args.mcm
useApiKey = args.useApiKey
showroles = args.showroles
privilege = args.privilege
showusers = args.showusers

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



#Get Helios Roles/Privs/Users
roles = api('get', 'roles', mcm=True)
privileges = api ('get', 'privileges', mcm=True)
filtered_privilege = [p for p in privileges if privilege.lower() in p['name'].lower()]
if len(filtered_privilege) == 0:
    print('%s privilege not found' % privilege)
    exit()
heliosusers = api('get', 'users', mcm=True)

#Define Report Lists
rolereport = []
userreport = []
allrolenames = []

#Get list of role names
for role in roles:
    rolename = role['name']
    allrolenames.append(rolename)

allrolenames = sorted(allrolenames)
allrolenames = ",".join(allrolenames)

rolenames = []

if showroles:
    # Define outfile
    roleoutfile = 'helios-roles-%s-%s.csv' % (privilege, dateString)
    rf = codecs.open(roleoutfile, 'w')
    rolereport.append('Category,Name,Role')

    # Check if role has the privilege
    for role in sorted(roles, key=itemgetter('name')):
        if filtered_privilege[0]['name'] in role['privileges']:
            print(role['name'])
            rolereport.append('%s,%s,%s' % (filtered_privilege[0]['category'], filtered_privilege[0]['name'], role['name']))
    #write to csv
    for record in (rolereport):
        rf.write ('%s\n' % record)
    rf.close()

if showusers:
    # Define outfile
    useroutfile = 'helios-users-%s-%s.csv' % (privilege, dateString)
    uf = codecs.open(useroutfile, 'w')
    userreport.append('User,Role,Domain')

    # Check if user has role that has the privilege
    for role in sorted(roles, key=itemgetter('name')):
        if filtered_privilege[0]['name']in role['privileges']:
            rolenames.append(role['name'])
            for user in heliosusers:
                for rolename in rolenames:
                    if rolename in user['roles']:
                        print(user['username'],user['roles'][0])
                        userreport.append('%s,%s,%s' % (user['username'],rolename,user['domain']))
    #write to csv
    for record in (userreport):
        uf.write ('%s\n' % record)
    uf.close()

#Output file names
try:
    if roleoutfile:
        print('\nOutput saved to %s\n' % roleoutfile)
except:
    pass

try:
    if useroutfile:
        print('\nOutput saved to %s\n' % useroutfile)
except:
    pass
  
