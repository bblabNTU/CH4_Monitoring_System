# Easy IoT data infrastructure setup via docker

Based on https://github.com/iothon/docker-compose-mqtt-influxdb-grafana and https://lucassardois.medium.com/handling-iot-data-with-mqtt-telegraf-influxdb-and-grafana-5a431480217

This docker compose installs and sets up:
- [Eclipse Mosquitto](https://mosquitto.org) - An open source MQTT broker to collect your data via MQTT protocol
- [InfluxDB](https://www.influxdata.com/) - The Time Series Data Platform to store your data in time series database 
- [Telegraf](https://www.influxdata.com/time-series-platform/telegraf/) - The open source server agent to connect Mosquitto and InfluxDB together
- [Grafana](https://grafana.com/) - The open observability platform to draw some graphs and more

# Setup process
## Install docker

```
sudo apt install docker.io
sudo apt install docker-compose 
```

```
sudo usermod -aG docker iothon
```

## Clone this repository

```
git clone https://github.com/bblabNTU/CH4_Monitoring_System.git
```

## Run it

To download, setup and start all the services run
```
cd CH4_Monitoring_System
sudo docker-compose up -d
```

To check the running setvices run
```
sudo docker ps
```

To shutdown the whole thing run
```
sudo docker-compose down
```

## Test your setup

Post some messages into your Mosquitto so you'll be able to see some data in Grafana already: 
```
sudo docker container exec mosquitto-test mosquitto_pub -t 'data/paper_wifi/test/' -m '{"humidity":21, "temperature":21, "battery_voltage_mv":3000}' -u mqttuser -P nxxxxxxxx5
```

### Grafana
Open in your browser: 
`http://localhost:3001`

Username and pasword are admin:admin. You should see a graph of the data you have entered with the `mosquitto_pub` command.

### InfluxDB
You can poke around your InfluxDB setup here:
`http://localhost:8086`
Username and password are user:nxxxxxxxx5

# Configuration 
### Mosquitto 
Mosquitto is configured to only allows authenticated access connections and posting of messages. Ref: https://weirenxue.github.io/2021/07/01/mqtt_mosquitto_docker/
```
persistence true
persistence_location /mosquitto/data/
log_dest file /mosquitto/log/mosquitto.log

allow_anonymous false
password_file /mosquitto/config/passwd_file

listener 1883
protocol mqtt
```

### InfluxDB 
The configuration is fully in `docker-compose.yml`. Note the `DOCKER_INFLUXDB_INIT_ADMIN_TOKEN` - you can run a test with the one given, but you better re-generate it for your own security. This same token is repeated in several other config files, you have to update it there also. I did not find an easy way to generate it automagically in docker yet. **Change it before you go live**. You have been warned. Also change the username and password.
```
  influxdb:
    image: influxdb:latest
    container_name: influxdb-TLRI
    restart: unless-stopped
    ports:
      - "8086:8086"
    networks:
      - iot
    volumes:
      - influxdb-data:/var/lib/influxdb2
      - influxdb-config:/etc/influxdb2
    environment:
      - DOCKER_INFLUXDB_INIT_MODE=setup
      - DOCKER_INFLUXDB_INIT_USERNAME=user
      - DOCKER_INFLUXDB_INIT_PASSWORD=nxxxxxxxx5
      - DOCKER_INFLUXDB_INIT_ORG=bblab
      - DOCKER_INFLUXDB_INIT_BUCKET=sensor_data
      - DOCKER_INFLUXDB_INIT_ADMIN_TOKEN=P1111111RbQQPadd5I0YA7HR1j_eFLdHpLBOMFPJMxjhyk5myZ-3Uaa4p5b5aUVLnOOxaMJtmc-IpfWYZTuyFA==

```

### Telegraf 
Telegraf is responsible for piping mqtt messages to influxdb. It is set up to listen for topic `paper_wifi/test`. You can alter this configuration according to your needs, check the official documentation on how to do that. Note the InfluxDB token you have to update.
```
[[inputs.mqtt_consumer]]
  servers = ["tcp://mosquitto:1883"]
  topics = [
    "data/#"
  ]
  data_format = "json"
  
  #json_query = "{humidity,temperature,battery_voltage_mv}"
  #json_name_key = "dev_id"
  #tag_keys = ["dev_id", "hardware_serial"]
  #json_string_fields=["hardware_serial"]
  #[tags]
  #  source="mqtt"

  ## Username and password to connect MQTT server.
  username = "mqttuser"
  password = "nxxxxxxxxx5"

[[outputs.influxdb_v2]]
  ## The URLs of the InfluxDB cluster nodes.
  ##
  ## Multiple URLs can be specified for a single cluster, only ONE of the
  ## urls will be written to each interval.
  ##   ex: urls = ["https://us-west-2-1.aws.cloud2.influxdata.com"]
  urls = ["http://influxdb:8086"]

  ## Token for authentication.
  token = "P1111111RbQQPadd5I0YA7HR1j_eFLdHpLBOMFPJMxjhyk5myZ-3Uaa4p5b5aUVLnOOxaMJtmc-IpfWYZTuyFA=="

  ## Organization is the name of the organization you wish to write to; must exist.
  organization = "bblab"

  ## Destination bucket to write into.
  bucket = "sensor_data"

```

### Grafana data source (TO BE UPDATED...)
Grafana is provisioned with a default data source pointing to the InfluxDB instance installed in this same compose. The configuration file is `grafana-provisioning/datasources/automatic.yml`. Note the InfluxDB token you have to update. 
```
apiVersion: 1

datasources:
  - name: InfluxDB_v2_Flux
    type: influxdb
    access: proxy
    url: http://influxdb:8086
    jsonData:
      version: Flux
      organization: some_org
      defaultBucket: some_data
      tlsSkipVerify: true
    secureJsonData:
      token: 4eYvsu8wZCJ6tKuE2sxvFHkvYFwSMVK0011hEEiojvejzpSaij86vYQomN_12au6eK-2MZ6Knr-Sax201y70w==
```

### Grafana dashboard (TO BE UPDATED...)
Default Grafana dashboard is also set up in this directory: `grafana-provisioning/dashboards`

