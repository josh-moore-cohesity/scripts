README.md content:

# protectVMs.py

A Python script to create and manage VMware VM protection groups on Cohesity clusters via the Cohesity REST API.

---

## Requirements

- Python 3.x
- [pyhesity](https://github.com/cohesity/community-automation-samples/blob/main/python/pyhesity.md) wrapper module

---

## Usage

```bash
python protectVMs.py -v <cluster> -u <username> -j <jobname> [options]
```

---

## Arguments

### Connection

| Argument | Short | Default | Description |
|---|---|---|---|
| `--vip` | `-v` | `helios.cohesity.com` | Cohesity cluster hostname or IP |
| `--username` | `-u` | `helios` | Username for authentication |
| `--domain` | `-d` | `local` | User domain |
| `--clustername` | `-c` | — | Cluster name (required when connecting via Helios/MCM) |
| `--mcm` | `-mcm` | — | Connect via MCM |
| `--useApiKey` | `-i` | — | Use API key for authentication |
| `--password` | `-pwd` | — | Password (prompted if not supplied) |
| `--noprompt` | `-np` | — | Suppress password prompt |
| `--mfacode` | `-m` | — | MFA code |
| `--emailmfacode` | `-e` | — | Email MFA code instead |

### Job Settings

| Argument | Short | Default | Description |
|---|---|---|---|
| `--jobname` | `-j` | *(required)* | Protection group name |
| `--vcentername` | `-vc` | — | vCenter name (required for new jobs) |
| `--policyname` | `-p` | — | Protection policy name (required for new jobs) |
| `--storagedomain` | `-sd` | `DefaultStorageDomain` | Storage domain name |
| `--timezone` | `-tz` | `US/Eastern` | Timezone for job schedule |
| `--starttime` | `-st` | `21:00` | Start time in `HH:MM` format |
| `--incrementalsla` | `-is` | `60` | Incremental backup SLA (minutes) |
| `--fullsla` | `-fs` | `120` | Full backup SLA (minutes) |
| `--pause` | `-z` | — | Create job in paused state |
| `--emailalerts` | `-ea` | — | Email address(es) for alerts (repeatable) |

### VM Selection

| Argument | Short | Description |
|---|---|---|
| `--vmname` | `-n` | VM name to protect (repeatable) |
| `--vmlist` | `-l` | Path to text file with VM names (one per line) |

### Indexing

| Argument | Short | Description |
|---|---|---|
| `--enableindexing` | `-ei` | Enable indexing |
| `--disableindexing` | `-di` | Disable indexing |
| `--usedefaults` | `-ud` | Reset include/exclude paths to built-in defaults |
| `--includepath` | `-ip` | **Replace** all include paths (repeatable) |
| `--excludepath` | `-ep` | **Replace** all exclude paths (repeatable) |
| `--addincludepath` | `-aip` | Add a path to existing include paths (repeatable) |
| `--addexcludepath` | `-aep` | Add a path to existing exclude paths (repeatable) |
| `--removeincludepath` | `-rip` | Remove a path from include paths (repeatable) |
| `--removeexcludepath` | `-rep` | Remove a path from exclude paths (repeatable) |

---

## Default Indexing Paths

When creating a new job or using `--usedefaults`, the following paths are applied:

**Include Paths:**
/

**Exclude Paths:**
/$Recycle.Bin
/Windows
/Program Files
/Program Files (x86)
/ProgramData
/System Volume Information
/Users/*/AppData
/Recovery
/var
/usr
/sys
/proc
/lib
/grub
/grub2
/opt/splunk
/splunk

---

## Examples

### Create a new protection job

```bash
python protectVMs.py \
  -v mycohesity.example.com \
  -u admin \
  -j "MyVMJob" \
  -vc "myvcenter" \
  -p "Gold Policy" \
  -n vm1 -n vm2
```

### Add VMs to an existing job

```bash
python protectVMs.py \
  -v mycohesity.example.com \
  -u admin \
  -j "MyVMJob" \
  -n vm3 -n vm4
```

### Enable indexing on an existing job

```bash
python protectVMs.py -v mycohesity.example.com -u admin -j "MyVMJob" -ei
```

### Reset indexing paths to defaults

```bash
python protectVMs.py -v mycohesity.example.com -u admin -j "MyVMJob" -ud
```

### Reset to defaults and add a custom exclude path

```bash
python protectVMs.py -v mycohesity.example.com -u admin -j "MyVMJob" -ud -aep "/opt/myapp"
```

### Add an exclude path without changing anything else

```bash
python protectVMs.py -v mycohesity.example.com -u admin -j "MyVMJob" -aep "/data/logs"
```

### Remove a specific exclude path

```bash
python protectVMs.py -v mycohesity.example.com -u admin -j "MyVMJob" -rep "/opt/splunk"
```

### Fully replace exclude paths

```bash
python protectVMs.py -v mycohesity.example.com -u admin -j "MyVMJob" \
  -ep "/$Recycle.Bin" -ep "/Windows" -ep "/tmp"
```

### Connect via Helios

```bash
python protectVMs.py \
  -v helios.cohesity.com \
  -u myuser@example.com \
  -c myclustername \
  -j "MyVMJob" \
  -n vm1
```

---

## Notes

- If the protection group specified by `--jobname` already exists, the script will **update** it rather than create a new one. VMs and indexing policy changes are additive/surgical unless a full replace flag (`-ip`, `-ep`) is used.
- When connecting to Helios or MCM, `--clustername` is required.
- VM names are **case-insensitive**.
- `--usedefaults` runs before any `--addincludepath` / `--addexcludepath` / `--removeincludepath` / `--removeexcludepath` flags, so you can reset and customize in a single command.
