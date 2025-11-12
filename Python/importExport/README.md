
# **exportConfigurationV2_helios.py**

   Export Cluster Config Info.

## **Parameters**
* -o (Output Path.  Default is ./configExports)
* -c (Cluster Name.  Can provide multiple such as "-c cluster1 cluster2")
* -cl (Cluster List File.  Provide 1 cluster name per line)
  
## **Examples**

### Export Config for 1 cluster
    python exportConfigurationV2_helios.py -i -c cluster1
### Export Config for 2 clusters
    python exportConfigurationV2_helios.py -i -c cluster1 cluster2
### Export Config for clusters in a list
    python exportConfigurationV2_helios.py -i -cl clusters.txt
    
## **Download**

    curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/refs/heads/main/Python/importExport/exportConfigurationV2_helios.py
    curl -O https://raw.githubusercontent.com/cohesity/community-automation-samples/main/python/pyhesity.py

[pyhesity.py](https://github.com/bseltz-cohesity/scripts/tree/master/python/pyhesity) is required 
    

