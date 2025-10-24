# **exportConfigurationV2_helios.ps1**

   Export Cluster Configuration using Helios.  This is a modified version of this [script](https://github.com/bseltz-cohesity/scripts/blob/master/powershell/importExport/exportConfigurationV2.ps1) to be able to run via Helios. <br />
   [cohesity-api.ps1](https://github.com/bseltz-cohesity/scripts/tree/master/powershell/cohesity-api) is required 

## **Examples**

    .\exportConfigurationV2_helios.ps1 -clusterName cluster1 -useApiKey
    .\exportConfigurationV2_helios.ps1 -clusterName cluster1,cluster2 -useApiKey
    .\exportConfigurationV2_helios.ps1 -clusterList .\clusterlist.txt -useApiKey
    
## **Download**
    curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/PowerShell/importExport/exportConfigurationV2_helios
