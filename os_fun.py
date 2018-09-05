import os
import sys
import time
import readline
import json
from array import array

def keypair_exists(nova ,key_name):
	
	keypair_exists = False
	
	list1 = nova.keypairs.list()
	for x in list1:
		if x.name == key_name:
			keypair_exists= True 
	
	return keypair_exists
def decide_zone(nova, temp_list, temp_list1):
 resp=[0] * 3
 resp1=[0] * 3
 zone='none'
 ram_gb = temp_list['free_ram_mb']/1024
 vcpus_available = int(temp_list['vcpus'])-int(temp_list['vcpus_used'])
 resp[0]=int(vcpus_available)
 resp[1]=int(ram_gb)
 resp[2]=int(temp_list['free_disk_gb'])
 flag=0
 flag1=0
 ram_gb = temp_list1['free_ram_mb']/1024
 vcpus_available = int(temp_list1['vcpus'])-int(temp_list1['vcpus_used'])
 resp1[0]=vcpus_available
 resp1[1]=int(ram_gb)
 resp1[2]=int(temp_list1['free_disk_gb'])
 if (resp[0] - resp1[0] > 0):
   flag=flag+1
 else:
   flag1=flag1+1
 if (resp[1] - resp1[1] > 0):
   flag=flag+1
 else:
   flag1=flag1+1
 if (resp[2] - resp1[2] > 0):
   flag=flag+1
 else:
   flag1=flag1+1

 # print resp[0]
 # print resp[1]
 # print resp[2]
 # print resp1[0] 
 
 
 # print resp1[1]
 
 
 # print resp1[2]
 # print (resp[0] - resp1[0])
 # print (resp[1] - resp1[1])
 # print (resp[2] - resp1[2])
 # print (flag)
 # print (flag1)
 if (flag1 > flag):
   zone = 'compute2'
 elif (flag1 < flag):
   zone = 'compute1'
 else:
   zone = 'compute2'
 return zone  
def check_resource(nova, node, temp_list):
 print ("Checking Resources on " + node)
 min_vcpus_required = 0
 min_ram_required = 0
 min_disk_required = 0
 
 if 'Compute 1' in node:
  min_vcpus_required = 10
  min_ram_required = 20
  min_disk_required = 200
 elif 'Compute 2' in node:
  min_vcpus_required = 10
  min_ram_required = 20
  min_disk_required = 200
 
 resource_check = False
 memory_true = False
 disk_true = False
 vcpu_true = False
 
 ram_gb = temp_list['free_ram_mb']/1024
 
 vcpus_available = int(temp_list['vcpus'])-int(temp_list['vcpus_used'])
 info_msg = "vCPUs available are " + str(vcpus_available)
 info_msg = "Memory available in GBs is " + str(ram_gb)
 info_msg = "Disk available in GBs is " + str(temp_list['free_disk_gb'])
 if( vcpus_available >= min_vcpus_required):
  vcpu_true = True

 if( int(ram_gb) >= min_ram_required):
  memory_true = True

 if( int(temp_list['free_disk_gb']) >= min_disk_required):
  disk_true = True
 
 if vcpu_true:
  if memory_true:
   #if disk_true:
    resource_check = True
   
 print( "Done checking Resources on " + node)
 return resource_check
def image_exists(glance, img_name):
	
	img_exists = False
	
	images = glance.images.list()
	while True:
		try:
			image = images.next()
			if (img_name == image.name):
				img_exists = True
				return img_exists
			#print image.name + ' - ' + image.id
		except StopIteration:
			break
	return img_exists	 
def stack_status(heat, stack_name):
	
  stack_status = False
  stack_details = heat.stacks.get(stack_name)
  if (stack_details.status == 'COMPLETE'):
    print 'stack exists'
    stack_status = True  
  elif stack_details.status == 'CREATE_FAILED':
    print('Stack Creation failed')
  return stack_status	
def stack_exists(heat, stack_name):
	
	stack_exists = False
	
	stack = heat.stacks.list()
	print stack.next()
	while True:
		try:
			stack = stack.next()
			print stack
			if (stack_name == stack.name):
				stack_exists = True
				print 'true'
				return stack_exists
		except StopIteration:
			break
	return stack_exists	
def get_stack_private_ip(heat, cluster_name, PATH):
     temp_list=[]
     cluster_full_name=cluster_name
     cluster_details=heat.stacks.get(cluster_full_name)
     file = open(PATH+ "/Private_net_ip.txt", "a")
     for i in cluster_details.outputs:
       if i['output_key']=='homestead_ip_private':
          homestead_ip_private= i['output_value']
          file.write(homestead_ip_private[0] + ",")
       if i['output_key']=='dns_ip_private':
          dns_ip_private= i['output_value']
          file.write(dns_ip_private + ",")
       if i['output_key']=='homer_ip_private':
          homer_ip_private= i['output_value']
          file.write(homer_ip_private[0] + ",")
       if i['output_key']=='bono_ip_private':
          bono_ip_private= i['output_value']
          file.write(bono_ip_private[0] + ",")
       if i['output_key']=='sprout_ip_private':
          sprout_ip_private= i['output_value']
          file.write(sprout_ip_private[0] + ",")
       if i['output_key']=='ellis_ip_private':
          ellis_ip_private= i['output_value']
          file.write(ellis_ip_private +"," )
       if i['output_key']=='ralf_ip_private':
          ralf_ip_private= i['output_value']
          file.write(ralf_ip_private[0] + ",")
     file.close()
	
     file1 = open(PATH+ "/Private_net_ip.txt", "r")
     Stack_private_ip= file1.read()
     file1.close()
     return Stack_private_ip