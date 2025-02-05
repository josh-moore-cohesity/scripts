#!/usr/bin/env python
"""Schedule Helios Report"""

### import pyhesity wrapper module
from pyhesity import *
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('-v', '--vip', type=str, default='helios.cohesity.com')
parser.add_argument('-u', '--username', type=str, default='helios')
parser.add_argument('-i', '--useApiKey', action='store_true')
parser.add_argument('-mcm', '--mcm', action='store_true')
parser.add_argument('-sn', '--schedulename', type=str, required=True)
parser.add_argument('-rr', '--recipient', action='append', type=str, required=True)
parser.add_argument('-es', '--emailsubject', type=str, required=True)
parser.add_argument('-st', '--sendtime', type=int, required=True)
parser.add_argument('-tz', '--timezone', type=str, default='America/New_York')
parser.add_argument('-dom', '--daysofmonth',nargs='+', type=int, required=True)

args = parser.parse_args()

vip = args.vip
username = args.username
mcm = args.mcm
useApiKey = args.useApiKey
schedulename = args.schedulename
recipients = args.recipient
emailsubject = args.emailsubject
sendtime = args.sendtime
timezone = args.timezone
daysofmonth = args.daysofmonth

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

emaillist = gatherList(recipients, name='email addresses', required=True)


# authentication =========================================================
apiauth(vip=vip, username=username, useApiKey=useApiKey)

# exit if not authenticated
if apiconnected() is False:
    print('authentication failed')
    exit(1)

# end authentication =====================================================

#Configure Scheduled Report Parameters
body = {
    "reportId":"protection-runs",
    "name":schedulename,
    "emailIds":emaillist,
    "reportFormat":["PDF"],
    "emailSubject":emailsubject,
    "scheduleTime":{"minutesOfDay":[sendtime],"userTimezone":timezone,"daysOfMonth":daysofmonth},
    "filters":[{
                "attribute":"environment",
                "filterType":"In","inFilterParams":{
                    "attributeDataType":"String","stringFilterValues":["kVMware", "kSQL", "kOracle"],"attributeLabels":["VMware", "Microsoft SQL", "Oracle"]}},
                    {
                        "attribute":"date","filterType":"TimeRange","timeRangeFilterParams":{"dateRange":"LastMonth"}
                        }]
    }

#check if schedule name exists
existingschedules = api ('get', 'schedules', reportingv2=True)
existingschedules = existingschedules['schedules']

#update existing if it exists
if[existingschedules] is not None:
    existingschedules = [s for s in existingschedules if s['name'] == body['name']]
    if existingschedules is not None and len(existingschedules) > 0:
        existingschedule = existingschedules[0]
        print("Schedule Exists, Updating:", existingschedule['name'])
        scheduleid = existingschedule['scheduleId']
        api('put', 'schedules/%s' % scheduleid, body, reportingv2=True)

#Create new if doesn't exist
    else:
        print("New Schedule, Creating:", body['name'])
        api('post', 'schedules', body, reportingv2=True)

