#!/usr/bin/env python

from pyhesity import *
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('-v', '--vip', type=str, default='helios.cohesity.com')
parser.add_argument('-sc', '--sourcecluster', type=str, required=True)
parser.add_argument('-spwd', '--sourcepassword', type=str, default=None)
parser.add_argument('-i', '--useApiKey', action='store_true')
parser.add_argument('-tc', '--targetcluster', type=str, required=True)
parser.add_argument('-tpwd', '--targetpassword', type=str, default=None)
parser.add_argument('-o', '--overwrite', action='store_true')
parser.add_argument('-n', '--rolename', action='append', type=str)
parser.add_argument('-l', '--rolelist', type=str)
args = parser.parse_args()

vip = args.vip
useApiKey = args.useApiKey
rolenames = args.rolename
rolelist = args.rolelist
sourcecluster = args.sourcecluster
targetcluster = args.targetcluster

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

rolenames = gatherList(rolenames, rolelist, name='roles', required=False)

if len(rolenames) == 0:
    print("No Roles selected to copy")
    exit(1)

print('connecting to Helios')
# authentication =========================================================
apiauth(vip=vip, useApiKey=useApiKey)

# exit if not authenticated
if apiconnected() is False:
    print('authentication failed')
    exit(1)


print('connecting to Source Cluster', sourcecluster)
# authentication =========================================================
heliosCluster(sourcecluster)
#print(sourcecluster)
if LAST_API_ERROR() != 'OK':
    exit(1)

#Get Source Roles
roles = api('get', 'roles')

# catch invalid role names
notfoundroles = [n for n in rolenames if n.lower() not in [r['label'].lower() for r in roles]]
if len(notfoundroles) > 0:
    print('roles not found: %s' % ', '.join(notfoundroles))
    exit(1)

if len(rolenames) > 0:
    roles = [r for r in roles if r['label'].lower() in [n.lower() for n in rolenames]]

customroles = [r for r in roles if r['isCustomRole'] is True]

print('connecting to target cluster', targetcluster)
# authentication =========================================================
heliosCluster(targetcluster)
#print(targetcluster)
if LAST_API_ERROR() != 'OK':
    exit(1)

overwrite = args.overwrite

roles = api('get', 'roles')

for customrole in sorted(customroles, key=lambda c: c['label'].lower()):
    existingrole = [r for r in roles if r['label'].lower() == customrole['label'].lower()]
    if len(existingrole) > 0:
        if overwrite is True:
            print('updating role %s' % customrole['label'])
            deleterole = api('delete', 'roles', {'names': [existingrole[0]['name']]})
            newrole = api('post', 'roles', customrole)
        else:
            print('role %s already exists' % customrole['label'])
    else:
        print('creating role %s' % customrole['label'])
        newrole = api('post', 'roles', customrole)
      
