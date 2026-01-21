#!/usr/bin/env python
"""Import Cluster Config"""

### import pyhesity wrapper module
from pyhesity import *
from datetime import datetime
import json
import os
import getpass

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
parser.add_argument('-newpass', '--newpassword', type=str, default=None)  # password for local user
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
newpassword = args.newpassword
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



# authentication =========================================================

if(mcm or vip.lower() != 'helios.cohesity.com'):
    clusternames = []
    clusternames.append(vip)

# Get cluster name or cluster list if connecting to helios or mcm
elif (mcm or vip.lower() == 'helios.cohesity.com'):
    clusternames = gatherList(clustername, clusterlist, name='clusters', required=True)


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
    clustershortname = clustername.split('.')[0]
    # if connected to helios or mcm, select access cluster
    if mcm or vip.lower() == 'helios.cohesity.com':
        heliosCluster(clustername)
    if LAST_API_ERROR() != 'OK':
        continue
    thisclusterpath = "%s/%s" % (outputpath,clustershortname)

    #Roles
    print("Importing Roles")
    roles_output_file = os.path.join(thisclusterpath, 'roles.json')

    with open(roles_output_file, 'r') as file:
        roles_payload = json.load(file)

    currentroles = api('get', 'roles')


    for role in roles_payload:
        rolename = role['name']
        currentrole = [p for p in currentroles if p['name'].lower() == rolename.lower()]

        if len(currentrole) == 0:
            print('Creating role %s' % rolename)
            newrole = api('post', 'roles', role)

        else:
            print('Role %s already exists...' % rolename)

    #idps
    print("Importing idp providers")
    idps_output_file = os.path.join(thisclusterpath, 'idps.json')

    with open(idps_output_file, 'r') as file:
        idps_payload = json.load(file)

    currentidps = api('get', 'idps?allUnderHierarchy=true')

    for idp in idps_payload:
        localidp = [i for i in currentidps if i['name'].lower() == idp['name'].lower()]
        if len(localidp) == 0:
            print('Adding IDP %s' % idp['name'])
            newidp = api('post', 'idps', idp)

        else:
            print('IDP %s already exists...' % idp['name'])

    #Join AD

    #Users
    print("Importing Users")
    print("\nA default password will be set for all users")
    while(True):
        newpassword = getpass.getpass("\nEnter the new password: ")
        confirmpassword = getpass.getpass("  Confirm new password: ")
        if newpassword == confirmpassword:
            break
        else:
            print('\nPasswords do not match')
    
    users_output_file = os.path.join(thisclusterpath, 'users.json')

    with open(users_output_file, 'r') as file:
        user_payload = json.load(file)


    for user in user_payload:
        if 'emailAddress' not in user:
            user['emailAddress'] = "noreply@domain.com"
        localusername = user['username']
        localuserrole = user['roles'][0]
        localuser = [u for u in api('get', 'users') if u['username'].lower() == localusername.lower()]
        if len(localuser) == 0:
            roles = api('get', 'roles')
            thisrole = [r for r in roles if r['name'].lower() == localuserrole.lower() or r['label'].lower() == localuserrole.lower()]
            if len(thisrole) == 0:
                print('Role %s not found' % localuserrole)
                continue
            else:
                thisrole = thisrole[0]
                user['password'] = newpassword
                user['passwordConfirm'] = newpassword


        # add user
            nowMsecs = int(round(dateToUsecs(datetime.now().strftime("%Y-%m-%d %H:%M:%S")) / 1000))

            print('creating user %s' % localusername)
            newuser = api('post', 'users', user)
            users = [user for user in api('get', 'users') if user['username'].lower() == localusername.lower()]

        else:
            print('User %s already exists...' % localusername)

    #Views
    currentsds = api ('get', 'viewBoxes')
    print("Importing Views")
    views_output_file = os.path.join(thisclusterpath, 'views.json')

    with open(views_output_file, 'r') as file:
        views_payload = json.load(file)

    currentviews = api('get', 'views?allUnderHierarchy=true')
    if currentviews['count'] != 0:
        currentviews = currentviews['views']

    #Create View
    for view in views_payload['views']:
        viewsd = [s for s in currentsds if s['name'].lower() == view['viewBoxName'].lower()]
        if viewsd is None or len(viewsd) == 0:
            viewsd = [s for s in currentsds if s['name'] == 'DefaultStorageDomain']
            view['viewBoxId'] = viewsd[0]['id']
        else:
            view['viewBoxId'] = viewsd[0]['id']
        localview= [v for v in currentviews if v['name'].lower() == view['name'].lower()]
        if len(localview) == 0:
            print('Adding View %s' % view['name'])
            newview= api('post', 'views', view)

        else:
            print('View %s already exists...' % view['name'])
    
    #Policies
    policy_output_file = os.path.join(thisclusterpath, 'policies.json')

    with open(policy_output_file, 'r') as file:
        policy_payload = json.load(file)

    currentpolicies = api('get', 'data-protect/policies', v=2)
    currentpolicies = currentpolicies['policies']

    for policy in policy_payload['policies']:
        policyname = policy['name']
        currentpolicy = [p for p in currentpolicies if p['name'].lower() == policyname.lower()]
        
        if len(currentpolicy) == 0:
            print('Creating policy %s' % policyname)
            newpolicy = api('post', 'data-protect/policies', policy, v=2)

        else:
            print('Policy %s already exists...' % policyname)
