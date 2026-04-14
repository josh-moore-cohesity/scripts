# **agent_summary.py**

   Report Agent Version and other info for all registered sources that utilize the Cohesity Agent.<br />
   [pyhesity.py](https://github.com/bseltz-cohesity/scripts/tree/master/python/pyhesity) is required 
   
## **Parameters**
* -c (Cluster Name.  Use "all" to get all agents on all clusters when using Helios.)
* -cl (Cluster File, 1 per line)
* -i (Use API Key)
     
## **Example**

    python agent_summary.py -i -c cluster1
    python agent_summary.py -i -cl clusters.txt
    python agent_summary.py -i -c all
    
## **Download**
    curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Python/Reports/Protected%20Objects/protectedObjects.py

