# -*- coding: utf-8 -*-
""" ***************************************************************************
mqtt2elasticsearch.py - a tool that subscribes to mqtt topics and writes the
  messages to an Elasticsearch or to an Opensearch database
Author: Michael Oberdorf
Date: 2019-03-14
Last modified by: Michael Oberdorf
Last modified at: 2025-03-10
*************************************************************************** """
import json
import logging
import os
import ssl
import sys
from datetime import datetime

import paho.mqtt.client as mqtt
from elasticsearch import Elasticsearch
from opensearchpy import OpenSearch

VERSION = "1.2.0"

CONFIG_FILE = "/app/etc/mqtt2elasticsearch.json"
if "CONFIG_FILE" in os.environ:
    CONFIG_FILE = os.environ["CONFIG_FILE"]
with open(CONFIG_FILE) as f:
    CONFIG = json.load(f)

ELASTICSEARCH_MAPPING_FILE = "/app/etc/mqtt2elasticsearch-mappings.json"
if "ELASTICSEARCH_MAPPING_FILE" in os.environ:
    ELASTICSEARCH_MAPPING_FILE = os.environ["ELASTICSEARCH_MAPPING_FILE"]
with open(ELASTICSEARCH_MAPPING_FILE) as f:
    topic2index = json.load(f)


"""
###############################################################################
# F U N C T I O N S
###############################################################################
"""


def prepareIndexName(index: str) -> str:
    """
    prepareIndexName
    @desc: replace tokens in index name
    @param: index, str(): The index name with placeholders
    @return: str(): The resolved index name
    """

    elasticIndex = (
        index.replace("{Y}", datetime.today().strftime("%Y"))
        .replace("{m}", datetime.today().strftime("%m"))
        .replace("{d}", datetime.today().strftime("%d"))
    )

    if index != elasticIndex:
        log.debug("Replacing placeholders in index name:")
        log.debug("  OLD: {}".format(index))
        log.debug("  NEW: {}".format(elasticIndex))

    return elasticIndex


def createIndex(index: str, body: dict):
    """
    createIndex
    @desc: creates a new index in DB if not exist
    @param index, str(): index name
    @param body, dict(): index settings and mappings
    @return: None
    """

    index = prepareIndexName(index)

    if not es.indices.exists(index=index):
        host_port = ""
        if isElasticsearch:
            host_port = CONFIG["elasticsearch"]["cluster"][0]
        elif isOpensearch:
            host_port = (
                CONFIG["opensearch"]["hosts"][0]["host"] + ":" + str(CONFIG["opensearch"]["hosts"][0]["port"]) + "/"
            )
        log.debug(f"Creating index: {host_port}{index}")
        log.debug(f"  {body}")
        es.indices.create(index=index, body=body)
    else:
        log.debug("Skip creation of opensearch Index, because it already exists.")

    return None


def removeIndex(index: str, exitAfterRemoval: bool = True):
    """
    removeIndex
    @desc: removes an index in DB if exist
    @param index, str(): index name
    @param exitAfterRemoval, bool(): Exit after removing index (default: True)
    @return: None
    """

    index = prepareIndexName(index)

    if es.indices.exists(index=index):
        log.debug("Removing index: {}".format(index))
        es.indices.delete(index=index)
    else:
        log.debug("Skip to removing index, because it is not existing.")

    if exitAfterRemoval:
        log.debug("End program after removing index.")
        sys.exit()
    else:
        return None


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

    log.debug("After connecting to MQTT server:")
    log.debug("- userdata: {}".format(userdata))
    log.debug("- flags: {}".format(flags))
    log.debug("- rc: {}".format(rc))

    # check for return code
    if rc != 0:
        log.error("Error in connecting to MQTT Server, RC={}".format(rc))
        sys.exit(1)

    # Subscribing in on_connect() means that if we lose the connection and reconnect then subscriptions will be renewed.
    for topic in topic2index.keys():
        log.debug("Subscribe to MQTT topic: {}".format(topic))
        client.subscribe(topic)

    return None


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

    log.debug("MQTT message received:")
    log.debug("- userdata: {}".format(userdata))

    # prepare index
    index = prepareIndexName(topic2index[msg.topic]["elasticIndex"])

    # check if index exist, if not trigger creation
    if not es.indices.exists(index=index):
        createIndex(index, topic2index[msg.topic]["elasticBody"])

    # parse message payload as JSON object
    PAYLOAD = json.loads(str(msg.payload.decode("utf-8")))

    log.info("Add data to index: {}".format(index))
    res = es.index(index=index, body=json.dumps(PAYLOAD))
    log.debug("{}".format(res["result"]))

    return None


"""
###############################################################################
# M A I N
###############################################################################
"""

# initialize logger
log = logging.getLogger()
log_handler = logging.StreamHandler(sys.stdout)
if "DEBUG" not in CONFIG:
    log.setLevel(logging.INFO)
    log_handler.setLevel(logging.INFO)
else:
    if CONFIG["DEBUG"]:
        log.setLevel(logging.DEBUG)
        log_handler.setLevel(logging.DEBUG)
    else:
        log.setLevel(logging.INFO)
        log_handler.setLevel(logging.INFO)
log_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
log_handler.setFormatter(log_formatter)
log.addHandler(log_handler)

log.info("MQTT to Eleasticsearch processor v{} started".format(VERSION))

isElasticsearch = False
isOpensearch = False

# set some defaults
if "removeIndex" not in CONFIG.keys():
    CONFIG["removeIndex"] = False
if "mqtt" not in CONFIG.keys():
    log.error("MQTT specific configuration is missing in {}".format(ELASTICSEARCH_MAPPING_FILE))
    sys.exit(1)
if "tls" not in CONFIG["mqtt"].keys():
    CONFIG["mqtt"]["tls"] = False
if "client_id" not in CONFIG["mqtt"].keys():
    CONFIG["mqtt"]["client_id"] = None
if "hostname_validation" not in CONFIG["mqtt"].keys():
    CONFIG["mqtt"]["hostname_validation"] = True
if "protocol_version" not in CONFIG["mqtt"].keys():
    CONFIG["mqtt"]["protocol_version"] = 3
if "elasticsearch" in CONFIG.keys():
    isElasticsearch = True
    if "cluster" not in CONFIG["elasticsearch"].keys():
        log.error("Cluster not defined in elasticsearch configuration!")
        sys.exit(1)
    if len(CONFIG["elasticsearch"]["cluster"]) < 1:
        log.error("Cluster not defined in elasticsearch configuration!")
        sys.exit(1)
    if "api_key" not in CONFIG["elasticsearch"]:
        CONFIG["elasticsearch"]["api_key"] = None
if "opensearch" in CONFIG.keys():
    isOpensearch = True
    if "hosts" not in CONFIG["opensearch"].keys():
        log.error("Hosts not defined in opensearch configuration!")
        sys.exit(1)
    if len(CONFIG["opensearch"]["hosts"]) < 1:
        log.error("Hosts not defined in opensearch configuration!")
        sys.exit(1)
    else:
        for i in range(len(CONFIG["opensearch"]["hosts"])):
            if "host" not in CONFIG["opensearch"]["hosts"][i].keys():
                log.error("Host not defined in opensearch hosts configuration!")
                sys.exit(1)
            if "port" not in CONFIG["opensearch"]["hosts"][i].keys():
                CONFIG["opensearch"]["hosts"][i]["port"] = 9200
    if "username" not in CONFIG["opensearch"].keys():
        CONFIG["opensearch"]["username"] = None
        CONFIG["opensearch"]["password"] = None
    if "password" not in CONFIG["opensearch"].keys():
        CONFIG["opensearch"]["username"] = None
        CONFIG["opensearch"]["password"] = None
    if "tls" not in CONFIG["opensearch"].keys():
        CONFIG["opensearch"]["tls"] = False
    if "verify_certs" not in CONFIG["opensearch"].keys():
        CONFIG["opensearch"]["verify_certs"] = False
    if "ca_certs_path" not in CONFIG["opensearch"].keys():
        CONFIG["opensearch"]["ca_certs_path"] = "/etc/ssl/certs/ca-certificates.crt"

# validate opensearch/elasticsearch
if isOpensearch and isElasticsearch:
    log.error("Elasticsearch and Opensearch can't be configured in parallel.")
    sys.exit(1)
if not isOpensearch and not isElasticsearch:
    log.error("Elasticsearch or Opensearch needs to be configured.")
    sys.exit(1)


# ------------------------------------------------------------------------------
es = None
if isElasticsearch:
    log.debug("Configure Elasticsearch connection")
    es = Elasticsearch(CONFIG["elasticsearch"]["cluster"], api_key=CONFIG["elasticsearch"]["api_key"])
if isOpensearch:
    log.debug("Configure Opensearch connection")
    auth = None
    if CONFIG["opensearch"]["username"] and CONFIG["opensearch"]["password"]:
        auth = (CONFIG["opensearch"]["username"], CONFIG["opensearch"]["password"])
    es = OpenSearch(
        hosts=CONFIG["opensearch"]["hosts"],
        http_compress=True,  # enables gzip compression for request bodies
        http_auth=auth,
        use_ssl=CONFIG["opensearch"]["tls"],
        verify_certs=CONFIG["opensearch"]["verify_certs"],
        ssl_assert_hostname=CONFIG["opensearch"]["verify_certs"],
        ssl_show_warn=False,
        ca_certs=CONFIG["opensearch"]["ca_certs_path"],
    )

# ------------------------------------------------------------------------------
log.debug("Configure MQTT client:")
log.debug("- client_id={}".format(CONFIG["mqtt"]["client_id"]))
log.debug("- transport=tcp")
if CONFIG["mqtt"]["protocol_version"] == 5:
    log.debug("- protocol=MQTTv5")
    client = mqtt.Client(client_id=CONFIG["mqtt"]["client_id"], userdata=None, transport="tcp", protocol=mqtt.MQTTv5)
else:
    log.debug("- clean_session=True")
    log.debug("- protocol=MQTTv5")
    client = mqtt.Client(
        client_id=CONFIG["mqtt"]["client_id"],
        clean_session=True,
        userdata=None,
        transport="tcp",
        protocol=mqtt.MQTTv311,
    )

if (
    "user" in CONFIG["mqtt"]
    and CONFIG["mqtt"]["user"] != ""
    and "password" in CONFIG["mqtt"]
    and CONFIG["mqtt"]["password"] != ""
):
    log.debug("Set username ({}) and password for MQTT connection".format(CONFIG["mqtt"]["user"]))
    client.username_pw_set(CONFIG["mqtt"]["user"], password=CONFIG["mqtt"]["password"])

if CONFIG["mqtt"]["tls"]:
    log.debug("MQTT connection is TLS encrypted")
    client.tls_set(ca_certs=None, cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS, ciphers=None)
    if CONFIG["mqtt"]["hostname_validation"]:
        client.tls_insecure_set(False)
    else:
        client.tls_insecure_set(True)

# initial creation of elasticsearch/opensearch index
for key, value in topic2index.items():
    if CONFIG["removeIndex"]:
        removeIndex(value["elasticIndex"], exitAfterRemoval=True)
    createIndex(value["elasticIndex"], value["elasticBody"])

# register MQTT callback functions
client.on_connect = on_connect
client.on_message = on_message

# connect to MQTT server
log.debug("Connecting to MQTT server {}:{}".format(CONFIG["mqtt"]["server"], CONFIG["mqtt"]["port"]))
client.connect(CONFIG["mqtt"]["server"], CONFIG["mqtt"]["port"], 60)

# Blocking call that processes network traffic, dispatches callbacks and
# handles reconnecting.
# Other loop*() functions are available that give a threaded interface and a
# manual interface.
client.loop_forever()

client.disconnect()

log.info("MQTT to Eleasticsearch processor v{} stopped".format(VERSION))
sys.exit()
