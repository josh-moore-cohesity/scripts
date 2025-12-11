
# **autoProtectS3.py**

   Find and add unprotected S3 Buckets to Protection Groups.  Results are shown on screen as well as saved to a csv file.

## **Parameters**
* -c (cluster or clusters to run against)
* -cl (cluster list text file of clusters to run against, 1 per line)
* -xl (REQUIRED - exclude file  - file must be csv in format of '<sourcename>,<bucket_name>', 1 per line)
* -preview (preview script run, but don't actually update the PGs)
  
## **Examples**

### Preview (Don't update the PG, but report on what would be executed)
    python .protect_s3_buckets.py -c cluster1 -xl exclude_s3.csv -preview

### Protect All S3 Buckets on 1 cluster (minus excludes)
    python .protect_s3_buckets.py -c cluster1 -xl exclude_s3.csv
    
### Protect All S3 Buckets on 2 clusters (minus excludes)
    python .protect_s3_buckets.py -c cluster1 cluster2 -xl exclude_s3.csv

### Protect All S3 Buckets on multiple clusters using a cluster list (minus excludes)
    python .protect_s3_buckets.py -cl clusters.txt -xl exclude_s3.csv
    
## **Download**

    curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/refs/heads/main/Python/Jobs/Protect%20S3/autoProtectS3.py
    curl -O https://raw.githubusercontent.com/cohesity/community-automation-samples/main/python/pyhesity.py

[pyhesity.py](https://github.com/bseltz-cohesity/scripts/tree/master/python/pyhesity) is required 
    

