# **pauseResumeVaulting.py**

   Pause or Resume Data Isolation Vaulting by enable/disabling in crontab.  The script will need run from the orchestration VM as well as the Master VM as the user where the cronjob(s) is/are configured.

   curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Python/Security/Vaulting/pauseResumeVaulting.py

## **Parameters**
pause or resume
  
## **Examples**

### Pause Vaulting
    python pauseResumeVaulting.py pause

### Resume Vaulting
    python pauseResumeVaulting.py resume
