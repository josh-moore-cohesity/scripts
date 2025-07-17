# **gflags.py**

   Query, Set, Or Clear Gflags and optionally restart services. This can be used for 1, multiple, or all clusters.<br />
   [pyhesity.py](https://github.com/bseltz-cohesity/scripts/tree/master/python/pyhesity) is required

## **Download**
    curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Python/Gflags/gflags.py

## **Parameters**
* -k (Use API Key)
* -c (space separated list of clusters)
* -cl (text file name of cluster names, 1 per line)
* -s (Service Name)
* -n (Flag Name)
* -f (Flag Value)
* -r (Reason)
* -e (effective now)
* -clear (clear gflag)
* -i (Import File Name, csv of service name, flag name, flag value, and reason.  1 per line)
* -x (Restart Services)
  
## **Examples**

   ### Get (query) Gflags from 1 cluster 
    python gflags.py -k -c cluster1
   ### Get (query) Gflags from multiple clusters
    python gflags.py -k -c cluster1 cluster2
   ### Get (query) Gflags from ALL clusters connected to Helios
    python gflags.py -k -c all
   ### Set Gflag for a cluster
    python gflags.py -k -c cluster1 -s <Service_Name> -n <Flag_Name> -f <Flag_Value> -r <Reason> -e
   ### Set Gflag for a cluster and restart services
    python gflags.py -k -c cluster1 -s <Service_Name> -n <Flag_Name> -f <Flag_Value> -r <Reason> -e -x
   ### Set Gflag using a cluster list and an import file
    python gflags.py -k -cl clusters.txt -i importgflags.txt -e
   ### Clear gflag from a cluster
    python gflags.py -k -c cluster1 -s <Service_Name> -n <Flag_Name> -r <Reason> -clear
    


