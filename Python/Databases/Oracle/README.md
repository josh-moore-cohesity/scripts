# **oracle_pg_durations.py**

   Graph Oracle Protection Group Run Durations and Data Read.
   [pyhesity.py](https://github.com/bseltz-cohesity/scripts/tree/master/python/pyhesity) is required 

 ## **Download**
   curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Python/Databases/Oracle/oracle_pg_durations.py

## **Parameters**
   Not using either will capture all scans
* -cl (Cluster List.  File with cluster names to report on, 1 per line)
* -daysback (default 30)
* -j (job name.  All jobs will be graphed by default)
* -jl (job list. File with job names to report on, 1 per line)
  
## **Examples**

### Graph Oracle PGs on 1 cluster (default last 30 days)
    python oracle_pg_durations.py -c cluster1

### Graph Oracle PGs on Multiple clusters using a cluster list file for the last 60 days
    python oracle_pg_durations.py -cl clusters.txt -daysback 60

### Graph Oracle PG on a clusters for a specific protection group(job)
    python oracle_pg_durations.py -c cluster1 -j oracle-pg-1

