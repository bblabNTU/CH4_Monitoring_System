import serial
import time

ser = serial.Serial('/dev/serial0', baudrate=9600, timeout=1)

def read_ch4():
    while True:
        ser.write(b'\xFF\x01\x86\x00\x00\x00\x00\x00\x79')
        data = ser.read(9)
        if len(data) == 9 and data[0] == 0xFF and data[1]== 0x86:
            high = data[2]
            low = data[3]
            ch4_ppm = (high << 8) +low
            print(f"CH4: {ch4_ppm} ppm")
        else:
            print("Invalid resoponse")
        time.sleep(2)

try:
    read_ch4()
except KeyboardInterrupt:
    ser.close()
    print("Stopped")
