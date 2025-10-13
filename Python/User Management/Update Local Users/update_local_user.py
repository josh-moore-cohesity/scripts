#!/usr/bin/env python
### Update 1 or more Local Users on 1 or more clusters ###
from pyhesity import *
from datetime import datetime
import getpass
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('-v', '--vip', type=str, default='helios.cohesity.com')           # cluster to connect to
parser.add_argument('-u', '--username', type=str, default='helios')   # admin user to do the work
parser.add_argument('-d', '--domain', type=str, default='local')      # domain of admin user
parser.add_argument('-i', '--useApiKey', action='store_true')         # use API key for authentication
parser.add_argument('-p', '--password', type=str, default=None)       # password for admin user
parser.add_argument('-mcm', '--mcm', action='store_true')
parser.add_argument('-np', '--noprompt', action='store_true')
parser.add_argument('-c', '--clustername', nargs='+', type=str, default=None)
parser.add_argument('-cl', '--clusters', type=str, default=None)
parser.add_argument('-n', '--existingusername', nargs='+', type=str, default=None)   # user name for local user
parser.add_argument('-nl', '--existingusernamelist', type=str, default=None)   # user name for local user
parser.add_argument('-e', '--emailaddress', type=str)  # email address for local user
parser.add_argument('-np', '--newpassword', action='store_true')  # password for local user
parser.add_argument('-m', '--moniker', type=str, default='key')  # API key name suffix
parser.add_argument('-r', '--role', type=str)    # Cohesity role to grant
parser.add_argument('-g', '--generateApiKey', action='store_true')    # generate new API key
parser.add_argument('-s', '--storeApiKey', action='store_true')       # stroe API key in file
parser.add_argument('-o', '--overwrite', action='store_true')         # overwrite existing API key
parser.add_argument('-x', '--disablemfa', action='store_true')        # exempt user from MFA
parser.add_argument('-mfa', '--enablemfa', action='store_true')        # Enable MFA for user

args = parser.parse_args()

vip = args.vip
username = args.username
domain = args.domain
useApiKey = args.useApiKey
password = args.password
mcm = args.mcm
noprompt = args.noprompt
clustername = args.clustername
clusterlist = args.clusters
existingusername = args.existingusername
existingusernamelist = args.existingusernamelist
email = args.emailaddress
newpassword = args.newpassword
moniker = args.moniker
role = args.role
generateApiKey = args.generateApiKey
storeApiKey = args.storeApiKey
overwrite = args.overwrite
disablemfa = args.disablemfa
enablemfa = args.enablemfa

# gather list function
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
existingusernames = gatherList(existingusername, existingusernamelist, name='existingusers', required=True)

# authentication =========================================================
# demand clustername if connecting to helios or mcm
if (mcm or vip.lower() == 'helios.cohesity.com') and clusternames is None:
    print('-c, --clustername is required when connecting to Helios or MCM')
    exit(1)

# authenticate
apiauth(vip, username, domain, password=password, useApiKey=useApiKey, prompt=(not noprompt))

# end authentication =====================================================

# if connected to helios or mcm, select access cluster
for cluster in clusternames:
    if mcm or vip.lower() == 'helios.cohesity.com':
    
       heliosCluster(cluster)
       print (cluster)
    if LAST_API_ERROR() != 'OK':
        exit(1)

    # get users
    for existinguser in existingusernames:
        users = [user for user in api('get', 'users') if user['username'].lower() == existinguser.lower()]
        if len(users) == 0:
            print('User %s Not Found...' % existinguser)
        else:
            sid = users[0]['sid']

            #Update Role
            if role is not None:
                roles = api('get', 'roles')
                thisrole = [r for r in roles if r['name'].lower() == role.lower() or r['label'].lower() == role.lower()]
                if len(thisrole) == 0:
                    print('Role %s not found' % role)
                    exit(1)
                users[0]['roles'] = [thisrole[0]['name']]

            #Update Password
            if newpassword:
                while(True):
                    newpassword = getpass.getpass("\nEnter the new password: ")
                    confirmpassword = getpass.getpass("  Confirm new password: ")
                    if newpassword == confirmpassword:
                        break
                    else:
                        print('\nPasswords do not match')
                users[0]['password'] = newpassword

            # Update user
            nowMsecs = int(round(dateToUsecs(datetime.now().strftime("%Y-%m-%d %H:%M:%S")) / 1000))

            #Enable MFA
            if enablemfa is True:
                users[0]['mfaInfo'] = {'isUserExemptFromMfa': False, 'isTotpSetupDone': False}
            
            #Disable MFA
            if disablemfa is True:
                users[0]['mfaInfo'] = {'isUserExemptFromMfa': True, 'isTotpSetupDone': False}
            
            #Update Email
            if email is not None:
                users[0]['emailAddress'] = email

            print('updating user %s' % existinguser)
            newuser = api('put', 'users', users[0])
            users = [user for user in api('get', 'users') if user['username'].lower() == existinguser.lower() and user['domain'].lower() == 'local']

        # generate API Key
        if generateApiKey:
            sid = users[0]['sid']

            keys = [key for key in api('get', 'usersApiKeys') if key['name'].lower() == '%s-%s' % (existinguser.lower(), moniker.lower())]
            if len(keys) > 0:
                if overwrite is True:
                    deletekey = api('delete', 'users/%s/apiKeys/%s' % (sid, keys[0]['id']))
                else:
                    print('api key already exists for %s' % username)
                    exit(1)

            params = {
                'user': users[0],
                'name': '%s-%s' % (users[0]['username'], moniker)
            }

            response = api('post', 'users/%s/apiKeys' % sid, params)

            if 'key' in response:
                if storeApiKey is True:
                    setpwd(v=vip, u=existinguser, d='local', password=response['key'])
                else:
                    print('New API Key: %s' % response['key'])
            else:
                display(response)
