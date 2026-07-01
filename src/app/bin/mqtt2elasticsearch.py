"""
mqtt2elasticsearch.py - a tool that subscribes to mqtt topics and writes the
  messages to an Elasticsearch or to an Opensearch database
Author: Michael Oberdorf
Date: 2019-03-14
Last modified by: Michael Oberdorf
Last modified at: 2026-07-01
"""

import json
import logging
import os
import ssl
import sys
import uuid
from datetime import datetime

import paho.mqtt.client as mqtt
from elasticsearch import Elasticsearch
from opensearchpy import OpenSearch

__author__ = "Michael Oberdorf <info@oberdorf-itc.de>"
__status__ = "production"
__date__ = "2026-07-01"
__version_info__ = ("1", "4", "0")
__version__ = ".".join(__version_info__)

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


def __initialize_logger(severity: int = logging.INFO) -> logging.Logger:
    """
    Initialize the logger with the given severity level.

    :param severity int: The optional severity level for the logger. (default: 20 (INFO))
    :return logging.RootLogger: The initialized logger.
    :raise ValueError: If the severity level is not valid.
    :raise TypeError: If the severity level is not an integer.
    :raise Exception: If the logger cannot be initialized.
    """
    valid_severity = [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL]
    if severity not in valid_severity:
        raise ValueError(f"Invalid severity level: {severity}. Must be one of {valid_severity}.")

    log = logging.getLogger()
    log_handler = logging.StreamHandler(sys.stdout)

    log.setLevel(severity)
    log_handler.setLevel(severity)
    log_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    log_handler.setFormatter(log_formatter)
    log.addHandler(log_handler)

    return log


def __validate_configuration() -> tuple[bool, bool]:
    """
    Validate the configuration loaded from the JSON file.

    :return tuple[bool, bool]: A tuple containing boolean values indicating whether Elasticsearch and Opensearch are configured.
    :raise ValueError: If the configuration is not valid.
    :raise Exception: If the configuration cannot be validated.
    """
    isElasticsearch = False
    isOpensearch = False

    if "mqtt" not in CONFIG:
        raise ValueError(f"MQTT specific configuration is missing in {ELASTICSEARCH_MAPPING_FILE}")
    if "elasticsearch" not in CONFIG and "opensearch" not in CONFIG:
        raise ValueError("Elasticsearch or Opensearch needs to be configured.")
    if "elasticsearch" in CONFIG and "opensearch" in CONFIG:
        raise ValueError("Elasticsearch and Opensearch can't be configured in parallel.")

    # set some defaults
    if "removeIndex" not in CONFIG.keys():
        CONFIG["removeIndex"] = False
    if "tls" not in CONFIG["mqtt"].keys():
        CONFIG["mqtt"]["tls"] = False
    if "clean_session" not in CONFIG["mqtt"].keys():
        CONFIG["mqtt"]["clean_session"] = False
    if "client_id" not in CONFIG["mqtt"].keys():
        CONFIG["mqtt"]["client_id"] = uuid.uuid4().hex
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
        CONFIG["thisismytest"] = "thisismytest"

    return isElasticsearch, isOpensearch


def __initialize_mqtt_client() -> mqtt.Client:
    """
    Initialize the MQTT client with the given configuration from environment.

    :return mqtt.Client: The initialized MQTT client.
    :raise ValueError: If the MQTT client configuration is not valid.
    :raise Exception: If the MQTT client cannot be initialized.
    """

    if CONFIG["mqtt"]["client_id"] is not None:
        log.debug(f"Use MQTT client ID: {CONFIG['mqtt']['client_id']}")

    if CONFIG["mqtt"]["protocol_version"] == "5":
        log.debug("MQTT protocol version 5")
        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=CONFIG["mqtt"]["client_id"],
            userdata=None,
            transport="tcp",
            protocol=mqtt.MQTTv5,
        )
    else:
        log.debug("MQTT protocol version 3.1.1")
        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=CONFIG["mqtt"]["client_id"],
            clean_session=True,
            userdata=None,
            transport="tcp",
            protocol=mqtt.MQTTv311,
        )

    # configure TLS
    if CONFIG["mqtt"]["tls"]:
        log.debug("Configure MQTT connection to use TLS encryption.")

        __ca_cert_file__ = "/etc/ssl/certs/ca-certificates.crt"
        if os.environ.get("REQUESTS_CA_BUNDLE", None) is not None:
            __ca_cert_file__ = os.environ.get("REQUESTS_CA_BUNDLE")

        if not CONFIG["mqtt"]["hostname_validation"]:
            log.debug("Configure MQTT connection to use TLS with insecure mode.")
            client.tls_set(
                ca_certs=__ca_cert_file__,
                cert_reqs=ssl.CERT_NONE,
                tls_version=ssl.PROTOCOL_TLSv1_2,
                ciphers=None,
            )
            client.tls_insecure_set(True)
        else:
            log.debug("Configure MQTT connection to use TLS with secure mode.")
            client.tls_set(
                ca_certs=__ca_cert_file__,
                cert_reqs=ssl.CERT_REQUIRED,
                tls_version=ssl.PROTOCOL_TLSv1_2,
                ciphers=None,
            )
            client.tls_insecure_set(False)

    # configure authentication
    if (
        "user" in CONFIG["mqtt"]
        and CONFIG["mqtt"]["user"] != ""
        and "password" in CONFIG["mqtt"]
        and CONFIG["mqtt"]["password"] != ""
    ):
        log.debug(f"Set username ({CONFIG['mqtt']['user']}) and password for MQTT connection")
        client.username_pw_set(CONFIG["mqtt"]["user"], CONFIG["mqtt"]["password"])

    # register callback functions
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_subscribe = on_subscribe

    return client


def on_connect(client: mqtt.Client, userdata: dict, flags: dict, rc: int, properties: mqtt.Properties) -> None:
    """
    on_connect - The MQTT callback for when the client receives a CONNACK response from the server.

    :param client: The object of the MQTT connection
    :type client: paho.mqtt.client.Client
    :param userdata: the user data of the MQTT connection
    :type userdata: dict
    :param flags: connection parameters
    :type flags: dict
    :param rc: the return code
    :type rc: int
    :return None
    """
    log.debug(f"MQTT client connected with result code {rc}")
    log.debug(f"MQTT connection flags: {flags}")
    log.debug(f"MQTT connection userdata: {userdata}")
    log.debug(f"MQTT connection properties: {properties}")

    # check for return code
    if rc != 0:
        log.error(f"Error in connecting to MQTT Server, RC={rc}")
        sys.exit(1)

    # Subscribing in on_connect() means that if we lose the connection and reconnect then subscriptions will be renewed.
    for topic in topic2index.keys():
        log.debug(f"MQTT client subscribing to topic: {topic}")
        client.subscribe(topic)

    return None


def on_subscribe(
    client: mqtt.Client, userdata: dict, mid: int, reason_code_list: list, properties: mqtt.Properties
) -> None:
    """
    on_subscribe - The MQTT callback for when the client receives a SUBACK response from the server.

    :param client: The object of the MQTT connection
    :type client: paho.mqtt.client.Client
    :param userdata: the user data of the MQTT connection
    :type userdata: dict
    :param mid: the message ID of the subscribe request
    :type mid: int
    :param reason_code_list: the list of reason codes for the subscribe request
    :type reason_code_list: list
    :param properties: the MQTT properties of the subscribe response
    :type properties: paho.mqtt.client.MQTTProperties
    :return None
    """
    log.debug(
        f"MQTT client received SUBACK for message ID {mid} with reason codes {reason_code_list} and properties {properties}"
    )
    log.debug(f"MQTT client userdata: {userdata}")
    if reason_code_list[0].is_failure:
        log.error(f"Broker rejected you subscription: {reason_code_list[0]}")
    else:
        log.debug(f"Broker granted the following QoS: {reason_code_list[0].value}")


def on_message(client: mqtt.Client, userdata: dict, msg: mqtt.MQTTMessage) -> None:
    """
    on_message - The MQTT callback for when a PUBLISH message is received from the server.

    :param client: the object of the MQTT connection
    :type client: paho.mqtt.client.Client
    :param userdata: the user data of the MQTT connection
    :type userdata: dict
    :param msg: the object of the MQTT message received
    :type msg: paho.mqtt.client.MQTTMessage
    :return None
    """
    log.debug(f"MQTT message received on topic {msg.topic} with QoS {msg.qos} and retain flag {msg.retain}")

    # Topic wildcard support
    topic2index_key = msg.topic
    if msg.topic not in topic2index.keys():
        for topic in topic2index.keys():
            if mqtt.topic_matches_sub(topic, msg.topic):
                topic2index_key = topic
                log.debug(f"- matched topic: {topic2index_key}")
                break

    if topic2index_key not in topic2index.keys():
        log.warning(f"No mapping found for topic: {msg.topic}, skipping message.")
        return None

    # prepare index
    index = prepareIndexName(topic2index[topic2index_key]["elasticIndex"])

    # check if index exist, if not trigger creation
    if not es.indices.exists(index=index):
        createIndex(index, topic2index[topic2index_key]["elasticBody"])

    # parse message payload as JSON object
    PAYLOAD = json.loads(str(msg.payload.decode("utf-8")))
    log.debug(f"MQTT message payload: {PAYLOAD}")

    log.info(f"Add data to index: {index}")
    res = es.index(index=index, body=json.dumps(PAYLOAD))
    log.debug(f"Result: {res['result']}")

    return None


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


"""
###############################################################################
# M A I N
###############################################################################
"""
if __name__ == "__main__":
    # initialize logger
    if "DEBUG" not in CONFIG:
        log = __initialize_logger(logging.INFO)
    else:
        if CONFIG["DEBUG"]:
            log = __initialize_logger(logging.DEBUG)
        else:
            log = __initialize_logger(logging.INFO)
    log.info(f"MQTT to Eleasticsearch processor v{__version__} started")

    # ------------------------------------------------------------------------------
    # validate configuration
    isElasticsearch, isOpensearch = __validate_configuration()

    # ------------------------------------------------------------------------------
    # initialize Elasticsearch/Opensearch connection
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
    if not es:
        log.error("No Elasticsearch or Opensearch connection configured!")
        sys.exit(1)

    # initial creation of elasticsearch/opensearch index
    for key, value in topic2index.items():
        if CONFIG["removeIndex"]:
            removeIndex(value["elasticIndex"], exitAfterRemoval=True)
        createIndex(value["elasticIndex"], value["elasticBody"])

    # ------------------------------------------------------------------------------
    # Initialize MQTT connection
    client = __initialize_mqtt_client()
    # connect to MQTT server
    log.debug("Connecting to MQTT server {}:{}".format(CONFIG["mqtt"]["server"], CONFIG["mqtt"]["port"]))
    try:
        client.connect(CONFIG["mqtt"]["server"], CONFIG["mqtt"]["port"], 60)
    except ssl.SSLCertVerificationError as e:
        log.error("SSL certificate verification error: {}".format(e))
        sys.exit(1)
    log.debug("Connected to MQTT server")

    # Blocking call that processes network traffic, dispatches callbacks and
    # handles reconnecting.
    # Other loop*() functions are available that give a threaded interface and a
    # manual interface.
    client.loop_forever()

    client.disconnect()

    log.info(f"MQTT to Eleasticsearch processor v{__version__} stopped")
    sys.exit()
