# **joblist.py**

   Get High Level Summary of Jobs / Protection Groups.

   curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Python/Jobs/Job%20List/joblist.py

## **Parameters**
* -e (environment)
* -j (job name - exact or character match)
* -paused (show paused jobs only)
  
## **Examples**

### Get all Jobs from all Clusters
    python joblist.py -c all

### Get all VMware Jobs from all clusters
    python joblist.py -c all -e vmware

### Get aLL VMware Jobs from all clusters that are paused
    python joblist.py -c all -e vmware -paused

### Get all Oracle Jobs from a single cluster
    python joblist.py -c cluster1 -e oracle

### Get all SQL Jobs from multiple clusters
    python joblist.py -c cluster1 -c cluster2 -e sql

### Get all SQL Jobs from multtiple clusters using a cluster list
    python joblist.py -cl clusters.txt -e sql
