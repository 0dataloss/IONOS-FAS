# IONOS-FAS
IONOS Fast Auto Scale Python Service

This script will provide you with a REST endpoint to scale up or down your Scaling Group based on IONOS Cloud API

Documentation yet to be finished
WIP

Limitations
Only 1 disk can be used
Only one network can be used
Only one forwarding rule for the network Load Balancer
The minimum and maximum numbers are ONLY related to the AutoScaled Replicas
Min=1 means delete all the replica, leave the origin server alone