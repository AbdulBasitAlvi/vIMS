import novaclient.v1_1.client as nvclient
import neutronclient.v2_0.client as ntrnclient
import sys
import os
from os_fun import *
from heatclient.client import Client as Heat_Client
from keystoneclient.v2_0 import Client as Keystone_Client
import glanceclient 
import keystoneclient.v2_0.client as ksClient
import json
import time
import paramiko
import select
import Scale
import Scale_down
import glanceclient as glclient
from commands import getoutput
from multiprocessing import Process
from os import system
from time import sleep
#----------------------------------#
from keystoneclient.auth.identity import v2
from keystoneclient import session
from novaclient import client
#----------------------------------#

##################################### File path function ###################################
import subprocess
p = subprocess.Popen(["pwd"], stdout=subprocess.PIPE , shell=True)
PATH = p.stdout.read()
PATH = PATH.rstrip('\n')

############################## Global Variables ##########################################
IMAGE_PATH = PATH+'/vIMS.qcow2'
#COMPRESSED_FILE_PATH = '/root/IMG/vIMS-image.tar.gz'
#IMAGE_DIRECTORY = '/root/IMG/'
SNMP_CONFIG_PATH = '/etc/snmp/snmpd.conf'
SNMP_FILE_PATH = PATH+'/snmpd.conf'
MIB_PATH = "/usr/share/mibs/PROJECT-CLEARWATER-MIB.txt"
#MIB_FILE_PATH = "/root/vIMS/PROJECT-CLEARWATER-MIB.txt"
MIB_FILE_PATH = "/vIMS/PROJECT-CLEARWATER-MIB.txt"
os.environ['IMAGE_PATH'] = PATH+'/IMG'
CONFIG_PATH = PATH+'/configurations.json'
USER_CONFIG_PATH = PATH+'/user_config.json'
STACK_NAME = 'IMS'
REPO_URL = 'http://repo.cw-ngv.com/stable'
ETCD_IP = ''
ELLIS_INDEX = '0'
BONO_INDEX = '0'
SPROUT_INDEX = '0'
HOMESTEAD_INDEX = '0'
HOMER_INDEX = '0'
DN_RANGE_START = '6505550000'
DN_RANGE_LENGTH = '1000'
CALL_THRESHOLD = '20000'
CALL_LOWER_THRESHOLD = '10'
STACK_HA_NAME = 'IMS-HA'
#LOCAL_IP = '10.204.110.42'

############################## User Configuration Functions ##############################

def get_user_configurations():
  file = open(USER_CONFIG_PATH)
  configurations = json.load(file)
  file.close()
  return configurations

print('Getting user confiurations...')
user_config = get_user_configurations()
ext_net = user_config['networks']['external']
ext_net = str(ext_net)
domain = user_config['domain']['zone']
domain = str(domain)

print('Successfull')


############################## logging #####################################################
import logging
import datetime
now = datetime.datetime.now()
date_time = now.strftime("%Y-%m-%d_%H-%M")
filename_activity = PATH+'/logs/deploy_' + date_time + '.log'
filename_error = PATH+'/logs/deploy_error_' + date_time + '.log'

logging.basicConfig(filename=filename_activity, level=logging.INFO, filemode='w', format='%(asctime)s %(levelname)-8s %(name)-23s [-]  %(message)s')

logger=logging.getLogger(__name__)
logger_nova=logging.getLogger('nova')
logger_neutron=logging.getLogger('neutron')
logger_glance = logging.getLogger('glance')
logger_ssh=logging.getLogger('paramiko')
error_logger = logging.getLogger('error_log')

# create logger with 'Error Loging'
error_logger.setLevel(logging.ERROR)
fh = logging.FileHandler(filename_error, mode = 'w')
fh.setLevel(logging.ERROR)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
error_logger.addHandler(fh)
############################## Time Stamp Function ########################################
import sys
from datetime import datetime as dt

old_f = sys.stdout

class F:
    nl = True

    def write(self, x):
        if x == '\n':
            old_f.write(x)
            self.nl = True
        elif self.nl == True:
            old_f.write('%s> %s' % (str(dt.now()), x))
            self.nl = False
        else:
            old_f.write(x)

sys.stdout = F()
############################## Environment Check #########################################

def check_env(logger, error_logger):
  filename = '/etc/*-release'
  try:
    logger.info("opening file to detect the environment")
    #file_read = open(filename, 'r').readlines()
    p = os.popen("cat /etc/*-release","r")
  except:
    error_logger.exception("unable to open file to detect the environment, returning default as CentOS ...")
    return 'CentOS'
  file_read = p.readlines()
  for line in file_read:
    if 'CentOS' in line:
      logger.info("Environment returned CentOS")
      return 'CentOS'
    elif 'Wind River' in line:
      logger.info("Environment returned Wind River")
      return 'Wind River'
    elif 'Ubuntu' in line:
      logger.info("Environment returned Ubuntu")
      return 'Ubuntu'
    elif 'Red Hat' in line:
      logger.info("Environment returned Red Hat")
      return 'Red Hat'
  logger.info("Environment returned unknown-environment")
  return 'unknown-environment'


############################## User Configuration Functions ##############################

def get_user_configurations():
  file = open(USER_CONFIG_PATH)
  configurations = json.load(file)
  file.close()
  return configurations

print('Getting user confiurations...')
logger.info("Getting initial user confiurations.")
user_config = get_user_configurations()
ext_net = user_config['networks']['external']
ext_net = str(ext_net)
domain = user_config['domain']['zone']
domain = str(domain)

print('Successfull')
logger.info("Getting initial user confiurations Successfull.")

############################## Environment Based Credential functions ####################

def keytsone_auth(name, configurations, logger, error_logger):
  keystone = ''
  logger.info("Creating authorized instance of keystone client")
  if name == 'Red Hat':
    # get credentials for keystone
    logger.info("Getting keystone credentials for authorization ...")
    credsks = get_keystone_creds(configurations)
    # get authorized instance of keystone
    logger.info("Getting authorized instance of keystone client")
    try:
      keystone = ksClient.Client(**credsks)
    except:
      error_logger.exception("Unable to create keystone client instance")
      print("[" + time.strftime("%H:%M:%S")+ "] Error creating keystone client, please check logs ...")
      sys.exit()
  elif (name == 'CentOS') or (name == 'Wind River') or (name == 'Ubuntu'):
    try:
      keystone = ksClient.Client(auth_url = configurations['os-creds']['os-authurl'],
                   username = configurations['os-creds']['os-user'],
                   password = configurations['os-creds']['os-pass'],
                   tenant_name = configurations['os-creds']['os-tenant-name'])
      
    except:
      error_logger.exception("Unable to create keyclient instance...")
      print ("[" + time.strftime("%H:%M:%S")+ "] Error creating keystone client, please check logs ...")
      sys.exit()
  logger.info("Authorized keystone instance ....")
  logger.info("Environment is " + name + " ...")
  return keystone

#========================================================#
def nova_auth(name, configurations, logger_nova, error_logger):
  nova_creds = get_nova_creds(configurations)
  nova = ''
  logger_nova.info("Creating authorized instance of nova client instance ...")
  if name == 'Red Hat':
    # get authorized instance of nova client
    logger_nova.info("Getting authorized instance to use Nova client API ...")
    try:
      auth = v2.Password(auth_url = nova_creds['auth_url'],
                username = nova_creds['username'],
                password = nova_creds['password'],
                tenant_name = nova_creds['project_id'])
      sess = session.Session(auth = auth)
      nova = client.Client(nova_creds['version'], session = sess)
    except:
      error_logger.exception("Unable to create nova client instance")
      print("[" + time.strftime("%H:%M:%S")+ "] Error authorizing nova client, please check logs ...")
      sys.exit()
  elif (name == 'CentOS') or (name == 'Wind River') or (name == 'Ubuntu'):
    try:      
      nova = client.Client('1.1', configurations['os-creds']['os-user'], 
                configurations['os-creds']['os-pass'], configurations['os-creds']['os-tenant-name'], 
                configurations['os-creds']['os-authurl'])
      
    except:
      error_logger.exception("Unable to create nova client instance ...")
      print ("[" + time.strftime("%H:%M:%S")+ "] Error authorizing nova client, please check logs ...")
      sys.exit()
  logger_nova.info("Authorized nova instance ....")
  logger_nova.info("Environment is " + name + " ...")
  return nova
#=========================================================#
def neutron_auth(name, configurations, logger_neutron, error_logger):
  credsks = get_keystone_creds(configurations)
  neutron = ''
  logger_neutron.info("Creating authorized instance of neutron client instance ...")
  if name == 'Red Hat':
    # get authorized instance of neutron client
    logger_neutron.info("Getting authorized instance of neutron client")
    try:
      neutron = ntrnclient.Client(**credsks)
    except:
      error_logger.exception("Unable to create neutron client instance")
      print("[" + time.strftime("%H:%M:%S")+ "] Error authorizing neutron client API, please check logs ...")
      sys.exit()
  elif (name == 'CentOS') or (name == 'Wind River') or (name == 'Ubuntu'):
    try:
      neutron = ntrnclient.Client(auth_url = configurations['os-creds']['os-authurl'],
                   username = configurations['os-creds']['os-user'],
                   password = configurations['os-creds']['os-pass'],
                   tenant_name = configurations['os-creds']['os-tenant-name'],
                   region_name = configurations['os-creds']['os-region-name'])
    except:
      error_logger.exception("Unable to create neutron client instance")
      print ("[" + time.strftime("%H:%M:%S")+ "] Error creating neutron client, please check logs ...")
      sys.exit()
  logger_neutron.info("Authorized neutron instance ....")
  logger_neutron.info("Environment is " + name + " ...")
  return neutron
#========================================================#
def glance_auth(name, configurations, keystone, logger_glance, error_logger):
  glance = ''
  logger_glance.info("Creating authorized instance of glance client instance ...")
  if name == 'Red Hat':
    #authorizing glance client
    logger_glance.info("Getting authorized instance of glance client")
    try:
      glance_endpoint = keystone.service_catalog.url_for(service_type = 'image', endpoint_type = 'publicURL')
      glance = glanceclient.Client('2', glance_endpoint, token = keystone.auth_token)
    except:
      error_logger.exception("Unable to create glance client instance")
      print("[" + time.strftime("%H:%M:%S")+ "] Error creating glance client, please check logs ...")
      sys.exit()
  elif (name == 'CentOS') or (name == 'Wind River') or (name == 'Ubuntu'):
    try:
      glance_endpoint = keystone.service_catalog.url_for(service_type = 'image', endpoint_type = 'publicURL')
      glance = glclient.Client('2', glance_endpoint, token = keystone.auth_token)
    except:
      error_logger.exception("Unable to create glance client instance")
      print ("[" + time.strftime("%H:%M:%S")+ "] Error creating glance client, please check logs ...")
      sys.exit()
  logger_glance.info("Authorized glance instance ....")
  logger_glance.info("Environment is " + name + " ...")
  return glance

############################## Keystone Credentials Functions ############################

def get_keystone_creds(configurations):
    d = {}
    d['username'] = configurations['os-creds']['os-user']
    d['password'] = configurations['os-creds']['os-pass']
    d['auth_url'] = configurations['os-creds']['os-authurl']
    d['tenant_name'] = configurations['os-creds']['os-tenant-name']
    return d

def get_nova_creds(configurations):
  d = {}
  d['username'] = configurations['os-creds']['os-user']
  d['api_key'] = configurations['os-creds']['os-api-key']
  d['password'] = configurations['os-creds']['os-pass']
  d['auth_url'] = configurations['os-creds']['os-authurl']
  d['project_id'] = configurations['os-creds']['os-project-id']
  d['version'] = "1.1"
  return d

print('Getting credentials')  
logger.info("Getting client credentials")
def get_configurations():
  file = open(CONFIG_PATH)
  configurations = json.load(file)
  file.close()
  return configurations
print('Credentials Loaded')
 
# Get configurations from file
config = get_configurations()

#################################### Credential Functions ######################################
#check OS environment
name = check_env(logger, error_logger)

config = get_configurations()
print ('Environment is ' + name)
#authenticating client APIs

if name != 'unknown-environment':
  
  keystone = keytsone_auth(name, config, logger, error_logger)

  nova = nova_auth(name, config, logger_nova, error_logger)

  neutron = neutron_auth(name, config, logger_neutron, error_logger)

  glance = glance_auth(name, config, keystone, logger_glance, error_logger)
else:
  name = 'CentOS'
  keystone = keytsone_auth(name, config, logger, error_logger)

  nova = nova_auth(name, config, logger_nova, error_logger)

  neutron = neutron_auth(name, config, logger_neutron, error_logger)

  glance = glance_auth(name, config, keystone, logger_glance, error_logger)
##

heat_endpoint = keystone.service_catalog.url_for(service_type='orchestration', endpoint_type='publicURL')
heatclient = Heat_Client('1', heat_endpoint, token=keystone.auth_token, username='admin', passwork='admin')


############################################################################################

print('Please enter the number of stress test nodes to spawn')
number = raw_input()
if number == '0':
  sys.exit()
stack_index = '1'
##################################### getting private ip address of stack ###################################

file1 = open(PATH+ "/test_index.txt", "r")
test_index = file1.read()
test_index = int(test_index)
number = int(number)
number = number + test_index
file2 = open(PATH+ "/test_index.txt", "w")
file2.write(str(number))
file2.close()

while(int(test_index) != int(number) ):
    ############################## logging #####################################################
    import logging
    import datetime											
    now = datetime.datetime.now()
    date_time = now.strftime("%Y-%m-%d_%H-%M")
    filename_activity = PATH+'/logs/Stress_test_' + date_time + '.log'
    filename_error = PATH+'/logs/Stress_test_error_' + date_time + '.log'

    logging.basicConfig(filename=filename_activity, level=logging.INFO, filemode='w', format='%(asctime)s %(levelname)-8s %(name)-23s [-]  %(message)s')

    logger=logging.getLogger(__name__)
    logger_nova=logging.getLogger('nova')
    logger_neutron=logging.getLogger('neutron')
    logger_glance = logging.getLogger('glance')
    logger_ssh=logging.getLogger('paramiko')
    error_logger = logging.getLogger('error_log')

    # create logger with 'Error Loging'
    error_logger.setLevel(logging.ERROR)
    fh = logging.FileHandler(filename_error, mode = 'w')
    fh.setLevel(logging.ERROR)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    error_logger.addHandler(fh)

    test_index = int(test_index)
    test_index = test_index + 1
    test_index = str(test_index)

    ############################## Global Variables ##########################################
    os.environ['IMAGE_PATH'] = PATH+'/IMG'
    CONFIG_PATH = PATH+'/configurations.json'
    USER_CONFIG_PATH = PATH+'/user_config.json'
    STACK_NAME = 'Test'+test_index
    REPO_URL = 'http://repo.cw-ngv.com/stable'
    ############################## User Configuration Functions ##############################

    def get_user_configurations():
    	file = open(USER_CONFIG_PATH)
    	configurations = json.load(file)
    	file.close()
    	return configurations

    print('Getting user confiurations...')
    logger.info("Getting user confiurations.")
    user_config = get_user_configurations()
    ext_net = user_config['networks']['external']
    ext_net = str(ext_net)
    domain = user_config['domain']['zone']
    domain = str(domain)

    print('Successfull')
    logger.info("Getting user confiurations Successfull.")
    ############################## Keystone Credentials Functions ############################

    def get_keystone_creds(configurations):
        d = {}
        d['username'] = configurations['os-creds']['os-user']
        d['password'] = configurations['os-creds']['os-pass']
        d['auth_url'] = configurations['os-creds']['os-authurl']
        d['tenant_name'] = configurations['os-creds']['os-tenant-name']
        return d

    def get_nova_creds(configurations):
    	d = {}
    	d['username'] = configurations['os-creds']['os-user']
    	d['api_key'] = configurations['os-creds']['os-api-key']
    	d['auth_url'] = configurations['os-creds']['os-authurl']
    	d['project_id'] = configurations['os-creds']['os-project-id']
    	return d
    print('Getting credentials')  
    def get_configurations():
    	file = open(CONFIG_PATH)
    	configurations = json.load(file)
    	file.close()
    	return configurations
    print('Credentials Loaded')
    logger.info("Credentials Loaded")  
    config = get_configurations()
    logger.info("Getting keystone credentials")
    credsks = get_keystone_creds(config)
    logger_nova.info("Getting Nova Credentials")
    creds = get_nova_creds(config)

    # Get authorized instance of nova client
    # logger_nova.info("Getting authorized instance of nova client")
    # nova = nvclient.Client(**creds)   
    # # Get authorized instance of neutron client
    # logger_neutron.info("Get authorized instance of neutron client")
    # neutron = ntrnclient.Client(**credsks)

    ############################## Create Ubuntu 14.04 Image ###################################

    #os.system("sudo -s")
    #os.system("mkdir $IMAGE_PATH")
    #os.system("cd $IMAGE_PATH")
    #os.system("wget http://cloud-images.ubuntu.com/trusty/current/trusty-server-cloudimg-amd64-disk1.img")

    # Get authorized instance of glance client
    #creden = get_keystone_creds(config)
    #keystone = ksClient.Client(**creden)
    #glance_endpoint = keystone.service_catalog.url_for(service_type='image', endpoint_type='publicURL')
    #glance = glanceclient.Client('2',glance_endpoint, token=keystone.auth_token)
    #
    #image = glance.images.create(name="IMS",disk_format = 'ami',container_format = 'ami')
    #image = glance.images.upload(image.id, open(IMAGE_PATH, 'rb'))
    #print ('Successfully added image')

    ############################# Create Availability Zones #################################

    def get_aggnameA():   
       return 'GroupA'
    def get_aggnameB():
       return 'GroupB'

    def get_avlzoneA():
       return 'compute1'
    def get_avlzoneB():
       return 'compute2'

    def create_agg(nova):
     hyper_list = nova.hypervisors.list()
     hostnA = hyper_list[0].service['host']
     print hostnA
     try:
       logger_nova.info("Creating aggregate group and availability zone for A")
       agg_idA = nova.aggregates.create(get_aggnameA(), get_avlzoneA())
     except:
       error_logger.exception("Unable to create nova aggregate group A and availability zone A")
       print('Error')
       pass
     try:
       logger_nova.info("creating nova aggregate group B and availability zone B")
       agg_idB = nova.aggregates.create(get_aggnameB(), get_avlzoneB())
     except:
       print('Error')
       error_logger.exception("Unable to create nova aggregate group B and availability zone B")
       pass
     try:
       logger_nova.info("Adding host to nova aggregate group A")
       nova.aggregates.add_host(aggregate=agg_idA, host=hostnA)
     except:
       print('Error')
       error_logger.exception("Error in adding host to nova aggregate group A")
       pass
     try:
       logger_nova.info("Adding host to nova aggregate group B")
       nova.aggregates.add_host(aggregate=agg_idB, host=hostnB)
     except:
       error_logger.exception("Error in adding host to nova aggregate group B")
       print('Error')
       pass

    print('Successfully added availaibility zones')
    logger.info("Successfully added availaibility zones")
    ########################### Fetch network ID of network netname ###########################

    def get_network_id(netname, neutron):
    	netw = neutron.list_networks()
    	for net in netw['networks']:
    		if(net['name'] == netname):
    			# print(net['id'])
    			return net['id']
    	return 'net-not-found'

    net_id = get_network_id(netname= ext_net, neutron = neutron)
    net_id = str(net_id)
    print ('Network ID of external network =' + net_id)
    logger.info("Fetch network ID of network netname")
    ############################### Create Keypair #########################################

    # Creating a keypair
    print('Creating Keypair')
    try:
        keypair = nova.keypairs.create(name = 'test')
        # Open a file for storing the private key
        f_private = open('/root/.ssh/test.pem', "w")
        # Store the private key
        f_private.write(keypair.private_key)
        f_private.close()
        # Open a file for storing the public key
        f_public = open('/root/.ssh/test.pub', "w")
        # Store the public key
        f_public.write(keypair.public_key)
        f_public.close()
        print('Finished Creating Keypairs')
    except:
        print('keypair already exists')
    ########################### Fetch network ID of private network ###########################

    def get_private_id(netname, neutron):
    	netw = neutron.list_networks()
    	for net in netw['networks']:
    		if(net['name'] == netname):
    			# print(net['id'])
    			return net['id']
    	return 'net-not-found'

    private_id = get_network_id('IMS-private', neutron = neutron)
    private_id = str(private_id)
    print ('Network ID of private network = ' + private_id)
    logger.info("Fetch network ID of private network")
    ############################## Heat Stack Create ##########################################
    def create_cluster(heat,cluster_name):
      cluster_full_name=STACK_NAME

      file_main= open(PATH+'/test.yaml', 'r')                

      cluster_body={
       "stack_name":cluster_full_name,
       "template":file_main.read(),
       "parameters": {
       "public_net_id": net_id,
       "zone" : domain,
       "flavor": "m1.medium",
       "image": "IMS",     
    	 "key_name":"test",
       "private_net_id": private_id
     #    "availability_zone":"compute1"
         }
        }
      #try:  
      logger.info("Create Heat stack")
      heat.stacks.create(**cluster_body)
      #except:
      #print ("There is an error creating cluster, exiting...")
      #sys.exit()
      print ("Creating stack "+ cluster_full_name )

    ########################### Create Heat Stack from credentials of keystone #####################
    # logger.info("Getting Keystone credentials")
    # cred = get_keystone_creds(config)
    # logger.info("creating keystone client")
    # ks_client = Keystone_Client(**cred)
    logger.info("creating heat endpoint")
    heat_endpoint = keystone.service_catalog.url_for(service_type='orchestration', endpoint_type='publicURL')
    logger.info("creating heat client")
    heatclient = Heat_Client('1', heat_endpoint, token=keystone.auth_token, username='admin', passwork='admin')
    create_cluster(heatclient,STACK_NAME)
    #stack = heatclient.stacks.list()
    #print stack.next()
    logger.info("deploying heat stack")
    print('Please wait while stack is deployed.......')
    #time.sleep(180)
    cluster_details=heatclient.stacks.get(STACK_NAME)
    while(cluster_details.status!= 'COMPLETE'):
       time.sleep(30)
       if cluster_details.status == 'IN_PROGRESS':
         print('Stack Creation in progress..')
       cluster_details=heatclient.stacks.get(STACK_NAME) 

    ######################################## Get Bono IP ##########################################

    def get_bono_ip(heat, cluster_name):
       temp_list=[]
       cluster_full_name=cluster_name
       cluster_details=heat.stacks.get(cluster_full_name)
       
       for i in cluster_details.outputs:
         if i['output_key']=='bono_ip':
            bono_ip= i['output_value']
       return bono_ip[0]

    #Get Bono IP
    logger.info("Getting bono IP")
    bono_ip = get_bono_ip(heatclient , 'IMS')
    ##################################### Get Node IP ################################################

    def get_node_ip(heat, cluster_name):
       cluster_full_name=cluster_name
       cluster_details=heat.stacks.get(cluster_full_name)
       
       for i in cluster_details.outputs:
         if i['output_key']=='public_ip':
            public_ip= i['output_value']
       return public_ip

    ################################# Configure Test Node #########################################
    #Get Node IP
    logger.info("configure test node")
    logger.info("getting node IP")
    node_ip = get_node_ip(heatclient , STACK_NAME)
    print('Waiting for the test node to spawn...')
    time.sleep(60) # wait for VM to spawn
    #Connect to Node
    while True:
      try:
    #    k = paramiko.RSAKey.from_private_key_file("/root/.ssh/test.pem")
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        logger_ssh.info("Connecting To Test Node")
        print ("Connecting To Test Node with IP " + node_ip)
        ssh.connect( hostname = node_ip , username = "root", password = "root123" )
        logger_ssh.info("Connected To Test Node")
        print ("Connected")
        break
      except:
        error_logger.exception("Unable to connect to test node")
        print("Could not connect. Retrying in 5 seconds...")
        time.sleep(5)    

    stdin, stdout, stderr = ssh.exec_command("(hostname -I)")
    node_host = stdout.read()
    node_host = str(node_host)

    # Configure the APT software source.
    print("Configuring APT software source")
    logger.info("Configuring APT software source")
    stdin, stdout, stderr = ssh.exec_command("echo 'deb "+REPO_URL+" binary/' > /etc/apt/sources.list.d/clearwater.list")
    stdin, stdout, stderr = ssh.exec_command("curl -L http://repo.cw-ngv.com/repo_key | apt-key add -")

    print('Updating Ubuntu..')
    logger.info("Updating Ubuntu.")
    stdin, stdout, stderr = ssh.exec_command("apt-get update")
    while not stdout.channel.exit_status_ready():
    	# Only print data if there is data to read in the channel 
    	if stdout.channel.recv_ready():
    		rl, wl, xl = select.select([stdout.channel], [], [], 0.0)
    		if len(rl) > 0:
    			# Print data from stdout
    			print stdout.channel.recv(1024),
          
    # Configure /etc/clearwater/local_config.
    print ("Configuring clearwater local settings")
    logger.info("Configuring clearwater local settings")
    stdin, stdout, stderr = ssh.exec_command("mkdir -p /etc/clearwater")
    stdin.flush()
    stdin, stdout, stderr = ssh.exec_command("cat > /etc/clearwater/local_config")
    stdin.write('local_ip='+node_host+'\n')
    stdin.flush()
    stdin.write('public_ip='+node_ip+'\n')
    stdin.flush()
    stdin.channel.shutdown_write()

    # Configure and upload /etc/clearwater/shared_config.
    print ("Configuring clearwater shared settings")
    logger.info("Configuring clearwater shared settings")
    stdin, stdout, stderr = ssh.exec_command("cat > /etc/clearwater/shared_config")
    stdin.write('home_domain='+domain+'\n')
    stdin.flush()
    stdin.write('bono_servers='+bono_ip+'\n')
    stdin.flush()
    stdin.write('stress_target='+bono_ip+'\n')
    stdin.flush()
    stdin.channel.shutdown_write()

    # Configure /etc/clearwater/local_config.
    print ("Configuring clearwater local settings")
    logger.info("Configuring clearwater local settings")
    stdin, stdout, stderr = ssh.exec_command("mkdir -p /etc/clearwater")
    stdin.flush()
    stdin, stdout, stderr = ssh.exec_command("cat > /etc/clearwater/local_config")
    stdin.write('local_ip='+node_host+'\n')
    stdin.flush()
    stdin.write('public_ip='+node_ip+'\n')
    stdin.flush()
    stdin.channel.shutdown_write()

    # Configure and upload /etc/clearwater/shared_config.
    print ("Configuring clearwater shared settings")
    logger.info("Configuring clearwater shared settings")
    stdin, stdout, stderr = ssh.exec_command("cat > /etc/clearwater/shared_config")
    stdin.write('home_domain='+domain+'\n')
    stdin.flush()
    stdin.write('bono_servers='+bono_ip+'\n')
    stdin.flush()
    stdin.write('stress_target='+bono_ip+'\n')
    stdin.flush()
    stdin.channel.shutdown_write()

    #Install Software
    stdin, stdout, stderr = ssh.exec_command("sudo DEBIAN_FRONTEND=noninteractive apt-get install clearwater-sip-stress --yes")
    while not stdout.channel.exit_status_ready():
    	# Only print data if there is data to read in the channel 
    	if stdout.channel.recv_ready():
    		rl, wl, xl = select.select([stdout.channel], [], [], 0.0)
    		if len(rl) > 0:
    			# Print data from stdout
    			print stdout.channel.recv(1024),
    while True:	
      if(not stdout.read()):
        stdin, stdout, stderr = ssh.exec_command("sudo DEBIAN_FRONTEND=noninteractive apt-get install clearwater-sip-stress --yes")
        print('Retrying Installation...')
        time.sleep(5)	
      else:
        break      

    #Install Software
    stdin, stdout, stderr = ssh.exec_command("sudo DEBIAN_FRONTEND=noninteractive apt-get install clearwater-sip-stress --yes")
    while not stdout.channel.exit_status_ready():
    	# Only print data if there is data to read in the channel 
    	if stdout.channel.recv_ready():
    		rl, wl, xl = select.select([stdout.channel], [], [], 0.0)
    		if len(rl) > 0:
    			# Print data from stdout
    			print stdout.channel.recv(1024),
    while True:	
      if('Err' in stdout.read()):
        stdin, stdout, stderr = ssh.exec_command("sudo DEBIAN_FRONTEND=noninteractive apt-get install clearwater-sip-stress --yes")
        print('Retrying Installation...')
        time.sleep(5)	
      else:
        break      

    stdin, stdout, stderr = ssh.exec_command("sudo DEBIAN_FRONTEND=noninteractive apt-get install clearwater-sip-stress --yes")    
    print('Finished installing software')
    logger.info("Finished installing software")