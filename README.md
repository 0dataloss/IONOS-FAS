# IONOS-FAS
IONOS Fast Autoscale Service (FAS)

This Python service will provide you with a REST endpoint to scale your infrastructure Up or Down.

This POC will enable you to start scaling up or down:

1 Template Server with:
- 1 Disk
- Multiple network cards
- 1 Network card connected to 1 Network Load Balancer

## Essential Configuration Files
- Rename ionos-example.py in ionos.py and set your username/password
- Configure at leas one section in the IONOS-FAS.ini file following the template

## How to run the script
This is a POC so please do not run the service in a public server.
I advise you to protect the port where the script is listening an
preferrably, just keeping it runnig locally on 127.0.0.1:5000

## LIMITATIONS
This script is a POC and as such has limitations:
- Please make sure to specify in the configuration file which one is the network ID connecting the machines to the Network Loadbalancer as the script does not looks for it
- Please make sure your master server does have only one disk as for the moment we do snapshot and replicate only 1
- Make sure your Network Loadbalancer has only one forwarding rule. you can manage more forwarding rules but you will need more sections in the configuration file.
- Min=1 means delete all the replica, leave the origin server. Setting Min=0 does have no effect on your infrastructure

## API Reference Guide
The service will expose 3 endpoints and some of those will accept parameters:

- /scaledown?ASgroup=<name of your section in the config file>
  - Example: 127.0.0.1:5000/scaledown?ASgroup=app01

- /scaleup
Example: 127.0.0.1:5000/scaleup?ASgroup=app01?ASgroup=<name of your section in the config file>
  - Example: 127.0.0.1:5000/scaleup?ASgroup=app01

- /snapshot
