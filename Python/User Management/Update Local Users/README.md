# **update_local_user.py**

   Update 1 or more local users on 1 or more clusters.<br />
   [pyhesity.py](https://github.com/bseltz-cohesity/scripts/tree/master/python/pyhesity) is required

## **Download**
    curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Python/User%20Management/Update%20Local%20Users/update_local_user.py

## **Parameters**
* -n (space separted list of usernames to add to local cluster)
* -nl (text file name of usernames, 1 per line)
* -c (space separated list of clusters to add user on)
* -cl (text file name of cluster names, 1 per line)
* -np (new password - will be prompted to provide)
* -e (email address)
* -r (role)
* -x (disable mfa)
* -mfa (enable mfa)
* -g (generate api key)
* -s (store api key in file)
* -o (overwrite existing api key)
* -m (add api key name suffix)
  
## **Examples**

   ### Update user role on 1 cluster
    .\update_local_user.py -c cluster1 -n user1 -r operator 
   ### Update user on multiple clusters
    .\update_local_user.py -c cluster1 cluster2 -n user1 -r operator
   ### Update multiple users on multiple clusters
    .\update_local_user.py -c cluster1 cluster2 -n user1 user2 -r operator
   ### Update user and disable mfa for the user
    .\update_local_user.py -c cluster1 -n user1 -r viewer -x
   ### Update user and generate new api key
    .\update_local_user.py -c cluster1 -n user1 -r operator -e email1@email.com -g -o
    
    


