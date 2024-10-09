#!/usr/bin/env python

from pyhesity import *
import argparse

parser = argparse.ArgumentParser()

parser.add_argument('-cl', '--clusters', type=str, default=None)
parser.add_argument('-c', '--clustername', action='append', type=str)
parser.add_argument('-s', '--severity', type=str, default=None)
parser.add_argument('-t', '--alerttype', type=str, default=None)
parser.add_argument('-r', '--resolution', type=str, default=None)
parser.add_argument('-o', '--olderthan', type=str, default=0)

args = parser.parse_args()

clusterlist = args.clusters
cluster = args.clustername
severity = args.severity
alerttype = args.alerttype
resolution = args.resolution
olderthan = args.olderthan



# gather list function
def gatherList(param=None, filename=None, name='items', required=True):
    items = []
    if param is not None:
        for item in param:
            items.append(item)
    if filename is not None:
        f = open(filename, 'r')
        items += [s.strip() for s in f.readlines() if s.strip() != '']
        f.close()
    if required is True and len(items) == 0:
        print('no %s specified' % name)
        exit()
    return items


# get list of clusters
clusternames = gatherList(cluster, clusterlist, name='clusters', required=True)

import subprocess

for cluster in clusternames:
    print(cluster)
# If no resolution
    if (resolution is None):
        if (severity is not None) and (olderthan != 0) and (alerttype is not None):
            print("Showing Alerts with severity", severity)
            subprocess.run(["python3", "resolve_alerts.py", '-c', cluster, '-k', '-s', severity, '-t', alerttype, '-o', olderthan ])
        
        elif (severity is not None) and (olderthan != 0):
            print ("Showing Alerts with severity", severity, "and older than", olderthan, "days")
            subprocess.run(["python3", "resolve_alerts.py", '-c', cluster, '-k', '-s', severity, '-o', olderthan ])
        
        elif (severity is not None) and (alerttype is not None):
            print ("Showing Alerts with severity", severity, "and alert type", alerttype)
            subprocess.run(["python3", "resolve_alerts.py", '-c', cluster, '-k', '-s', severity, '-t', alerttype ])

        elif (olderthan !=0) and (alerttype is not None):
            print ("Showing Alerts older than", olderthan, "days", "and alert type", alerttype)
            subprocess.run(["python3", "resolve_alerts.py", '-c', cluster, '-k', '-o', olderthan, '-t', alerttype ])

        elif (alerttype is not None):
            print ("Showing Alerts with Type", alerttype)
            subprocess.run(["python3", "resolve_alerts.py", '-c', cluster, '-k', '-t', alerttype ])

        elif (severity is not None):
            print ("Showing Alerts with Severity", severity)
            subprocess.run(["python3", "resolve_alerts.py", '-c', cluster, '-k', '-s', severity ])

        elif (olderthan != 0):
            print ("Showing Alerts Older than", olderthan, "days")
            subprocess.run(["python3", "resolve_alerts.py", '-c', cluster, '-k', '-o', olderthan ])

        else:
            print ("Showing All Alerts")
            subprocess.run(["python3", "resolve_alerts.py", '-c', cluster, '-k' ])

    #If Resolution
    if (resolution is not None):
        if (severity is not None) and (olderthan != 0) and (alerttype is not None):
            print ("Resolving Alerts with Type", alerttype,"severity of",severity, "and Older than", olderthan, "days")
            subprocess.run(["python3", "resolve_alerts.py", '-c', cluster, '-k', '-s', severity, '-t', alerttype, '-o', olderthan, '-r', resolution ])
    
        elif (severity is not None) and (olderthan != 0):
            print ("Resolving Alerts with severity", severity, "and older than", olderthan, "days")
            subprocess.run(["python3", "resolve_alerts.py", '-c', cluster, '-k', '-s', severity, '-o', olderthan, '-r', resolution ])
    
        elif (severity is not None) and (alerttype is not None):
            print ("Resolving Alerts with severity", severity, "and alert type", alerttype)
            subprocess.run(["python3", "resolve_alerts.py", '-c', cluster, '-k', '-s', severity, '-t', alerttype, '-r', resolution ])

        elif (olderthan !=0) and (alerttype is not None):
            print ("Resovling Alerts with Type", alerttype, "and older than", olderthan, "days")
            subprocess.run(["python3", "resolve_alerts.py", '-c', cluster, '-k', '-o', olderthan, '-t', alerttype, '-r', resolution ])

        elif (alerttype is not None):
            print ("Resovling Alerts with Type", alerttype)
            subprocess.run(["python3", "resolve_alerts.py", '-c', cluster, '-k', '-t', alerttype, '-r', resolution ])

        elif (severity is not None):
            print ("Resolving Alerts with Severity", severity)
            subprocess.run(["python3", "resolve_alerts.py", '-c', cluster, '-k', '-s', severity, '-r', resolution ])

        elif (olderthan != 0):
            print ("Resovling Alerts Older than", olderthan, "days")
            subprocess.run(["python3", "resolve_alerts.py", '-c', cluster, '-k', '-o', olderthan, '-r', resolution ])

        else:
            print ("Resolving All Alerts")
            subprocess.run(["python3", "resolve_alerts.py", '-c', cluster, '-k', '-r', resolution ])