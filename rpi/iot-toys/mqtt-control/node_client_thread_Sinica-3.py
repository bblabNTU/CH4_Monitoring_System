import os
import socket
import threading
import paho.mqtt.client as mqtt
import time
from datetime import datetime
from dotenv import load_dotenv
import json
import csv
import multisensor
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
from rpi_lcd import LCD


class CH4SensorMonitor:
    def __init__(self, config_file=None):
        if config_file:
            load_dotenv(config_file)
        else:
            load_dotenv()

        self.host = os.getenv("HOST", "")
        self.port = int(os.getenv("PORT", 1883))
        self.username = os.getenv("USERNAME", "")
        self.password = os.getenv("PASSWORD")
        self.node = os.getenv("NODE")
        self.location = os.getenv("LOCATION")

        self.TGS_R0 = 1.46

        self.is_stop = False
        self.mqtt_setup_status = False
        self.mqtt_connected = False

        self.client = None
        self.lcd = LCD()
        self.sensors = {}
        self.ads = None

        self.data_dir = "/home/pi/CH4_data"
        os.makedirs(self.data_dir, exist_ok=True)

        # Add lock for thread safety
        self.mqtt_lock = threading.Lock()

    def setup_mqtt(self):
        """Setup MQTT connection with proper error handling and callbacks"""
        try:
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
            self.client.username_pw_set(self.username, self.password)
            
            # Set up connection callbacks
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_publish = self._on_publish
            
            self.client.connect(self.host, self.port, keepalive=60)

            self.client.message_callback_add(f"ctl/{self.location}/thi", self._ctl_thi_callback)
            self.client.message_callback_add(f"ctl/{self.location}/thi/{self.node}", self._ctl_thi_callback)
            self.client.on_message = self._default_message_callback

            self.client.subscribe(f"ctl/{self.location}/thi/#")
            self.client.loop_start()

        except Exception as e:
            print(f"MQTT setup error: {e}")
            self.mqtt_setup_status = False
            self.mqtt_connected = False

    def _on_connect(self, client, userdata, flags, rc):
        """Callback for MQTT connection"""
        if rc == 0:
            self.mqtt_setup_status = True
            self.mqtt_connected = True
            print("MQTT connected successfully")
        else:
            self.mqtt_setup_status = False
            self.mqtt_connected = False
            print(f"MQTT connection failed with code: {rc}")

    def _on_disconnect(self, client, userdata, rc):
        """Callback for MQTT disconnection"""
        self.mqtt_connected = False
        print(f"MQTT disconnected with code: {rc}")
        
    def _on_publish(self, client, userdata, mid):
        """Callback for successful publish"""
        # This can be used for publish confirmation if needed
        pass

    def setup_sensors(self):
        """Setup sensors with error handling"""
        try:
            i2c = busio.I2C(board.SCL, board.SDA, frequency=100000)
            self.ads = ADS.ADS1115(i2c)
            self.ads.gain = 1

            chan0 = AnalogIn(self.ads, ADS.P0)

            self.sensors['tgs'] = multisensor.TGS2611(chan0, R0=self.TGS_R0)
            self.sensors['mht7042a'] = multisensor.MHT7042A()

        except Exception as e:
            print(f"Sensor setup error: {e}")
            raise

    def _default_message_callback(self, client, userdata, message):
        """Default MQTT message callback"""
        print("Received:", str(message.payload.decode("utf-8")))
        print("Topic:", message.topic)
        print("QoS:", message.qos)
        print("Retain flag:", message.retain)

    def _ctl_thi_callback(self, client, userdata, message):
        """Control callback for start/stop commands"""
        msg = str(message.payload.decode("utf-8"))
        print(" " * 100, end="\r")
        self.is_stop = True if msg == "stop" else False

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        status = "Stopped" if self.is_stop else "Started"
        print(f"{timestamp}: ...{status}")

        # Send status confirmation
        if self.mqtt_connected:
            client.publish(f"log/{self.location}/thi/{self.node}", str(self.is_stop))

    def check_internet(self, host="8.8.8.8", port=53, timeout=3):
        """Check internet connectivity"""
        try:
            socket.setdefaulttimeout(timeout)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
            return True
        except socket.error as err:
            return False

    def is_file_empty(self, file_path):
        """Check if file is empty or doesn't exist"""
        if not os.path.exists(file_path):
            return True
        return os.path.getsize(file_path) == 0

    def read_sensors(self):
        """Read sensor data with error handling"""
        try:
            tgs_ch4, tgs_voltage = self.sensors['tgs'].read_ppm()
            mht_ch4 = self.sensors['mht7042a'].read_ch4()

            return {
                'tgs_ch4': tgs_ch4,
                'tgs_voltage': tgs_voltage,
                'mht_ch4': mht_ch4,
                'timestamp': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
            }
        except Exception as e:
            print(f"Sensor reading error: {e}")
            return None

    def save_data_to_file(self, sensor_data):
        """Save sensor data to local files"""
        if not sensor_data:
            return

        timestamp_str = sensor_data['timestamp']  # Already formatted
        date_str = datetime.now().strftime('%Y%m%d')

        # Save PPM data
        ppm_file = f"{self.data_dir}/node{self.node}_{date_str}.csv"
        file_exists = os.path.exists(ppm_file)

        try:
            with open(ppm_file, 'a', newline='') as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(["node", self.node])
                    writer.writerow(["time", "TGS", "MH_T7042A"])
                writer.writerow([timestamp_str, sensor_data['tgs_ch4'], sensor_data['mht_ch4']])
        except Exception as e:
            print(f"Error saving PPM data: {e}")

        # Save voltage data
        voltage_file = f"{self.data_dir}/node{self.node}_{date_str}_voltage.csv"
        voltage_file_exists = os.path.exists(voltage_file)

        try:
            with open(voltage_file, 'a', newline='') as f:
                writer = csv.writer(f)
                if not voltage_file_exists:
                    writer.writerow(["node", self.node])
                    writer.writerow(["time", "TGS_voltage"])
                writer.writerow([timestamp_str, sensor_data['tgs_voltage']])
        except Exception as e:
            print(f"Error saving voltage data: {e}")

    def upload_data(self, sensor_data):
        """Upload data to MQTT broker with confirmation"""
        if not sensor_data or not self.client or not self.mqtt_connected:
            return False

        try:
            with self.mqtt_lock:

                data = json.dumps({
                    "node": self.node,
                    "TGS": sensor_data['tgs_ch4'],
                    "TGS_voltage": sensor_data['tgs_voltage'],
                    "MH_T7042A": sensor_data['mht_ch4'],
                    "timestamp": sensor_data['timestamp'],  # Already formatted
                })

                # Publish with QoS 1 for better reliability
                result = self.client.publish(
                    f"data/{self.location}/sensors/{self.node}", 
                    data, 
                    qos=1
                )

                # Check if publish was successful
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    # Wait a moment for the message to be sent
                    result.wait_for_publish(timeout=5.0)
                    # print(f"Data sent with timestamp: {sensor_data['timestamp']}")
                    return True
                else:
                    print(f"MQTT publish failed with code: {result.rc}")
                    return False

        except Exception as e:
            print(f"Error uploading data: {e}")
            return False

    def save_loss_data(self, sensor_data):
        """Save data that failed to upload"""
        if not sensor_data:
            return

        loss_data_file = f"{self.data_dir}/node{self.node}_loss_data.csv"
        timestamp_str = sensor_data['timestamp']  # Already formatted

        try:
            with open(loss_data_file, 'a', newline='') as f:
                writer = csv.writer(f)
                # Save complete data including voltage
                writer.writerow([
                    timestamp_str, 
                    sensor_data['tgs_ch4'], 
                    sensor_data['tgs_voltage'],
                    sensor_data['mht_ch4']
                ])
        except Exception as e:
            print(f"Error saving loss data: {e}")

    def send_loss_data(self):
        """Send previously failed data with retry logic"""
        loss_data_file = f"{self.data_dir}/node{self.node}_loss_data.csv"

        if self.is_file_empty(loss_data_file):
            return

        try:
            successful_rows = []
            failed_rows = []

            with open(loss_data_file, 'r') as f:
                csv_reader = csv.reader(f)
                for row in csv_reader:
                    if len(row) >= 4:  # timestamp, tgs_ch4, tgs_voltage, mht_ch4
                        try:
                            # Reconstruct sensor data format
                            loss_sensor_data = {
                                'timestamp': row[0],  # Already in correct format
                                'tgs_ch4': float(row[1]),
                                'tgs_voltage': float(row[2]),
                                'mht_ch4': float(row[3]) if row[3] != '' else None
                            }

                            # Try to upload the loss data
                            if self.upload_data(loss_sensor_data):
                                successful_rows.append(row)
                                print(f"Sent loss data: {row[0]}")
                            else:
                                failed_rows.append(row)
                                
                        except (ValueError, IndexError) as e:
                            print(f"Error processing loss data row {row}: {e}")
                            failed_rows.append(row)

            # Rewrite file with only failed rows
            with open(loss_data_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerows(failed_rows)

            if successful_rows:
                print(f"Loss data processing: {len(successful_rows)} sent, {len(failed_rows)} remain")

        except Exception as e:
            print(f"Error sending loss data: {e}")

    def process_data(self, sensor_data):
        """Process sensor data with robust upload and loss data handling"""
        if not sensor_data:
            return

        # Always save locally first
        self.save_data_to_file(sensor_data)

        # Try to upload if internet is available
        if self.check_internet():
            # Setup MQTT if not already connected
            if not self.mqtt_setup_status:
                self.setup_mqtt()
                time.sleep(1)  # Give connection time to establish

            if self.mqtt_connected:
                # Try to upload current data
                upload_success = self.upload_data(sensor_data)

                if upload_success:
                    # If current data uploaded successfully, try to send any backlog
                    self.send_loss_data()
                else:
                    # If upload failed, save to loss data
                    print("Current data upload failed, saving to loss data")
                    self.save_loss_data(sensor_data)
            else:
                # MQTT not connected, save to loss data
                self.save_loss_data(sensor_data)
        else:
            # No internet, save to loss data
            self.save_loss_data(sensor_data)

    def print_configuration(self):
        """Print system configuration"""
        print(f"Node: {self.node}")
        print(f"Location: {self.location}")
        print(f"Host: {self.host}")
        print(f"Port: {self.port}")
        print(f"User: {self.username[:2] + '*'*(len(self.username) - 2) if self.username else 'Not set'}")
        print(f"Password: {'*'*10 if self.password else 'Not set'}")
        print("Demo: use ctrl-c to exit the program")
        print()

    def run(self):
        """Main execution loop"""
        self.print_configuration()

        # Initial setup
        if self.check_internet():
            self.setup_mqtt()

        self.setup_sensors()

        try:
            while True:
                if not self.is_stop:
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    print(f"{timestamp}: ...Collecting data", end="\r")

                    sensor_data = self.read_sensors()

                    if sensor_data:
                        # Update LCD display
                        try:
                            self.lcd.text(f"TGS: {sensor_data['tgs_ch4']:.2f} ppm", 1)
                            if sensor_data['mht_ch4'] is not None:
                                self.lcd.text(f"MHT: {sensor_data['mht_ch4']:.2f} ppm", 2)
                            else:
                                self.lcd.text("MHT: Error", 2)
                        except Exception as e:
                            print(f"LCD update error: {e}")

                        # Process data (save locally and upload if possible)
                        self.process_data(sensor_data)

                time.sleep(2)

        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up resources"""
        if self.client and self.mqtt_setup_status:
            self.client.loop_stop()
            self.client.disconnect()
        
        try:
            self.lcd.clear()
        except:
            pass


# Usage example
if __name__ == "__main__":
    monitor = CH4SensorMonitor()
    monitor.run()
