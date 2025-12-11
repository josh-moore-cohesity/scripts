
# **autoProtectS3.py**

   Find and add unprotected S3 Buckets to Protection Groups.  Results are shown on screen as well as saved to a csv file.

## **Parameters**
* -c (cluster or clusters to run against)
* -cl (cluster list text file of clusters to run against, 1 per line)
* -xl (REQUIRED - exclude file  - file must be csv in format of `<sourcename>`,`<bucket_name>`, 1 per line)
* -preview (preview script run, but don't actually update the PGs)
* -cg (Create PG if one does not exist for the S3 source)
* -gp (PG Name prefix if creating a new PG.  Default is S3-PG-1. The source name will be appended to the prefix for the PG Name.  For example, S3-PG-1-s3source.domain.com)
* -p (PG Policy Name if creating a new PG)
* -st (PG Start Time if creating a new PG.  Default is 05:00)
* -tz (PG Time Zone if creating a new PG.  Default is US/EASTERN.)
* -sd (Storage Domain if creating a new PG.  Default is DefaultStorageDomain.)
* -is (incremental SLA if creating a new PG.  Default is 1440.)
* -fs (full SLA if creating a new PG.  Default is 1440.)
* -pause (Create the PG in the paused state if creating a new PG.)
* -ea (Optional - email address to send alerts to if creating a new PG.  These email alerts are specific for the new PG only.  Admins will still receive failure alerts regardless.)
  
## **Examples**

### Preview (Don't actually update the PG, but report on what would be executed)
    python .autoProtectS3.py -c cluster1 -xl exclude_s3.csv -preview

### Protect All S3 Buckets on 1 cluster (minus excludes)
    python .autoProtectS3.py -c cluster1 -xl exclude_s3.csv
    
### Protect All S3 Buckets on 2 clusters (minus excludes)
    python .autoProtectS3.py -c cluster1 cluster2 -xl exclude_s3.csv

### Protect All S3 Buckets on multiple clusters using a cluster list (minus excludes)
    python .autoProtectS3.py -cl clusters.txt -xl exclude_s3.csv

### Protect All S3 Buckets and create a new PG for any S3 sources that don't already have an existing PG, utilzing a custom PG Name Prefix,Start Time, and Time Zone.
    python .autoProtectS3.py -c cluster1 -xl exclude_s3.csv -cg -gp S3-PG-ABC -p <policyName> -st 17:00 -tz US/Central

### Protect All S3 Buckets and create a new PG for any S3 sources that don't already have an existing PG in a paused state.
    python .autoProtectS3.py -c cluster1 -xl exclude_s3.csv -cg -gp S3-PG-ABC -p <policyName> -st 17:00 -tz US/Central -pause
    
## **Download**

    curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/refs/heads/main/Python/Jobs/Protect%20S3/autoProtectS3.py
    curl -O https://raw.githubusercontent.com/cohesity/community-automation-samples/main/python/pyhesity.py

[pyhesity.py](https://github.com/bseltz-cohesity/scripts/tree/master/python/pyhesity) is required 
    

