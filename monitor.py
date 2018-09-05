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
Index = 2
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


############################## logging ####################################################
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
#################################### Get Homestead IP ###########################################

def get_homestead_ip(heat, cluster_name):
   temp_list=[]
   cluster_full_name=cluster_name
   cluster_details=heat.stacks.get(cluster_full_name)
   
   for i in cluster_details.outputs:
     if i['output_key']=='homestead_ip':
        homestead_ip= i['output_value']
   return homestead_ip[0]
homestead_ip = get_homestead_ip(heatclient , STACK_NAME)

#################################### Get Sprout IP ############################################
def get_sprout_ip(heat, cluster_name):
   temp_list=[]
   cluster_full_name=cluster_name
   cluster_details=heat.stacks.get(cluster_full_name)
   
   for i in cluster_details.outputs:
     if i['output_key']=='sprout_ip':
        sprout_ip= i['output_value']
   return sprout_ip[0]      

sprout_ip = get_sprout_ip(heatclient , STACK_NAME)
sprout_ha_ip = get_sprout_ip(heatclient , STACK_HA_NAME)
SCALE_UP = False
################################## Get Sprout information ###################################
while True:
  
  #Connect to Sprout
  #k = paramiko.RSAKey.from_private_key_file("/root/.ssh/secure.pem")
  ssh = paramiko.SSHClient()
  ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
#  print ("Connecting To Sprout Node with IP " + sprout_ip)
  ssh.connect( hostname = sprout_ip , username = "root", password = "root123" )
#  print ("Connected")
  stdin, stdout, stderr = ssh.exec_command("sudo -s")  
  
  
  #print('Checking MIB libraries')
  #stdin, stdout, stderr = ssh.exec_command("snmpwalk -v2c -c clearwater localhost PROJECT-CLEARWATER-MIB::dataConnection")
  #while not stdout.channel.exit_status_ready():
  #	# Only print data if there is data to read in the channel 
  #	if stdout.channel.recv_ready():
  #		rl, wl, xl = select.select([stdout.channel], [], [], 0.0)
  #		if len(rl) > 0:
  #			# Print data from stdout
  #			print stdout.channel.recv(1024),
      
  os.system('clear')
      
  # stdin, stdout, stderr = ssh.exec_command("snmpwalk -v2c -c clearwater localhost PROJECT-CLEARWATER-MIB::homesteadIncomingRequestsCount.scopeCurrent5MinutePeriod ")
  # mib_data = stdout.read()
  # mib_data = str(mib_data)
  # data = mib_data.split()
  # no_of_incomming_requests =  data[3]
  
  stdin, stdout, stderr = ssh.exec_command("snmpwalk -v2c -c clearwater localhost PROJECT-CLEARWATER-MIB::sproutRejectedOverloadCount.scopeCurrent5MinutePeriod")
  mib_data = stdout.read()
  mib_data = str(mib_data)
  data = mib_data.split()
  no_of_rejected_requests_1 =  data[3]
  
  stdin, stdout, stderr = ssh.exec_command("snmpwalk -v2c -c clearwater localhost .1.3.6.1.4.1.2021.11.9.0")
  mib_data = stdout.read()
  mib_data = str(mib_data)
  data = mib_data.split()
  CPU_load_sprout_1 =  data[3]

  #Connect to Sprout
  #k = paramiko.RSAKey.from_private_key_file("/root/.ssh/secure.pem")
  ssh = paramiko.SSHClient()
  ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
#  print ("Connecting To Sprout Node with IP " + sprout_ha_ip)
  ssh.connect( hostname = sprout_ha_ip , username = "root", password = "root123" )
#  print ("Connected")
  stdin, stdout, stderr = ssh.exec_command("sudo -s")  
  
  
  #print('Checking MIB libraries')
  #stdin, stdout, stderr = ssh.exec_command("snmpwalk -v2c -c clearwater localhost PROJECT-CLEARWATER-MIB::dataConnection")
  #while not stdout.channel.exit_status_ready():
  # # Only print data if there is data to read in the channel 
  # if stdout.channel.recv_ready():
  #   rl, wl, xl = select.select([stdout.channel], [], [], 0.0)
  #   if len(rl) > 0:
  #     # Print data from stdout
  #     print stdout.channel.recv(1024),
      
  os.system('clear')
      
  # stdin, stdout, stderr = ssh.exec_command("snmpwalk -v2c -c clearwater localhost PROJECT-CLEARWATER-MIB::homesteadIncomingRequestsCount.scopeCurrent5MinutePeriod ")
  # mib_data = stdout.read()
  # mib_data = str(mib_data)
  # data = mib_data.split()
  # no_of_incomming_requests =  data[3]
  
  stdin, stdout, stderr = ssh.exec_command("snmpwalk -v2c -c clearwater localhost PROJECT-CLEARWATER-MIB::sproutRejectedOverloadCount.scopeCurrent5MinutePeriod ")
  mib_data = stdout.read()
  data = mib_data.split()
  no_of_rejected_requests_2 =  data[3]
  
  stdin, stdout, stderr = ssh.exec_command("snmpwalk -v2c -c clearwater localhost .1.3.6.1.4.1.2021.11.9.0")
  mib_data = stdout.read()
  mib_data = str(mib_data)
  data = mib_data.split()
  CPU_load_sprout_2 =  data[3]
  #Connect to Homestead
  #k = paramiko.RSAKey.from_private_key_file("/root/.ssh/secure.pem")
  ssh = paramiko.SSHClient()
  ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
#  print ("Connecting To Homestead Node with IP " + homestead_ip)
  ssh.connect( hostname = homestead_ip , username = "root", password = "root123" )
#  print ("Connected")
  stdin, stdout, stderr = ssh.exec_command("sudo -s")  
  
  
  #print('Checking MIB libraries')
  #stdin, stdout, stderr = ssh.exec_command("snmpwalk -v2c -c clearwater localhost PROJECT-CLEARWATER-MIB::dataConnection")
  #while not stdout.channel.exit_status_ready():
  # # Only print data if there is data to read in the channel 
  # if stdout.channel.recv_ready():
  #   rl, wl, xl = select.select([stdout.channel], [], [], 0.0)
  #   if len(rl) > 0:
  #     # Print data from stdout
  #     print stdout.channel.recv(1024),
      
  os.system('clear')
      
  stdin, stdout, stderr = ssh.exec_command("snmpwalk -v2c -c clearwater localhost PROJECT-CLEARWATER-MIB::homesteadIncomingRequestsCount.scopeCurrent5MinutePeriod ")
  mib_data = stdout.read()
  mib_data = str(mib_data)
  data = mib_data.split()
  no_of_incomming_requests =  data[3]
  

  try:
    num1 = int(no_of_rejected_requests_1)
  except:
    print num1
  try: 
    num2 = int(no_of_rejected_requests_2)
  except:
    print num2
  try:
  	incomming_requests = int(no_of_incomming_requests)
  except:
  	incomming_requests = 0
  try:  
    threshold = num1 + num2
  except:
    threshold = '0'


  print ('************************************************************************')
  print ('Number of incomming total rejected requests in the current 5 minute period due to overload= '+ str(threshold) )
  print ('CPU load Sprout 1 = '+CPU_load_sprout_1)
  print ('CPU load Sprout 2 = '+CPU_load_sprout_2)
  print ('************************************************************************')
  
  if (int(threshold) > 10):
    SCALE_UP = True    
    Stack_index = str(Index)
    Scale.scale_up(Stack_index)
    Index=Index + 1  

  elif (int(CPU_load_sprout_2) > 30 and int(CPU_load_sprout_1) > 30):
    SCALE_UP = True    
    Stack_index = str(Index)
    Scale.scale_up(Stack_index)
    Index=Index + 1    

  if (incomming_requests < int(CALL_LOWER_THRESHOLD) and int(Index) > 2):

    Index=Index - 1
    SCALE_UP = False
    Stack_index = str(Index)
    Scale_down.scale_down(Stack_index)

    
  time.sleep(30)

  
  