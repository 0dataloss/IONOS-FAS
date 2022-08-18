# IONOS-FAS
IONOS Fast Autoscale Service (FAS)

This Python service will provide you with a REST endpoint to scale your infrastructure Up or Down.

## Essential Configuration Files
- Rename ionos-example.py in ionos.py and set your username/password
- Configure at leas one section in the IONOS-FAS.ini file

## How to run the script
This is a POC so please do not run the service in a public server.
I advise you to protect the port where the script is listening an
preferrably, just keeping it runnig locally on 127.0.0.1:5000

## LIMITATIONS
This script is a POC and as such has limitations:
- Please make sure to specify in the configuration file which one is the network ID connecting the machines to the Network Loadbalancer as only one network can be replicated
- Please make sure your master server does have only one disk
- Make sure your Network Loadbalancer has only one forwarding rule. you can manage more forwarding rules but you will need more sections in the configuration file.
- Min=1 means delete all the replica, leave the origin server. Setting Min=0 does have no effect on your infrastructure

## API Reference Guide
The service will expose 4 endpoints and some of those will accept parameters:
- /scaledown
-- Required /scaledown?Sgroup=<name of your section in the config file>
- /scaleup
-- Required /scaledown?Sgroup=<name of your section in the config file>
- /snapshot