# Register a Remote Cluster Replication Partnership

Warning: this code is provided on a best effort basis and is not in any way officially supported or sanctioned by Cohesity. The code is intentionally kept simple to retain value as example code. The code in this repository is provided as-is and the author accepts no liability for damages resulting from its use.

`register_remote_cluster.py` pairs two Cohesity clusters for replication by registering each one as a remote-cluster partner of the other. It connects once through Helios/MCM and routes the cluster-specific API calls to each side using `heliosCluster()`, so both clusters must already be connected to the same Helios/MCM tenant.

This is a Python port of `register_remote_cluster.ps1`, built on the [pyhesity](https://raw.githubusercontent.com/cohesity/community-automation-samples/main/python/pyhesity/pyhesity.py) REST API wrapper instead of `cohesity-api.ps1`, adapted to authenticate via Helios rather than connecting to each cluster's vip directly.

## Requirements

* Python 3
* [`requests`](https://pypi.org/project/requests/) (`pip install requests`)
* `pyhesity.py` in the same directory as `register_remote_cluster.py`
* Both clusters connected to the same Helios/MCM instance
* Admin credentials on each cluster (used to establish the replication trust itself - see [Cluster Admin Credentials](#cluster-admin-credentials))

## Components

* `register_remote_cluster.py` - the main script
* `pyhesity.py` - the Cohesity REST API helper module

## How It Works

1. Authenticates once to Helios/MCM.
2. Switches to the local cluster (`heliosCluster`) and collects its cluster info, node IP, and storage domain.
3. Switches to the remote cluster and collects the same info.
4. Builds the two `remoteClusters` registration payloads (one for each direction).
5. Posts the remote-cluster-as-partner payload while routed to the remote cluster, then switches back and posts the local-cluster-as-partner payload while routed to the local cluster.

## Examples

Basic pairing using the default storage domain on both sides:

```
python register_remote_cluster.py -lc ClusterA -lu admin -rc ClusterB -ru admin
```

Specify a non-default storage domain on each side:

```
python register_remote_cluster.py -lc ClusterA -lu admin -lsd Domain1 -rc ClusterB -ru admin -rsd Domain2
```

Authenticate to Helios with an API key and enable remote access (not just replication):

```
python register_remote_cluster.py -i -lc ClusterA -lu admin -rc ClusterB -ru admin -ra
```

Supply all passwords up front (non-interactive):

```
python register_remote_cluster.py -i -pwd <heliosApiKey> -lc ClusterA -lu admin -lp <localPwd> -rc ClusterB -ru admin -rp <remotePwd>
```

## Helios Authentication Parameters

| Flag | Description |
|---|---|
| `-v, --vip` | (optional) Helios/MCM/cluster address (defaults to `helios.cohesity.com`) |
| `-u, --username` | (optional) name of user to connect with (defaults to `helios`) |
| `-d, --domain` | (optional) your AD domain (defaults to `local`) |
| `-i, --useApiKey` | (optional) use an API key for authentication |
| `-pwd, --password` | (optional) will use cached password/key or will be prompted |
| `-np, --noprompt` | (optional) do not prompt for password |
| `-mcm, --mcm` | (optional) connect through MCM |
| `-m, --mfacode` | (optional) TOTP MFA code |
| `-e, --emailmfacode` | (optional) send MFA code via email |

## Local Cluster Parameters

| Flag | Description |
|---|---|
| `-lc, --localcluster` | (required) local cluster name, as registered in Helios |
| `-lu, --localusername` | (required) local cluster admin username |
| `-ld, --localdomain` | (optional) local cluster admin user domain (defaults to `local`) |
| `-lp, --localpassword` | (optional) local cluster admin password; prompted if omitted |
| `-lsd, --localstoragedomain` | (optional) local storage domain name (defaults to `DefaultStorageDomain`) |

## Remote Cluster Parameters

| Flag | Description |
|---|---|
| `-rc, --remotecluster` | (required) remote cluster name, as registered in Helios |
| `-ru, --remoteusername` | (required) remote cluster admin username |
| `-rd, --remotedomain` | (optional) remote cluster admin user domain (defaults to `local`) |
| `-rp, --remotepassword` | (optional) remote cluster admin password; prompted if omitted |
| `-rsd, --remotestoragedomain` | (optional) remote storage domain name (defaults to `DefaultStorageDomain`) |

## Other Parameters

| Flag | Description |
|---|---|
| `-ra, --remoteaccess` | (optional) also enable remote access (not just replication) between the two clusters |

## Cluster Admin Credentials

`-lu`/`-lp` and `-ru`/`-rp` are the credentials each cluster uses to authenticate to the other when establishing the replication trust - they are unrelated to the Helios login used to reach the clusters (`-u`/`-pwd`), and are not read from pyhesity's stored password cache. If `-lp`/`-rp` are omitted, the script prompts for them interactively.

## Storage Domain Fallback

If the storage domain named by `-lsd`/`-rsd` (default `DefaultStorageDomain`) doesn't exist on a cluster, the script looks up that cluster's actual storage domains:

* If the cluster has exactly one storage domain, it's used automatically (a notice is printed).
* If the cluster has multiple storage domains and none match, the script prints the available names and exits so you can rerun with the correct `-lsd`/`-rsd` value.
