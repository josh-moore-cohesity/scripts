# **close_anomalies.py**

   Resolve Anti-Ransomware anomalies through Helios.

   curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Python/Security/close_anomalies.py
 
## **Examples**

### Report Only (Don't close)
    python close_anomalies.py -s <strength> -o <older than days> -e <entity>

### Close Anomalies based on stregth (70 or less)
    python close_anomalies.py -s 70 -r

### Close Anomalies based on stregth (70 or less) and older than 60 days
    python close_anomalies.py -s 70 -o 60 -r

### Close Anomalies based on entity
    python close_anomalies.py -e server1 -r
