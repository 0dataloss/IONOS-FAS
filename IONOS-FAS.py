#!/bin/python3

from http import server
import sys
import ionoscloud
import time
import configparser
import os
import base64
from flask import Flask, request
import requests


if os.getenv('IONOS_USERNAME'):
    if os.getenv('IONOS_PASSWORD'):
      usernameio = os.getenv('IONOS_USERNAME')
      passwordio = os.getenv('IONOS_PASSWORD')
else:
    if os.path.exists("ionos.py"):
      # File Exist so  Import ionos.py
      sys.path.append("ionos")
      import ionos as i
      usernameio=i.username
      passwordio=i.password
    else:
      print("You can create a configuration file in your home directory\n"
      "This will make easy to run the script.\n"
      "Create the file ionos.py in this same directory with content:\n\n"
      "username=\"<replace with your username>\"\n"
      "contract=\"<replace with your contract number>\"\n\n")

#### Configure IONOSCLOUD SDK ####
configuration = ionoscloud.Configuration(
    username=usernameio,
    password=passwordio
)
client = ionoscloud.ApiClient(configuration)
##################################
######################
apiEndpoint="https://api.ionos.com/cloudapi/v6"
######################

# Prepare base46 username:password Headers
user_input_usernameandpassword=str(usernameio+":"+passwordio)
message_bytes = user_input_usernameandpassword.encode('ascii')
base64_bytes = base64.b64encode(message_bytes)
token = base64_bytes.decode('ascii')
authAcc={"Authorization": "Basic "+token+""}

app = Flask(__name__)

def catalog(authAcc):
  url = apiEndpoint+"/snapshots?pretty=true&depth=2"
  response = requests.get(url, headers=authAcc)
  catalogSnap = (response.json())
  return catalogSnap

def take_snapshot(apiEndpoint,dcuuid,volumeID,scaleSection,now):
  url=apiEndpoint+"/datacenters/"+ dcuuid +"/volumes/"+ volumeID +"/create-snapshot"
  dataForCreate={'name': scaleSection+"-"+str(now),'description':volumeID}
  response=requests.post(url, headers=authAcc, data=dataForCreate)
  response=response.json()
  uuid=response['id']
  return uuid

def only_take_snapshot(apiEndpoint,scaleSection,dcuuid,serveruuid):
  # Retrieve Server details
  url=apiEndpoint + "/datacenters/" + dcuuid + "/servers/" + serveruuid + "/?depth=3"
  serverDetails=requests.get(url, headers=authAcc)
  serverDetails=(serverDetails.json())
  volumeID=serverDetails['entities']['volumes']['items'][0]['id']
  # calculate Epoch-NOW
  now = int( time.time() )
  url=apiEndpoint+"/datacenters/"+ dcuuid +"/volumes/"+ volumeID +"/create-snapshot"
  dataForCreate={'name': scaleSection+"-"+str(now),'description':volumeID}
  response=requests.post(url, headers=authAcc, data=dataForCreate)
  response=(response.json())
  return response

def scaling_up_server(forwardruleuuid,snapResponse,singleNicProperties,volumeType,volumeSize,cpuType,cpuNumber,memRAM,min,max,cooldown,apiEndpoint,scaleSection,scaleUpOf,dcuuid,serveruuid,lbuuid):
#  servercount=0
#  while int(servercount) <= int(scaleUpOf):
  url=apiEndpoint+"/datacenters/"+ dcuuid +"/servers?depth=3"
  compositenameDRV=str(scaleSection + "-AutoScaledDRV")
  compositenameSRV=str(scaleSection + "-AutoScaledSRV")
  serversIDs=[]
  body = {
  "properties": {
        "name": compositenameSRV,
        "cores": cpuNumber,
        "ram": memRAM,
        "availabilityZone": "AUTO"
     },
    "entities": {
        "volumes": {
            "items": [{
                "properties": {
                  "name": compositenameDRV,
                  "image": snapResponse,
                  "type": volumeType,
                  "size": volumeSize,
                  "availabilityZone": "AUTO",
                  "bus": "VIRTIO",
                  "cpuHotPlug": True,
                  "ramHotPlug": True,
                  "nicHotPlug": True,
                  "nicHotUnplug": True,
                  "discVirtioHotPlug": True,
                  "discVirtioHotUnplug": True,
                  "userData": "",
                  "bootOrder": "AUTO"
               }
            }]
        },
        "nics": {
            "items": [{
                "properties": {
                  "dhcp": singleNicProperties['dhcp'],
                  "lan": singleNicProperties['lan'],
                  "firewallActive": singleNicProperties['firewall']
                }
            }]
        }    
    }
  }
  response=requests.post(url, headers=authAcc, json=body)
  response=response.json()
  serverUUID=response['id']
  serversIDs.append(serverUUID)
  serverurl=apiEndpoint + "/datacenters/" + dcuuid + "/servers/" + serverUUID + "/?depth=3"
  request=requests.get(serverurl, headers=authAcc)
  while request.status_code != 200:
    print(f"Server not available yet, waiting to connect to LB")
    time.sleep(10)
    request=requests.get(serverurl, headers=authAcc)
  request=request.json()
  # is it available?
  serverAvilable=request['metadata']['state']
  while serverAvilable != "AVAILABLE":
    print(f"Server not available yet, waiting to connect to LB")
    time.sleep(10)
    request=requests.get(serverurl, headers=authAcc)
    request=request.json()
    serverAvilable=request['metadata']['state']
  serverIP=request['entities']['nics']['items'][0]['properties']['ips'][0]
  # Attach server to forwardrule at the LB level
  url=apiEndpoint + "/datacenters/" + dcuuid + "/networkloadbalancers/" + lbuuid + "/forwardingrules/" + forwardruleuuid
  request=requests.get(url, headers=authAcc)
  request=request.json()
  properties=request['properties']
  target=request['properties']['targets']
  newdict={}
  for i in target[0].keys():
    if i == "ip":
      newdict['ip']=serverIP
    else:
      value=target[0][i]
      newdict[i]=value
  # Add nwedict to the current list
  target.append(newdict)
  # add the list target to the main body so we can connect the new server to the LB
  properties.update({'targets': target})
  body={
   "properties": properties
}
  url=apiEndpoint + "/datacenters/" + dcuuid + "/networkloadbalancers/" + lbuuid + "/forwardingrules/" + forwardruleuuid
  request=requests.put(url, headers=authAcc, json=body)
  request=request.json()  
#    servercount+=1
  return request

def scaleDown(forwardruleuuid,lanid,min,max,cooldown,apiEndpoint,scaleSection,scaleDownOf,dcuuid,serveruuid,lbuuid):
    url=apiEndpoint + "/datacenters/" + dcuuid + "/servers?depth=3"
    serversDetails=requests.get(url, headers=authAcc)
    serversDetails=(serversDetails.json())
    countersrv=int(min)
    counterdel=0
    msg="never touched the while loop"
    for autoscaledSrv in serversDetails['items']:
      while counterdel < 1:
        name=autoscaledSrv['properties']['name']
        uuid=autoscaledSrv['id']
        volumeID=autoscaledSrv['entities']['volumes']['items'][0]['id']
        serverIP=autoscaledSrv['entities']['nics']['items'][0]['properties']['ips'][0]
        compositeName=(scaleSection + "-AutoScaledSRV")
        if name == compositeName:
          countersrv+=1
          if countersrv > int(min) :
            url=apiEndpoint + "/datacenters/" + dcuuid + "/servers/" + uuid
            volumeurl=apiEndpoint + "/datacenters/" + dcuuid + "/volumes/" + volumeID
            msg="I have more servers than the minimum will delete one "
            print(f"Trying to delete server {uuid} and disk {volumeID}")
            serversDetails=requests.delete(url, headers=authAcc)
            volumeDetails=requests.delete(volumeurl, headers=authAcc)
            # modify LB Forward Rules
            url=apiEndpoint + "/datacenters/" + dcuuid + "/networkloadbalancers/" + lbuuid + "/forwardingrules/" + forwardruleuuid
            request=requests.get(url, headers=authAcc)
            request=request.json()
            properties=request['properties']
            target=request['properties']['targets']
            for i in target:
              if i['ip'] == serverIP:
                target.remove(i)
            # Add nwedict to the current list
            # add the list target to the main body so we can connect the new server to the LB
            properties.update({'targets': target})
            body={
             "properties": properties
            }
            url=apiEndpoint + "/datacenters/" + dcuuid + "/networkloadbalancers/" + lbuuid + "/forwardingrules/" + forwardruleuuid
            request=requests.put(url, headers=authAcc, json=body)
            request=request.json()
            ##########################
            counterdel+=1
          else:
            counterdel+=1
            msg="You reach the min amount of servers for your configuration"
        else:
          counterdel+=1
          msg="Not a server to delete"
    return msg

def scaleUp(forwardruleuuid,lanid,min,max,cooldown,force,apiEndpoint,scaleSection,scaleUpOf,dcuuid,serveruuid,lbuuid):
    # Retrieve Template Server details
    url=apiEndpoint + "/datacenters/" + dcuuid + "/servers/" + serveruuid + "/?depth=4"
    serverDetails=requests.get(url, headers=authAcc)
    serverDetails=(serverDetails.json())
    volumeID=serverDetails['entities']['volumes']['items'][0]['id']
    volumeSize=serverDetails['entities']['volumes']['items'][0]['properties']['size']
    volumeType=serverDetails['entities']['volumes']['items'][0]['properties']['type']
    for nic in serverDetails['entities']['nics']['items']:
      singleNicProperties={}
      lan=nic['properties']['lan']
      if str(lan) == lanid:
        singleNicProperties['lan']=lan
        firewall=nic['properties']['firewallActive']
        singleNicProperties['firewall']=firewall
        dhcp=nic['properties']['dhcp']
        singleNicProperties['dhcp']=dhcp
      else:
        continue
    cpuNumber=serverDetails['properties']['cores']
    cpuType=serverDetails['properties']['cpuFamily']
    memRAM=serverDetails['properties']['ram']
    # Must check most recent snapshot for the server
    # Snapshot has specific name: scaleSection-unixtime
    # calculate Epoch-NOW
    now = int( time.time() )
    # Verify if there is a snapshot for scaleSection-epoch
    snapshotList=catalog(authAcc)
    finshedWithSnapshot=False
    # check every single snapshot
    for i in snapshotList['items']:
      idFound=i['id']
      nameFound=i['properties']['name']
      volumeidFOUND=i['properties']['description']
      nameFoundSplit=nameFound.split("-")
      namefoundScaleSect=nameFoundSplit[0]
      # Check if a snapshot has been taken already
      if finshedWithSnapshot is True:
        continue
      # Check if the name matches
      if namefoundScaleSect == scaleSection:
        # Check if the volume ID matches, if not the user has refreshed the disk so we need a new snapshot
        if volumeidFOUND == volumeID:
          nameFoundEpoch=nameFoundSplit[1]
          timePastFromLastSnapshot=(((now - int(nameFoundEpoch))/60)/60)
          # Check if it has been more than 2 hours
          if timePastFromLastSnapshot >= 2:
            print("Take a snapshoot as it is too old to be trusted")
            snapResponse=(take_snapshot(apiEndpoint,dcuuid,volumeID,scaleSection,now))
            finshedWithSnapshot=True
          elif force is True:
            print("I am forced to take a snapshot")
            snapResponse=(take_snapshot(apiEndpoint,dcuuid,volumeID,scaleSection,now))
            finshedWithSnapshot=True
          else:
            print("Snapshot is ok multiply the server")
            snapResponse=idFound
            finshedWithSnapshot=True
    if finshedWithSnapshot is False:
      print("Take a snapshoot as no snapshot exists")
      snapResponse=(take_snapshot(apiEndpoint,dcuuid,volumeID,scaleSection,now))

    # Must check when snapshot is done
    # Must check server's spec
    # Must spin up n# servers as scaleUpOf
    # Verify if I can scale up in terms of servers
    url=apiEndpoint + "/datacenters/" + dcuuid + "/servers?depth=3"
    serversDetails=requests.get(url, headers=authAcc)
    serversDetails=(serversDetails.json())
    countersrv=0
    for autoscaledSrv in serversDetails['items']:
      name=autoscaledSrv['properties']['name']
      compositeName=(scaleSection + "-AutoScaledSRV")
      if name == compositeName:
        countersrv+=1
    if countersrv <= int(max) :
      response=(scaling_up_server(forwardruleuuid,snapResponse,singleNicProperties,volumeType,volumeSize,cpuType,cpuNumber,memRAM,min,max,cooldown,apiEndpoint,scaleSection,scaleUpOf,dcuuid,serveruuid,lbuuid))
      msg="I am less than maximum"
    else:
      msg="You reach the max amount of deployable servers"
    return msg

# Define and star the Flask server on port 5000
@app.route('/scaledown')
def scaledown_query():
  try:
    config = configparser.ConfigParser()
    config.read('IONOS-FAS.ini')
  except:
    print("The configuration file IONOS-FAS.ini does not exist")

  scaleSection=request.args.get('Sgroup')
  looping=config.sections()
  for i in looping:
    if i != scaleSection:
      continue
    else:
      serveruuid=config[i]['serverID']
      lbuuid=config[i]['loadbalancerID']
      dcuuid=config[i]['datacenterID']
      min=config[i]['min']
      max=config[i]['max']
#      cooldown=config[i]['cooldown']
      cooldown=""
      lanid=config[i]['lanID']
      forwardruleuuid=config[i]['forwardingID']
  scaleDownOf=request.args.get('addSrv')
  if scaleDownOf is None:
    scaleDownOf='1'
  tot=(scaleDown(forwardruleuuid,lanid,min,max,cooldown,apiEndpoint,scaleSection,scaleDownOf,dcuuid,serveruuid,lbuuid))
  return tot

@app.route('/scaleup')
def scaleup_query():
# Load the configuration file
  try:
    config = configparser.ConfigParser()
    config.read('IONOS-FAS.ini')
  except:
    print("The configuration file IONOS-FAS.ini does not exist")

  scaleSection=request.args.get('Sgroup')
  force=request.args.get('force')
  force=bool(force)
  looping=config.sections()
  for i in looping:
    if i != scaleSection:
      continue
    else:
      serveruuid=config[i]['serverID']
      lbuuid=config[i]['loadbalancerID']
      dcuuid=config[i]['datacenterID']
      min=config[i]['min']
      max=config[i]['max']
#      cooldown=config[i]['cooldown']
      cooldown=""
      lanid=config[i]['lanID']
      forwardruleuuid=config[i]['forwardingID']
  scaleUpOf=request.args.get('addSrv')
  if scaleUpOf is None:
      scaleUpOf='1'
  tot=(scaleUp(forwardruleuuid,lanid,min,max,cooldown,force,apiEndpoint,scaleSection,scaleUpOf,dcuuid,serveruuid,lbuuid))
  return tot

@app.route('/snapshot')
def snapshot_query():
# Load the configuration file
  try:
    config = configparser.ConfigParser()
    config.read('IONOS-FAS.ini')
  except:
    print("The configuration file IONOS-FAS.ini does not exist")

  scaleSection=request.args.get('Sgroup')
  looping=config.sections()
  for i in looping:
    if i != scaleSection:
      continue
    else:
      serveruuid=config[i]['serverID']
      dcuuid=config[i]['datacenterID']
  tot=(only_take_snapshot(apiEndpoint,scaleSection,dcuuid,serveruuid))
  return tot
if __name__ == '__main__':
  app.run(debug=True)