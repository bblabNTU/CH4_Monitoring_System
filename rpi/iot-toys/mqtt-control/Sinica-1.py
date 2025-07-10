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
import math
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
from rpi_lcd import LCD



load_dotenv()

is_stop = False

#MQ4_R0=3.323
TGS0_R0=1.46
TGS_R0=1.93

host = os.getenv("HOST", "")
port = int(os.getenv("PORT", 1883))
username = os.getenv("USERNAME", "")
password = os.getenv("PASSWORD")
node = os.getenv("NODE")
location = os.getenv("LOCATION")

def mqtt_connect_setup():
    try: 
        client.username_pw_set(username, password)
        client.connect(host, port)
        
        client.message_callback_add(f"ctl/{location}/thi", ctl_thi_cb)
        client.message_callback_add(f"ctl/{location}/thi/{node}", ctl_thi_cb)
        client.on_message = default_cb  # default received callback

        client.subscribe(f"ctl/{location}/thi/#")
        client.loop_start()
        mqttSetupStatus = True
    except ConnectionError as e:
        print(e)

def default_cb(client: mqtt.Client, userdata, message):
    _ = client, userdata
    print("received:", str(message.payload.decode("utf-8")))
    print("topic:", message.topic)
    print("qos:", message.qos)
    print("retain flag:", message.retain)


def ctl_thi_cb(client: mqtt.Client, userdata, message):
    _ = client, userdata
    global is_stop
    msg = str(message.payload.decode("utf-8"))
    print(" " * 100, end="\r")
    is_stop = True if msg == "stop" else False

    if is_stop:
        print(
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}:" " ...Stopped",
        )
    else:
        print(
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}:" " ...Start",
        )

    # return log
    client.publish(f"log/{location}/thi/{node}", str(is_stop))

def have_internet(host="8.8.8.8", port=53, timeout=3):
    '''
    Check internet status. Return 'True' if connected; 'False' if NOT connected.
    '''
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except socket.error as err:
        print(err)
        return False

def is_file_empty(file_path):
    if not os.path.exists(file_path):
        return True
    return os.path.getsize(file_path) == 0

# ===== Sensor upload func =====
def upload_data(data):
    # Upload current data to server
    client.publish(f"data/{location}/sensors/{node}", data)
    
            
# ===== Resend loss data func =====
def send_loss_data(tempFilePath):
    # Check if there is loss data
        if not is_file_empty(tempFilePath):
            # Insert data from temp file
            with open(tempFilePath, 'r') as read_file:
                csv_reader = csv.reader(read_file)
                for row in csv_reader:
                    data = json.dumps(
                        {"node": node, "MQ4": float(row[1]), "TGS": float(row[2]), "timestamp": row[0]}
                    )
                    client.publish(f"data/{location}/sensors/{node}", data)
                    print(data)
                  

            # Cleanup file after sending to server
            with open(tempFilePath, 'w') as clean_file:
                clean_file.truncate(0)

if __name__ == "__main__":
    print(f"node: {node}")
    print(f"location: {location}")
    print(f"host: {host}")
    print(f"port: {port}")
    print(f"user: {username[:2] + '*'*(len(username) - 2)}")
    print(f"password: {'*'*10}")
    print("demo: use ctrl-c to exit the program")
    print()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    mqttSetupStatus = False
    if have_internet():
        mqtt_connect_setup()
        mqttSetupStatus = True
### for sensors
    # Create the I2C bus
    i2c = busio.I2C(board.SCL, board.SDA, frequency=100000)
    ads = ADS.ADS1115(i2c)
    ads.gain = 1
    chan0 = AnalogIn(ads, ADS.P0)
    chan1 = AnalogIn(ads, ADS.P1)
    #mq4_sensor = multisensor.MQ4GasSensor(chan0, R0=MQ4_R0)
    tgs0 = multisensor.TGS2611(chan0, R0=TGS0_R0)
    tgs_sensor = multisensor.TGS2611(chan1, R0=TGS_R0)

    lcd = LCD()

    try:
        while True:
            if not is_stop:
                print(
                    f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}:"
                    " ...Colleting data",
                    end="\r",
                )
            # TODO: write yout logic here

            # get thi from sensor. and return the data like below
                #mq4_ch4, mq4_voltage = mq4_sensor.read_ppm()
                tgs0_ch4, tgs0_voltage = tgs0.read_ppm()
                tgs_ch4, tgs_voltage = tgs_sensor.read_ppm()
            # print("MQ4 ppm:", mq4_ch4, "Voltage:", mq4_voltage)
                #print("TGS ppm:", tgs_ch4, "Voltage:", tgs_voltage)

                lcd.text(f"TGS0: {tgs0_ch4:.2f} ppm", 1)
                lcd.text(f"TGS: {tgs_ch4:.2f} ppm", 2)
                
                now = datetime.utcnow()
                 
                
            # ===== Save the data to a local file =====
                file_path = f"/home/pi/CH4_data/node{node}_{datetime.now().strftime('%Y%m%d')}.csv"
                file_exist = os.path.exists(file_path)
                with open(file_path, 'a') as f:
                    # now = datetime.now()

                    writer_object =csv.writer(f)
                    if not file_exist:
                        writer_object.writerow(["node", node])
                        writer_object.writerow(["time", "TGS0", "TGS2611"])

                    writer_object.writerow([now.strftime('%Y-%m-%dT%H:%M:%SZ'), tgs0_ch4, tgs_ch4])
                    f.close()

                file_path_voltage = f"/home/pi/CH4_data/node{node}_{datetime.now().strftime('%Y%m%d')}_voltage.csv"
                file_voltage_exist = os.path.exists(file_path_voltage)

                with open(file_path_voltage, 'a') as f:
                    # now = datetime.now()

                    writer_object =csv.writer(f)
                    if not file_voltage_exist:
                        writer_object.writerow(["node", node])
                        writer_object.writerow(["time", "TGS0_voltage", "TGS2611_voltage"])

                    writer_object.writerow([now.strftime('%Y-%m-%dT%H:%M:%SZ'), tgs0_voltage, tgs_voltage])
                    f.close()

            # ===== Save data to server =====
                data = json.dumps(
                    {"node": node, "TGS0": tgs0_ch4, "TGS0_voltage": tgs0_voltage, "TGS": tgs_ch4, "TGS_voltage": tgs_voltage, "timestamp": now.strftime('%Y-%m-%dT%H:%M:%SZ')}
                )
                loss_data_file_path = f"/home/pi/CH4_data/node{node}_loss_data.csv"
                if have_internet():
                    if not mqttSetupStatus:
                        mqtt_connect_setup()
                        mqttSetupStatus = True
                    
                    thread1 = threading.Thread(target=upload_data, args=(data,))
                    thread2 = threading.Thread(target=send_loss_data, args=(loss_data_file_path,))

                    thread1.start()
                    thread2.start()
                    thread1.join()
                    thread2.join()
                else:
                    with open(loss_data_file_path, 'a') as f:
                        writer_object =csv.writer(f)
                        writer_object.writerow([now.strftime('%Y-%m-%dT%H:%M:%SZ'), tgs0_ch4, tgs_ch4])
    # print(now)
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        lcd.clear()

    # NOTE: this shouldn't be execute. Use kill to close the program
    # client.loop_stop()
