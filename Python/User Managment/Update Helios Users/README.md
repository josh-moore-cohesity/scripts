# **update_helios_sso_user.ps1**

   Update or Query Cluster Access for Helios SSO Users.<br />
   [pyhesity.py](https://github.com/bseltz-cohesity/scripts/tree/master/python/pyhesity) is required

## **Download**
    curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Python/User%20Management/Update%20Helios%20Users/update_helios_sso_user.py

## **Parameters**
* -un (comma seperated list of Helios SSO usernames)
* -ul (text file name of usernames, 1 per line)
* -c (cli list of clusters to add/remove)
* -cl (text file name of cluster names, 1 per line)
* -action (Add,Remove,Query)
  
## **Examples**

   ### Add a cluster to a user's access
    .\update_helios_sso_user.py -un user1@domain.com -c cluster1 -action add
   ### Remove a cluster from a user's access
    .\update_helios_sso_user.py -un user1@domain.com -c cluster1 -action remove
   ### Add multiple clusters to multiple user's access
    .\update_helios_sso_user.py -un user1@domain.com user2@domain.com -c cluster1 cluster2 -action add
   ### Add all clusters to a user's access (Current clusters and new clusters that are added later)
    .\update_helios_sso_user.py -un user1@domain.com -clusternames all -action add
   ### Add cluster(s) to 1 or multiple user's access (use files containing users and clusters names)
    .\update_helios_sso_user.py -ul userlist.txt -cl clusternames.txt -action add
   ### Query a user's access
    .\update_helios_sso_user.py -un user1@domain.com -c all -action query
    
    
