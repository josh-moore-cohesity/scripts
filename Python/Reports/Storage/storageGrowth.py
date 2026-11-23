#!/usr/bin/env python
"""Storage Report for Python"""

# import pyhesity wrapper module
from pyhesity import *
from datetime import datetime
import codecs
import html
import json

# command line arguments
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('-v', '--vip', type=str, default='helios.cohesity.com')
parser.add_argument('-u', '--username', type=str, default='helios')
parser.add_argument('-d', '--domain', type=str, default='local')
parser.add_argument('-t', '--tenant', type=str, default=None)
parser.add_argument('-c', '--clustername', action='append', default=None)
parser.add_argument('-mcm', '--mcm', action='store_true')
parser.add_argument('-i', '--useApiKey', action='store_true')
parser.add_argument('-pwd', '--password', type=str, default=None)
parser.add_argument('-np', '--noprompt', action='store_true')
parser.add_argument('-m', '--mfacode', type=str, default=None)
parser.add_argument('-e', '--emailmfacode', action='store_true')
parser.add_argument('-of', '--outfolder', type=str, default='.')
parser.add_argument('-y', '--days', type=int, default=None)
parser.add_argument('-x', '--units', type=str, choices=['GiB', 'TiB', 'gib', 'tib'], default='GiB')

args = parser.parse_args()

vip = args.vip
username = args.username
domain = args.domain
tenant = args.tenant
mcm = args.mcm
useApiKey = args.useApiKey
password = args.password
noprompt = args.noprompt
mfacode = args.mfacode
emailmfacode = args.emailmfacode
folder = args.outfolder
days = args.days
units = args.units

# -c may be repeated and/or comma separated, and may be 'all'
clusternames = []
for entry in (args.clustername or []):
    clusternames += [e.strip() for e in entry.split(',') if e.strip()]
clusternames = list(dict.fromkeys(clusternames))
useAll = any(n.lower() == 'all' for n in clusternames)

if units.lower() == 'tib':
    units = 'TiB'
    multiplier = 1024 * 1024 * 1024 * 1024
if units.lower() == 'gib':
    units = 'GiB'
    multiplier = 1024 * 1024 * 1024

# authentication =========================================================
# demand clustername if connecting to helios or mcm
heliosConnection = mcm or vip.lower() == 'helios.cohesity.com'
if heliosConnection and len(clusternames) == 0:
    print('-c, --clustername is required when connecting to Helios or MCM (use -c all for every connected cluster)')
    exit(1)
if useAll and not heliosConnection:
    print('-c all is only supported when connecting to Helios or MCM')
    exit(1)

# authenticate
apiauth(vip=vip, username=username, domain=domain, password=password, useApiKey=useApiKey, helios=mcm, prompt=(not noprompt), mfaCode=mfacode, emailMfaCode=emailmfacode, tenantId=tenant)

# exit if not authenticated
if apiconnected() is False:
    print('authentication failed')
    exit(1)

# build the list of clusters to report on
if heliosConnection:
    if useAll:
        # '-c all' expands to every cluster currently connected to Helios, plus any explicitly named clusters
        connected = [c['name'] for c in heliosClusters()]
        clusternames = list(dict.fromkeys([n for n in clusternames if n.lower() != 'all'] + connected))
        print('found %s cluster(s) connected to Helios' % len(connected))
else:
    clusternames = [None]  # direct connection to a single cluster
# end authentication =====================================================

now = datetime.now()
datestring = now.strftime("%Y-%m-%d")


def collectCluster(name):
    """Return (clusterName, rows) for one cluster, or None on failure. rows are oldest -> newest."""
    if name is not None:
        heliosCluster(name)
        if LAST_API_ERROR() != 'OK':
            return None

    cluster = api('get', 'cluster')
    if cluster is None or 'id' not in cluster:
        print('unable to get cluster info for %s' % name)
        return None

    if days is not None:
        startTimeMsecs = int(timeAgo(days, 'days') / 1000)
    else:
        startTimeMsecs = cluster['createdTimeMsecs']

    print('Collecting report data for %s...' % cluster['name'])

    consumptionStats = api('get', 'statistics/timeSeriesStats?schemaName=kBridgeClusterStats&entityId=%s&metricName=kMorphedUsageBytes&startTimeMsecs=%s&rollupFunction=latest&rollupIntervalSecs=86400' % (cluster['id'], startTimeMsecs))
    capacityStats = api('get', 'statistics/timeSeriesStats?schemaName=kBridgeClusterStats&entityId=%s&metricName=kCapacityBytes&startTimeMsecs=%s&rollupFunction=latest&rollupIntervalSecs=86400' % (cluster['id'], startTimeMsecs))
    if not consumptionStats or not capacityStats or 'dataPointVec' not in consumptionStats or 'dataPointVec' not in capacityStats:
        print('unable to get storage stats for %s' % cluster['name'])
        return None

    statsConsumed = {}
    for stat in consumptionStats['dataPointVec']:
        dt = datetime.strptime(usecsToDate(stat['timestampMsecs'] * 1000), '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')
        statsConsumed[dt] = round(stat['data']['int64Value'] / multiplier, 1)

    statsCapacity = {}
    for stat in capacityStats['dataPointVec']:
        dt = datetime.strptime(usecsToDate(stat['timestampMsecs'] * 1000), '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')
        statsCapacity[dt] = round(stat['data']['int64Value'] / multiplier, 1)

    rows = []
    for dt in sorted(statsConsumed):
        if dt not in statsCapacity or statsCapacity[dt] == 0:
            continue
        pctFull = round(100 * statsConsumed[dt] / statsCapacity[dt], 1)
        rows.append({'date': dt, 'consumed': statsConsumed[dt], 'capacity': statsCapacity[dt], 'pct': pctFull})
    return cluster['name'], rows


results = []
for name in clusternames:
    result = collectCluster(name)
    if result is not None:
        results.append(result)

if len(results) == 0:
    print('no storage data collected')
    exit(1)

# csv output =============================================================
multi = len(results) > 1
if multi:
    fileLabel = 'all-clusters'
else:
    fileLabel = results[0][0]
csvfileName = '%s/storageReport-%s-%s.csv' % (folder, fileLabel, datestring)
csv = codecs.open(csvfileName, 'w', 'utf-8')
if multi:
    csv.write("Cluster,Date,Consumed (%s),Capacity (%s),PCT Full\n" % (units, units))
else:
    csv.write("Date,Consumed (%s),Capacity (%s),PCT Full\n" % (units, units))

for clusterName, rows in results:
    if multi:
        print('\n%s' % clusterName)
    for r in reversed(rows):
        print('%s, %s, %s, %s' % (r['date'], r['consumed'], r['capacity'], r['pct']))
        if multi:
            csv.write('%s,%s,%s,%s,%s\n' % (clusterName, r['date'], r['consumed'], r['capacity'], r['pct']))
        else:
            csv.write('%s,%s,%s,%s\n' % (r['date'], r['consumed'], r['capacity'], r['pct']))

csv.close()
print('\nOutput written to %s' % csvfileName)

# html output ============================================================
htmlTemplate = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Storage Usage - __TITLE__</title>
<style>
  :root {
    --bg: #ffffff; --panel: #f6f8fa; --text: #1f2933; --muted: #65727f; --grid: #dde3e8;
    --consumed: #1f77b4; --capacity: #d9822b; --warn: #c0392b;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #14181d; --panel: #1d232a; --text: #e6ebf0; --muted: #94a1ae; --grid: #2f3841;
      --consumed: #5aa9e6; --capacity: #f0a35e; --warn: #ef6b5b;
    }
  }
  * { box-sizing: border-box; }
  body { margin: 0; padding: 24px 16px; background: var(--bg); color: var(--text);
         font: 14px/1.4 -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
  .wrap { max-width: 1100px; margin: 0 auto; }
  h1 { font-size: 22px; margin: 0 0 4px; }
  .sub { color: var(--muted); margin-bottom: 20px; }
  .tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin-bottom: 12px; }
  .tile { background: var(--panel); border-radius: 8px; padding: 12px 14px; }
  .tile .label { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }
  .tile .value { font-size: 22px; font-weight: 600; margin-top: 2px; }
  .warn { color: var(--warn); }
  .section { margin-bottom: 32px; }
  .section h2 { font-size: 18px; margin: 0 0 10px; }
  .chartbox { background: var(--panel); border-radius: 8px; padding: 12px; position: relative; }
  .chartbox h3 { font-size: 15px; margin: 0 0 8px; font-weight: 600; }
  .legend { display: flex; gap: 16px; color: var(--muted); font-size: 13px; margin-bottom: 6px; }
  .legend span::before { content: ""; display: inline-block; width: 12px; height: 3px; margin-right: 6px; vertical-align: middle; background: var(--c); }
  .legend .cap::before { background: none; border-top: 2px dashed var(--c); height: 0; }
  svg { width: 100%; height: auto; display: block; }
  svg text { fill: var(--muted); font-size: 11px; }
  .tip { position: absolute; pointer-events: none; display: none; background: var(--bg); color: var(--text);
         border: 1px solid var(--grid); border-radius: 6px; padding: 6px 10px; font-size: 12px; white-space: nowrap;
         box-shadow: 0 2px 8px rgba(0,0,0,.18); }
  .tip b { display: block; margin-bottom: 2px; }
  table { width: 100%; border-collapse: collapse; background: var(--panel); border-radius: 8px; overflow: hidden; }
  th, td { padding: 8px 12px; text-align: right; border-bottom: 1px solid var(--grid); }
  th:first-child, td:first-child { text-align: left; }
  th { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; cursor: pointer; user-select: none; }
  tr:last-child td { border-bottom: none; }
  td a { color: var(--consumed); text-decoration: none; }
  .tablewrap { overflow-x: auto; margin-bottom: 12px; }
  .toggle { margin-bottom: 28px; padding: 7px 16px; border: 1px solid var(--grid); border-radius: 6px; background: var(--panel);
            color: var(--text); font: inherit; cursor: pointer; }
  .toggle:hover { border-color: var(--consumed); color: var(--consumed); }
  .controls { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; }
  .controls label { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }
  .controls select { padding: 7px 10px; border: 1px solid var(--grid); border-radius: 6px; background: var(--panel);
                     color: var(--text); font: inherit; min-width: 260px; max-width: 100%; }
</style>
</head>
<body>
<div class="wrap">
  <h1>Storage Usage Over Time</h1>
  <div class="sub">__SUBTITLE__ &middot; Generated __GENERATED__ &middot; Units: __UNITS__</div>
  <div id="controls"></div>
  <div id="summary"></div>
  <div id="clusters"></div>
</div>
<script>
const CLUSTERS = __DATA__;
const UNITS = "__UNITS__";
// order clusters by % full, highest first (clusters without data last)
CLUSTERS.sort((a, b) => (b.data.length ? b.data[b.data.length - 1].pct : -1) - (a.data.length ? a.data[a.data.length - 1].pct : -1));
const NS = "http://www.w3.org/2000/svg";
const fmt = n => n.toLocaleString(undefined, {maximumFractionDigits: 1});
const signed = n => (n >= 0 ? "+" : "") + fmt(n);
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
const t = d => Date.parse(d + "T00:00:00Z");

function stats(rows) {
  const first = rows[0], last = rows[rows.length - 1];
  const spanDays = Math.max(1, (t(last.date) - t(first.date)) / 86400000);
  const growth = last.consumed - first.consumed;
  const perDay = growth / spanDays;
  let daysLeft = null;
  if (perDay > 0 && last.capacity > last.consumed) daysLeft = Math.round((last.capacity - last.consumed) / perDay);
  return {last: last, growth: growth, perDay: perDay, daysLeft: daysLeft};
}

function el(name, attrs, parent) {
  const e = document.createElementNS(NS, name);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(e);
  return e;
}

function niceMax(v) {
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  const n = v / p;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * p;
}

function drawChart(svg, tip, DATA) {
  const W = 1000, H = 420, m = {l: 64, r: 20, t: 12, b: 36};
  svg.setAttribute("viewBox", "0 0 " + W + " " + H);
  const x0 = t(DATA[0].date), x1 = t(DATA[DATA.length - 1].date);
  const xs = d => m.l + (x1 === x0 ? (W - m.l - m.r) / 2 : (t(d) - x0) / (x1 - x0) * (W - m.l - m.r));
  const ymax = niceMax(Math.max.apply(null, DATA.map(d => Math.max(d.consumed, d.capacity))) * 1.02);
  const ys = v => H - m.b - v / ymax * (H - m.t - m.b);

  for (let i = 0; i <= 5; i++) {
    const v = ymax * i / 5, y = ys(v);
    el("line", {x1: m.l, x2: W - m.r, y1: y, y2: y, stroke: "var(--grid)", "stroke-width": 1}, svg);
    el("text", {x: m.l - 8, y: y + 4, "text-anchor": "end"}, svg).textContent = fmt(v);
  }
  const nx = Math.min(6, DATA.length);
  for (let i = 0; i < nx; i++) {
    const d = DATA[nx === 1 ? 0 : Math.round(i * (DATA.length - 1) / (nx - 1))];
    el("text", {x: xs(d.date), y: H - m.b + 18, "text-anchor": i === 0 ? "start" : i === nx - 1 ? "end" : "middle"}, svg).textContent = d.date;
  }
  const pts = k => DATA.map(d => xs(d.date).toFixed(1) + "," + ys(d[k]).toFixed(1));
  el("polygon", {points: xs(DATA[0].date) + "," + ys(0) + " " + pts("consumed").join(" ") + " " + xs(DATA[DATA.length - 1].date) + "," + ys(0),
                 fill: "var(--consumed)", "fill-opacity": 0.15}, svg);
  el("polyline", {points: pts("capacity").join(" "), fill: "none", stroke: "var(--capacity)", "stroke-width": 2, "stroke-dasharray": "6 4"}, svg);
  el("polyline", {points: pts("consumed").join(" "), fill: "none", stroke: "var(--consumed)", "stroke-width": 2.5, "stroke-linejoin": "round"}, svg);

  const cross = el("line", {y1: m.t, y2: H - m.b, stroke: "var(--muted)", "stroke-width": 1, visibility: "hidden"}, svg);
  const dot = el("circle", {r: 4.5, fill: "var(--consumed)", stroke: "var(--bg)", "stroke-width": 2, visibility: "hidden"}, svg);
  const hit = el("rect", {x: m.l, y: m.t, width: W - m.l - m.r, height: H - m.t - m.b, fill: "transparent"}, svg);
  hit.addEventListener("mousemove", ev => {
    const r = svg.getBoundingClientRect(), sc = W / r.width;
    const mx = (ev.clientX - r.left) * sc;
    let best = DATA[0], bd = Infinity;
    DATA.forEach(d => { const dd = Math.abs(xs(d.date) - mx); if (dd < bd) { bd = dd; best = d; } });
    const px = xs(best.date);
    cross.setAttribute("x1", px); cross.setAttribute("x2", px); cross.setAttribute("visibility", "visible");
    dot.setAttribute("cx", px); dot.setAttribute("cy", ys(best.consumed)); dot.setAttribute("visibility", "visible");
    tip.innerHTML = "<b>" + best.date + "</b>Consumed: " + fmt(best.consumed) + " " + UNITS +
                    "<br>Capacity: " + fmt(best.capacity) + " " + UNITS + "<br>Full: " + best.pct + "%";
    tip.style.display = "block";
    const box = tip.parentNode.getBoundingClientRect();
    let left = ev.clientX - box.left + 14;
    if (left + tip.offsetWidth > box.width - 8) left = ev.clientX - box.left - tip.offsetWidth - 14;
    tip.style.left = left + "px";
    tip.style.top = (ev.clientY - box.top + 14) + "px";
  });
  hit.addEventListener("mouseleave", () => {
    tip.style.display = "none"; cross.setAttribute("visibility", "hidden"); dot.setAttribute("visibility", "hidden");
  });
}

// per-cluster sections
const holder = document.getElementById("clusters");
CLUSTERS.forEach((c, idx) => {
  const sec = document.createElement("div");
  sec.className = "section";
  sec.id = "cluster-" + idx;
  if (!c.data.length) {
    sec.innerHTML = "<h2>" + esc(c.name) + "</h2><div class='sub'>No data returned.</div>";
    holder.appendChild(sec);
    return;
  }
  const s = stats(c.data);
  const tiles = [
    ["Consumed (latest)", fmt(s.last.consumed) + " " + UNITS],
    ["Capacity (latest)", fmt(s.last.capacity) + " " + UNITS],
    ["% Full", s.last.pct + "%", s.last.pct >= 80],
    ["Change over period", signed(s.growth) + " " + UNITS],
    ["Avg daily change", signed(s.perDay) + " " + UNITS]
  ];
  if (s.daysLeft !== null) tiles.push(["Est. days until full", s.daysLeft.toLocaleString()]);
  sec.innerHTML = "<h2>" + esc(c.name) + "</h2><div class='tiles'>" +
    tiles.map(x => '<div class="tile"><div class="label">' + x[0] + '</div><div class="value' + (x[2] ? ' warn' : '') + '">' + x[1] + '</div></div>').join("") +
    "</div><div class='chartbox'><div class='legend'><span style='--c:var(--consumed)'>Consumed</span><span class='cap' style='--c:var(--capacity)'>Capacity</span></div>" +
    "<svg role='img' aria-label='Storage usage over time for " + esc(c.name) + "'></svg><div class='tip'></div></div>";
  holder.appendChild(sec);
  drawChart(sec.querySelector("svg"), sec.querySelector(".tip"), c.data);
});

// cluster selector: "All clusters" (default) or filter to a single cluster chart
function showCluster(v) {
  document.querySelectorAll(".section").forEach(s => { s.style.display = (v === "all" || s.id === "cluster-" + v) ? "" : "none"; });
  const sel = document.getElementById("clusterSelect");
  if (sel) sel.value = v;
}
if (CLUSTERS.length > 1) {
  document.getElementById("controls").className = "controls";
  document.getElementById("controls").innerHTML = "<label for='clusterSelect'>Show chart</label><select id='clusterSelect'><option value='all'>All clusters (" + CLUSTERS.length + ")</option>" +
    CLUSTERS.map((c, i) => "<option value='" + i + "'>" + esc(c.name) + (c.data.length ? " (" + c.data[c.data.length - 1].pct + "% full)" : "") + "</option>").join("") + "</select>";
  document.getElementById("clusterSelect").addEventListener("change", e => showCluster(e.target.value));
}

// summary table (multiple clusters only)
if (CLUSTERS.length > 1) {
  const cols = [
    ["Cluster", r => r.name, r => r.name.toLowerCase()],
    ["Consumed (" + UNITS + ")", r => fmt(r.s.last.consumed), r => r.s.last.consumed],
    ["Capacity (" + UNITS + ")", r => fmt(r.s.last.capacity), r => r.s.last.capacity],
    ["% Full", r => '<span class="' + (r.s.last.pct >= 80 ? 'warn' : '') + '">' + r.s.last.pct + "%</span>", r => r.s.last.pct],
    ["Change (" + UNITS + ")", r => signed(r.s.growth), r => r.s.growth],
    ["Avg daily (" + UNITS + ")", r => signed(r.s.perDay), r => r.s.perDay],
    ["Est. days to full", r => r.s.daysLeft === null ? "&ndash;" : r.s.daysLeft.toLocaleString(), r => r.s.daysLeft === null ? Infinity : r.s.daysLeft]
  ];
  const rows = CLUSTERS.map((c, i) => ({name: c.name, idx: i, s: c.data.length ? stats(c.data) : null})).filter(r => r.s);
  let sortCol = 3, sortDir = -1;   // default: % Full, highest first
  const COLLAPSED_ROWS = 5;
  let expanded = false;
  const render = () => {
    rows.sort((a, b) => { const x = cols[sortCol][2](a), y = cols[sortCol][2](b); return (x < y ? -1 : x > y ? 1 : 0) * sortDir; });
    const shown = expanded ? rows : rows.slice(0, COLLAPSED_ROWS);
    const canToggle = rows.length > COLLAPSED_ROWS;
    document.getElementById("summary").innerHTML = "<div class='tablewrap'><table><thead><tr>" +
      cols.map((c, i) => "<th data-i='" + i + "'>" + esc(c[0]) + (i === sortCol ? (sortDir > 0 ? " &#9650;" : " &#9660;") : "") + "</th>").join("") +
      "</tr></thead><tbody>" +
      shown.map(r => "<tr>" + cols.map((c, i) => "<td>" + (i === 0 ? "<a href='#cluster-" + r.idx + "' data-idx='" + r.idx + "'>" + esc(c[1](r)) + "</a>" : c[1](r)) + "</td>").join("") + "</tr>").join("") +
      "</tbody></table></div>" +
      (canToggle ? "<button id='toggle' class='toggle'>" + (expanded ? "Show top " + COLLAPSED_ROWS : "Show all " + rows.length + " clusters") + "</button>" : "");
    document.querySelectorAll("#summary th").forEach(th => th.addEventListener("click", () => {
      const i = +th.dataset.i;
      if (i === sortCol) sortDir = -sortDir; else { sortCol = i; sortDir = i === 0 ? 1 : -1; }
      render();
    }));
    // clicking a cluster name filters to that cluster's chart
    document.querySelectorAll("#summary a[data-idx]").forEach(a => a.addEventListener("click", ev => {
      ev.preventDefault();
      showCluster(a.dataset.idx);
      document.getElementById("cluster-" + a.dataset.idx).scrollIntoView();
    }));
    const tg = document.getElementById("toggle");
    if (tg) tg.addEventListener("click", () => { expanded = !expanded; render(); });
  };
  render();
}
</script>
</body>
</html>
'''

if multi:
    title = '%s clusters' % len(results)
    subtitle = '%s clusters' % len(results)
else:
    title = results[0][0]
    subtitle = 'Cluster: <b>%s</b>' % html.escape(results[0][0])

chartData = [{'name': n, 'data': rows} for n, rows in results]
htmlFileName = '%s/storageReport-%s-%s.html' % (folder, fileLabel, datestring)
htmlOut = (htmlTemplate
           .replace('__TITLE__', html.escape(title))
           .replace('__SUBTITLE__', subtitle)
           .replace('__GENERATED__', now.strftime('%Y-%m-%d %H:%M'))
           .replace('__UNITS__', units)
           .replace('__DATA__', json.dumps(chartData).replace('</', '<\\/')))
with codecs.open(htmlFileName, 'w', 'utf-8') as htmlFile:
    htmlFile.write(htmlOut)
print('HTML chart written to %s' % htmlFileName)
