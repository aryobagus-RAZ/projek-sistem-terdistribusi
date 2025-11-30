import argparse
import json
import queue
import threading
import time
import uuid
import importlib
import pkgutil

if not hasattr(pkgutil, 'get_loader'):
  def _get_loader(name):
    try:
      spec = importlib.util.find_spec(name)
      return getattr(spec, 'loader', None) if spec is not None else None
    except Exception:
      try:
        return importlib.find_loader(name)
      except Exception:
        return None
  pkgutil.get_loader = _get_loader

from flask import Flask, Response, stream_with_context, render_template_string
import paho.mqtt.client as mqtt

app = Flask(__name__)

event_q = queue.Queue()
latest = {}

SENSOR_TOPICS = [
    'home/livingroom/temperature',
    'home/livingroom/humidity',
    'home/entrance/motion',
    'home/livingroom/light',
    'home/entrance/door',
]

def mqtt_on_connect(client, userdata, flags, rc):
    print('Connected to broker, rc=', rc)
    for t in SENSOR_TOPICS:
        client.subscribe(t)
    client.subscribe('ack/#')

def mqtt_on_message(client, userdata, msg):
  try:
    payload = json.loads(msg.payload.decode())
  except Exception:
    print('Malformed message on', msg.topic)
    return
  ts = int(time.time()*1000)
  topic = msg.topic

  if topic.startswith('ack/'):
    event = {'direction': 'broker->publisher', 'topic': topic, 'payload': payload, 'ts': ts}
    event_q.put(event)
    print(f"[BROKER->PUBLISHER] {topic} -> {payload}")
    return

  event_q.put({'direction': 'publisher->broker', 'topic': topic, 'payload': payload, 'ts': ts})
  print(f"[PUBLISH] {topic} -> {payload}")

  event_q.put({'direction': 'broker->subscriber', 'topic': topic, 'payload': payload, 'ts': ts, 'subscriber': 'dashboard'})
  print(f"[DELIVER] {topic} -> dashboard -> {payload}")

  sensor_id = payload.get('sensor')
  latest[sensor_id] = payload

  ack_topic = f"ack/{sensor_id}"
  ack_msg = { 'origId': payload.get('id'), 'ts': int(time.time()*1000), 'from': 'dashboard' }

  info = client.publish(ack_topic, json.dumps(ack_msg))
  mid = None
  try:
    mid = info.mid
  except Exception:
    mid = None
  if mid is not None:
    userdata['pending_publishes'][mid] = {'topic': ack_topic, 'payload': ack_msg, 'ts': int(time.time()*1000)}

  event_q.put({'direction': 'subscriber->broker', 'topic': ack_topic, 'payload': ack_msg, 'ts': int(time.time()*1000), 'publisher': 'dashboard'})
  print(f"[ACK PUBLISH] {ack_topic} -> {ack_msg}")

def start_mqtt(broker, port):
    userdata = {'pending_publishes': {}}
    client = mqtt.Client(client_id=f"dashboard-{uuid.uuid4()}", userdata=userdata)
    client.user_data_set(userdata)
    client.on_connect = mqtt_on_connect
    client.on_message = mqtt_on_message

    def on_publish(c, u, mid):
        info = u['pending_publishes'].pop(mid, None)
        if info:
            event_q.put({'direction': 'broker->subscriber', 'topic': info['topic'], 'payload': info['payload'], 'ts': int(time.time()*1000), 'note': 'broker accepted publish'})
            print(f"[BROKER ACCEPTED PUBLISH mid={mid}] topic={info['topic']} payload={info['payload']}")
    client.on_publish = on_publish

    client.connect(broker, port, keepalive=60)
    t = threading.Thread(target=client.loop_forever, daemon=True)
    t.start()
    return client

@app.route('/')
def index():
    # Import HTML template dari file terpisah
    with open('dashboard_template.html', 'r', encoding='utf-8') as f:
        return f.read()

@app.route('/stream')
def stream():
    def event_stream():
        while True:
            item = event_q.get()
            data = json.dumps(item)
            yield f"data: {data}\n\n"
    return Response(stream_with_context(event_stream()), mimetype='text/event-stream')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--broker', default='localhost')
    parser.add_argument('--port', type=int, default=1883)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--webport', type=int, default=5000)
    args = parser.parse_args()

    mqtt_client = start_mqtt(args.broker, args.port)

    print(f"Starting Flask app on http://{args.host}:{args.webport}")
    app.run(host=args.host, port=args.webport, debug=False, threaded=True)

if __name__ == '__main__':
    main()