import os
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()

location = os.getenv("LOCATION")

host = os.getenv("HOST", "")
port = int(os.getenv("PORT", 1883))
username = os.getenv("USERNAME", "")
password = os.getenv("PASSWORD")


def getch():
    import termios
    import sys, tty

    def _getch():
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

    return _getch()


if __name__ == "__main__":
    client = mqtt.Client()
    client.username_pw_set(username, password)
    client.connect(host, port)

    client.loop_start()
    while True:
        print("wait for user input...(press h for help)")
        ch = getch()
        if ch == "q":
            print("closing the program...")
            break
        elif ch == "h":
            print()
            print(
                "s: start group thi nodes",
                f"(topic: ctl/{location}/thi, payload: start)",
            )
            print(
                "x: stop group thi nodes",
                f"(topic: ctl/{location}/thi, payload: stop)",
            )
            print("q: quit the program")
            print("h: show help message")
        elif ch == "s":
            client.publish(f"ctl/{location}/thi", "start")
            print("...nodes start")
        elif ch == "x":
            client.publish(f"ctl/{location}/thi", "stop")
            print("...nodes stop")
        else:
            print("...wrong key")

        # control specific node only
        # client.publish(f"ctl/{location}/thi/1", "stop")
        # client.publish(f"ctl/{location}/thi/1", "start")
        print()
    client.loop_stop()
