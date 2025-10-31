#!/usr/bin/env python
"""Auto Protect S3 Buckets"""

### import pyhesity wrapper module
from pyhesity import *
from datetime import datetime
import codecs
import csv

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
parser.add_argument('-xl', '--excludelist', type=str, default=None, required=True)
parser.add_argument('-preview', '--preview', action='store_true')

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
excludelist = args.excludelist
preview = args.preview

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
datetimestring = now.strftime("%m/%d/%Y %I:%M %p")
dateString = now.strftime("%Y-%m-%d-%I-%M-%S")

# authenticate
apiauth(vip=vip, username=username, domain=domain, password=password, useApiKey=useApiKey, helios=mcm, prompt=(not noprompt), mfaCode=mfacode, emailMfaCode=emailmfacode)

# exit if not authenticated
if apiconnected() is False:
    print('authentication failed')
    exit(1)


# end authentication =====================================================

#Define Report For Results
report = []

#Define Outfile
if preview:
    outfile = 'protect-buckets-%s-preview.csv' % dateString
else:
    outfile = 'protect-buckets-%s.csv' % dateString
f = codecs.open(outfile, 'w')
f.write("Cluster,Source,Bucket,PG,Action\n")

#Loop through each cluster specified
for clustername in clusternames:
    heliosCluster(clustername)
    print(clustername)

    if LAST_API_ERROR() != 'OK':
        exit(1)

    #Get S3 Sources and S3 Protection Groups
    s3sources = api('get', 'protectionSources?environment=kS3Compatible')
    s3pgs = api('get', 'protectionJobs?environment=kS3Compatible')

    #Loop through each s3 source (refresh source, and find unprotected buckets)
    for s3source in s3sources:
        sourceid = s3source['protectionSource']['id']
        sourcename = s3source['protectionSource']['name']
        print('Refreshing Source %s' % sourcename)
        refreshsource = api('post', 'protectionSources/refresh/%s' % sourceid)
        nodes = s3source['nodes']
        protectionsources = nodes[0]['nodes']

        for protectionsource in protectionsources:
            updatepg = False
            bucketid = protectionsource['protectionSource']['id']
            parentid = protectionsource['protectionSource']['parentId']
            bucketname = protectionsource['protectionSource']['name']
            protectionsourcessummary = [p for p in protectionsource['protectedSourcesSummary']]

            if 'leavesCount' in protectionsourcessummary[0]:
                protected = True
            else:
                protected = False

            if protected == False:
                #Check exclude file for exclusions
                with open(excludelist, mode='r', newline='') as excludefile:
                    csv_reader = csv.reader(excludefile)
                    for row in csv_reader:
                        skip_outer = False

                        #Skip protection if matching source and bucket in exclude list
                        if sourcename in row[0] and bucketname in row[1]:
                            print("Not Adding %s (%s) to PG.  Found in Exclude List" % (bucketname,sourcename))
                            report.append('%s,%s,%s,,Excluded' % (clustername,sourcename,bucketname))
                            skip_outer = True
                            break
                if skip_outer:
                    continue

                addtopg = [pg for pg in s3pgs if parentid == pg['parentSourceId']]
                
                #Skip if no PG found for the source
                if len(addtopg) == 0:
                    print("Cannot Add %s. No PG found for source %s" % (bucketname,sourcename))
                    report.append('%s,%s,%s,,No PG Found' % (clustername,sourcename,bucketname))
                    continue
                
                #Skip if more than 1 PG found for the source
                if len(addtopg) > 1:
                    print("Cannot add %s to PG.  Mutliple PGs exists for source %s" % (bucketname, sourcename))
                    report.append('%s,%s,%s,,Not Added - Multiple PGs Exist for Source' % (clustername,sourcename,bucketname))
                    continue
                
                #Add Bucket IDs to PG Source IDs (PG count for source is exactly 1)
                thispg = addtopg[0]
                name = thispg['name']
                print("Going to Add %s to %s (%s)" % (bucketname, name, sourcename))
                updatepg = True
                thispg['sourceIds'].append(bucketid)
                report.append('%s,%s,%s,%s,Added' % (clustername, sourcename, bucketname, name))
        
        #Update the PG if -preview was not specifed and PGs count for the source is exactly 1
        if not preview and updatepg == True:
            print("Updating PG %s" % name)
            updatedJob = api('put', 'protectionJobs/%s' % thispg['id'], thispg)

#Output Results to csv
for item in report:
    f.write('%s\n' % item)

f.close()
print('\nOutput saved to %s\n' % outfile)
