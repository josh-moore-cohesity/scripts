# **performance_monitor_cassandra.py**

   Monitor an actively running Cassandra Protection Group.<br />
   [pyhesity.py](https://github.com/bseltz-cohesity/scripts/tree/master/python/pyhesity) is required

## **Download**
    curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Python/Databases/Cassandra/Performance%20Monitoring/performance_monitor_cassandra.py

## **Primary Parameters**
* -v (local cluster vip)
* -u (local user name)
* -pg (protection group name)
* -runtime (Duration to run the monitor.  Default is 5 minutes)
* -interval (How many seconds between monitor runs.  Default is 10 seconds).
  
## **Examples**

   ### Monitor a PG run with default options
    python performance_monitor_cassandra.py -v cluster1.domain.com -u admin 
   ### Monitor a PG run for 20 minutes and query stats every 30 seconds
    python performance_monitor_cassandra.py -v cluster1.domain.com -u admin -runtime 20 -interval 30

    

