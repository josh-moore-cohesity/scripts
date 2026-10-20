#!/usr/bin/env python
"""Audit Helios User Logins"""

# version 2026.10.21

### import pyhesity wrapper module
from pyhesity import *
import codecs
from datetime import datetime

### command line arguments
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
parser.add_argument('-y', '--days', type=int)
parser.add_argument('-user', '--user', type=str, default=None)
parser.add_argument('-html', '--html', action='store_true')

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
days = args.days
filteruser = args.user
html = args.html

if html and filteruser:
    print("-html is only used for all users; ignoring -html because -user was specified")
    html = False

if days:
    if days > 365:
        print("Days Back Must be 365 or less")
        exit(1)

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
outfile = 'user_audit-%s.csv' % dateString
f = codecs.open(outfile, 'w')

# Add headings to outfile
f.write("Username,Domain,Last Login,Last Logout,Role,Total Clusters,Accessible Clusters\n")

#Define Report
report = []
htmldata = []

#Get Users
users = api('get', 'users', mcm=True)
print(len(users), "users")

# limit to a single user if requested (match on username or user@domain)
if filteruser:
    users = [u for u in users if filteruser.lower() in (u['username'].lower(), ('%s@%s' % (u['username'], u['domain'])).lower())]
    if len(users) == 0:
        print("User '%s' not found" % filteruser)
        exit(1)

#Get Clusters
clusters = api('get', 'cluster-mgmt/info',mcmv2=True)
clusters = clusters['cohesityClusters']

if days:
    #set start time
    daysBackUsecs = timeAgo(days, 'days')
    auditlog = api('get', 'audit-logs?startTimeUsecs=%s&actions=login%%2Clogout&count=10000' % (daysBackUsecs), mcmv2=True )
else:
    #get all records
    daysBackUsecs = timeAgo(365, 'days')
    auditlog = api('get', 'audit-logs?startTimeUsecs=%s&actions=login%%2Clogout&count=10000' % (daysBackUsecs), mcmv2=True )

auditlog = (auditlog['auditLogs'])
auditlog = [a for a in auditlog if a['sourceType'] == 'helios']

print(len(auditlog), "total records")

#report oldest record
if not filteruser:
    oldestrecord =  auditlog[-1]
    print(oldestrecord)
    oldestdatestamp = usecsToDate(oldestrecord['timestampUsecs'])
    print("Oldest record is", oldestdatestamp)

#get user info
print("Username,Domain,Last Login,Last Logout,Role,Total Clusters,Accessible Clusters")
for user in users:
    username = user['username']
    accesibleclusters = []
    role = user['roles']
    role = str(role)[1:-1].strip('\'')
    domain = user['domain']
    logins = [record for record in auditlog if record['username'] == username and record['domain'] == domain.lower() and record['action'] == 'Login']
    logouts = [record for record in auditlog if record['username'] == username and record['domain'] == domain.lower() and record['action'] == 'Logout']
    loginrecords = [login for login in logins]
    logoutrecords = [logout for logout in logouts]
    clusteraccess = [c for c in user['clusterIdentifiers']]
    totalclusters = len(clusters)
    if clusteraccess[0]['clusterId'] == -1:
        accessibleclustercount = len(clusters)
        for cluster in clusters:
            accesibleclusters.append(cluster['clusterName'])
    else:
        for cluster in clusteraccess:
            clusterid = cluster['clusterId']
            clustername = [c for c in clusters if clusterid == c['clusterId']]
            for name in clustername:
                accesibleclusters.append(name['clusterName'])
        accessibleclustercount = len(accesibleclusters)
    clusterlist = list(accesibleclusters)
    accesibleclusters = ",".join(accesibleclusters)
    
    if len(logins) > 0:
        lastlogin = usecsToDate (logins[0]['timestampUsecs'])
        
    if len(logins) == 0:
        lastlogin = "NA"
    
    if len(logouts) > 0:
        lastlogout = usecsToDate (logouts[0]['timestampUsecs'])
        
    if len(logouts) == 0:
        lastlogout = "NA"
    
    print('%s,%s,%s,%s,%s,%s,%s' %(username,domain,lastlogin,lastlogout,role,totalclusters,accessibleclustercount))
    if filteruser:
        print('\nClusters accessible to %s (%s):' % (username, domain))
        for clustername in sorted(clusterlist, key=str.lower):
            print('  %s' % clustername)

    report.append(str('%s,%s,%s,%s,%s,%s,%s,%s' %(username,domain,lastlogin,lastlogout,role,totalclusters,accessibleclustercount, accesibleclusters)))
    htmldata.append({'username': username, 'domain': domain, 'lastLogin': str(lastlogin), 'lastLogout': str(lastlogout), 'role': role, 'totalClusters': totalclusters, 'clusters': sorted(clusterlist, key=str.lower)})

#write results to file        
for item in sorted(report):
    f.write('%s\n' % item)

f.close()
print('\nOutput saved to %s\n' % outfile)

#write html report (all users)
if html:
    import json
    htmlfile = 'user_audit-%s.html' % dateString
    htmldata = sorted(htmldata, key=lambda u: (u['username'].lower(), u['domain'].lower()))
    # escape '</' so user data can't terminate the script block
    jsondata = json.dumps(htmldata).replace('</', '<\\/')
    template = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Helios User Cluster Access</title>
<style>
body { font-family: Segoe UI, Arial, sans-serif; margin: 2em; color: #222; }
h1 { font-size: 1.4em; }
select { font-size: 1em; padding: 4px; min-width: 320px; }
table.info td { padding: 2px 12px 2px 0; }
table.info td:first-child { font-weight: bold; }
ul { columns: 3; margin-top: .5em; }
.muted { color: #777; }
</style>
</head>
<body>
<h1>Helios User Cluster Access</h1>
<p class="muted">Generated __GENERATED__ &mdash; __COUNT__ users</p>
<label for="users">User: </label>
<select id="users"><option value="">-- select a user --</option></select>
<div id="details" style="margin-top:1.5em"></div>
<script>
var data = __DATA__;
var sel = document.getElementById('users');
var out = document.getElementById('details');
function esc(s) { var d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
data.forEach(function (u, i) {
    var o = document.createElement('option');
    o.value = i;
    o.textContent = u.username + ' (' + u.domain + ')';
    sel.appendChild(o);
});
sel.addEventListener('change', function () {
    if (sel.value === '') { out.innerHTML = ''; return; }
    var u = data[sel.value];
    var h = '<table class="info">' +
        '<tr><td>Username</td><td>' + esc(u.username) + '</td></tr>' +
        '<tr><td>Domain</td><td>' + esc(u.domain) + '</td></tr>' +
        '<tr><td>Role</td><td>' + esc(u.role) + '</td></tr>' +
        '<tr><td>Last Login</td><td>' + esc(u.lastLogin) + '</td></tr>' +
        '<tr><td>Last Logout</td><td>' + esc(u.lastLogout) + '</td></tr>' +
        '<tr><td>Accessible Clusters</td><td>' + u.clusters.length + ' of ' + u.totalClusters + '</td></tr></table>';
    if (u.clusters.length) {
        h += '<h3>Clusters</h3><ul>' + u.clusters.map(function (c) { return '<li>' + esc(c) + '</li>'; }).join('') + '</ul>';
    } else {
        h += '<p class="muted">No accessible clusters.</p>';
    }
    out.innerHTML = h;
});
</script>
</body>
</html>
'''
    template = template.replace('__GENERATED__', datetimestring).replace('__COUNT__', str(len(htmldata))).replace('__DATA__', jsondata)
    h = codecs.open(htmlfile, 'w', 'utf-8')
    h.write(template)
    h.close()
    print('HTML report saved to %s\n' % htmlfile)
