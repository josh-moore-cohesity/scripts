#!/bin/bash

#set path varaiables
PATH="/home/cohesity/software/crux/bin/tools:/home/cohesity/software/toolchain/x86_64-linux/7.1-ssl/bin:/home/cohesity/software/crux/bin:/home/cohesity/software/crux/bin/ssh:/home/cohesity/software/crux/bin/scp:/usr/local/bin:/usr/bin:/bin:/usr/local/games:/usr/games:/usr/local/sbin:/usr/sbin:/usr/Arcconf:/user/local/sbin:/usr/sbin:/home/cohesity/.local/bin:/home/cohesity/bin"

#clear old results
echo -n > athena_connections.out

#get new results
for host in $(hostips) ; do echo ----$host---- ; ssh -o StrictHostKeyChecking=no $host eval "sudo netstat -atulnp | grep ESTABLISHED | awk ' { print \$7 } ' | sort | uniq -c | egrep 'athena'" ; done >> athena_connections.out

#set email parameters
subject="Athena Processes"
from="email@domain.com"
to="email@domain.com"

#email results
mail -s "$subject" -r "$from" "$to" < athena_connections.out
