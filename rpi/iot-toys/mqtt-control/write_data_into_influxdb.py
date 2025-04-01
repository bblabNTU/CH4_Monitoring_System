import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS

bucket = "sensor_data"
org = "bblab"
token = "4eYvsu8wZCJ6tKuE2sxvFHkvYFwSMVK0011hEEiojvejzpSaij86vYQomN_12au6eK-2MZ6Knr-Sax2"
# Store the URL of your InfluxDB instance
url="http://influxdb:8086"

client = influxdb_client.InfluxDBClient(
    url=url,
    token=token,
    org=org
)

# Write script
write_api = client.write_api(write_options=SYNCHRONOUS)
datetime_obj = "2023/05/19T17:24:46.000Z"
p = influxdb_client.Point("mqtt_consumer").field("humidity", 85.75).time(datetime_obj, influxdb_client.WritePrecision.MS)
write_api.write(bucket=bucket, org=org, record=p)
