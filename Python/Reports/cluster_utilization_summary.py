#!/usr/bin/env python3

from pyhesity import *
import argparse
from datetime import datetime
import os
import html

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart



parser = argparse.ArgumentParser()
parser.add_argument('-v', '--vip', type=str, default='helios.cohesity.com')
parser.add_argument('-u', '--username', type=str, default='helios')
parser.add_argument('-i', '--useApiKey', action='store_true')
parser.add_argument('-mcm', '--mcm', action='store_true')
parser.add_argument('-np', '--noprompt', action='store_true')
parser.add_argument('-m', '--mfacode', type=str, default=None)
parser.add_argument('-e', '--emailmfacode', action='store_true')
parser.add_argument('-c', '--clustername', nargs='+', type=str, default=None)
parser.add_argument('-cl', '--clusters', type=str)

args = parser.parse_args()

vip = args.vip
username = args.username
mcm = args.mcm
useApiKey = args.useApiKey
noprompt = args.noprompt
mfacode = args.mfacode
emailmfacode = args.emailmfacode
clustername = args.clustername
clusterlist = args.clusters

# authentication =========================================================
apiauth(
    vip=vip,
    username=username,
    useApiKey=useApiKey,
    helios=mcm,
    prompt=(not noprompt),
    mfaCode=mfacode,
    emailMfaCode=emailmfacode
)

if apiconnected() is False:
    print('authentication failed')
    exit(1)
# ======================================================================

# Date and Time
now = datetime.now()
dateString = now.strftime("%Y-%m-%d")

# HTML output file
html_file = f'cluster_utilization_{dateString}.html'

# gather server list
def gatherList(param=None, filename=None, name='items'):
    items = []
    if param is not None:
        for item in param:
            items.append(item)
    if filename is not None:
        with open(filename, 'r') as f:
            items += [s.strip() for s in f.readlines() if s.strip() != '']
    return items

# Combine list of clusters
clusternames = gatherList(clustername, clusterlist, name='clusters')

# Get clusters if none specified
if len(clusternames) == 0:
    clusters = api('get', 'cluster-mgmt/info', mcmv2=True)
    clusters = clusters['cohesityClusters']
    clusters = [c for c in clusters if c['isConnectedToHelios'] is True]
    clusternames = [c['clusterName'] for c in clusters]

# Collect cluster data
cluster_rows = []
total_replication = 0.0
total_backup = 0.0
total_utilization = 0.0

for cluster in clusternames:
    print(cluster)
    heliosCluster(cluster)

    reputilization = api('get', 'stats/consumers?consumerType=kReplicationRuns')
    reputilization = reputilization.get('statsList', [])
    repsum = round(
        sum(pg.get('stats', {}).get('storageConsumedBytes', 0)
            for pg in reputilization) / (1024 ** 4),
        2
    )

    backuputilization = api('get', 'stats/consumers?consumerType=kProtectionRuns')
    backuputilization = backuputilization.get('statsList', [])
    backupsum = round(
        sum(pg.get('stats', {}).get('storageConsumedBytes', 0)
            for pg in backuputilization) / (1024 ** 4),
        2
    )

    totalsum = round(repsum + backupsum, 2)

    cluster_rows.append({
        'cluster': cluster,
        'replication_tb': repsum,
        'backup_tb': backupsum,
        'total_tb': totalsum
    })

    total_replication += repsum
    total_backup += backupsum
    total_utilization += totalsum

# Round grand totals
total_replication = round(total_replication, 2)
total_backup = round(total_backup, 2)
total_utilization = round(total_utilization, 2)

#Sort by Cluster Name
cluster_rows = sorted(cluster_rows, key=lambda x: x['cluster'].lower())

# Build HTML rows
table_rows_html = ""
for row in cluster_rows:
    table_rows_html += f"""
        <tr>
            <td>{html.escape(row['cluster'])}</td>
            <td>{row['replication_tb']:.2f}</td>
            <td>{row['backup_tb']:.2f}</td>
            <td>{row['total_tb']:.2f}</td>
        </tr>
    """

# HTML content
html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cluster Utilization Report - {dateString}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 30px;
            background-color: #f7f9fc;
            color: #333;
        }}
        h1 {{
            margin-bottom: 10px;
        }}
        .subtitle {{
            color: #666;
            margin-bottom: 25px;
        }}
        .summary-container {{
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
            margin-bottom: 30px;
        }}
        .summary-card {{
            background: #ffffff;
            border: 1px solid #d9e2f0;
            border-radius: 8px;
            padding: 20px;
            min-width: 220px;
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
        }}
        .summary-card h2 {{
            font-size: 16px;
            margin: 0 0 10px 0;
            color: #1f4e79;
        }}
        .summary-card .value {{
            font-size: 28px;
            font-weight: bold;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: #ffffff;
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
        }}
        th, td {{
            padding: 12px 14px;
            border: 1px solid #d9e2f0;
            text-align: left;
        }}
        th {{
            background-color: #1f4e79;
            color: white;
        }}
        tr:nth-child(even) {{
            background-color: #f4f8fc;
        }}
    </style>
</head>
<body>
    <h1>Cluster Utilization Report</h1>
    <div class="subtitle">Generated on {dateString}</div>

    <div class="summary-container">
        <div class="summary-card">
            <h2>Total Utilization (TB)</h2>
            <div class="value">{total_utilization:.2f}</div>
        </div>
        <div class="summary-card">
            <h2>Total Backup Utilization (TB)</h2>
            <div class="value">{total_backup:.2f}</div>
        </div>
        <div class="summary-card">
            <h2>Total Replication Utilization (TB)</h2>
            <div class="value">{total_replication:.2f}</div>
        </div>
    </div>

    <table>
        <thead>
            <tr>
                <th>Cluster Name</th>
                <th>Replication_Sum_TB</th>
                <th>Backup_Sum_TB</th>
                <th>Total_Sum_TB</th>
            </tr>
        </thead>
        <tbody>
            {table_rows_html}
        </tbody>
    </table>
</body>
</html>
"""

# Write HTML file
with open(html_file, 'w', encoding='utf-8') as f:
    f.write(html_content)

print(f'\nHTML written to {html_file}')


# === CONFIG ===
smtp_server = "smtp.domain.com"
smtp_port = 25   # or 587 if using TLS
from_email = "email1@domain.com"
#to_email = "email2@domain.com"
to_list = ["email3@domain.com", "email4@domain.com"]

date_str = datetime.now().strftime("%Y-%m-%d")
html_file = f"cluster_utilization_{date_str}.html"

subject = f"Cluster Utilization Report - {date_str}"

# === READ HTML FILE ===
with open(html_file, "r", encoding="utf-8") as f:
    html_content = f.read()

# === BUILD EMAIL ===
msg = MIMEMultipart("alternative")
msg["Subject"] = subject
msg["From"] = from_email
#msg["To"] = to_email
msg["To"] = ", ".join(to_list)
# Attach HTML
msg.attach(MIMEText(html_content, "html"))

# === SEND EMAIL ===
with smtplib.SMTP(smtp_server, smtp_port) as server:
    # If needed:
    # server.starttls()
    # server.login("username", "password")

    server.sendmail(from_email, to_list, msg.as_string())

print("Email sent successfully.")
