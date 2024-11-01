#!/bin/bash

#set path varaiables
PATH="/home/cohesity/software/crux/bin/tools:/home/cohesity/software/toolchain/x86_64-linux/7.1-ssl/bin:/home/cohesity/software/crux/bin:/home/cohesity/software/crux/bin/ssh:/home/cohesity/software/crux/bin/scp:/usr/local/bin:/usr/bin:/bin:/usr/local/games:/usr/games:/usr/local/sbin:/usr/sbin:/usr/Arcconf:/user/local/sbin:/usr/sbin:/home/cohesity/.local/bin:/home/cohesity/bin"

#clear old results
echo -n > athena_connections.out

#add date to top of file
date > athena_connections.out

#get new results
for host in $(hostips) ; do echo ----$host---- ; ssh -o StrictHostKeyChecking=no $host eval "sudo netstat -atulnp | grep ESTABLISHED | awk ' { print \$7 } ' | sort | uniq -c | egrep 'athena'" ; done >> athena_connections.out

#add date to end of file
date >> athena_connections.out

#set email parameters
export subject="Athena Processes"
export from="email@domain.com"
export to="email@domain.com"

#Find records > 10000
p=$(awk '{if ($1+0 > 10000) print $1;}' athena_connections.out)

#Pull Max Record
max=0

for num in $p; do
  if [ "$num" -gt "$max" ]; then
    max="$num"
  fi
done

if [ "$max" -gt "0" ]; then
         echo "The maximum processes is: $max"
fi

#Do Actions based on Max Processes

#if nothing over 10000 (Do nothing)
if [ "$max" = "0" ]; then
       echo "Not over threshold. No Action Required"

#if between 10000 and 15000 (Email Only)
elif [ "$max" -gt "10000" ] && [ "$max" -lt "15000" ]; then

       #email results
        echo "Processes between 10k and 15k. Sending email only"
        ( echo "Athena Processes Over 10k ("$max")! Check Athena!";echo "";cat "athena_connections.out"  )|mail -s "$subject" -r "$from" "$to"

else [ "$max" -gt "15000" ]
        #Email Alert and Restart Athena
        echo "Athena Processes Greater Than 15k. Sending alert email and killing processes"
        ( echo "Athena Processes Over 15k ("$max")! RESTARTING ATHENA!";echo "";cat "athena_connections.out"  )| mail -s "$subject" -r "$from" "$to"
        #Restart Athena
        echo -n > athena_resarts.out
        for host in $(hostips) ; do echo ----$host---- ; ssh -o StrictHostKeyChecking=no $host athena.sh stop; athena.sh start; done >> athena_restarts.out


fi
