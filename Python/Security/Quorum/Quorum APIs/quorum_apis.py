#!/usr/bin/env python
"""Export every quorum-governable API operation from Helios"""

### import pyhesity wrapper module
from pyhesity import *
from datetime import datetime
import codecs
import csv
import json
import os
import re

### command line arguments
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('-v', '--vip', type=str, default='helios.cohesity.com')
parser.add_argument('-u', '--username', type=str, default='helios')
parser.add_argument('-d', '--domain', type=str, default='local')
parser.add_argument('-i', '--useApiKey', action='store_true')
parser.add_argument('-pwd', '--password', type=str, default=None)
parser.add_argument('-np', '--noprompt', action='store_true')
parser.add_argument('-m', '--mfacode', type=str, default=None)
parser.add_argument('-e', '--emailmfacode', action='store_true')
parser.add_argument('-outputpath', '--outputpath', type=str, default='./Results')
parser.add_argument('-o', '-output', '--output', type=str, choices=['csv', 'json'], default='csv')

args = parser.parse_args()

vip = args.vip
username = args.username
domain = args.domain
useApiKey = args.useApiKey
password = args.password
noprompt = args.noprompt
mfacode = args.mfacode
emailmfacode = args.emailmfacode
outputpath = args.outputpath
output = args.output

# authenticate
apiauth(vip=vip, username=username, domain=domain, password=password, useApiKey=useApiKey, helios=True, prompt=(not noprompt), mfaCode=mfacode, emailMfaCode=emailmfacode)

# exit if not authenticated
if apiconnected() is False:
    print('authentication failed')
    exit(1)

# end authentication =====================================================

if not os.path.exists(outputpath):
    os.makedirs(outputpath)

dateString = datetime.now().strftime("%Y-%m-%d")
outFile = os.path.join(outputpath, 'quorum-operations-%s.%s' % (dateString, output))

# get operation templates
templates = api('get', 'quorum/operations/templates', mcmv2=True)
if templates is None:
    print('failed to get quorum operations: %s' % LAST_API_ERROR())
    exit(1)

pathKey = re.compile(r'path|uri|url|endpoint', re.IGNORECASE)
rows = []


def walk(node, context):
    """find dicts that look like an operation (have a path-like key) and record them with their parent names"""
    if isinstance(node, list):
        for item in node:
            walk(item, context)
    elif isinstance(node, dict):
        scalars = {k: v for k, v in node.items() if not isinstance(v, (dict, list))}
        if any(pathKey.search(k) for k in scalars):
            row = dict(context)
            row.update(scalars)
            rows.append(row)
        # carry this level's name down so operations know their template/group
        childContext = dict(context)
        for k in ('name', 'templateName', 'displayName'):
            if k in scalars:
                childContext['parent_%s' % k] = scalars[k]
                break
        for k, v in node.items():
            if isinstance(v, (dict, list)):
                walk(v, childContext)


walk(templates, {})

# de-duplicate (the same operation can appear under more than one template)
seen = set()
uniqueRows = []
for row in rows:
    key = json.dumps(row, sort_keys=True, default=str)
    if key not in seen:
        seen.add(key)
        uniqueRows.append(row)

if len(uniqueRows) == 0:
    print('no operations recognized - the API response shape may have changed')
    exit(1)

# key columns first, then everything else in first-seen order
columns = ['templateName', 'category', 'functionId', 'criticality', 'version', 'httpAction', 'apiPath', 'summary', 'id']
for row in uniqueRows:
    for k in row:
        if k not in columns:
            columns.append(k)

if output == 'json':
    with codecs.open(outFile, 'w', 'utf-8') as f:
        json.dump(uniqueRows, f, indent=2)
else:
    with codecs.open(outFile, 'w', 'utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(uniqueRows)

# summary by template
templateCounts = {}
for row in uniqueRows:
    name = row.get('templateName', 'Unknown')
    templateCounts[name] = templateCounts.get(name, 0) + 1

print('\nOperations by template:')
for name in sorted(templateCounts):
    print('  %-28s %s' % (name, templateCounts[name]))
print('  %-28s %s' % ('Total', len(uniqueRows)))
print('\nOutput written to %s' % outFile)
