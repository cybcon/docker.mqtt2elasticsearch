# Quick reference

Maintained by: [Michael Oberdorf IT-Consulting](https://www.oberdorf-itc.de/)

Source code: [GitHub](https://github.com/cybcon/docker.mqtt2elasticsearch)

Container image: [DockerHub](https://hub.docker.com/repository/docker/oitc/mqtt2elasticsearch)

<!-- SHIELD GROUP -->
[![][github-action-test-shield]][github-action-test-link]
[![][github-action-release-shield]][github-action-release-link]
[![][github-release-shield]][github-release-link]
[![][github-releasedate-shield]][github-releasedate-link]
[![][github-stars-shield]][github-stars-link]
[![][github-forks-shield]][github-forks-link]
[![][github-issues-shield]][github-issues-link]
[![][github-license-shield]][github-license-link]

[![][docker-release-shield]][docker-release-link]
[![][docker-pulls-shield]][docker-pulls-link]
[![][docker-stars-shield]][docker-stars-link]
[![][docker-size-shield]][docker-size-link]

# Supported tags and respective `Dockerfile` links

* [`latest`, `1.2.1`](https://github.com/cybcon/docker.mqtt2elasticsearch/blob/v1.2.1/Dockerfile)
* [`1.1.1`](https://github.com/cybcon/docker.mqtt2elasticsearch/blob/v1.1.1/Dockerfile)
* [`1.1.0`](https://github.com/cybcon/docker.mqtt2elasticsearch/blob/v1.1.0/Dockerfile)
* [`1.0.0`](https://github.com/cybcon/docker.mqtt2elasticsearch/blob/v1.0.0/Dockerfile)

# Summary

The container image is based on Alpine Linux with python3 interpreter.
The tool is written in python and connects to a MQTT server and subscripes to one ore more topics.
All messages in that topic will be pushed to an elasticsearch or opensearch server.

# Prerequisites to run the docker container
1. You need a MQTT server to read the data from the topics.
2. You need an elasticsearch v8 / or opensearch v2 database to store the data inside.

# Configuration
## Container configuration

The container grab some configuration via environment variables.

| Environment variable name    | Description                                                                                      | Required     | Default value                               |
|------------------------------|--------------------------------------------------------------------------------------------------|--------------|---------------------------------------------|
| `CONFIG_FILE`                | The general configuration file that contains the connection parameters to MQTT and Elasticsearch | **OPTIONAL** | `/app/etc/mqtt2elasticsearch.json`          |
| `ELASTICSEARCH_MAPPING_FILE` | The MQTT topics and the associated Elasticsearch index configuration for the messages.           | **OPTIONAL** | `/app/etc/mqtt2elasticsearch-mappings.json` |



## General configuration file

The path and filename to the general configuration file can be set via environment variable `CONFIG_FILE`. By default, the script will use `/app/etc/mqtt2elasticsearch.json`.

Inside this file we need to configure the Elasticsearch (or Opensearch) and MQTT server connection parameters.

### Example with Elasticsearch

```json
{
"DEBUG": true,
"removeIndex": false,
"elasticsearch": {
  "cluster": [ "http://elasticsearch:9200/" ]
  },
"mqtt": {
  "client_id": "mqtt2elasticsearch",
  "user": "mqtt2elasticsearch",
  "password": "myPassword",
  "server": "test.mosquitto.org",
  "port": 1883,
  "tls": false,
  "hostname_validation": true,
  "protocol_version": 3
  }
}
```

### Example with Opensearch

```json
{
"DEBUG": true,
"removeIndex": false,
"opensearch": {
  "hosts": [
    {
      "host": "opensearch",
      "port": 9200
    }
  ],
  "tls": true,
  "verify_certs": true,
  "username": "admin",
  "password": "admin"
  },
"mqtt": {
  "client_id": "mqtt2elasticsearch",
  "user": "mqtt2elasticsearch",
  "password": "myPassword",
  "server": "test.mosquitto.org",
  "port": 1883,
  "tls": false,
  "hostname_validation": true,
  "protocol_version": 3
  }
}
```


### Field description

| Field                      | Type    | Description                                                                                                      |
|----------------------------|---------|------------------------------------------------------------------------------------------------------------------|
| `DEBUG`                    | Boolean | Enable debug output on stdout                                                                                    |
| `removeIndex`              | Boolean | If this flag is set to `true`, the script will remove the Elasticsearch index and exits.                         |
| `elasticsearch`            | Object  | Contains Elasticsearch specific configuration parameters.                                                        |
| `elasticsearch.cluster`    | Array   | Contains a list of Eleasticsearch cluster node URLs.                                                             |
| `elasticsearch.api_ley`    | String  | Optional api\_key if Elasticsearch requires authentication.                                                      |
| `opensearch`               | Object  | Contains Opensearch specific configuration parameters.                                                           |
| `opensearch.hosts`         | Array   | Contains a list of Opensearch hosts objects.                                                                     |
| `opensearch.hosts[].host`  | String  | Opensearch hostname (fqdn) or IP address.                                                                        |
| `opensearch.hosts[].port`  | String  | Optional Opensearch TCP port (Default: 9200).                                                                    |
| `opensearch.username`      | String  | Optional username for authentication (Default: null).                                                            |
| `opensearch.password`      | String  | Optional password for authentication (Default: null.                                                             |
| `opensearch.tls`           | Boolean | Optional if a TLS encrpted communication should be established or not (Default: false).                          |
| `opensearch.verify_certs`  | Boolean | Optional to validate the server certificate ort not (Default: false).                                            |
| `opensearch.ca_certs_path` | String  | Optional path to CA certs (Default: "/etc/ssl/certs/ca-certificates.crt").                                       |
| `mqtt`                     | Object  | Contains MQTT specific configuration parameters.                                                                 |
| `mqtt.client_id`           | String  | The MQTT client identifier.                                                                                      |
| `mqtt.user`                | String  | The username to authenticate to the MQTT server.                                                                 |
| `mqtt.password`            | String  | The password to authenticate to the MQTT server.                                                                 |
| `mqtt.server`              | String  | IP address or FQDN of the MQTT server.                                                                           |
| `mqtt.port`                | String  | The TCP port number of the MQTT server.                                                                          |
| `mqtt.tls`                 | Boolean | If a TLS encrpted communication should be established or not.                                                    |
| `mqtt.hostname_validation` | Boolean | Validate the hostname from the servercertificate or not.                                                         |
| `mqtt.protocol_version`    | Integer | The MQTT protocol version. Can be 3 (for MQTTv311) or 5 (for MQTTv5).                                            |


##  Elasticsearch/Opensearch index configuration file

The path and filename to the Elasticsearch/Opensearch index configuration file can be set via environment variable `ELASTICSEARCH_MAPPING_FILE`.
By default, the script will use `/app/etc/mqtt2elasticsearch-mappings.json`.

Inside this file we need to configure the MQTT topic and the associated Elasticsearch/Opensearch index with it's configuration.

### Example

This is  minimal example. The JSON file contains the MQTT topic as **key**. Every topic contains the associated Elasticsearch/Opensearch index and an optional index configuration.
You can use placeholder inside the index name. Following will be translated on the fly:
- `{Y}`: the 4-digit year
- `{m}`: the 2-digit month
- `{d}`: the 2-digit day

```json
{
  "de/oberdorf-itc/some/topic": {
    "elasticIndex": "mydata-{Y}-{m}",
    "elasticBody": {
    }
  }
}
```

Full blown examples can be found here:
- [speedtest2mqtt-elasticsearch-mapping.json](./examples/speedtest2mqtt-elasticsearch-mapping.json).
- [dockerhub-stats-opensearch-mapping.json](./examples/dockerhub-stats-opensearch-mapping.json).


### Field description

| Field                      | Type   | Description |
|----------------------------|--------|-------------|
| *\<topic\>*                | String | The MQTT topic to subscripe to                                                                                                                                    |
| *\<topic\>*.`elasticIndex` | String | The name of the Elasticsearch index. Allowed placeholders are `{Y}` (year), `{m}` (month) and `{d}` (day)                                                         |
| *\<topic\>*.`elasticBody`  | Object | The Elastic index configuration as documented here: [Create index API](https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-create-index.html) |


# Running the container image

```
docker run --rm oitc/mqtt2elasticsearch:latest
```

# Docker compose configuration

```yaml
version: '3.8'

services:
  elasticsearch:
    restart: always
    image: elasticsearch:8.10.2
    container_name: elasticsearch
    hostname: elasticsearch
    environment:
      - cluster.name=docker-cluster
      - discovery.type=single-node
      - bootstrap.memory_lock=true
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
      - xpack.security.enabled=false
      - xpack.security.enrollment.enabled=false
    ulimits:
      memlock:
        soft: -1
        hard: -1
    ports:
      - 9200:9200
    volumes:
      - /srv/docker/elasticsearch/data:/usr/share/elasticsearch/data
    healthcheck:
      test: ["CMD", "wget", "http://localhost:9200", "-O-"]
      interval: 1s
      timeout: 1s
      retries: 120

  kibana:
    restart: always
    image: kibana:8.10.2
    container_name: kibana
    hostname: kibana
    ports:
      - 5601:5601
    volumes:
      - /srv/docker/kibana/etc:/usr/share/kibana/config
    depends_on:
      - elasticsearch

  mqtt2elasticsearch:
    restart: always
    image: oitc/mqtt2elasticsearch
    container_name: mqtt2elasticsearch
    hostname: mqtt2elasticsearch
    volumes:
      - /srv/docker/mqtt2elasticsearch/etc/speedtest2mqtt-elasticsearch-mapping.json:/app/etc/mqtt2elasticsearch-mappings.json:ro
    depends_on:
      - elasticsearch

  speedtest2mqtt:
    container_name: speedtest2mqtt
    restart: always
    read_only: true
    user: 2536:2536
    image: oitc/speedtest2mqtt
    environment:
      MQTT_SERVER: test.mosquitto.org
      MQTT_PORT: 1883
      MQTT_TOPIC: de/oberdorf-itc/speedtest2mqtt/results
      FREQUENCE: 300
    secrets:
      - speedtest2mqtt_mqtt_password
    tmpfs:
      - /tmp

secrets:
  speedtest2mqtt_mqtt_password:
    file: /srv/docker/speedtest2mqtt/secrets/mqtt_password
```

# Donate
I would appreciate a small donation to support the further development of my open source projects.

<a href="https://www.paypal.com/donate/?hosted_button_id=BHGJGGUS6RH44" target="_blank"><img src="https://raw.githubusercontent.com/stefan-niedermann/paypal-donate-button/master/paypal-donate-button.png" alt="Donate with PayPal" width="200px"></a>


# License

Copyright (c) 2023-2025 Michael Oberdorf IT-Consulting

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

<!-- LINK GROUP -->
[docker-pulls-link]: https://hub.docker.com/r/oitc/mqtt2elasticsearch
[docker-pulls-shield]: https://img.shields.io/docker/pulls/oitc/mqtt2elasticsearch?color=45cc11&labelColor=black&style=flat-square
[docker-release-link]: https://hub.docker.com/r/oitc/mqtt2elasticsearch
[docker-release-shield]: https://img.shields.io/docker/v/oitc/mqtt2elasticsearch?color=369eff&label=docker&labelColor=black&logo=docker&logoColor=white&style=flat-square
[docker-size-link]: https://hub.docker.com/r/oitc/mqtt2elasticsearch
[docker-size-shield]: https://img.shields.io/docker/image-size/oitc/mqtt2elasticsearch?color=369eff&labelColor=black&style=flat-square
[docker-stars-link]: https://hub.docker.com/r/oitc/mqtt2elasticsearch
[docker-stars-shield]: https://img.shields.io/docker/stars/oitc/mqtt2elasticsearch?color=45cc11&labelColor=black&style=flat-square
[github-action-release-link]: https://github.com/cybcon/docker.mqtt2elasticsearch/actions/workflows/release-from-label.yaml
[github-action-release-shield]: https://img.shields.io/github/actions/workflow/status/cybcon/docker.mqtt2elasticsearch/release-from-label.yaml?label=release&labelColor=black&logo=githubactions&logoColor=white&style=flat-square
[github-action-test-link]: https://github.com/cybcon/docker.mqtt2elasticsearch/actions/workflows/container-image-build-validation.yaml
[github-action-test-shield-original]: https://github.com/cybcon/docker.mqtt2elasticsearch/actions/workflows/container-image-build-validation.yaml/badge.svg
[github-action-test-shield]: https://img.shields.io/github/actions/workflow/status/cybcon/docker.mqtt2elasticsearch/container-image-build-validation.yaml?label=tests&labelColor=black&logo=githubactions&logoColor=white&style=flat-square
[github-forks-link]: https://github.com/cybcon/docker.mqtt2elasticsearch/network/members
[github-forks-shield]: https://img.shields.io/github/forks/cybcon/docker.mqtt2elasticsearch?color=8ae8ff&labelColor=black&style=flat-square
[github-issues-link]: https://github.com/cybcon/docker.mqtt2elasticsearch/issues
[github-issues-shield]: https://img.shields.io/github/issues/cybcon/docker.mqtt2elasticsearch?color=ff80eb&labelColor=black&style=flat-square
[github-license-link]: https://github.com/cybcon/docker.mqtt2elasticsearch/blob/main/LICENSE
[github-license-shield]: https://img.shields.io/badge/license-MIT-blue?labelColor=black&style=flat-square
[github-release-link]: https://github.com/cybcon/docker.mqtt2elasticsearch/releases
[github-release-shield]: https://img.shields.io/github/v/release/cybcon/docker.mqtt2elasticsearch?color=369eff&labelColor=black&logo=github&style=flat-square
[github-releasedate-link]: https://github.com/cybcon/docker.mqtt2elasticsearch/releases
[github-releasedate-shield]: https://img.shields.io/github/release-date/cybcon/docker.mqtt2elasticsearch?labelColor=black&style=flat-square
[github-stars-link]: https://github.com/cybcon/docker.mqtt2elasticsearch
[github-stars-shield]: https://img.shields.io/github/stars/cybcon/docker.mqtt2elasticsearch?color=ffcb47&labelColor=black&style=flat-square
