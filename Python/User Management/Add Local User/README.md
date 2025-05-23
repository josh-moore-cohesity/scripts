# **add_local_user.py**

   Add Local User to Cluster.<br />
   [pyhesity.py](https://github.com/bseltz-cohesity/scripts/tree/master/python/pyhesity) is required

## **Download**
    curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Python/User%20Management/Add%20Local%20User/add_local_user.py

## **Parameters**
* -n (username to add to local cluster)
* -c (space separated list of clusters to add user)
* -cl (text file name of cluster names, 1 per line)
* -np (new password - optional and will be prompted if not provided)
* -e (email address)
* -r (role)
* -x (disable mfa)
* -g (generate api key)
* -s (store api key in file)
* -o (overwrite existing api key)
* -m (add api key name suffix)
  
## **Examples**

   ### Add user to 1 cluster
    python add_local_user.py -c cluster1 -n user1 -r operator -e email1@email.com
   ### Add user to multiple clusters
    python add_local_user.py -c cluster1 cluster2 -n user1 -r operator -e email1@email.com
   ### Add user and disable mfa for the user
    python add_local_user.py -c cluster1 -n user1 -r operator -e email1@email.com -x
   ### Add user and generate api key
    python add_local_user.py -c cluster1 -n user1 -r operator -e email1@email.com -g
    
    

