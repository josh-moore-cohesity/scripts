#!/usr/bin/env python
"""VM tag report: vCenter, VM name and VMware tag(s) for every VM, via Helios (auto-discovers vCenters)"""

### import pyhesity wrapper module
from pyhesity import *
from datetime import datetime
from urllib.parse import quote

### command line arguments
import argparse
import csv
import sys
import json

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

# --- report-specific args (AFTER template args) ---
parser.add_argument(
    '-s', '--vcenter',
    type=str,
    default=None,
    help='vCenter source name as registered on the cluster. '
         'If omitted (or -c omitted), vCenters are auto-discovered via the Helios reporting resources API'
)
parser.add_argument(
    '-of', '--output',
    nargs='?',
    const='',
    type=str,
    default=None,
    help='Write a CSV. No file name needed (auto-named vm_tags_<date>.csv); a name may optionally be given'
)
parser.add_argument(
    '-o', '--object',
    nargs='+',
    type=str,
    default=None,
    help='Only report on these VM(s). Each VM is found via Helios global search to identify its '
         'cluster and vCenter, then tags are read from that vCenter source'
)
parser.add_argument(
    '-ol', '--objectlist',
    type=str,
    default=None,
    help='Text file with one VM name per line (same as -o)'
)
parser.add_argument(
    '--pgs',
    action='store_true',
    help='Also look up protection groups and add a "Protection Groups" column (extra API calls)'
)
parser.add_argument(
    '-t', '--tag',
    nargs='+',
    type=str,
    default=None,
    help='Only show VMs that have one of these VMware tags (case-insensitive, exact tag name)'
)
parser.add_argument(
    '--debug',
    action='store_true',
    help='Dump raw protectionSources / protectionGroups JSON for troubleshooting'
)

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

vcenter_name = args.vcenter
vcenter_name_arg = args.vcenter  # remember whether -s was given (vcenter_name is reassigned in the loop)
output_base = args.output
include_pgs = args.pgs
tag_filter = [t.lower() for t in args.tag] if args.tag else None
debug = args.debug

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

# get list of clusters (optional - if omitted, vCenters are auto-discovered)
clusternames = gatherList(clustername, clusterlist, name='clusters', required=False)

# get list of specific VMs (optional - if given, each VM is located via Helios global search)
objectnames = gatherList(args.object, args.objectlist, name='objects', required=False)

# Legacy mode: both a cluster and a vCenter were given -> no discovery needed
discover = not (clusternames and vcenter_name)

# Object mode: VMs are located via global search, so vCenter discovery is not needed
if objectnames:
    discover = False

# Date
now = datetime.now()
dateString = now.strftime("%Y-%m-%d")

# discovery and global search go through Helios, so force Helios mode
if discover or objectnames:
    mcm = True

# authenticate
apiauth(vip=vip,
        username=username,
        domain=domain,
        password=password,
        useApiKey=useApiKey,
        helios=mcm,
        prompt=(not noprompt),
        mfaCode=mfacode,
        emailMfaCode=emailmfacode)

# exit if not authenticated
if apiconnected() is False:
    print('authentication failed')
    exit(1)

# -------------------------------------------------------------------------
# Helper functions
# -------------------------------------------------------------------------

def normalize_source_nodes(sources):
    """
    Normalize getProtectionSources response to a list of ProtectionSourceNode roots.
    """
    if not sources:
        return []

    if isinstance(sources, list):
        return sources

    if isinstance(sources, dict):
        # Adjust if your JSON has a different wrapper
        return sources.get('nodes') or sources.get('rootNodes') or []

    return []


def extract_tags_from_vmware(vmware_obj):
    """
    Extract VMware tags from vmWareProtectionSource.

    For your cluster, tags look like:
      "tagAttributes": [
        { "id": 20, "name": "SNAP", "uuid": "..." }
      ]
    """
    tags = set()
    tag_ids = set()

    if not isinstance(vmware_obj, dict):
        return [], set()

    # tagAttributes: id + name
    for t in vmware_obj.get('tagAttributes', []):
        if not isinstance(t, dict):
            continue
        name = t.get('name')  # <-- important
        tid = t.get('id')
        if name:
            tags.add(name)
        if tid is not None:
            tag_ids.add(tid)

    # (Keep the older patterns as a fallback if you like)
    for t in vmware_obj.get('tags', []):
        if not isinstance(t, dict):
            continue
        name = t.get('name') or t.get('tagName') or t.get('value')
        category = t.get('categoryName') or t.get('category')
        if category and name:
            tags.add(f"{category}:{name}")
        elif name:
            tags.add(name)

    for t in vmware_obj.get('tagAttributes', []):
        # If they ever add attributeValue/value/etc in the future
        for key in ('attributeValue', 'value', 'tagValue'):
            if key in t and t[key]:
                tags.add(t[key])

    return sorted(tags), tag_ids

def walk_vmware_tree(node, nodes_by_id, children_by_id, vm_info):
    """
    Recursively walk a ProtectionSourceNode tree, building:
      - nodes_by_id: sourceId -> node
      - children_by_id: sourceId -> [childSourceId, ...]
      - vm_info: vmId -> { name, tags }
    """
    if not isinstance(node, dict):
        return

    ps = node.get('protectionSource') or {}
    node_id = ps.get('id')
    env = ps.get('environment')
    vmware_obj = ps.get('vmWareProtectionSource') or ps.get('vmwareProtectionSource') or {}

    if node_id is None:
        # Some wrappers (like the vCenter "root") might not have id; skip in maps
        pass
    else:
        nodes_by_id[node_id] = node
        children_by_id.setdefault(node_id, [])

        # Capture VMs
        vm_type = vmware_obj.get('type')
        if env == 'kVMware' and vm_type == 'kVirtualMachine':
            vm_name = ps.get('name')
            if vm_name:
                
                tags = []
                tag_ids = set()
                
                for t in vmware_obj.get('tagAttributes', []):
                    if not isinstance(t, dict):
                        continue
                    if t.get('name'):
                        tags.append(t['name'])
                    if t.get('id') is not None:
                        tag_ids.add(t['id'])
    
                #tags, tag_ids = extract_tags_from_vmware(vmware_obj)
                vm_info[node_id] = {
                    'name': vm_name,
                    'tags': sorted(set(tags)),
                    'tagIds': tag_ids
                }

    # Recurse into children
    for child in node.get('nodes', []):
        if not isinstance(child, dict):
            continue
        child_ps = child.get('protectionSource') or {}
        child_id = child_ps.get('id')
        if node_id is not None and child_id is not None:
            children_by_id[node_id].append(child_id)
        walk_vmware_tree(child, nodes_by_id, children_by_id, vm_info)


def find_vcenter_root(nodes, vcenter_name):
    """
    Locate the vCenter root node whose protectionSource.name matches vcenter_name.
    """
    for n in nodes:
        if not isinstance(n, dict):
            continue
        ps = n.get('protectionSource') or {}
        name = ps.get('name', '')
        if name.lower() == vcenter_name.lower():
            return n

        # search recursively
        child = find_vcenter_root(n.get('nodes', []), vcenter_name)
        if child is not None:
            return child

    return None


def normalize_protection_groups(pgs):
    """
    Normalize getProtectionGroups response to a list.
    """
    if not pgs:
        return []

    if isinstance(pgs, list):
        return pgs

    if isinstance(pgs, dict):
        return pgs.get('protectionGroups') or pgs.get('jobs') or []

    return []


def extract_object_ids_from_pg(pg):
    """
    Extract *protection source IDs* referenced by a VMware PG.

    These are NOT necessarily VMs; they can be folders, tags, clusters, etc.
    We will later expand them to all descendant VMs using the tree.

    Common patterns (may vary):
      - pg["vmwareParams"]["objects"][i]["id"]
      - pg["vmWareParams"]["objects"][i]["sourceId"]
      - pg["vmProtectionSourceParams"]["objects"][i]["protectionSourceId"]
    """
    object_ids = set()

    if not isinstance(pg, dict):
        return object_ids

    env = pg.get('environment')
    if env != 'kVMware':
        return object_ids

    params = (
        pg.get('vmwareParams') or
        pg.get('vmWareParams') or
        pg.get('vmProtectionSourceParams') or
        pg.get('sourceParams') or
        {}
    )
    objects = params.get('objects', []) or params.get('sources', [])

    for obj in objects:
        if not isinstance(obj, dict):
            continue
        oid = (
            obj.get('id') or
            obj.get('sourceId') or
            obj.get('protectionSourceId') or
            obj.get('entityId')
        )
        if oid is not None:
            object_ids.add(oid)

    return object_ids


def get_descendant_vms(root_source_id, children_by_id, vm_info, cache):
    """
    Given a protectionSource ID, return set of VM IDs that are that node or its descendants.

    This handles BOTH:
      - explicit VM selection (object is a VM node)
      - ancestor selection (folder/cluster/tag/container node)
    """
    if root_source_id in cache:
        return cache[root_source_id]

    result = set()
    # If this node itself is a VM, include it
    if root_source_id in vm_info:
        result.add(root_source_id)

    for child_id in children_by_id.get(root_source_id, []):
        result.update(get_descendant_vms(child_id, children_by_id, vm_info, cache))

    cache[root_source_id] = result
    return result


def build_vm_to_pg_map(pg_list, children_by_id, vm_info, tag_id_to_vms, tag_name_to_vms):
    """
    Build map: vmId -> [PG names], considering:
      - explicit object selections (VMs/folders/clusters/tags) + descendants
      - tag-based selections via vmTagIds (and optionally named selections)
    """
    vm_to_pgs = {}
    vm_descendant_cache = {}  # rootSourceId -> set(vmIds)

    for pg in pg_list:
        if not isinstance(pg, dict):
            continue

        # Environment filter (v1+v2-friendly)
        env = (
            pg.get('environment') or
            pg.get('environmentType') or
            pg.get('environmentTypes')
        )
        if env != 'kVMware':
            continue

        pg_name = pg.get('name', 'UNKNOWN_PG')

        # --- 1) Explicit object selections (via protection source IDs) ---
        object_ids = extract_object_ids_from_pg(pg)
        vm_ids_explicit = set()
        for oid in object_ids:
            vm_ids_explicit.update(
                get_descendant_vms(oid, children_by_id, vm_info, vm_descendant_cache)
            )

        # --- 2) Tag-based selections via vmTagIds (as seen in your PG) ---
        params = (
            pg.get('vmwareParams') or
            pg.get('vmWareParams') or
            pg.get('vmProtectionSourceParams') or
            ((pg.get('environmentParameters') or {}).get('vmwareParams')) or
            (pg.get('sourceParams') or {})
        )
        if not isinstance(params, dict):
            params = {}

        # vmTagIds is a 2D array in your cluster, e.g. [[20]]
        raw_vm_tag_ids = params.get('vmTagIds') or []
        include_tag_ids = set()

        for entry in raw_vm_tag_ids:
            if isinstance(entry, list):
                include_tag_ids.update(entry)
            else:
                include_tag_ids.add(entry)

        # excludeVmTagIds (if present)
        raw_exclude_tag_ids = params.get('excludeVmTagIds') or []
        exclude_tag_ids = set()
        for entry in raw_exclude_tag_ids:
            if isinstance(entry, list):
                exclude_tag_ids.update(entry)
            else:
                exclude_tag_ids.add(entry)

        vm_ids_tag_based = set()

        # Match by tag ID
        for tid in include_tag_ids:
            vm_ids_tag_based.update(tag_id_to_vms.get(tid, set()))

        # Optionally, you could support name-based selection too if needed:
        # include_tag_names = params.get('vmTagNames') or []
        # for tname in include_tag_names:
        #     key = str(tname).lower()
        #     vm_ids_tag_based.update(tag_name_to_vms.get(key, set()))

        # Apply excludeVmTagIds if any
        for tid in exclude_tag_ids:
            vm_ids_tag_based -= tag_id_to_vms.get(tid, set())

        # Final VM set for this PG
        vm_ids = vm_ids_explicit | vm_ids_tag_based

        for vm_id in vm_ids:
            vm_to_pgs.setdefault(vm_id, []).append(pg_name)

    # dedupe + sort
    for vm_id, jobs in vm_to_pgs.items():
        vm_to_pgs[vm_id] = sorted(set(jobs))

    return vm_to_pgs



def write_csv(output_path, records):
    """
    Write VM records to CSV.
    """
    fieldnames = ['vCenter', 'VM Name', 'VMware Tags']
    if include_pgs:
        fieldnames.append('Protection Groups')
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            row = {
                'vCenter': r['vcenter'],
                'VM Name': r['name'],
                'VMware Tags': ', '.join(r['tags'])
            }
            if include_pgs:
                row['Protection Groups'] = ', '.join(r['protection_groups']) if r['protection_groups'] else 'Unprotected'
            writer.writerow(row)


def print_table(records):
    """
    Simple console table output.
    """
    if not records:
        print("  No VMs found.")
        return

    vc_col = max([len(r['vcenter']) for r in records] + [7])
    vm_col = max([len(r['name']) for r in records] + [7])
    pg_col = max([len(', '.join(r['protection_groups'])) for r in records] + [17])
    tag_col = max([len(', '.join(r['tags'])) for r in records] + [11])

    header = f"{'vCenter'.ljust(vc_col)}  {'VM Name'.ljust(vm_col)}  {'VMware Tags'.ljust(tag_col)}"
    if include_pgs:
        header += f"  {'Protection Groups'.ljust(pg_col)}"
    print("  " + header)
    print("  " + '-' * len(header))

    for r in records:
        line = f"{r['vcenter'].ljust(vc_col)}  {r['name'].ljust(vm_col)}  {', '.join(r['tags']).ljust(tag_col)}"
        if include_pgs:
            pg_text = ', '.join(r['protection_groups']) if r['protection_groups'] else 'Unprotected'
            line += f"  {pg_text.ljust(pg_col)}"
        print("  " + line)

def build_tag_vm_maps(vm_info):
    """
    Build:
      - tag_id_to_vms: tagId -> set(vmIds)
      - tag_name_to_vms: tagNameLower -> set(vmIds)
    """
    tag_id_to_vms = {}
    tag_name_to_vms = {}

    for vm_id, info in vm_info.items():
        for tid in info.get('tagIds', []):
            tag_id_to_vms.setdefault(tid, set()).add(vm_id)
        for tname in info.get('tags', []):
            if not tname:
                continue
            key = str(tname).lower()
            tag_name_to_vms.setdefault(key, set()).add(vm_id)

    return tag_id_to_vms, tag_name_to_vms

def _first(d, *keys):
    """Return the first non-empty value in dict d for the given keys."""
    for k in keys:
        v = d.get(k)
        if v not in (None, '', []):
            return v
    return None


def _resource_items(resp):
    """Normalize a resources API response to (list of items, pagination cookie)."""
    if isinstance(resp, list):
        return resp, None
    if isinstance(resp, dict):
        for k in ('resources', 'objects', 'items', 'sources', 'data'):
            if isinstance(resp.get(k), list):
                return resp[k], _first(resp, 'paginationCookie', 'cookie', 'nextCookie')
    return [], None


def discover_vcenter_targets(wanted_vcenter=None, wanted_clusters=None):
    """
    Use the Helios reporting 'resources' API to find every registered VMware vCenter.

    A vCenter registered on several clusters is returned ONCE (first cluster seen,
    preferring the order Helios returns), so tags are only pulled one time per vCenter.
    Returns a list of (clusterName, vcenterName) tuples.
    """
    cluster_by_id = {str(c['clusterId']): c['name'] for c in heliosClusters()}
    connected = {c['name'].lower(): c['name'] for c in heliosClusters()}
    wanted_clusters = [c.lower() for c in (wanted_clusters or [])]

    items = []
    cookie = None
    while True:
        body = {'resourceType': 'RegisteredSources', 'environments': ['kVMware']}
        if cookie:
            body['paginationCookie'] = cookie
        try:
            resp = api('post', 'resources', body, reportingv2=True)
        except Exception as ex:
            print('ERROR calling heliosreporting resources API: %s' % ex)
            break
        page, cookie = _resource_items(resp)
        if debug and not items:
            try:
                print('DEBUG: resources response keys: %s' % (list(resp.keys()) if isinstance(resp, dict) else type(resp)))
                vm = [p for p in page if isinstance(p, dict) and 'kVMware' in (p.get('environments') or [])]
                print('DEBUG: first kVMware source (full):')
                print(json.dumps(vm[0] if vm else (page[0] if page else resp), indent=2)[:3000])
            except Exception:
                pass
        items += page
        if not cookie or not page:
            break

    # vcenter key (lower name) -> {'name':..., 'clusters':[...]}
    vcenters = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        # RegisteredSources items look like {"environments": ["kVMware"], "name": ..., "uuid": ...}
        envs = item.get('environments') or [item.get('environment')]
        rname = _first(item, 'name', 'resourceName', 'sourceName')
        # keep only registered VMware (vCenter) sources
        if not any('vmware' in str(e).lower() for e in envs):
            continue
        if not rname:
            continue

        # figure out which cluster(s) this registration lives on
        cnames = []
        cl_list = _first(item, 'clusters', 'registeredClusters', 'clusterInfo')
        if isinstance(cl_list, dict):
            cl_list = [cl_list]
        if isinstance(cl_list, list):
            for c in cl_list:
                if isinstance(c, dict):
                    cn = _first(c, 'name', 'clusterName') or cluster_by_id.get(str(_first(c, 'id', 'clusterId')))
                else:
                    cn = cluster_by_id.get(str(c)) or str(c)
                if cn:
                    cnames.append(cn)
        cn = _first(item, 'clusterName')
        if not cn:
            cid = str(_first(item, 'clusterId', 'clusterIdentifier') or '')
            cn = cluster_by_id.get(cid) or cluster_by_id.get(cid.split(':')[0])
        if cn:
            cnames.append(cn)

        entry = vcenters.setdefault(rname.lower(), {'name': rname, 'clusters': []})
        for cn in cnames:
            if cn not in entry['clusters']:
                entry['clusters'].append(cn)

    # The resources API does not say which cluster a source is registered on, so resolve
    # unknown vCenters by asking each cluster for its registered VMware sources.
    # Stops as soon as every vCenter has been located (each vCenter only needs one cluster).
    wanted_keys = [k for k in vcenters if not wanted_vcenter or k == wanted_vcenter.lower()]
    unresolved = set(k for k in wanted_keys if not vcenters[k]['clusters'])
    if unresolved:
        print('Locating clusters for %d vCenter(s)...' % len(unresolved))
        for cname in sorted(connected.values(), key=str.lower):
            if not unresolved:
                break
            if wanted_clusters and cname.lower() not in wanted_clusters:
                continue
            heliosCluster(cname)
            if LAST_API_ERROR() != 'OK':
                continue
            try:
                reg = api('get', 'protectionSources/registrationInfo?environments=kVMware', quiet=True)
            except Exception:
                continue
            if not isinstance(reg, dict):
                continue
            for r in reg.get('rootNodes', []) or []:
                node = r.get('rootNode') or r.get('protectionSource') or {}
                rn = str(node.get('name', '')).lower()
                if rn in vcenters:
                    if cname not in vcenters[rn]['clusters']:
                        vcenters[rn]['clusters'].append(cname)
                    unresolved.discard(rn)
        heliosCluster('-')

    targets = []
    for key in sorted(vcenters):
        entry = vcenters[key]
        if wanted_vcenter and key != wanted_vcenter.lower():
            continue
        # clusters this vCenter is registered on that we can actually reach (and the user asked for)
        usable = [c for c in entry['clusters']
                  if c.lower() in connected and (not wanted_clusters or c.lower() in wanted_clusters)]
        if not usable:
            print("vCenter '%s': no usable cluster (registered on: %s) - skipping" %
                  (entry['name'], ', '.join(entry['clusters']) or 'unknown'))
            continue
        if len(entry['clusters']) > 1:
            print("vCenter '%s' registered on %d clusters (%s) - pulling once from %s" %
                  (entry['name'], len(entry['clusters']), ', '.join(entry['clusters']), usable[0]))
        targets.append((connected[usable[0].lower()], entry['name']))
    return targets


# -------------------------------------------------------------------------
# Build work list: list of (cluster, vcenter) - one entry per unique vCenter
# -------------------------------------------------------------------------

def find_object_targets(names, wanted_vcenter=None, wanted_clusters=None):
    """
    Locate each VM via Helios global search to learn which cluster and vCenter source it lives on.

    Returns (targets, wanted) where
      targets = [(clusterName, vcenterName), ...]  one entry per unique vCenter
      wanted  = {vcenterLower: set(vmNameLower)}  VMs to keep for that vCenter
    """
    cluster_by_id = {str(c['clusterId']): c['name'] for c in heliosClusters()}
    wanted_clusters = [c.lower() for c in (wanted_clusters or [])]
    targets = []
    wanted = {}
    shown_debug = False

    for nm in names:
        print("Searching for %s..." % nm)
        search = api('get', 'data-protect/search/objects?searchString=%s&includeTenants=true' % quote(nm), v=2)
        objs = (search.get('objects') if isinstance(search, dict) else None) or []
        # exact (case-insensitive) VMware VM name matches only
        matches = [o for o in objs
                   if str(o.get('name', '')).lower() == nm.lower() and o.get('environment') == 'kVMware']
        if not matches:
            print("  %s not found as a VMware VM" % nm)
            continue

        located = False
        for obj in matches:
            if debug and not shown_debug:
                shown_debug = True
                print("  DEBUG: first matching search object:")
                print(json.dumps(obj, indent=2)[:3000])
            for opi in (obj.get('objectProtectionInfos') or []):
                cname = cluster_by_id.get(str(opi.get('clusterId')))
                vcname = opi.get('sourceName') or (obj.get('sourceInfo') or {}).get('name')
                if not cname:
                    print("  %s: cluster id %s is not connected to Helios, skipping" % (nm, opi.get('clusterId')))
                    continue
                if not vcname:
                    print("  %s: could not determine vCenter on %s (run with --debug to inspect the search result)" % (nm, cname))
                    continue
                if wanted_clusters and cname.lower() not in wanted_clusters:
                    continue
                if wanted_vcenter and vcname.lower() != wanted_vcenter.lower():
                    continue
                # the same vCenter is registered on several clusters: only query it once
                # (via the first cluster that reported it)
                key = vcname.lower()
                if key not in wanted:
                    wanted[key] = set()
                    targets.append((cname, vcname))
                if nm.lower() not in wanted[key]:
                    print("  %s -> vCenter %s (using cluster %s)" % (nm, vcname, next(c for c, v in targets if v.lower() == key)))
                wanted[key].add(nm.lower())
                located = True
        if not located:
            print("  %s: no usable cluster/vCenter found" % nm)
    return targets, wanted


object_wanted = {}
if objectnames:
    targets, object_wanted = find_object_targets(objectnames, vcenter_name, clusternames)
    if not targets:
        print('None of the specified VMs could be located')
        exit(1)
    print('Checking %d vCenter(s): %s' % (len(targets), ', '.join(v for _, v in targets)))
elif discover:
    targets = discover_vcenter_targets(vcenter_name, clusternames)
    if not targets:
        print('No VMware vCenter sources found via Helios resources API (try --debug)')
        exit(1)
    print('Found %d unique vCenter(s): %s' % (len(targets), ', '.join(v for _, v in targets)))
else:
    targets = [(c, vcenter_name) for c in clusternames]

def fetch_subtree(node_id):
    """Fetch one source and everything below it. Returns the node dict, or None on failure
    (e.g. response larger than the Helios proxy's 8MB gRPC limit)."""
    try:
        res = api('get', 'protectionSources?id=%s&environments=kVMware' % node_id, quiet=True)
    except Exception:
        return None
    nodes = normalize_source_nodes(res)
    for n in nodes:
        if isinstance(n, dict) and (n.get('protectionSource') or {}).get('id') == node_id:
            return n
    return nodes[0] if nodes and isinstance(nodes[0], dict) else None


def fetch_full(skel):
    """Fetch a node's full subtree; if too large, fetch each child separately using the
    skeleton (VMs excluded) to know the children."""
    node_id = (skel.get('protectionSource') or {}).get('id')
    full = fetch_subtree(node_id)
    if full is not None:
        return full
    children = skel.get('nodes') or []
    if not children:
        print("  WARNING: could not fetch '%s' (too large or error) - VMs under it are missing" %
              (skel.get('protectionSource') or {}).get('name'))
        return skel
    skel['nodes'] = [fetch_full(c) for c in children]
    return skel


def get_vcenter_tree(vcenter):
    """Return the protection source tree (root node) for one vCenter on the current cluster."""
    reg = api('get', 'protectionSources/registrationInfo?environments=kVMware', quiet=True)
    root_id = None
    if isinstance(reg, dict):
        for r in reg.get('rootNodes', []) or []:
            node = r.get('rootNode') or r.get('protectionSource') or {}
            if str(node.get('name', '')).lower() == vcenter.lower():
                root_id = node.get('id')
                break
    if root_id is None:
        return None

    full = fetch_subtree(root_id)
    if full is not None:
        return full

    # too large: get the skeleton (everything except VMs) and fetch it piece by piece
    print("  vCenter tree too large for one call - fetching in pieces...")
    res = api('get', 'protectionSources?id=%s&excludeTypes=kVirtualMachine' % root_id, quiet=True)
    skeleton = normalize_source_nodes(res)
    if not skeleton:
        print("  WARNING: could not fetch vCenter skeleton")
        return None
    return fetch_full(skeleton[0])


# -------------------------------------------------------------------------
# Main per-vCenter loop
# -------------------------------------------------------------------------

all_records = []

for thiscluster, vcenter_name in targets:
    heliosCluster(thiscluster)
    print('%s (vCenter: %s)' % (thiscluster, vcenter_name))
    if LAST_API_ERROR() != 'OK':
        print(f"  Skipping cluster {thiscluster} due to connection error")
        continue

    # 1) Get VMware protection sources tree
    #    Only this vCenter's subtree is requested (the cluster-wide call can exceed the
    #    8MB Helios proxy message limit), splitting further if the subtree is still too big.
    try:
        vcenter_root = get_vcenter_tree(vcenter_name)
    except Exception as ex:
        print(f"  ERROR calling getProtectionSources on {thiscluster}: {ex}")
        continue

    if debug:
        print("  DEBUG: vCenter tree (truncated to first 1K chars):")
        try:
            print("  " + json.dumps(vcenter_root, indent=2)[:1000])
        except Exception:
            print("  (could not serialize sources JSON)")

    if not vcenter_root:
        print(f"  vCenter '{vcenter_name}' not found under VMware protection sources on {thiscluster}")
        continue

    # Build maps from the subtree under this vCenter
    nodes_by_id = {}
    children_by_id = {}
    vm_info = {}

    walk_vmware_tree(vcenter_root, nodes_by_id, children_by_id, vm_info)
    if debug:
        # Find ecs-monitor in the vm_info map
        for vm_id, info in vm_info.items():
            if info['name'] == 'ecs-monitor':
                print("  DEBUG: ecs-monitor VM:")
                print(f"    vm_id: {vm_id}")
                # Also print the underlying protectionSource node if available
                node = nodes_by_id.get(vm_id)
                try:
                    print(json.dumps(node, indent=2))
                except Exception:
                    print("    (could not serialize ecs-monitor node JSON)")
                break

    if not vm_info:
        print(f"  No VMs found under vCenter '{vcenter_name}' on {thiscluster}")
        continue
    
    
    # NEW: build tag → VM maps
    tag_id_to_vms, tag_name_to_vms = build_tag_vm_maps(vm_info)

    
    # 2) Get protection groups (v2 DP API)
    #    API: GET /v2/data-protect/protection-groups
    try:
        pgs = api('get', 'data-protect/protection-groups', v=2) if include_pgs else []
    except Exception as ex:
        print(f"  ERROR calling v2/data-protect/protection-groups on {thiscluster}: {ex}")
        pgs = []

    if debug:
        print("  DEBUG: protectionGroups response (truncated to first 1K chars):")
        try:
            pg_json = json.dumps(pgs, indent=2)
            print("  " + pg_json[:1000])
        except Exception:
            print("  (could not serialize protectionGroups JSON)")

    pg_list = normalize_protection_groups(pgs)
    # TEMP: debug specific PG
    if debug:
    # Find vm-pg00-fscvc01 in the list and dump its full v2 details
        for pg in pg_list:
            if pg.get('name') == 'VM-PG00-fscvc01':
                print("  DEBUG: VM-PG00-fscvc01 (summary from list):")
                try:
                    print(json.dumps(pg, indent=2))
                except Exception:
                    print("  (could not serialize summary JSON)")

                pg_id = pg.get('id')
                if pg_id:
                    print("  DEBUG: VM-PG00-fscvc01 full details:")
                    try:
                        pg_detail = api('get', f'data-protect/protection-groups/{pg_id}', v=2)
                        print(json.dumps(pg_detail, indent=2))
                    except Exception as ex:
                        print(f"  ERROR retrieving details for {pg_id}: {ex}")
                break

    vm_to_pgs = build_vm_to_pg_map(pg_list, children_by_id, vm_info,tag_id_to_vms, tag_name_to_vms)
    
    # Final records
    records = []
    for vm_id, info in vm_info.items():
        records.append({
            'vcenter': vcenter_name,
            'id': vm_id,
            'name': info['name'],
            'tags': info['tags'],
            'protection_groups': vm_to_pgs.get(vm_id, [])
        })

    # Optional object filter: keep only the VMs that were requested with -o / -ol
    if objectnames:
        want = object_wanted.get(vcenter_name.lower(), set())
        records = [r for r in records if r['name'].lower() in want]
        found_names = set(r['name'].lower() for r in records)
        for nm in sorted(want - found_names):
            print(f"  WARNING: {nm} not found in the vCenter tree for '{vcenter_name}'")
        if not records:
            continue

    # Optional tag filter (applied after PG mapping so PG membership is still computed from all VMs)
    if tag_filter:
        records = [r for r in records if any(t.lower() in tag_filter for t in r['tags'])]
        if not records:
            print(f"  No VMs with tag(s) {', '.join(args.tag)} on vCenter '{vcenter_name}'")
            continue

    # Collect for the single combined CSV written after the loop
    all_records.extend(sorted(records, key=lambda r: r['name'].lower()))
    print(f"  {len(records)} VM(s) collected")

# -------------------------------------------------------------------------
# Output: one CSV covering every vCenter (vCenter, VM Name, VMware Tags)
# -------------------------------------------------------------------------
if not all_records:
    print('No VMs to report')
    exit(0)

if vcenter_name_arg or objectnames:
    # -s or -o/-ol given: show on screen; only write a CSV if -of was also given
    print()
    print_table(all_records)
    if output_base is None:
        exit(0)

if output_base:
    output_path = output_base
else:
    # auto name; include the vCenter name when a single vCenter was requested with -s
    label = f"_{vcenter_name_arg}" if vcenter_name_arg else ('_objects' if objectnames else '')
    output_path = f"vm_tags{label}_{dateString}.csv"
if not output_path.lower().endswith('.csv'):
    output_path += '.csv'
write_csv(output_path, all_records)
print(f"Wrote {len(all_records)} VM(s) from {len(set(r['vcenter'] for r in all_records))} vCenter(s) to {output_path}")