#!/usr/bin/env python
"""Update Local User Roles """

# import pyhesity wrapper module
from pyhesity import *
from datetime import datetime
import codecs

# command line arguments
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


# gather list function
def gatherList(param=None, filename=None, name='items'):
    items = []
    if param is not None:
        for item in param:
            items.append(item)
    if filename is not None:
        f = open(filename, 'r')
        items += [s.strip() for s in f.readlines() if s.strip() != '']
        f.close()

    return items


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
outfile = 'local_user_audit-%s.csv' % dateString
f = codecs.open(outfile, 'w')

# Add headings to outfile
f.write("Cluster, Username, Email, Domain, Role\n")

report = []

clusters = api('get', 'cluster-mgmt/info',mcmv2=True)
clusters = clusters['cohesityClusters']

for cluster in clusters:
    clustername = cluster['clusterName']

    heliosCluster(clustername)
    if LAST_API_ERROR() != 'OK':
        continue
    
    users = api('get', 'users')

    for user in users:
        username = user['username']
        try:
            email = user['emailAddress']
        except:
            email = "NA"
        domain = user['domain']
        role = [r for r in user['roles']]
        roles = ",".join(role)
        print(str('%s,%s,%s,%s,%s' % (clustername, username, email, domain, roles)))
        report.append(str('%s,%s,%s,%s,%s' % (clustername,username,email,domain,roles) ))

#Save to File
for record in (report):
    f.write ('%s\n' % record)
f.close()
print('\nOutput saved to %s\n' % outfile)
