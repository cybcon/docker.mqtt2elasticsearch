# -*- coding: utf-8 -*-
""" ***************************************************************************
mqtt2elasticsearch.py - a tool that subscribes to mqtt topics and writes the
  messages to an Elasticsearch database
Author: Michael Oberdorf
Date: 2019-03-14
Last modified by: Michael Oberdorf
Last changed at: 2023-10-30
*************************************************************************** """
import os
import sys
import json
import logging
import paho.mqtt.client as mqtt
from datetime import datetime
from elasticsearch import Elasticsearch

VERSION='1.0.0'

CONFIG_FILE='/app/etc/mqtt2elasticsearch.json'
if 'CONFIG_FILE' in os.environ:
  CONFIG_FILE=os.environ['CONFIG_FILE']
with open(CONFIG_FILE) as f: CONFIG = json.load(f)

ELASTICSEARCH_MAPPING_FILE='/app/etc/mqtt2elasticsearch-mappings.json'
if 'ELASTICSEARCH_MAPPING_FILE' in os.environ:
  ELASTICSEARCH_MAPPING_FILE=os.environ['ELASTICSEARCH_MAPPING_FILE']
with open(ELASTICSEARCH_MAPPING_FILE) as f: topic2index = json.load(f)

"""
###############################################################################
# F U N C T I O N S
###############################################################################
"""


def prepareElasticsearchIndex(index: str) -> str:
  """
  prepareElasticsearchIndex
  @desc: replace tokens in elasticsearch index name
  @param: index, str(): The Elasticsearch index name with placeholders
  @return: str(): The resolved Elasticsearch index name
  """

  elasticIndex = index.replace('{Y}', datetime.today().strftime("%Y")).replace('{m}', datetime.today().strftime("%m")).replace('{d}', datetime.today().strftime("%d"))

  if index != elasticIndex:
    log.debug('Replacing placeholders in Elasticsearch index name:')
    log.debug('  OLD: {}'.format(index))
    log.debug('  NEW: {}'.format(elasticIndex))

  return(elasticIndex)


def createElasticsearchIndex(index: str, body: dict):
  """
  createElasticsearchIndex
  @desc: creates a new index in Elasticsearch DB if not exist
  @param index, str(): Elasticsearch index name
  @param body, dict(): Elasticsearch index settings and mappings
  @return: None
  """

  index = prepareElasticsearchIndex(index)

  if not es.indices.exists(index=index):
    log.debug('Creating elasticsearch index: {}{}'.format(CONFIG['elasticsearch']['cluster'][0], index))
    log.debug('  {}'.format(body))
    es.indices.create(index=index, body=body)
  else:
    log.debug('Skip creation of elasticsearch Index, because it already exists.')

  return(None)


def removeElasticsearchIndex(index: str, exitAfterRemoval: bool = True):
  """
  removeElasticsearchIndex
  @desc: removes an index in Elasticsearch DB if exist
  @param index, str(): Elasticsearch index name
  @param exitAfterRemoval, bool(): Exit after removing index (default: True)
  @return: None
  """

  index = prepareElasticsearchIndex(index)

  if es.indices.exists(index=index):
    log.debug('Removing elasticsearch Index: {}'.format(index))
    es.indices.delete(index=index)
  else:
    log.debug('Skip to removing elasticsearch Index, because it is not existing.')

  if exitAfterRemoval:
    log.debug('End program after removing index.')
    sys.exit()
  else:
    return(None)


def on_connect(client, userdata, flags, rc):
  """
  on_connect
  @desc: Function call when (re-)connecting to the MQTT broker. We subscribe
    here to the relevant topics.
  @param client, paho.mqtt.client.Client(): The object of the MQTT connection
  @param userdata, any: user defined data of any type that is passed as the userdata
     parameter to callbacks. Defined within the Client() constructor.
  @param flags, dict(): JsonString, connection parameters
  @param rc, int(): the return code
  @return: None
  """

  log.debug('After connecting to MQTT server:')
  log.debug('- userdata: {}'.format(userdata))
  log.debug('- flags: {}'.format(flags))
  log.debug('- rc: {}'.format(rc))

  # check for return code
  if rc!=0:
    log.error('Error in connecting to MQTT Server, RC={}'.format(rc))
    sys.exit(1)

  # Subscribing in on_connect() means that if we lose the connection and reconnect then subscriptions will be renewed.
  for topic in topic2index.keys():
    log.debug('Subscribe to MQTT topic: {}'.format(topic))
    client.subscribe(topic)

  return(None)


def on_message(client, userdata, msg):
  """
  on_message
  @desc: The MQTT callback for when a PUBLISH message is received from the server.
  @param client, paho.mqtt.client.Client(): The object of the MQTT connection
  @param userdata, any: user defined data of any type that is passed as the userdata
     parameter to callbacks. Defined within the Client() constructor.
  @param msg, paho.mqtt.client.MQTTMessage(): The object of the MQTT message received
  @return: None
  """

  log.debug('MQTT message received:')
  log.debug('- userdata: {}'.format(userdata))

  # prepare index
  index = prepareElasticsearchIndex(topic2index[msg.topic]['elasticIndex'])

  # check if index exist, if not trigger creation
  if not es.indices.exists(index=index):
    createElasticsearchIndex(index, topic2index[msg.topic]['elasticBody']);

  # parse message payload as JSON object
  PAYLOAD = json.loads(str(msg.payload.decode("utf-8")))

  log.info('Add data to elasticsearch index: {}'.format(index))
  res = es.index(index=index, body=json.dumps(PAYLOAD))
  log.debug('{}'.format(res['result']))

  return(None)

"""
###############################################################################
# M A I N
###############################################################################
"""

# initialize logger
log = logging.getLogger()
log_handler = logging.StreamHandler(sys.stdout)
if not 'DEBUG' in CONFIG:
    log.setLevel(logging.INFO)
    log_handler.setLevel(logging.INFO)
else:
  if CONFIG['DEBUG']:
      log.setLevel(logging.DEBUG)
      log_handler.setLevel(logging.DEBUG)
  else:
      log.setLevel(logging.INFO)
      log_handler.setLevel(logging.INFO)
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log_handler.setFormatter(log_formatter)
log.addHandler(log_handler)

log.info('MQTT to Eleasticsearch processor v{} started'.format(VERSION))


# set some defaults
if not 'removeIndex' in CONFIG:
  CONFIG['removeIndex']=False
if not 'mqtt' in CONFIG:
  log.error('MQTT specific configuration is missing in {}'.format(ELASTICSEARCH_MAPPING_FILE))
if not 'tls' in CONFIG['mqtt']:
  CONFIG['mqtt']['tls']=False

#------------------------------------------------------------------------------
es = Elasticsearch(CONFIG['elasticsearch']['cluster'])

client = mqtt.Client(client_id=CONFIG['mqtt']['client_id'], clean_session=True, userdata=None)

if 'user' in CONFIG['mqtt'] and CONFIG['mqtt']['user'] != '' and 'password' in CONFIG['mqtt'] and CONFIG['mqtt']['password'] != '':
  log.debug('Set username and password for MQTT connection')
  client.username_pw_set(CONFIG['mqtt']['user'], password=CONFIG['mqtt']['password'])

if CONFIG['mqtt']['tls']:
  log.debug('MQTT connection is TLS encrypted')
  client.tls_set()

# initial creation of elasticsearch index
for key, value in topic2index.items():
    if CONFIG['removeIndex']:
      removeElasticsearchIndex(value['elasticIndex'], exitAfterRemoval=True)
    createElasticsearchIndex(value['elasticIndex'], value['elasticBody'])

# register MQTT callback functions
client.on_connect = on_connect
client.on_message = on_message
client.connect(CONFIG['mqtt']['server'], CONFIG['mqtt']['port'], 60)

# Blocking call that processes network traffic, dispatches callbacks and
# handles reconnecting.
# Other loop*() functions are available that give a threaded interface and a
# manual interface.
client.loop_forever()

client.disconnect()

log.info('MQTT to Eleasticsearch processor v{} stopped'.format(VERSION))
sys.exit()
