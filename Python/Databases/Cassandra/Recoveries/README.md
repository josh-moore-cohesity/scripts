# **cassandra_recoveries.py**

   Query Cassandra Recoveries per cluster.<br />
   [pyhesity.py](https://github.com/bseltz-cohesity/scripts/tree/master/python/pyhesity) is required 
   
   
## **Examples**

    python recovery_task_details.py -c clusterA (Single Cluster, default time range of last 7 days)
    python recovery_task_details.py -c clusterA clusterB -days 15 (Multiple clusters, last 15 days)
    python recovery_task_details.py -cl clusters.txt -days 10 (cluster file, last 10 days)
    python recovery_task_details.py -c clusterA -days 10 -s running (single cluster, in running state, last 10 days)
    

    
## **Download**
    curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Python/Databases/Cassandra/Recoveries/cassandra_recoveries.py


