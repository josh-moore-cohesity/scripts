#!/usr/bin/env python

from pyhesity import *
import argparse
import codecs
import json
import os
from datetime import datetime

# PDF generation
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, HRFlowable
from reportlab.platypus import KeepTogether

# ── Cohesity brand palette ───────────────────────────────────────────────────
COHESITY_GREEN      = colors.HexColor('#67BF1B')   # primary brand green
COHESITY_GREEN_DARK = colors.HexColor('#4E9114')   # darker green for contrast
COHESITY_BLACK      = colors.HexColor('#0C0C0C')   # brand near-black
COHESITY_ALT_ROW    = colors.HexColor('#EEF7E3')   # very light green for alternating rows
COHESITY_RULE       = colors.HexColor('#67BF1B')   # section divider color
# ─────────────────────────────────────────────────────────────────────────────

parser = argparse.ArgumentParser()
parser.add_argument('-v', '--vip', type=str, default='helios.cohesity.com')
parser.add_argument('-u', '--username', type=str, default='helios')
parser.add_argument('-i', '--useApiKey', action='store_true')
parser.add_argument('-mcm', '--mcm', action='store_true')
parser.add_argument('-np', '--noprompt', action='store_true')
parser.add_argument('-m', '--mfacode', type=str, default=None)
parser.add_argument('-e', '--emailmfacode', action='store_true')
parser.add_argument('-pdf', '--pdf', action='store_true')
parser.add_argument('-outputpath', '--outputpath', type=str, default='./ClusterInfoPDFs')

args = parser.parse_args()

vip = args.vip
username = args.username
mcm = args.mcm
useApiKey = args.useApiKey
noprompt = args.noprompt
mfacode = args.mfacode
emailmfacode = args.emailmfacode
pdf = args.pdf
outputpath = args.outputpath

# authentication =========================================================
apiauth(vip=vip, username=username, useApiKey=useApiKey, helios=mcm, prompt=(not noprompt), mfaCode=mfacode, emailMfaCode=emailmfacode)

# exit if not authenticated
if apiconnected() is False:
    print('authentication failed')
    exit(1)

# end authentication =====================================================

#Date and Time
now = datetime.now()
datetimestring = now.strftime("%m/%d/%Y %I:%M %p")
dateString = now.strftime("%Y-%m-%d")

#Cluster File
outfile = 'cluster_info-%s.csv' % dateString

f = codecs.open(outfile, 'w')
f.write('Cluster,Cluster ID,Type,Node Count,Install Date,Timezone,Version,Encryption,Redundancy,Erasure Coding,EC Post Processing,DNS 1,DNS 2,SMTP Enabled,SMTP Server,SMTP Sender,NTP Server,NTP Auth Enabled,NTP Auth Key ID,SSO,Cluster Audit Log Days,Filer Audit Log Days,Apps Network,Critical Alert Email,Custom Roles,Custom Users,Banner\n')
report = []

#GFLAG File
gflagfile = 'cluster_info_gflags-%s.csv' % dateString
gf = codecs.open(gflagfile, 'w', 'utf-8')
gf.write('Cluster,Service Name,Flag Name,Flag Value,Reason\n')
gflagreport = []

#Apps File
appsfile = 'cluster_info_apps-%s.csv' % dateString
af = codecs.open(appsfile, 'w', 'utf-8')
af.write('Cluster,App Name,Running Instances\n')
appsreport = []

#Nodes File
nodesfile = 'cluster_info_nodes-%s.csv' % dateString
nf = codecs.open(nodesfile, 'w', 'utf-8')
nf.write('Cluster,Node,Type,ID,Node IP,Node IPMI IP\n')
nodesreport = []

# ── PDF helpers ──────────────────────────────────────────────────────────────

styles = getSampleStyleSheet()

def _cell(text, bold=False):
    """Wrap text in a Paragraph so long values wrap inside table cells."""
    base = ParagraphStyle('cell', parent=styles['Normal'], fontSize=8,
                          leading=10, wordWrap='CJK', textColor=COHESITY_BLACK)
    if bold:
        base = ParagraphStyle('cellbold', parent=styles['Normal'], fontSize=8,
                              leading=10, fontName='Helvetica-Bold',
                              textColor=COHESITY_BLACK)
    return Paragraph(str(text) if text is not None else 'NA', base)


def _build_table(headers, rows, col_widths=None):
    """Return a Cohesity-branded reportlab Table."""
    table_data = [[_cell(h, bold=True) for h in headers]]
    for row in rows:
        table_data.append([_cell(v) for v in row])

    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND',     (0, 0), (-1, 0),  COHESITY_GREEN),
        ('TEXTCOLOR',      (0, 0), (-1, 0),  colors.white),
        ('FONTNAME',       (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',       (0, 0), (-1, -1), 8),
        ('GRID',           (0, 0), (-1, -1), 0.4, colors.HexColor('#CCCCCC')),
        ('LINEBELOW',      (0, 0), (-1, 0),  1.5, COHESITY_GREEN_DARK),
        ('VALIGN',         (0, 0), (-1, -1), 'TOP'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COHESITY_ALT_ROW]),
    ]))
    return t


def _section_heading(text):
    """Green bold section heading with a thin rule underneath."""
    return Paragraph(text, ParagraphStyle(
        'coheading',
        parent=styles['Normal'],
        fontSize=11,
        fontName='Helvetica-Bold',
        textColor=COHESITY_GREEN_DARK,
        spaceBefore=10,
        spaceAfter=3,
    ))


def _divider():
    return HRFlowable(width='100%', thickness=1.5, color=COHESITY_GREEN,
                      spaceAfter=6)


def _on_page(canvas, doc):
    """Draw Cohesity-branded header and footer on every page."""
    canvas.saveState()
    w, h = landscape(letter)

    # Green top bar
    canvas.setFillColor(COHESITY_GREEN)
    canvas.rect(0, h - 22, w, 22, fill=1, stroke=0)

    # 'COHESITY' wordmark in the bar
    canvas.setFillColor(colors.white)
    canvas.setFont('Helvetica-Bold', 11)
    canvas.drawString(0.5 * inch, h - 16, 'COHESITY')

    # Cluster name in bar (right-aligned)
    canvas.setFont('Helvetica', 9)
    cluster_label = getattr(doc, '_cluster_name', '')
    canvas.drawRightString(w - 0.5 * inch, h - 16, cluster_label)

    # Thin black footer bar
    canvas.setFillColor(COHESITY_BLACK)
    canvas.rect(0, 0, w, 18, fill=1, stroke=0)

    # Footer: date left, page number right
    canvas.setFillColor(colors.white)
    canvas.setFont('Helvetica', 7)
    canvas.drawString(0.5 * inch, 5, f'Generated: {datetimestring}')
    canvas.drawRightString(w - 0.5 * inch, 5,
                           f'Page {doc.page}')

    canvas.restoreState()


def generate_cluster_pdf(cluster_name, date_str, cluster_row,
                         gflag_rows, app_rows, node_rows, outputpath):
    """Write a single-cluster Cohesity-branded PDF and return the filename."""
    safe_name = cluster_name.replace(' ', '_').replace('/', '-')
    filename = f'cluster_info_{safe_name}_{date_str}.pdf'
    os.makedirs(outputpath, exist_ok=True)
    filepath = os.path.join(outputpath, filename)

    doc = SimpleDocTemplate(
        filepath,
        pagesize=landscape(letter),
        leftMargin=0.5 * inch,
        rightMargin=0.5 * inch,
        topMargin=0.6 * inch,   # room for green header bar
        bottomMargin=0.4 * inch,
    )
    doc._cluster_name = cluster_name   # passed through to _on_page

    page_w = landscape(letter)[0] - inch   # usable width
    story = []

    # ── Title block ──────────────────────────────────────────────────────────
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f'Cluster Report',
        ParagraphStyle('rptlabel', parent=styles['Normal'], fontSize=9,
                       textColor=colors.HexColor('#666666'), spaceAfter=0),
    ))
    story.append(Paragraph(
        cluster_name,
        ParagraphStyle('rpttitle', parent=styles['Normal'], fontSize=20,
                       fontName='Helvetica-Bold', textColor=COHESITY_BLACK,
                       spaceAfter=10),
    ))
    story.append(_divider())
    story.append(Spacer(1, 4))

    # ── Section 1 — Cluster Info ─────────────────────────────────────────────
    story.append(_section_heading('Cluster Information'))
    story.append(_divider())
    ci_headers = [
        'Cluster', 'Cluster ID', 'Type', 'Node Count', 'Install Date',
        'Timezone', 'Version', 'Encryption', 'Redundancy', 'Erasure Coding',
        'EC Post Processing', 'DNS 1', 'DNS 2', 'SMTP Enabled', 'SMTP Server',
        'SMTP Sender', 'NTP Server', 'NTP Auth Enabled', 'NTP Auth Key ID',
        'SSO', 'Cluster Audit Log Days', 'Filer Audit Log Days', 'Apps Network',
        'Critical Alert Email', 'Custom Roles', 'Custom Users', 'Banner',
    ]
    kv_rows = [(h, v) for h, v in zip(ci_headers, cluster_row)]
    story.append(_build_table(['Field', 'Value'], kv_rows,
                              col_widths=[2.2 * inch, page_w - 2.2 * inch]))
    story.append(Spacer(1, 12))

    # ── Section 2 — GFlags ───────────────────────────────────────────────────
    story.append(_section_heading('Custom GFlags'))
    story.append(_divider())
    if gflag_rows:
        col_w = [2.0 * inch, 2.2 * inch, 2.0 * inch, page_w - 6.2 * inch]
        story.append(_build_table(
            ['Service Name', 'Flag Name', 'Flag Value', 'Reason'],
            gflag_rows, col_widths=col_w))
    else:
        story.append(Paragraph('No custom gflags configured.', styles['Normal']))
    story.append(Spacer(1, 12))

    # ── Section 3 — Apps ─────────────────────────────────────────────────────
    story.append(_section_heading('Marketplace Apps'))
    story.append(_divider())
    if app_rows:
        story.append(_build_table(
            ['App Name', 'Running Instances'], app_rows,
            col_widths=[page_w * 0.65, page_w * 0.35]))
    else:
        story.append(Paragraph('No app data collected.', styles['Normal']))
    story.append(Spacer(1, 12))

    # ── Section 4 — Nodes ────────────────────────────────────────────────────
    story.append(_section_heading('Nodes'))
    story.append(_divider())
    if node_rows:
        col_w = [2.4 * inch, 1.6 * inch, 1.4 * inch, 1.6 * inch, 1.6 * inch]
        story.append(_build_table(
            ['Node', 'Type', 'ID', 'Node IP', 'Node IPMI IP'],
            node_rows, col_widths=col_w))
    else:
        story.append(Paragraph('No node data collected.', styles['Normal']))

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return filepath

# ── end PDF helpers ──────────────────────────────────────────────────────────

#Get Clusters
clusters = api('get', 'cluster-mgmt/info',mcmv2=True)
clusters = clusters['cohesityClusters']

#Get info for each cluster
for cluster in clusters:

    #Skip Cluster if not connected to Helios
    if cluster['isConnectedToHelios'] == False:
        print(cluster['clusterName'],"Not Connected to Helios")
        continue

    print(cluster['clusterName'])

    #Connect to Cluster
    heliosCluster (cluster['clusterName'])

    # Per-cluster data collectors for PDF
    cluster_pdf_row  = []
    cluster_gflags   = []
    cluster_apps     = []
    cluster_nodes    = []

    #Cluster Info
    clusterinfo = api('get', 'cluster?fetchStats=true')
    if clusterinfo is None:
        print("API Error for", cluster['clusterName'], "...skipping")
        continue
    version = clusterinfo['clusterSoftwareVersion'].split('_r')[0]
    nodecount = clusterinfo['nodeCount']
    installmsecs = clusterinfo['createdTimeMsecs']
    installusecs = installmsecs * 1000
    installdate = usecsToDate (installusecs)
    loginbanner = api('get', 'banners')
    loginbanner = loginbanner['content']
    loginbanner = "".join(loginbanner.splitlines())
    timezone = clusterinfo['timezone']
    clusterauditinfo = clusterinfo['clusterAuditLogConfig']
    clusterauditretention = clusterauditinfo['retentionPeriodDays']
    filerauditinfo = clusterinfo['filerAuditLogConfig']
    filerauditretention = clusterauditinfo['retentionPeriodDays']
    dnsServers = clusterinfo['dnsServerIps']
    if len(dnsServers) > 1:
        dns1 = dnsServers[0]
        dns2 = dnsServers[1]
    if len(dnsServers) == 1:
        dns1 = dnsServers[0]
        dns2 = "NA"
    appsSubnet = clusterinfo['appsSubnet']
    appsip = appsSubnet['ip']
    appsbits = appsSubnet['netmaskBits']
    appsnetwork = f"{appsip}/{appsbits}"

    #SMTP Info
    smtpinfo = api('get', '/smtpServer')
    if smtpinfo == 'null\n':
        smtpenabled = "NA"
        smtpserver = "NA"
        smtpsender = "NA"
    if smtpinfo != 'null\n':
        smtpserver = smtpinfo['server']
        smtpdisabled = smtpinfo['disableSmtp']
        if smtpdisabled == False:
            smtpenabled = True
        if smtpdisabled == True:
            smtpenabled = False
        smtpsender = smtpinfo['senderEmailAddress']

    #NTP Info
    ntpinfo = api('get', '/ntpServers')
    ntpserver = ntpinfo['ntpServers'][0]
    if ntpinfo.get('ntpAuthenticationEnabled'):
        ntpauthinfo = ntpinfo.get('ntpServerAuthInfo', [])
        if ntpauthinfo:
            ntpauthenabled = True
            ntpauthinfo = ntpinfo['ntpServerAuthInfo']
            ntpauthserver = ntpauthinfo[0]
            ntpauthkeyid = ntpauthserver.get('ntpServerAuthKeyId')
    else:
        ntpauthenabled = False
        ntpauthkeyid = "NA"

    #SSO Info
    ssoinfo = api('get', 'idps?allUnderHierarchy=true')
    if len(ssoinfo) == 0:
        ssoname = "NA"
    else:
        ssoinfo = ssoinfo[0]
        ssoname = ssoinfo['name']

    #Storage Domains
    sd = api('get', 'storage-domains?matchPartialNames=false&includeTenants=true&includeStats=true', v=2)
    sd = sd['storageDomains'][0]
    sdpolicy = sd['storagePolicy']
    diskfailstolerated = (sdpolicy['numDiskFailuresTolerated'])
    nodefailstolerated = (sdpolicy['numNodeFailuresTolerated'])
    redundancy = f"{diskfailstolerated}" +"D:" + f"{nodefailstolerated}" +"N"
    if 'erasureCodingParams' in sdpolicy:
        numDataStripes = sdpolicy['erasureCodingParams']['numDataStripes']
        numCodedStripes = sdpolicy['erasureCodingParams']['numCodedStripes']
        ec = f"{numDataStripes}" + ":" + f"{numCodedStripes}"
        ecinlineEnabled = sdpolicy['erasureCodingParams']['inlineEnabled']
        if ecinlineEnabled == False:
            ecpostprocess = "True"
        if ecinlineEnabled == True:
            ecpostprocess = "False"
    else:
        ec = "NA"
        ecpostprocess = "NA"

    #Cluster Notifications
    clusteralertnotifcations = api('get', 'alertNotificationRules')
    for n in clusteralertnotifcations:
        if 'severities' in n:
            severities = n['severities']
            sevstring = ", ".join(severities)
            if sevstring == 'kCritical':
                emailinfo = n['emailDeliveryTargets'][0]
                alertemailto = emailinfo['emailAddress']
            else:
                alertemailto = "NA"
    if 'alertemailto' not in locals():
        alertemailto = "NA"

    #Roles
    roles = api('get', 'roles')
    customroles = [r for r in roles if r['isCustomRole'] == True]
    customrolecount= len(customroles)

    #Users
    users = api('get', 'users')
    customusers = [u for u in users if u['username'] != 'admin' and not (u['username'].startswith('cohesity_ui_support'))]
    customusercount = len(customusers)

    #add all data to cluster report
    csv_row = str('%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s' % (clusterinfo['name'],clusterinfo['id'],clusterinfo['clusterType'],nodecount,installdate,timezone,version,clusterinfo['aesEncryptionMode'],redundancy,ec,ecpostprocess,dns1,dns2,smtpenabled,smtpserver,smtpsender,ntpserver,ntpauthenabled,ntpauthkeyid,ssoname,clusterauditretention,filerauditretention,appsnetwork,alertemailto,customrolecount,customusercount,loginbanner))
    report.append(csv_row)

    # Collect cluster info values for PDF (same order as CSV headers)
    cluster_pdf_row = [
        clusterinfo['name'], clusterinfo['id'], clusterinfo['clusterType'],
        nodecount, installdate, timezone, version,
        clusterinfo['aesEncryptionMode'], redundancy, ec, ecpostprocess,
        dns1, dns2, smtpenabled, smtpserver, smtpsender,
        ntpserver, ntpauthenabled, ntpauthkeyid, ssoname,
        clusterauditretention, filerauditretention, appsnetwork,
        alertemailto, customrolecount, customusercount, loginbanner,
    ]

    #GFLAGS
    flags = api('get', '/clusters/gflag')
    for flag in flags:
        servicename = flag['serviceName']
        if 'gflags' in flag:
            gflags = flag['gflags']
            customgflags = [g for g in gflags if not g['reason'].startswith('Auto') and not g['reason'].startswith('Maybe')]
            for customgflag in customgflags:
                flagname = customgflag['name']
                flagvalue = customgflag['value']
                reason = customgflag['reason']
                flagvalue = flagvalue.replace(',', ';;')
                gflagreport.append(str('%s,%s,%s,%s,%s' % (clusterinfo['name'],servicename, flagname, flagvalue, reason)))
                cluster_gflags.append([servicename, flagname, flagvalue, reason])

    #APPS
    appsmode = api('get', 'cluster/appSettings')
    if appsmode['marketplaceAppsMode'] == 'kDisabled':
        appsreport.append(str('%s,%s' % (clusterinfo['name'],'Apps Disabled')))
        cluster_apps.append(['Apps Disabled', ''])

    if appsmode['marketplaceAppsMode'] == 'kBareMetal':
        apps = api('get', 'apps')
        if 'error' in apps:
            appsreport.append(str('%s,%s' % (clusterinfo['name'],'Internal Error. Check Athena')))
            cluster_apps.append(['Internal Error. Check Athena', ''])
        else:
            for app in apps:
                if len(app['metadata']) == 0:
                    continue
                appname =app['metadata']['name']
                if 'installState' in app:
                    appinstances = api('get', 'appInstances')
                    runningapps = [i for i in appinstances if i['appName'] == appname and i['state'] == 'kRunning']
                    totalinstances = len(runningapps)
                    appsreport.append(str('%s,%s,%s' % (clusterinfo['name'],appname,totalinstances)))
                    cluster_apps.append([appname, totalinstances])
                else:
                    appsreport.append(str('%s,%s,%s' % (clusterinfo['name'],appname,'Not Installed')))
                    cluster_apps.append([appname, 'Not Installed'])

    #NODES
    nodes = api('get', 'nodes')
    if clusterinfo['clusterType'] == 'kPhysical':
        ipmiinfo = api('get', '/nexus/ipmi/cluster_get_lan_info')
        if 'nodesIpmiInfo' not in ipmiinfo:
            print('Could not retrieve IPMI info for %s, marking IPMI IPs as NA' % clusterinfo['name'])
            ipminodeinfo = "NA"
        else:
            ipminodeinfo = ipmiinfo['nodesIpmiInfo']
    else:
        ipminodeinfo = "NA"

    for node in nodes:
        nodeid = node['id']
        nodeip = node['ip']
        hostname = node['hostName']
        nodetype = node['productModel']
        if ipminodeinfo != "NA":
            for nodeips in ipminodeinfo:
                if nodeips['nodeIp'] == nodeip:
                    nodeipmiip = nodeips['nodeIpmiIp']
        else:
            nodeipmiip = "NA"
        nodesreport.append(str('%s,%s,%s,%s,%s,%s' % (cluster['clusterName'],hostname,nodetype,nodeid,nodeip,nodeipmiip)))
        cluster_nodes.append([hostname, nodetype, nodeid, nodeip, nodeipmiip])

    if pdf:
        # Generate per-cluster PDF
        pdf_file = generate_cluster_pdf(
            cluster_name=clusterinfo['name'],
            date_str=dateString,
            cluster_row=cluster_pdf_row,
            gflag_rows=cluster_gflags,
            app_rows=cluster_apps,
            node_rows=cluster_nodes,
            outputpath=outputpath,
        )
        print('PDF saved to %s' % pdf_file)

#write Cluster Info to report
for item in sorted(report):
    f.write('%s\n' % item)
f.close()
print('\nCluster Output saved to %s\n' % outfile)

#write gflags to report
for flags in sorted(gflagreport):
    gf.write ('%s\n' % flags)
gf.close()
print('\nGFLAG Output saved to %s\n' % gflagfile)

#write Apps to report
for app in sorted(appsreport):
    af.write ('%s\n' % app)
af.close()
print('\nApps Output saved to %s\n' % appsfile)

#write Nodes to report
for nodes in sorted(nodesreport):
    nf.write ('%s\n' % nodes)
nf.close()
print('\nNodes Output saved to %s\n' % nodesfile)
