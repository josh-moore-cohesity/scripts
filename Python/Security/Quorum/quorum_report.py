#!/usr/bin/env python
"""Cohesity Quorum Group report

Modes:
  (default / -a)   Audit quorum groups against all Helios-connected clusters and
                   list which clusters are MISSING from which groups.
                   Limit to one group with -g <groupname>.
  -c <cluster>    List every quorum group a specific cluster is a member of.

Output: onscreen plus a timestamped file in -outputpath (-outtype csv|html, default csv).
The file mirrors the onscreen layout: per quorum group, the included clusters followed by
the missing clusters (csv 'membership' column; html one section per group).
Use -nofile for screen only, or -q to silence the screen.
Exit code is 1 on a scheduled audit when any cluster is missing from a group
(handy for alerting), 0 otherwise.

NOTE: uses GET /v2/mcm/quorum/groups?fetchConflictDetails=true. The response shape is
not publicly documented, so field parsing is defensive. Use -dump to print the raw
response if it needs adjusting, and -endpoint to override the API path.
"""

### import pyhesity wrapper module
from pyhesity import *
from datetime import datetime
import argparse
import csv
import html
import json
import os
import sys

### command line arguments
parser = argparse.ArgumentParser()
parser.add_argument('-v', '--vip', type=str, default='helios.cohesity.com')
parser.add_argument('-u', '--username', type=str, default='helios')
parser.add_argument('-d', '--domain', type=str, default='local')
parser.add_argument('-i', '--useApiKey', action='store_true')
parser.add_argument('-pwd', '--password', type=str, default=None)
parser.add_argument('-np', '--noprompt', action='store_true')
parser.add_argument('-m', '--mfacode', type=str, default=None)
parser.add_argument('-e', '--emailmfacode', action='store_true')
parser.add_argument('-a', '--audit', action='store_true', help='audit groups vs all clusters (default)')
parser.add_argument('-g', '--groupname', type=str, default=None, help='limit audit to one quorum group')
parser.add_argument('-c', '--clustername', type=str, default=None, help='show quorum groups this cluster is in')
parser.add_argument('-outtype', '--outtype', type=str, choices=['csv', 'html'], default='csv', help='output file type (default csv)')
parser.add_argument('-nofile', '--nofile', action='store_true', help='onscreen only, do not write an output file')
parser.add_argument('-outputpath', '--outputpath', type=str, default='./Results')
parser.add_argument('-q', '--quiet', action='store_true', help='no onscreen output')
parser.add_argument('-endpoint', '--endpoint', type=str, default=None, help='override quorum group API path')
parser.add_argument('-dump', '--dump', action='store_true', help='print raw quorum group API response and exit')
args = parser.parse_args()

now = datetime.now()
stamp = now.strftime('%Y-%m-%d_%H%M')
lines = []


def out(text=''):
    lines.append(text)
    if not args.quiet:
        print(text)


# authenticate ==============================================================
apiauth(vip=args.vip, username=args.username, domain=args.domain, password=args.password,
        useApiKey=args.useApiKey, helios=True, prompt=(not args.noprompt),
        mfaCode=args.mfacode, emailMfaCode=args.emailmfacode)

if apiconnected() is False:
    print('authentication failed')
    sys.exit(2)

# clusters ==================================================================
info = api('get', 'cluster-mgmt/info', mcmv2=True)
allclusters = [c for c in info['cohesityClusters'] if c.get('isConnectedToHelios') is True]
by_id = {}
by_name = {}
for c in allclusters:
    cid = str(c.get('clusterId'))
    by_id[cid] = c['clusterName']
    by_name[c['clusterName'].lower()] = c['clusterName']
all_names = sorted(by_id.values(), key=str.lower)

# quorum groups =============================================================
candidates = [(args.endpoint, {})] if args.endpoint else [
    ('quorum/groups?fetchConflictDetails=true', {'mcmv2': True}),
]
raw = None
for path, kw in candidates:
    try:
        raw = api('get', path, quiet=True, **kw)
    except Exception:
        raw = None
    if raw:
        break
if not raw:
    print('unable to retrieve quorum groups (try -endpoint and -dump)')
    sys.exit(2)

if args.dump:
    print(json.dumps(raw, indent=2))
    sys.exit(0)

if isinstance(raw, dict):
    groups_raw = None
    for k in ('quorumGroups', 'groups', 'items', 'quorumGroupList'):
        if isinstance(raw.get(k), list):
            groups_raw = raw[k]
            break
    if groups_raw is None:
        groups_raw = [v for v in raw.values() if isinstance(v, list) and v and isinstance(v[0], dict)]
        groups_raw = groups_raw[0] if groups_raw else []
else:
    groups_raw = raw


def member_to_name(m):
    """Resolve a member entry (dict / id / name) to a known cluster name."""
    if isinstance(m, dict):
        for k in ('clusterName', 'name'):
            if m.get(k) and str(m[k]).lower() in by_name:
                return by_name[str(m[k]).lower()]
        for k in ('clusterId', 'id', 'clusterIncarnationId'):
            if m.get(k) is not None and str(m[k]) in by_id:
                return by_id[str(m[k])]
        return m.get('clusterName') or m.get('name') or str(m.get('clusterId', m.get('id', 'unknown')))
    if str(m) in by_id:
        return by_id[str(m)]
    first = str(m).split(':')[0]  # "clusterId:incarnationId" style identifiers
    if first in by_id:
        return by_id[first]
    return by_name.get(str(m).lower(), str(m))


groups = []
for g in groups_raw:
    members = []
    for k in ('clusters', 'clusterIdentifiers', 'clusterMembers', 'clusterIds', 'members', 'entities'):
        if isinstance(g.get(k), list) and g[k]:
            members = g[k]
            break
    groups.append({
        'name': (g.get('name') or g.get('groupName') or str(g.get('id', 'unknown'))).strip(),
        'id': g.get('id'),
        'clusters': sorted({member_to_name(m) for m in members}, key=str.lower)
    })
groups.sort(key=lambda x: x['name'].lower())

# Helios-level groups (e.g. "Accounts | Helios Local") have no clusterIdentifiers because
# they are not cluster-scoped; auditing them against clusters would be meaningless.
helios_level = [g for g in groups if not g['clusters']]
groups = [g for g in groups if g['clusters']]

# report ====================================================================
rows = []
sections = []  # one per group (audit) or one for the cluster; mirrors the onscreen layout in the html file
exit_code = 0

if args.clustername:
    target = by_name.get(args.clustername.lower(), args.clustername)
    out('Quorum groups containing cluster "%s"  (%s)' % (target, now.strftime('%m/%d/%Y %I:%M %p')))
    out('-' * 70)
    hits = [g for g in groups if target in g['clusters']]
    for g in hits:
        out('  %s  (%d clusters)' % (g['name'], len(g['clusters'])))
        rows.append({'cluster': target, 'quorumGroup': g['name'], 'groupClusterCount': len(g['clusters']),
                     'membership': 'member'})
    if not hits:
        out('  (cluster is not in any quorum group)')
    out('')
    not_member = [g for g in groups if g not in hits]
    out('Not a member of:' if not_member else 'Not a member of: (none)')
    for g in not_member:
        out('  - %s' % g['name'])
        rows.append({'cluster': target, 'quorumGroup': g['name'], 'groupClusterCount': len(g['clusters']),
                     'membership': 'not-member'})
    sections.append({
        'title': target, 'status': '',
        'lists': [('Member of', 'ok', ['%s  (%d clusters)' % (g['name'], len(g['clusters'])) for g in hits]),
                  ('Not a member of', 'bad', [g['name'] for g in not_member])]})
else:
    sel = groups
    if args.groupname:
        sel = [g for g in groups if g['name'].lower() == args.groupname.lower()]
        if not sel and any(g['name'].lower() == args.groupname.lower() for g in helios_level):
            print('"%s" is a Helios-level group with no cluster scope; nothing to audit.' % args.groupname)
            sys.exit(0)
        if not sel:
            print('quorum group "%s" not found. Available: %s' % (args.groupname, ', '.join(g['name'] for g in groups)))
            sys.exit(2)
    out('Quorum group audit - %d group(s) vs %d Helios-connected cluster(s)  (%s)' %
        (len(sel), len(all_names), now.strftime('%m/%d/%Y %I:%M %p')))
    out('=' * 70)
    for g in sel:
        missing = [n for n in all_names if n not in g['clusters']]
        extra = [n for n in g['clusters'] if n not in all_names]
        status = 'OK' if not missing else 'MISSING %d' % len(missing)
        out('%s  [%s]  members: %d' % (g['name'], status, len(g['clusters'])))
        out('  Included clusters:')
        gfields = {'quorumGroup': g['name'], 'groupStatus': status,
                   'groupMemberCount': len(g['clusters']), 'missingCount': len(missing)}
        for n in g['clusters']:
            out('    + %s' % n)
            rows.append(dict(gfields, cluster=n,
                             membership='included-not-in-helios-list' if n in extra else 'included'))
        if missing:
            out('  Missing clusters:')
        for n in missing:
            out('    - missing: %s' % n)
            rows.append(dict(gfields, cluster=n, membership='missing'))
        for n in extra:
            out('    ? member not in Helios-connected cluster list (cluster id): %s' % n)
        if not g['clusters'] and not missing:
            rows.append(dict(gfields, cluster='', membership=''))
        sections.append({
            'title': g['name'], 'status': status,
            'lists': [('Included clusters (%d)' % len(g['clusters']), 'ok',
                       [n + ('  (not in Helios-connected cluster list)' if n in extra else '') for n in g['clusters']]),
                      ('Missing clusters (%d)' % len(missing), 'bad', missing)]})
        if missing:
            exit_code = 1
    out('')
    out('Summary: %d of %d group(s) have missing clusters' %
        (sum(1 for g in sel if any(n not in g['clusters'] for n in all_names)), len(sel)))
    if helios_level and not args.groupname:
        out('Skipped %d Helios-level group(s) with no cluster scope.' % len(helios_level))

# file output ===============================================================
if not args.nofile:
    os.makedirs(args.outputpath, exist_ok=True)
    base = 'quorum-%s-%s' % ('cluster' if args.clustername else 'audit', stamp)
    path = os.path.join(args.outputpath, base + '.' + args.outtype)
    if args.clustername:
        fields = ['cluster', 'quorumGroup', 'groupClusterCount', 'membership']
    else:
        # rows are already grouped per quorum group: included clusters, then missing clusters
        fields = ['quorumGroup', 'groupStatus', 'groupMemberCount', 'missingCount', 'cluster', 'membership']
    if args.outtype == 'csv':
        with open(path, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
    else:
        title = lines[0] if lines else 'Quorum report'
        summary = [l for l in lines if l.startswith(('Summary', 'Skipped'))]
        cards = []
        for s in sections:
            cols = []
            for label, cls, items in s['lists']:
                li = ''.join('<li>%s</li>' % html.escape(i) for i in items) or '<li class="none">(none)</li>'
                cols.append('<div class="col"><h4 class="%s">%s</h4><ul>%s</ul></div>' % (cls, html.escape(label), li))
            badge = ''
            if s['status']:
                badge = ' <span class="badge %s">%s</span>' % ('ok' if s['status'] == 'OK' else 'bad',
                                                               html.escape(s['status']))
            cards.append('<div class="card"><h3>%s%s</h3><div class="cols">%s</div></div>' % (
                html.escape(s['title']), badge, ''.join(cols)))
        with open(path, 'w', encoding='utf-8') as f:
            f.write('<!DOCTYPE html><html><head><meta charset="utf-8"><title>Quorum Report</title>'
                    '<style>body{font-family:Segoe UI,Arial,sans-serif;margin:24px}'
                    '.card{border:1px solid #ccc;border-radius:6px;padding:12px 18px;margin-bottom:16px}'
                    '.card h3{margin:0 0 8px}.cols{display:flex;gap:48px;flex-wrap:wrap}'
                    '.col h4{margin:4px 0}.col ul{margin:0;padding-left:20px}'
                    '.ok{color:#1a7f37}.bad{color:#c62828}li.none{list-style:none;color:#777}'
                    '.badge{font-size:12px;border:1px solid currentColor;border-radius:10px;padding:1px 8px;'
                    'vertical-align:middle}</style></head><body>'
                    '<h2>%s</h2>%s%s</body></html>' % (
                        html.escape(title), ''.join(cards),
                        ''.join('<p>%s</p>' % html.escape(s) for s in summary)))
    print('output written to %s' % path)

sys.exit(exit_code)
