# **resolve_alerts.py**

   Resolve Alerts through Helios.  Provide either single cluster or cluster list (txt file)
 
## **Examples**

### single cluster
    python resolve_alerts.py -c <clustername> -s <severity> -o <older than days> -t <type> -r <resolution>

### multiple clusters
    python resolve_alerts.py -cl <clusterfile.txt> -s <severity> -o <older than days> -t <type> -r <resolution>
