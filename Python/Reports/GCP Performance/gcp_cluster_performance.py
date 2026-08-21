#!/usr/bin/env python
"""Pull storage, ingest, and network performance stats for GCP clusters via Helios and render an HTML report"""

### import pyhesity wrapper module
from pyhesity import *
from datetime import datetime
import os
import html

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
parser.add_argument('-outputpath', '--outputpath', type=str, default='./Results')

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
outputpath = args.outputpath

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

# get list of GCP clusters (falls back to auto-discovery via cluster-mgmt/info below if not given)
clusternames = gatherList(clustername, clusterlist, name='GCP clusters', required=False)

# Date and Time
now = datetime.now()
datetimestring = now.strftime("%m/%d/%Y %I:%M %p")
dateString = now.strftime("%Y-%m-%d")

# authenticate
apiauth(vip=vip, username=username, domain=domain, password=password, useApiKey=useApiKey, helios=mcm, prompt=(not noprompt), mfaCode=mfacode, emailMfaCode=emailmfacode)

# exit if not authenticated
if apiconnected() is False:
    print('authentication failed')
    exit(1)

# end authentication =====================================================

# auto-discover GCP clusters if none were specified on the command line
if len(clusternames) == 0:
    clusters = api('get', 'cluster-mgmt/info', mcmv2=True)
    clusters = clusters['cohesityClusters']
    clusters = [c for c in clusters if c['isConnectedToHelios'] == True and c.get('type') == 'kGoogleCloud']
    clusternames = [c['clusterName'] for c in clusters]
    if len(clusternames) == 0:
        print('no GCP clusters found (isConnectedToHelios + type=kGoogleCloud)')
        exit()

os.makedirs(outputpath, exist_ok=True)

def clusterEnvironment(name):
    """classify a cluster by naming convention (check nonprod before prod, since it's a substring of it)"""
    n = name.lower()
    if 'nonprod' in n:
        return 'nonprod'
    if 'lab' in n:
        return 'lab'
    if 'prod' in n:
        return 'prod'
    return 'other'

env_counts = {'nonprod': 0, 'lab': 0, 'prod': 0, 'other': 0}
for name in clusternames:
    env_counts[clusterEnvironment(name)] += 1

BYTES_GB = 1024 ** 3
BYTES_TB = 1024 ** 4

nowUsecs = dateToUsecs(now.strftime("%Y-%m-%d %H:%M:%S"))
dayAgoUsecs = timeAgo(24, 'hours')
weekAgoUsecs = timeAgo(7, 'days')
nowMsecs = int(nowUsecs / 1000)
dayAgoMsecs = int(dayAgoUsecs / 1000)
weekAgoMsecs = int(weekAgoUsecs / 1000)

INGEST_ROLLUP_INTERVAL_SECS = 300     # 5 minute buckets across the last 24 hours
THROUGHPUT_ROLLUP_INTERVAL_SECS = 3600  # 1 hour buckets across the last 7 days

def dataPointValue(dataPoint):
    """pull the numeric value out of a timeSeriesStats data point regardless of value type"""
    data = dataPoint.get('data', {})
    for key in ('int64Value', 'doubleValue', 'value'):
        if key in data:
            return data[key]
    return 0

def latestSeriesValue(schemaName, metricName, clusterId, startTimeMsecs, endTimeMsecs, rollupIntervalSecs=86400):
    """latest value of a cluster-level timeSeriesStats metric (e.g. backend capacity/usage)"""
    series = api('get', ('statistics/timeSeriesStats?schemaName=%s&metricName=%s&rollupFunction=latest'
                          '&rollupIntervalSecs=%s&entityId=%s&startTimeMsecs=%s&endTimeMsecs=%s')
                 % (schemaName, metricName, rollupIntervalSecs, clusterId, startTimeMsecs, endTimeMsecs))
    if series and series.get('dataPointVec'):
        return dataPointValue(series['dataPointVec'][-1])
    return None

def sparkline(values, width=220, height=40, top_margin=10, color='#1f4e79', peak_color='#d9534f'):
    """render a small inline SVG line chart for a list of throughput values, labeling the peak point(s) with their value"""
    if not values:
        return '<span class="nodata">no data</span>'
    maxval = max(values)
    if maxval <= 0:
        return '<span class="nodata">no data</span>'
    n = len(values)
    plot_height = height - 4
    step = width / max(n - 1, 1)
    coords = []
    for i, v in enumerate(values):
        x = i * step
        y = top_margin + plot_height - ((v / maxval) * (plot_height - 4)) - 2
        coords.append((x, y, v))
    points_str = ' '.join('%.1f,%.1f' % (x, y) for x, y, _ in coords)
    peak_labels = ''.join(
        ('<circle cx="%.1f" cy="%.1f" r="2.5" fill="%s"/>'
         '<text x="%.1f" y="%.1f" font-size="9" text-anchor="middle" fill="%s">%.0f</text>')
        % (x, y, peak_color, x, y - 4, peak_color, v)
        for x, y, v in coords if v == maxval
    )
    total_height = top_margin + height
    return ('<svg width="%d" height="%d" viewBox="0 0 %d %d">'
            '<polyline points="%s" fill="none" stroke="%s" stroke-width="2"/>'
            '%s'
            '</svg>' % (width, total_height, width, total_height, points_str, color, peak_labels))

cluster_rows = []
total_used_tb = 0.0
total_ingest_gb = 0.0

for cluster in clusternames:
    heliosCluster(cluster)
    print(cluster)

    if LAST_API_ERROR() != 'OK':
        continue

    clusterinfo = api('get', 'cluster?fetchStats=true')
    if clusterinfo is None:
        print('  unable to reach cluster, skipping')
        continue
    clusterId = clusterinfo.get('id')

    # storage utilization --------------------------------------------------
    # Backup data on these Cloud Edition clusters lives entirely in the GCP
    # bucket configured as the cluster's external target, not on local node
    # disks or the cluster's own logical storage layer. Find the external
    # target tied to this cluster's storage domain, then read its usage from
    # the vault's own Icebox stats (kIceboxVaultStats/kMorphedUsageBytes).
    used_tb = 0.0
    used_capacity_bytes = None

    storageDomains = api('get', 'storage-domains?matchPartialNames=false&includeTenants=true&includeStats=true', v=2)
    storageDomainName = None
    if storageDomains and storageDomains.get('storageDomains'):
        storageDomainName = storageDomains['storageDomains'][0].get('name')

    if storageDomainName is not None:
        externalTargets = api('get', 'data-protect/external-targets', v=2)
        matches = []
        if externalTargets and externalTargets.get('externalTargets'):
            for target in externalTargets['externalTargets']:
                cloudDomains = target.get('cloudDomains') or []
                if any((cd.get('storageDomainName') or '').lower() == storageDomainName.lower() for cd in cloudDomains):
                    matches.append(target)
        if matches:
            vaultId = matches[0].get('id')
            used_capacity_bytes = latestSeriesValue('kIceboxVaultStats', 'kMorphedUsageBytes', vaultId, dayAgoMsecs, nowMsecs)
        else:
            print('  no external target found for storage domain "%s"' % storageDomainName)
    else:
        print('  unable to determine storage domain for %s' % cluster)

    if used_capacity_bytes:
        used_tb = round(used_capacity_bytes / BYTES_TB, 2)

    # daily ingest, last 24h -------------------------------------------------
    ingest_gb = 0.0
    if clusterId is not None:
        ingestSeries = api('get', ('statistics/timeSeriesStats?schemaName=kBridgeClusterLogicalStats'
                                    '&metricName=kNumBytesWritten&rollupFunction=rate'
                                    '&rollupIntervalSecs=%s&prorateDataPoints=true'
                                    '&entityId=%s&startTimeMsecs=%s&endTimeMsecs=%s')
                           % (INGEST_ROLLUP_INTERVAL_SECS, clusterId, dayAgoMsecs, nowMsecs))
        if ingestSeries and ingestSeries.get('dataPointVec'):
            bytesPerSecValues = [dataPointValue(dp) for dp in ingestSeries['dataPointVec']]
            total_bytes_written = sum(bytesPerSecValues) * INGEST_ROLLUP_INTERVAL_SECS
            ingest_gb = round(total_bytes_written / BYTES_GB, 2)

    # network throughput (avg/peak/trend), last 7 days -----------------------
    throughput_mbps = []
    avg_mbps = peak_mbps = 0.0
    if clusterId is not None:
        throughputSeries = api('get', ('statistics/timeSeriesStats?schemaName=kBridgeClusterLogicalStats'
                                        '&metricName=kNumBytesWritten&rollupFunction=rate'
                                        '&rollupIntervalSecs=%s&prorateDataPoints=true'
                                        '&entityId=%s&startTimeMsecs=%s&endTimeMsecs=%s')
                               % (THROUGHPUT_ROLLUP_INTERVAL_SECS, clusterId, weekAgoMsecs, nowMsecs))
        if throughputSeries and throughputSeries.get('dataPointVec'):
            bytesPerSecValues = [dataPointValue(dp) for dp in throughputSeries['dataPointVec']]
            throughput_mbps = [round(v / (1024 ** 2), 2) for v in bytesPerSecValues]
            avg_mbps = round(sum(throughput_mbps) / len(throughput_mbps), 2)
            peak_mbps = round(max(throughput_mbps), 2)

    cluster_rows.append({
        'cluster': cluster,
        'used_tb': used_tb,
        'ingest_gb': ingest_gb,
        'avg_mbps': avg_mbps,
        'peak_mbps': peak_mbps,
        'throughput_points': throughput_mbps,
    })

    total_used_tb += used_tb
    total_ingest_gb += ingest_gb

total_used_tb = round(total_used_tb, 2)
total_ingest_gb = round(total_ingest_gb, 2)

cluster_rows = sorted(cluster_rows, key=lambda x: x['cluster'].lower())

# Build HTML rows -----------------------------------------------------------
table_rows_html = ''
for row in cluster_rows:
    table_rows_html += '''
        <tr>
            <td>%s</td>
            <td>%.2f</td>
            <td>%.2f</td>
            <td>%.2f</td>
            <td>%.2f</td>
            <td>%s</td>
        </tr>
    ''' % (
        html.escape(row['cluster']), row['used_tb'], row['ingest_gb'], row['avg_mbps'], row['peak_mbps'],
        sparkline(row['throughput_points']),
    )

html_content = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GCP Cluster Utilization Report - %s</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 30px;
            background-color: #f7f9fc;
            color: #333;
        }
        h1 {
            margin-bottom: 10px;
        }
        .subtitle {
            color: #666;
            margin-bottom: 25px;
        }
        .summary-container {
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
            margin-bottom: 30px;
        }
        .summary-card {
            background: #ffffff;
            border: 1px solid #d9e2f0;
            border-radius: 8px;
            padding: 20px;
            min-width: 220px;
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
        }
        .summary-card h2 {
            font-size: 16px;
            margin: 0 0 10px 0;
            color: #1f4e79;
        }
        .summary-card .value {
            font-size: 28px;
            font-weight: bold;
        }
        table {
            width: 100%%;
            border-collapse: collapse;
            background: #ffffff;
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
        }
        th, td {
            padding: 12px 14px;
            border: 1px solid #d9e2f0;
            text-align: left;
            vertical-align: middle;
        }
        th {
            background-color: #1f4e79;
            color: white;
        }
        tr:nth-child(even) {
            background-color: #f4f8fc;
        }
        .nodata {
            color: #999;
            font-style: italic;
        }
    </style>
</head>
<body>
    <h1>GCP Cluster Utilization Report</h1>
    <div class="subtitle">Generated on %s &mdash; ingest covers the trailing 24 hours, throughput covers the trailing 7 days</div>

    <div class="summary-container">
        <div class="summary-card">
            <h2>Total Target Usage (TB)</h2>
            <div class="value">%.2f</div>
        </div>
        <div class="summary-card">
            <h2>Total Ingest, Last 24h (GB)</h2>
            <div class="value">%.2f</div>
        </div>
        <div class="summary-card">
            <h2>Nonprod Clusters</h2>
            <div class="value">%d</div>
        </div>
        <div class="summary-card">
            <h2>Lab Clusters</h2>
            <div class="value">%d</div>
        </div>
        <div class="summary-card">
            <h2>Prod Clusters</h2>
            <div class="value">%d</div>
        </div>
    </div>

    <table>
        <thead>
            <tr>
                <th>Cluster</th>
                <th>Target Usage (TB)</th>
                <th>Ingest, Last 24h (GB)</th>
                <th>Avg Throughput, Last 7d (MB/s)</th>
                <th>Peak Throughput, Last 7d (MB/s)</th>
                <th>Throughput Trend (7d)</th>
            </tr>
        </thead>
        <tbody>
            %s
        </tbody>
    </table>
</body>
</html>
''' % (dateString, datetimestring, total_used_tb, total_ingest_gb,
       env_counts['nonprod'], env_counts['lab'], env_counts['prod'], table_rows_html)

html_file = os.path.join(outputpath, 'gcp_cluster_performance_%s.html' % dateString)
with open(html_file, 'w', encoding='utf-8') as f:
    f.write(html_content)

print('\nHTML written to %s' % html_file)
