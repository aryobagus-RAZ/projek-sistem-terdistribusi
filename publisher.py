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
            message = {
                'id': str(uuid.uuid4()),
                'sensor': self.id,
                'value': val,
                'ts': int(time.time() * 1000)
            }
            self.client.publish(self.topic, json.dumps(message))
            print(f"[PUBLISH] {self.topic} -> {message}")
            
            # wait with random jitter
            time.sleep(self.interval + random.uniform(-0.7, 0.7))


def temp_gen():
    """Generate realistic temperature readings (18-26°C with sine wave variation)"""
    base_temp = 22.0
    variation = 4.0 * math.sin(time.time() / 60)
    noise = random.uniform(-0.5, 0.5)
    return round(base_temp + variation + noise, 1)


def humidity_gen():
    """Generate realistic humidity readings (30-60%)"""
    base_humidity = 45
    variation = 10 * math.sin(time.time() / 90)
    noise = random.randint(-3, 3)
    return max(30, min(60, int(base_humidity + variation + noise)))


def motion_gen():
    """Generate motion sensor readings (binary: 0 or 1)"""
    # 15% chance of motion detection
    return 1 if random.random() < 0.15 else 0


def light_gen():
    """Generate realistic light level readings (0-1200 lux)"""
    # Simulate day/night cycle
    base = 400 + 600 * (0.5 + 0.5 * math.sin(time.time() / 300))
    noise = random.uniform(-100, 100)
    return max(0, min(1200, int(base + noise)))


def door_gen():
    """Generate door sensor readings (binary: 0 or 1)"""
    # 10% chance of door being open
    return 1 if random.random() < 0.10 else 0


def main():
    parser = argparse.ArgumentParser(description='MQTT Sensor Publisher')
    parser.add_argument('--broker', default='localhost', help='MQTT broker address')
    parser.add_argument('--port', type=int, default=1883, help='MQTT broker port')
    args = parser.parse_args()

    # Create MQTT client
    client = mqtt.Client(client_id=f"publisher-{uuid.uuid4()}")
    
    # Connect to broker
    print(f"Connecting to MQTT broker at {args.broker}:{args.port}...")
    client.connect(args.broker, args.port, keepalive=60)
    client.loop_start()
    
    print("Connected successfully!")

    def make_id(room, kind):
        """Generate readable sensor ID: <room>-<kind>-<6hex>"""
        return f"{room}-{kind}-{uuid.uuid4().hex[:6]}"

    # Create sensors with different intervals
    sensors = [
        Sensor(
            client,
            make_id('livingroom', 'temperature'),
            'Temperature (Livingroom)',
            'home/livingroom/temperature',
            4,
            temp_gen
        ),
        Sensor(
            client,
            make_id('livingroom', 'humidity'),
            'Humidity (Livingroom)',
            'home/livingroom/humidity',
            6,
            humidity_gen
        ),
        Sensor(
            client,
            make_id('entrance', 'motion'),
            'Motion (Entrance)',
            'home/entrance/motion',
            3,
            motion_gen
        ),
        Sensor(
            client,
            make_id('livingroom', 'light'),
            'Light Level (Livingroom)',
            'home/livingroom/light',
            5,
            light_gen
        ),
        Sensor(
            client,
            make_id('entrance', 'door'),
            'Door (Entrance)',
            'home/entrance/door',
            7,
            door_gen
        ),
    ]

    # Start all sensors
    print("\n=== Starting sensors ===")
    for s in sensors:
        s.start()
        print(f"✓ Started: {s.display_name} (ID: {s.id})")

    print("\n=== Sensors are running ===")
    print("Press Ctrl-C to stop.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n=== Stopping sensors ===")
        for s in sensors:
            s.stop()
            print(f"✓ Stopped: {s.display_name}")
        
        client.loop_stop()
        client.disconnect()
        print("\n=== All sensors stopped ===")


if __name__ == '__main__':
    main()