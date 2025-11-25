# **datahawk_app_status.py**

   Report on the health status of the DataHawk App.

   curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Python/Apps/DataHawk/datahawk_app_status.py

## **Parameters**
   Not using either will report on all clusters that are connected to Helios
* -c (cluster name or cluster names to run against)
* -cl (file of cluster names to run against, 1 per line)
  
## **Examples**

### Report on clusters
    python datahawk_app_status.py

### Report on a single cluster
    python datahawk_app_status.py -c cluster1

### Report on multiple clusters
    python datahawk_app_status.py -c cluster1 cluster2

### Report on multiple clusters using cluster file
    python datahawk_app_status.py -cl clusters.txt
    

