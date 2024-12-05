
# **excludeVMsAllJobs.py**

   Exclude VMs from all protectiong groups. Options include to exclude by full VM name, parital name(any match), and to exclude all templates.

# **excludeVMsAllJobs.py**

   Exclude VMs from specified protection group. Options include to exclude by full VM name, parital name(any match), and to exclude all templates.

## **Examples**

    python excludeVMsAllJobs.py -i -xt -x sql -c cluster1
    python excludeVMs.py -i -xt -x win -x sql -c cluster1 -j job1
    
## **Download**

    curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/refs/heads/main/Python/Jobs/Exclude%20VMs/excludeVMsAllJobs.py <br />
    curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/refs/heads/main/Python/Jobs/Exclude%20VMs/excludeVMs.py <br />
    curl -O https://raw.githubusercontent.com/cohesity/community-automation-samples/main/python/pyhesity.py

[pyhesity.py](https://github.com/bseltz-cohesity/scripts/tree/master/python/pyhesity) is required 
    
