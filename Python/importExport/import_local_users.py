#!/usr/bin/env python
"""Script Overview"""

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

if newpassword is None:
    print("\nA default password will be set for all users")
    while(True):
        newpassword = getpass.getpass("\nEnter the new password: ")
        confirmpassword = getpass.getpass("  Confirm new password: ")
        if newpassword == confirmpassword:
            break
        else:
            print('\nPasswords do not match')

for clustername in clusternames:
    print(clustername)
    # if connected to helios or mcm, select access cluster
    if mcm or vip.lower() == 'helios.cohesity.com':
        heliosCluster(clustername)
    if LAST_API_ERROR() != 'OK':
        continue
    thisclusterpath = "%s/%s" % (outputpath,clustername)

    #Users
    users_output_file = os.path.join(thisclusterpath, 'users.json')

    with open(users_output_file, 'r') as file:
        user_payload = json.load(file)


    for user in user_payload:
        if 'emailAddress' not in user:
            user['emailAddress'] = "noreply@domain.com"
        localusername = user['username']
        localuserrole = user['roles'][0]
        localuser = [u for u in api('get', 'users') if u['username'].lower() == localusername.lower() and u['domain'].lower() == 'local' ]
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
            users = [user for user in api('get', 'users') if user['username'].lower() == localusername.lower() and user['domain'].lower() == 'local']

        else:
            print('User %s already exists...' % localusername)
