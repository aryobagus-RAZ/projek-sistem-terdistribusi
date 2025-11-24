"""
dashboard.py

Runs an MQTT subscriber that listens to all sensor topics, sends ack messages
back to sensor-specific ack topics, and exposes a small Flask web UI that shows
live readings via Server-Sent Events (SSE).

Usage (after installing requirements):
  python dashboard.py --broker localhost --port 1883 --host 0.0.0.0 --webport 5000

Open http://localhost:5000 in a browser.
"""
import argparse
import json
import queue
import threading
import time
import uuid
import importlib
import pkgutil

# Compatibility shim: ensure pkgutil.get_loader exists. Some environments (or a
# local module named 'pkgutil') can shadow the stdlib and miss this helper.
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

# Simple in-memory event queue for SSE
event_q = queue.Queue()

# store latest sensor values
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
    # subscribe to ack topics to observe ack deliveries back to publishers
    client.subscribe('ack/#')


def mqtt_on_message(client, userdata, msg):
  try:
    payload = json.loads(msg.payload.decode())
  except Exception:
    print('Malformed message on', msg.topic)
    return
  ts = int(time.time()*1000)
  topic = msg.topic

  # If this is an ack topic, it's a broker delivery of an ack (subscriber->broker->publisher path)
  if topic.startswith('ack/'):
    # broker -> (subscribers including publisher)
    event = {'direction': 'broker->publisher', 'topic': topic, 'payload': payload, 'ts': ts}
    event_q.put(event)
    print(f"[BROKER->PUBLISHER] {topic} -> {payload}")
    return

  # Regular sensor topic: represent the two hops
  # 1) publisher -> broker (publish)
  event_q.put({'direction': 'publisher->broker', 'topic': topic, 'payload': payload, 'ts': ts})
  print(f"[PUBLISH] {topic} -> {payload}")

  # 2) broker -> subscriber (delivery to this dashboard)
  event_q.put({'direction': 'broker->subscriber', 'topic': topic, 'payload': payload, 'ts': ts, 'subscriber': 'dashboard'})
  print(f"[DELIVER] {topic} -> dashboard -> {payload}")

  # store latest
  sensor_id = payload.get('sensor')
  latest[sensor_id] = payload

  # send ack back
  ack_topic = f"ack/{sensor_id}"
  ack_msg = { 'origId': payload.get('id'), 'ts': int(time.time()*1000), 'from': 'dashboard' }

  # publish and track mid to log broker acceptance
  info = client.publish(ack_topic, json.dumps(ack_msg))
  mid = None
  try:
    mid = info.mid
  except Exception:
    mid = None
  if mid is not None:
    # store pending publish details so on_publish can log them
    userdata['pending_publishes'][mid] = {'topic': ack_topic, 'payload': ack_msg, 'ts': int(time.time()*1000)}

  event_q.put({'direction': 'subscriber->broker', 'topic': ack_topic, 'payload': ack_msg, 'ts': int(time.time()*1000), 'publisher': 'dashboard'})
  print(f"[ACK PUBLISH] {ack_topic} -> {ack_msg}")


def start_mqtt(broker, port):
    # we attach a userdata dict to share state (pending publishes mapping)
    userdata = {'pending_publishes': {}}
    client = mqtt.Client(client_id=f"dashboard-{uuid.uuid4()}", userdata=userdata)
    client.user_data_set(userdata)
    client.on_connect = mqtt_on_connect
    client.on_message = mqtt_on_message

    # on_publish: called when broker acknowledges receipt of a PUBLISH (server ack for QoS>0)
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
    # simple page that opens EventSource and draws cards
    return render_template_string(INDEX_HTML)


@app.route('/stream')
def stream():
    def event_stream():
        while True:
            item = event_q.get()
            data = json.dumps(item)
            yield f"data: {data}\n\n"
    return Response(stream_with_context(event_stream()), mimetype='text/event-stream')


INDEX_HTML = r"""
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>MQTT Dashboard</title>
    <style>
      html{background:linear-gradient(180deg,#FFD3D5 0%, #FFD3D5 100%);min-height:100vh}
      body{font-family:Segoe UI,Roboto,Arial;background:linear-gradient(180deg,#FFD3D5 0%, #FFD3D5 100%);color:#000000;padding:18px}
      .layout{display:grid;grid-template-columns:2fr 1fr;gap:14px}
      .grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}
      .card{background:#ffffff;padding:12px;border-radius:8px;border:1px solid rgba(0,0,0,0.08);box-shadow:0 1px 3px rgba(0,0,0,0.05);margin-bottom:8px}
      h3{margin:0;font-size:13px;color:#000000}
      .value{font-weight:700;font-size:20px;margin-top:6px;color:#000000}
      .small{font-size:12px;color:#000000}
      .log{background:#fafaf9;padding:10px;border-radius:8px;border:1px solid rgba(0,0,0,0.08);height:480px;overflow:auto;font-size:13px}
      .evt{padding:6px;border-bottom:1px dashed rgba(0,0,0,0.05);}
      .dir-pubbroker{color:#f59e0b}
      .dir-brokerpub{color:#16a34a}
      .dir-brokersub{color:#ff6b6b}
      .dir-subbroker{color:#f59e0b}
      .tiny{font-size:11px;color:#6b7280}
    </style>
  </head>
  <body>
    <h1>MQTT Dashboard</h1>
    <div class="layout">
      <div>
        <div class="grid" id="cards"></div>
        <div style="margin-top:12px;color:#000000">Open this page while `publisher.py` is running. Dashboard will send acks back to sensors.</div>
      </div>
      <div>
        <div style="margin-bottom:8px"><strong>Event Log</strong></div>
        <div id="events" class="log"></div>
      </div>
    </div>
    <script>
      const topics = {
        'home/livingroom/temperature':'Temperature (Livingroom)',
        'home/livingroom/humidity':'Humidity (Livingroom)',
        'home/entrance/motion':'Motion (Entrance)',
        'home/livingroom/light':'Light Level (Livingroom)',
        'home/entrance/door':'Door (Entrance)'
      };
      const cards = {};
      const cardsEl = document.getElementById('cards');
      for (let t in topics) {
        const id = t.replace(/\//g,'-');
        const c = document.createElement('div'); c.className='card'; c.id='card-'+id;
        c.innerHTML = `<h3>${topics[t]}</h3><div class='value' id='v-${id}'>—</div><div class='small' id='m-${id}'>topic: ${t}</div>`;
        cardsEl.appendChild(c);
        cards[t] = {v:document.getElementById('v-'+id), m:document.getElementById('m-'+id)};
      }

      const eventsEl = document.getElementById('events');
      function appendEvent(item){
        const d = new Date(item.ts||Date.now()).toLocaleTimeString();
        const div = document.createElement('div'); div.className='evt';
        const dir = item.direction || '';
        let cls = '';
        if(dir==='publisher->broker') cls='dir-pubbroker';
        if(dir==='broker->subscriber') cls='dir-brokersub';
        if(dir==='subscriber->broker') cls='dir-subbroker';
        if(dir==='broker->publisher') cls='dir-brokerpub';
        const topic = item.topic || '';
        const payload = item.payload ? JSON.stringify(item.payload) : '';
        div.innerHTML = `<div><span class='${cls}'>${dir}</span> <span class='tiny'>${d}</span></div><div><strong>${topic}</strong> ${payload}</div>`;
        eventsEl.prepend(div);
      }

      const es = new EventSource('/stream');
      es.onmessage = function(e) {
        const item = JSON.parse(e.data);
        // update cards for sensor messages
        if(item.direction && (item.direction==='publisher->broker' || item.direction==='broker->subscriber')){
          const topic = item.topic;
          const payload = item.payload || {};
          const el = cards[topic];
          if(el && payload.value!==undefined){
            el.v.textContent = payload.value;
            el.m.textContent = `last: ${new Date(payload.ts).toLocaleTimeString()} id:${payload.id}`;
          }
        }
        // append every event to the log for visibility
        appendEvent(item);
      };
    </script>
  </body>
</html>
"""


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
