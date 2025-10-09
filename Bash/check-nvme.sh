#!/bin/bash

#set path varaiables
PATH="/home/cohesity/software/crux/bin/tools:/home/cohesity/software/toolchain/x86_64-linux/7.1-ssl/bin:/home/cohesity/software/crux/bin:/home/cohesity/software/crux/bin/ssh:/home/cohesity/software/crux/bin/scp:/usr/local/bin:/usr/bin:/bin:/usr/local/games:/usr/games:/usr/local/sbin:/usr/sbin:/usr/Arcconf:/user/local/sbin:/usr/sbin:/home/cohesity/.local/bin:/home/cohesity/bin"

#clear old results
echo -n > nvme_averages.out

#add date to top of file
date > nvme_averages.out
yesterday=$(date -d "yesterday" +"%d")
echo -e "\nResults pulled from file /var/log/sa/sa${yesterday}\n" >> nvme_averages.out

#get new results
for host in $(hostips) ; do echo ----$host---- ; ssh -o StrictHostKeyChecking=no $host eval "sar -f /var/log/sa/sa$yesterday -dp | grep -e DEV -e Average | grep -e DEV -e nvme[210]" ; done >> nvme_averages.out

#add date to end of file
date >> nvme_averages.out

#set email parameters
export subject="NVME Utilization Average"
export from="FROM"
export to="TO"

#email results
echo "Sending email"
( echo "NVME Average Usage";echo "";cat "nvme_averages.out"  )|mail -s "$subject" -r "$from" "$to"
