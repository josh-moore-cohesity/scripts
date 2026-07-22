#!/usr/bin/env python
"""Script Overview"""

### import pyhesity wrapper module
from pyhesity import *
from datetime import datetime
import json

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
parser.add_argument('-add', '--add', type=str, action='append', default=None)
parser.add_argument('-remove', '--remove', type=str, action='append', default=None)
parser.add_argument('-rulename', '--rulename', type=str, action='append', default=None)
parser.add_argument('-updatename', '--updatename', type=str, default=None)
parser.add_argument('-debug', '--debug', action='store_true')

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
addEmails = args.add or []
removeEmails = args.remove or []
ruleNames = args.rulename or []
updatename = args.updatename
debug = args.debug

if updatename is not None and len(ruleNames) != 1:
    print('-updatename requires exactly one -rulename to be specified')
    exit()

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

# get list of clusters
clusternames = gatherList(clustername, clusterlist, name='clusters', required=True)

#Date
now = datetime.now()
dateString = now.strftime("%Y-%m-%d")

if debug:
    enableCohesityAPIDebugger()

# authenticate
apiauth(vip=vip, username=username, domain=domain, password=password, useApiKey=useApiKey, helios=mcm, prompt=(not noprompt), mfaCode=mfacode, emailMfaCode=emailmfacode)


# exit if not authenticated
if apiconnected() is False:
    print('authentication failed')
    exit(1)

# end authentication =====================================================



for clustername in clusternames:
    heliosCluster(clustername)
    print(clustername)

    if LAST_API_ERROR() != 'OK':
        continue

    #Code starts here
    rules = api('get', 'alertNotificationRules') or []

    for rule in rules:
        ruleName = rule.get('ruleName', '')

        if len(ruleNames) > 0 and ruleName not in ruleNames:
            continue

        ruleId = rule.get('ruleId')
        changed = False

        if updatename is not None and updatename != ruleName:
            rule['ruleName'] = updatename
            changed = True

        if len(addEmails) > 0 or len(removeEmails) > 0:
            targets = rule.get('emailDeliveryTargets', []) or []

            if len(removeEmails) > 0:
                keptTargets = [t for t in targets if t.get('emailAddress') not in removeEmails]
                if len(keptTargets) != len(targets):
                    changed = True
                targets = keptTargets

            if len(addEmails) > 0:
                existingEmails = [t.get('emailAddress') for t in targets]
                newTargets = [
                    {
                        "emailAddress": e,
                        "locale": "en-us",
                        "recipientType": "kTo"
                    }
                    for e in addEmails
                    if e not in existingEmails
                ]
                if len(newTargets) > 0:
                    changed = True
                targets = targets + newTargets

            rule['emailDeliveryTargets'] = targets

        if changed:
            print('  updating rule %s' % ruleName)
            body = {k: v for k, v in rule.items() if k != 'ruleId'}
            result = api('put', 'alerts/config/notification-rules/%s' % ruleId, body, v=2)
            if LAST_API_ERROR() != 'OK':
                print('  *** failed to update rule %s: %s' % (ruleName, LAST_API_ERROR()))
                print('  raw rule object for troubleshooting:')
                print(json.dumps(body, indent=2))
