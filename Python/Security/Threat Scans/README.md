# **threat_scan_report.py**

   Report Threat Scan Results.

   curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Python/Security/Threat%20Scans/threat_scan_report.py

## **Parameters**
   Not using either will capture all scans
* -nt (scans newer than)
* -ot (scans older than)
  
## **Examples**

### Report on all scans
    python threat_scan_report.py

### Report on all scans within the last 30 days
    python close_anomalies.py -nt 30

### Report on all scans within the last 30 days and older than 7 days ago
    python close_anomalies.py -nt 30 -ot 7
