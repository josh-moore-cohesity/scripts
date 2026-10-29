# Match Helios SSO User Cluster Access Using Python

Warning: this code is provided on a best effort basis and is not in any way officially supported or sanctioned by Cohesity. The code is intentionally kept simple to retain value as example code. The code in this repository is provided as-is and the author accepts no liability for damages resulting from its use.

`user_match_permissions.py` copies the cluster access of one Helios SSO user (the match user) to one or more other Helios SSO users. It reads the cluster access list of the match user from Helios, then updates each target user so their cluster access is exactly the same. A `-preview` option shows what would change without changing anything.

The script uses the Helios `cluster-mgmt/info` and `idps/principals` APIs, the same ones used by [update_helios_sso_user.py](../Update%20Helios%20Users/update_helios_sso_user.py).

## Requirements

* Python 3
* [`requests`](https://pypi.org/project/requests/) (`pip install requests`)
* [`pyhesity.py`](https://github.com/bseltz-cohesity/scripts/tree/master/python/pyhesity) in the same directory as `user_match_permissions.py`

## Components

* `user_match_permissions.py` - the main script
* `pyhesity.py` - the Cohesity REST API helper module

## Usage

### Match one or more users to another user

```
python user_match_permissions.py -matchuser boss@domain.com -touser user1@domain.com user2@domain.com
```

### Match users listed in a text file (one user per line)

```
python user_match_permissions.py -matchuser boss@domain.com -touserlist users.txt
```

### Preview the changes without making them

```
python user_match_permissions.py -matchuser boss@domain.com -touserlist users.txt -preview
```

### What the output looks like

The match user's clusters are listed first, then each target user is reported as updated, already matching, skipped or not found:

```
boss@domain.com has access to: cluster1, cluster2

Updating user1@domain.com
    adding: cluster2
Updating user2@domain.com
    removing: cluster3
user3@domain.com already matches
```

With `-preview`, `Updating` becomes `Would update` and nothing is changed.

## Parameters

### Authentication

| Flag | Description |
| --- | --- |
| -v, --vip | DNS or IP of the Cohesity endpoint (optional, default is helios.cohesity.com) |
| -u, --username | Username (optional, default is helios) |
| -d, --domain | Domain of the user (optional, default is local) |
| -i, --useApiKey | Use an API key for authentication |
| -pwd, --password | Password or API key (optional, will prompt if omitted) |
| -np, --noprompt | Do not prompt for a password |
| -m, --mfacode | MFA code for authentication |
| -e, --emailmfacode | Send an MFA code via email |

### Matching

| Flag | Description |
| --- | --- |
| -matchuser, --matchuser | Helios SSO user whose cluster access will be copied (required) |
| -touser, --touser | One or more Helios SSO users to update (required unless -touserlist is used) |
| -touserlist, --touserlist | Text file of Helios SSO users to update, one per line (required unless -touser is used) |
| -preview, --preview | Show what would change without updating any users (optional) |

## Notes

* **Exact match.** Each target user's cluster access is set to be identical to the match user's. Clusters the target user has that the match user does not have are removed, so this can reduce a user's access.
* **All cluster access.** If the match user has access to all clusters (including clusters added later), the target users are given all cluster access. A target user with all cluster access who is matched to a user with specific clusters loses the all cluster access and gets only those clusters.
* Only the cluster access list is changed. Other settings on the target user are left as they are.
* If the match user also appears in the target list, they are skipped. Users that are not found are listed at the end of the output.
* User names are matched without regard to case.
* Run with `-preview` first to check the changes before applying them.

## Download

```
curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Python/User%20Management/Match%20Permissions/user_match_permissions.py
```
