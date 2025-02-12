# **update_helios_sso_user.ps1**

   Update Cluster Access List for Helios SSO Users.<br />
   [cohesity-api.ps1](https://github.com/bseltz-cohesity/scripts/tree/master/powershell/cohesity-api) is required 

## **Download**
    curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/PowerShell/Users/Update%20Helios%20Users/update_helios_sso_user.ps1

## **Parameters**
* -usernames (comma seperated list of Helios SSO usernames)
* -userlist (text file name of usernames, 1 per line)
* -clusternames (comma seperated list of clusters to add/remove)
* -clusterlist (text file name of cluster names, 1 per line)
* -action (Add,Remove,Query)
  
## **Examples**

   ### Add a cluster to a user's access
    .\update_helios_sso_user.ps1 -usernames user1@domain.com -clusternames cluster1 -action add
   ### Remove a cluster from a user's access
    .\update_helios_sso_user.ps1 -usernames user1@domain.com -clusternames cluster1 -action remove
   ### Add multiple clusters to multiple user's access
    .\update_helios_sso_user.ps1 -usernames user1@domain.com,user2@domain.com -clusternames cluster1,cluster2 -action add
   ### Add all clusters to a user's access (Current clusters and new clusters that are added later)
    .\update_helios_sso_user.ps1 -usernames user1@domain.com -clusternames all -action add
   ### Add cluster(s) to 1 or multiple user access (use files container users and clusters names)
    .\update_helios_sso_user.ps1 -usernames userlist.txt -clusternames clusternames.txt -action add
   ### Query a user's access
    .\update_helios_sso_user.ps1 -usernames user1@domain.com -action query
    
    

