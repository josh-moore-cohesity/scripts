
[pyhesity.py](https://github.com/bseltz-cohesity/scripts/tree/master/python/pyhesity) is required 

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

# **import_vcenter_sources.py**

   Import vCenter sources back into a cluster.  The script will prompt for vCenter credentials for the user used in the original registration.

## **Parameters**
* -o (Output Path.  Default is ./configExports)
* -c (Cluster Name.  Can provide multiple such as "-c cluster1 cluster2" if using Helios) 
* -cl (Cluster List File.  Provide 1 cluster name per line)
  
## **Examples**

### Import vCenter sources for 1 cluster via Helios
    python import_vcenter_sources.py -i -c cluster1
### Import vCenter sources for 1 cluster via Local VIP
    python import_vcenter_sources.py -VIP 0.0.0.0 -u admin
### Import vCenter sources for multiple clusters in a list
    python import_vcenter_sources.py -i -cl clusters.txt
    
## **Download**

    curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/refs/heads/main/Python/importExport/import_vcenter_sources.py
    curl -O https://raw.githubusercontent.com/cohesity/community-automation-samples/main/python/pyhesity.py

    

