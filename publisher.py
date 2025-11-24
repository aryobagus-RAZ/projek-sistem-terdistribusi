"""
publisher.py

Simulates 5 home sensors (Temperature, Humidity, Motion, Light, Door)
Each sensor publishes realistic random readings to MQTT topics and
listens for acknowledgements on `ack/<sensor_id>`.

Usage (after installing requirements):
  python publisher.py --broker localhost --port 1883

"""
import argparse
import json
import random
import math
import threading
import time
import uuid

import paho.mqtt.client as mqtt


class Sensor(threading.Thread):
    def __init__(self, client, sensor_id, display_name, topic, interval, generator):
        super().__init__(daemon=True)
        self.client = client
        self.id = sensor_id
        self.display_name = display_name
        self.topic = topic
        self.interval = interval
        self.generator = generator
        self.acked = None
        self._stop = threading.Event()

        # subscribe to ack topic
        self.ack_topic = f"ack/{self.id}"
        self.client.message_callback_add(self.ack_topic, self._on_ack)
        self.client.subscribe(self.ack_topic)

    def _on_ack(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            orig = payload.get('origId')
            print(f"[ACK RECEIVED] {self.display_name} <- ack for msg {orig}")
            self.acked = orig
        except Exception as e:
            print("Malformed ack", e)

    def stop(self):
        self._stop.set()

    def run(self):
        while not self._stop.is_set():
            val = self.generator()
            message = { 'id': str(uuid.uuid4()), 'sensor': self.id, 'value': val, 'ts': int(time.time()*1000) }
            self.client.publish(self.topic, json.dumps(message))
            print(f"[PUBLISH] {self.topic} -> {message}")
            # wait with small jitter
            time.sleep(self.interval + random.uniform(-0.7, 0.7))


def temp_gen():
    return round(random.uniform(18.0, 26.0) + (0.5 * math.sin(time.time()/60)), 1)


def humidity_gen():
    return int(random.uniform(30, 60))


def motion_gen():
    return 'motion' if random.random() < 0.12 else 'idle'


def light_gen():
    base = 400 + 600 * (0.5 + 0.5 * math.sin(time.time()/300))
    return int(abs(base + random.uniform(-100, 100)))


def door_gen():
    return 'open' if random.random() < 0.08 else 'closed'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--broker', default='localhost')
    parser.add_argument('--port', type=int, default=1883)
    args = parser.parse_args()

    client = mqtt.Client(client_id=f"publisher-{uuid.uuid4()}")
    client.connect(args.broker, args.port, keepalive=60)
    client.loop_start()

    def make_id(room, kind):
        # readable id: <room>-<kind>-<6hex>
        return f"{room}-{kind}-{uuid.uuid4().hex[:6]}"

    sensors = [
        Sensor(client, make_id('livingroom', 'temperature'), 'Temperature (Livingroom)', 'home/livingroom/temperature', 4, temp_gen),
        Sensor(client, make_id('livingroom', 'humidity'), 'Humidity (Livingroom)', 'home/livingroom/humidity', 6, humidity_gen),
        Sensor(client, make_id('entrance', 'motion'), 'Motion (Entrance)', 'home/entrance/motion', 3, motion_gen),
        Sensor(client, make_id('livingroom', 'light'), 'Light Level (Livingroom)', 'home/livingroom/light', 5, light_gen),
        Sensor(client, make_id('entrance', 'door'), 'Door (Entrance)', 'home/entrance/door', 7, door_gen),
    ]

    for s in sensors:
        s.start()

    print("Sensors started. Press Ctrl-C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping sensors...")
        for s in sensors:
            s.stop()
        client.loop_stop()
        client.disconnect()


if __name__ == '__main__':
    main()
