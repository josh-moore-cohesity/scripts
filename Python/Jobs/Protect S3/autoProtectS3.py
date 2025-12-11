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
parser.add_argument('-cg', '--creategroup', action='store_true')
parser.add_argument('-gp', '--groupprefix', type=str, default='S3-PG-1')
parser.add_argument('-p', '--policyname', type=str, default=None)
parser.add_argument('-st', '--starttime', type=str, default='05:00')
parser.add_argument('-tz', '--timezone', type=str, default='US/Eastern')
parser.add_argument('-sd', '--storagedomain', type=str, default='DefaultStorageDomain')
parser.add_argument('-is', '--incrementalsla', type=int, default=1440)    # incremental SLA minutes
parser.add_argument('-fs', '--fullsla', type=int, default=1440)          # full SLA minutes
parser.add_argument('-pause', '--pause', action='store_true')
parser.add_argument('-ea', '--emailalerts', type=str, default=None)
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
creategroup = args.creategroup
groupprefix = args.groupprefix
policyname = args.policyname
preview = args.preview
starttime = args.starttime
timezone = args.timezone
storagedomain = args.storagedomain
incrementalsla = args.incrementalsla
fullsla = args.fullsla
pause = args.pause
emailalerts = args.emailalerts

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

#Function to get S3 PGs
def gets3pgs():
    return api('get', 'protectionJobs?environments=kS3Compatible&isDeleted=false')

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
f.write("Cluster,Source,Bucket,PG,Action,Details\n")

#Loop through each cluster specified
for clustername in clusternames:
    heliosCluster(clustername)
    print(clustername)

    if LAST_API_ERROR() != 'OK':
        exit(1)

    #Get S3 Sources and S3 Protection Groups
    s3sources = api('get', 'protectionSources?environments=kS3Compatible')
    if 'error' in s3sources:
        s3sources_error_message = s3sources['error'].replace('\n', '')
        report.append('%s,NA,NA,NA,Error,%s' % (clustername,s3sources_error_message))
        continue
    s3pgs = gets3pgs()

    #Loop through each s3 source (refresh source, and find unprotected buckets)
    for s3source in s3sources:
        sourceid = s3source['protectionSource']['id']
        sourcename = s3source['protectionSource']['name']
        print('Refreshing Source %s' % sourcename)
        thispg = []
        refreshsource = api('post', 'protectionSources/refresh/%s' % sourceid)
        nodes = s3source['nodes']
        protectionsources = nodes[0]['nodes']

        #Gather Unprotected Buckets
        for protectionsource in protectionsources:
            data = []
            addtopg = []
            updatepg = False
            bucketid = protectionsource['protectionSource']['id']
            parentid = protectionsource['protectionSource']['parentId']
            bucketname = protectionsource['protectionSource']['name']
            protectionsourcessummary = [p for p in protectionsource['protectedSourcesSummary']]

            if 'leavesCount' in protectionsourcessummary[0]:
                protected = True
            else:
                protected = False

            #Protect Buckets if unprotected
            if protected == False:
                #Check exclude file for exclusions
                with open(excludelist, mode='r', newline='') as excludefile:
                    csv_reader = csv.reader(excludefile)
                    for row in csv_reader:
                        skip_outer = False

                        #Skip protection if matching source and bucket in exclude list
                        if sourcename in row[0] and bucketname in row[1]:
                            print("Not Adding %s (%s) to PG.  Found in Exclude List" % (bucketname,sourcename))
                            if preview:
                                excluded = "Preview-Excluded"
                            else:
                                excluded = "Excluded"
                            report.append('%s,%s,%s,,%s' % (clustername,sourcename,bucketname,excluded))
                            skip_outer = True
                            break
                if skip_outer:
                    continue
                
                #Identify PG to add bucket to
                addtopg = [pg for pg in s3pgs if parentid == pg['parentSourceId']]
                
                #Skip if no PG found for the source and -cg (Create Group) is not specified
                if len(addtopg) == 0 and not creategroup:
                    print("No PG found for source %s and -cg not specified. Not Adding %s." % (sourcename,bucketname))
                    report.append('%s,%s,%s,,None,No PG Found (-cg not specified)' % (clustername,sourcename,bucketname))
                    continue
                
                #Create PG if it doesn't exist for the source and -cg (Create Group) is specified
                elif len(addtopg) == 0 and creategroup:
                    newjobname = "%s-%s" % (groupprefix,sourcename)
                    
                    #Pause New PG?
                    if pause:
                        isPaused = True
                    else:
                        isPaused = False

                    # Get Policy
                    if policyname is None:
                        print('Cannot Create PG.. Policy name required')
                        report.append('%s,%s,%s,,Error,Policy Required To Create PG' % (clustername,sourcename,bucketname))
                        continue
                    else:
                        policy = [p for p in (api('get', 'data-protect/policies', v=2))['policies'] if p['name'].lower() == policyname.lower()]
                        if policy is None or len(policy) == 0:
                            print('Cannot Create PG.. Policy %s not found' % policyname)
                            report.append('%s,%s,%s,,Error,Policy %s Not Found to Create PG' % (clustername,sourcename,bucketname,policyname.lower()))
                            continue
                        else:
                            policy = policy[0]
                    
                    # get storageDomain
                    viewBox = [v for v in api('get', 'viewBoxes') if v['name'].lower() == storagedomain.lower()]
                    if viewBox is None or len(viewBox) == 0:
                        print('Storage Domain %s not found' % storagedomain)
                        exit(1)
                    else:
                        viewBox = viewBox[0]

                    # parse starttime
                    try:
                        (hour, minute) = starttime.split(':')
                        hour = int(hour)
                        minute = int(minute)
                        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                            print('starttime is invalid!')
                            exit(1)
                    except Exception:
                        print('starttime is invalid!')
                        exit(1)

                    if emailalerts is None:
                       alerttargets = []
                    else:
                        alerttargets = [{"emailAddress": emailalerts }]

                    #new job params
                    job = {
                        "name": newjobname,
                        "environment": "kS3Compatible",
                        "isPaused": isPaused,
                        "policyId": policy['id'],
                        "priority": "kMedium",
                        "storageDomainId": viewBox['id'],
                        "description": "protectS3 generated",
                        "startTime": {
                            "hour": hour,
                            "minute": minute,
                            "timeZone": timezone
                        },
                        "abortInBlackouts": False,
                        "alertPolicy": {
                            "backupRunStatus": [
                                "kFailure"
                            ],
                            "alertTargets": alerttargets
                        },
                        "sla": [
                            {
                                "backupRunType": "kFull",
                                "slaMinutes": fullsla
                            },
                            {
                                "backupRunType": "kIncremental",
                                "slaMinutes": incrementalsla
                            }
                        ],
                        "qosPolicy": "kBackupHDD",
                        "s3CompatibleParams": {
                            "objects": [
                                {
                                    "id": bucketid
                                }
                            ]
                        }
                    }
                    
                    #Create PG if not preview
                    if not preview:
                        print("Creating PG %s for %s" % (newjobname,sourcename))
                        newJob = api('post', 'data-protect/protection-groups', job,v=2)
                        if 'error' in newJob:
                            print('Error Creating PG %s' % newjobname)
                            new_job_error_message = newJob['error'].replace('\n', '')
                            report.append('%s,%s,%s,%s,Error,%s' % (clustername, sourcename, bucketname, job['name'],new_job_error_message))
                        else:
                            print('PG %s Created' % newjobname)
                            report.append('%s,%s,%s,%s,Created' % (clustername, sourcename, bucketname, job['name']))
                            s3pgs = gets3pgs()                
                        continue

                    #Still report if preview
                    else:
                        print("Creating PG %s for %s" % (newjobname,sourcename))
                        report.append('%s,%s,%s,%s,Preview-Created' % (clustername, sourcename, bucketname, job['name']))
                        continue

                #Add to Last PG if more than 1 PG found for the source
                if len(addtopg) > 1:
                    addtopg = addtopg[-1:]
                
                #Add Bucket IDs to PG Source IDs (PG count for source is exactly 1)
                thispg = addtopg[0]
                pgname = thispg['name']
                print("Going to Add %s to %s (%s)" % (bucketname, pgname, sourcename))
                updatepg = True
                thispg['sourceIds'].append(bucketid)
                data.append('%s,%s,%s,%s' % (clustername, sourcename, bucketname, pgname))
                
                #Update the PG if -preview was not specifed and PGs count for the source is exactly 1
                if not preview and updatepg == True:
                    print("Updating PG %s" % pgname)
                    updatedJob = api('put', 'protectionJobs/%s' % thispg['id'], thispg)
                    if 'error' in updatedJob:
                        print("Error Updating PG %s" % pgname)
                        update_job_error_message = updatedJob['error'].replace('\n', '')
                        for record in data:
                            report.append('%s,Error,%s' % (record, update_job_error_message))
                    else:
                        print("PG Updated Successfully")
                        for record in data:
                            report.append('%s,Added' % record)

                #Still Report if Preview
                elif preview and updatepg == True:
                    for record in data:
                        report.append('%s,Preview-Added' % record)

#Output Results to csv
for item in report:
    f.write('%s\n' % item)

f.close()
print('\nOutput saved to %s\n' % outfile)
