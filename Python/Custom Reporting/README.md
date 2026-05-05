# **allow_reporting_db_firewall.py**

   Enable Reporting Firewall.  This assumes using Helios.

    curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Python/Custom%20Reporting/allow_reporting_db_firewall.py
   
## **Examples**

### Enable for 1 cluster using api key to authenticate (-i)
    python allow_reporting_db_firewall.py -i -c cluster1
    
### Enable for multiple clusters using api key to authenticate (-i) and a cluster list file (1 cluster name per line)
    python allow_reporting_db_firewall.py -i -cl clusters.txt
    
### Enable for all clusters connect to helios using api key to authenticate (-i)
    python allow_reporting_db_firewall.py -i -c all

# **get_cohesity_postgres_details.py**

   Get Postgres DB Details Per Cluster.  Output save to a file.

    curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Python/Custom%20Reporting/get_cohesity_postgres_details.py
 
## **Examples**

### Get Postgres DB Details for 1 cluster
    python get_cohesity_postgres_details.py -i -c cluster1

### Get Postgres DB Details for multiple clusters using a cluster list file (1 cluster per line)
    python get_cohesity_postgres_details.py -i -cl clusters.txt

### Get Postgres DB Details for all clusters that are connect to helios
    python get_cohesity_postgres_details.py -i -c all
    
