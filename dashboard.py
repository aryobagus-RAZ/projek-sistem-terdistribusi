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
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
    <style>
      html{background:linear-gradient(180deg,#FFD3D5 0%, #FFD3D5 100%);min-height:100vh}
      body{font-family:Segoe UI,Roboto,Arial;background:linear-gradient(180deg,#FFD3D5 0%, #FFD3D5 100%);color:#000000;padding:18px;margin:0}
      h1{margin:0 0 16px 0}
      .main-layout{display:grid;grid-template-columns:1fr 320px;gap:16px}
      .sensors-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}
      .card{background:#ffffff;padding:14px;border-radius:10px;border:1px solid rgba(0,0,0,0.08);box-shadow:0 2px 6px rgba(0,0,0,0.06)}
      .card-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
      .card-header h3{margin:0;font-size:14px;color:#000000;font-weight:600}
      .unit-badge{background:#f3f4f6;color:#374151;font-size:11px;padding:2px 8px;border-radius:10px;font-weight:500}
      .value-row{display:flex;align-items:baseline;gap:6px;margin-bottom:4px}
      .value{font-weight:700;font-size:28px;color:#000000}
      .unit{font-size:14px;color:#6b7280}
      .small{font-size:11px;color:#6b7280;margin-bottom:10px}
      .chart-container{position:relative;height:100px;width:100%}
      .log-panel{background:#ffffff;padding:14px;border-radius:10px;border:1px solid rgba(0,0,0,0.08);box-shadow:0 2px 6px rgba(0,0,0,0.06)}
      .log-panel h3{margin:0 0 10px 0;font-size:14px}
      .log{background:#fafaf9;padding:10px;border-radius:8px;border:1px solid rgba(0,0,0,0.06);height:calc(100vh - 180px);overflow-y:auto;font-size:12px}
      .evt{padding:6px 4px;border-bottom:1px dashed rgba(0,0,0,0.06)}
      .dir-pubbroker{color:#f59e0b}
      .dir-brokerpub{color:#16a34a}
      .dir-brokersub{color:#ff6b6b}
      .dir-subbroker{color:#f59e0b}
      .tiny{font-size:10px;color:#9ca3af}
      .footer-note{margin-top:14px;font-size:12px;color:#6b7280}
      @media(max-width:900px){
        .main-layout{grid-template-columns:1fr}
        .log{height:300px}
      }
      @media(max-width:600px){
        .sensors-grid{grid-template-columns:1fr}
        body{padding:12px}
      }
    </style>
  </head>
  <body>
    <h1>MQTT Dashboard</h1>
    <div class="main-layout">
      <div>
        <div class="sensors-grid" id="cards"></div>
        <div class="footer-note">Open this page while <code>publisher.py</code> is running. Dashboard sends acks back to sensors.</div>
      </div>
      <div class="log-panel">
        <h3>Event Log</h3>
        <div id="events" class="log"></div>
      </div>
    </div>
    <script>
      const MAX_POINTS = 30;
      const sensorConfig = {
        'home/livingroom/temperature': {label:'Temperature (Livingroom)', unit:'°C', color:'#ef4444', min:15, max:35},
        'home/livingroom/humidity':    {label:'Humidity (Livingroom)',    unit:'%',  color:'#3b82f6', min:0,  max:100},
        'home/entrance/motion':        {label:'Motion (Entrance)',        unit:'',   color:'#8b5cf6', min:0,  max:1},
        'home/livingroom/light':       {label:'Light Level (Livingroom)', unit:'lux',color:'#f59e0b', min:0,  max:1000},
        'home/entrance/door':          {label:'Door (Entrance)',          unit:'',   color:'#10b981', min:0,  max:1}
      };

      const cards = {};
      const charts = {};
      const cardsEl = document.getElementById('cards');

      for (let topic in sensorConfig) {
        const cfg = sensorConfig[topic];
        const id = topic.replace(/\//g,'-');
        const card = document.createElement('div');
        card.className = 'card';
        card.id = 'card-' + id;
        card.innerHTML = `
          <div class="card-header">
            <h3>${cfg.label}</h3>
            <span class="unit-badge">${cfg.unit || 'state'}</span>
          </div>
          <div class="value-row">
            <span class="value" id="v-${id}">—</span>
            <span class="unit">${cfg.unit}</span>
          </div>
          <div class="small" id="m-${id}">Waiting for data...</div>
          <div class="chart-container">
            <canvas id="chart-${id}"></canvas>
          </div>
        `;
        cardsEl.appendChild(card);

        cards[topic] = {
          v: document.getElementById('v-' + id),
          m: document.getElementById('m-' + id),
          data: []
        };

        const ctx = document.getElementById('chart-' + id).getContext('2d');
        charts[topic] = new Chart(ctx, {
          type: 'line',
          data: {
            labels: [],
            datasets: [{
              data: [],
              borderColor: cfg.color,
              backgroundColor: cfg.color + '20',
              borderWidth: 2,
              fill: true,
              tension: 0.3,
              pointRadius: 0,
              pointHoverRadius: 4
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: {duration: 200},
            plugins: {legend: {display: false}},
            scales: {
              x: {display: false},
              y: {
                display: true,
                min: cfg.min,
                max: cfg.max,
                grid: {color: 'rgba(0,0,0,0.05)'},
                ticks: {font: {size: 10}, color: '#9ca3af', maxTicksLimit: 4}
              }
            }
          }
        });
      }

      function updateChart(topic, value, timestamp) {
        const chart = charts[topic];
        const card = cards[topic];
        if (!chart || !card) return;

        const timeLabel = new Date(timestamp).toLocaleTimeString();
        card.data.push({t: timeLabel, v: value});
        if (card.data.length > MAX_POINTS) card.data.shift();

        chart.data.labels = card.data.map(d => d.t);
        chart.data.datasets[0].data = card.data.map(d => d.v);
        chart.update('none');
      }

      const eventsEl = document.getElementById('events');
      function appendEvent(item) {
        const d = new Date(item.ts || Date.now()).toLocaleTimeString();
        const div = document.createElement('div');
        div.className = 'evt';
        const dir = item.direction || '';
        let cls = '';
        if (dir === 'publisher->broker') cls = 'dir-pubbroker';
        if (dir === 'broker->subscriber') cls = 'dir-brokersub';
        if (dir === 'subscriber->broker') cls = 'dir-subbroker';
        if (dir === 'broker->publisher') cls = 'dir-brokerpub';
        const topic = item.topic || '';
        const payload = item.payload ? JSON.stringify(item.payload) : '';
        div.innerHTML = `<div><span class="${cls}">${dir}</span> <span class="tiny">${d}</span></div><div><strong>${topic}</strong> <span class="tiny">${payload}</span></div>`;
        eventsEl.prepend(div);
        if (eventsEl.children.length > 100) eventsEl.lastChild.remove();
      }

      const es = new EventSource('/stream');
      es.onmessage = function(e) {
        const item = JSON.parse(e.data);
        if (item.direction && (item.direction === 'publisher->broker' || item.direction === 'broker->subscriber')) {
          const topic = item.topic;
          const payload = item.payload || {};
          const card = cards[topic];
          if (card && payload.value !== undefined) {
            const cfg = sensorConfig[topic];
            const displayVal = (cfg && cfg.unit === '') ? (payload.value ? 'Active' : 'Inactive') : payload.value;
            card.v.textContent = displayVal;
            card.m.textContent = `Last: ${new Date(payload.ts).toLocaleTimeString()} | ID: ${payload.id}`;
            updateChart(topic, parseFloat(payload.value) || 0, payload.ts);
          }
        }
        appendEvent(item);
      };
      es.onerror = function() { console.warn('SSE connection error, will retry...'); };
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

    print(f"starting Flask app on http://{args.host}:{args.webport}")
    app.run(host=args.host, port=args.webport, debug=False, threaded=True)


if __name__ == '__main__':
    main()
