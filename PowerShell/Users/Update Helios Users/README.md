# **update_helios_sso_user.ps1**

   Update Cluster Access List for Helios SSO Users.<br />
   [cohesity-api.ps1](https://github.com/bseltz-cohesity/scripts/tree/master/powershell/cohesity-api) is required 

## **Examples**

    .\update_helios_sso_user.ps1 -usernames user1@domain.com -clusternames cluster1 -action add
    .\update_helios_sso_user.ps1 -usernames user1@domain.com -clusternames cluster1 -action remove
    .\update_helios_sso_user.ps1 -usernames user1@domain.com,user2@domain.com -clusternames cluster1,cluster2 -action add
    .\update_helios_sso_user.ps1 -usernames user1@domain.com -clusternames all -action add
    .\update_helios_sso_user.ps1 -usernames userlist.txt -clusternames clusternames.txt -action add
    .\update_helios_sso_user.ps1 -usernames user1@domain.com -action query
    
    
## **Download**
    curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/PowerShell/Users/Update%20Helios%20Users/update_helios_sso_user.ps1
