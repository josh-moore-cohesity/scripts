# **copyroles.py**

   Copy a role from 1 cluster to another.<br />
   [pyhesity.py](https://github.com/bseltz-cohesity/scripts/tree/master/python/pyhesity) is required

## **Download**
    curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Python/User%20Management/Copy%20Roles/copyroles.py

## **Parameters**
* -sc (Source Cluster)
* -tc (Target Cluster)
* -o (Optional - Overwrite role if it already exists)
* -n (Role Name)
* -l (Role List)

  
## **Examples**

   ### Copy Role from 1 cluster to another Cluster
    python .\copyRoles.py -sc <Source_Cluster> -tc <Target Cluster> -n <role_name>
   ### Copy and Overwrite a role from 1 cluster to another cluster
    python .\copyRoles.py -sc <Source_Cluster> -tc <Target Cluster> -n <role_name> -o
   ### Copy Multiple Roles from 1 cluster to another cluster
    python .\copyRoles.py -sc <Source_Cluster> -tc <Target Cluster> -l <role_list.txt>

    
    


