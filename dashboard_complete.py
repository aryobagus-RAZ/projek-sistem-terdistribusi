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
    return render_template_string(DASHBOARD_HTML)

@app.route('/stream')
def stream():
    def event_stream():
        while True:
            item = event_q.get()
            data = json.dumps(item)
            yield f"data: {data}\n\n"
    return Response(stream_with_context(event_stream()), mimetype='text/event-stream')

# HTML Template with embedded CSS and JavaScript
DASHBOARD_HTML = '''<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>MQTT Smart Home Dashboard</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    html{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);min-height:100vh}
    body{font-family:'Segoe UI',Roboto,Arial;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:#1f2937;padding:20px}
    .header{text-align:center;margin-bottom:30px;animation:fadeIn .8s}
    .header h1{color:#fff;font-size:2.5rem;font-weight:700;margin-bottom:8px;text-shadow:0 2px 10px rgba(0,0,0,.2)}
    .header p{color:rgba(255,255,255,.9);font-size:1rem}
    .main-layout{display:grid;grid-template-columns:1fr 520px;gap:24px;max-width:1800px;margin:0 auto}
    .sensors-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:20px;animation:fadeIn 1s}
    .card{background:rgba(255,255,255,.95);backdrop-filter:blur(10px);padding:24px;border-radius:16px;border:1px solid rgba(255,255,255,.3);box-shadow:0 8px 32px rgba(0,0,0,.1);transition:all .3s;animation:slideUp .6s}
    .card:hover{transform:translateY(-5px);box-shadow:0 12px 40px rgba(0,0,0,.15)}
    .card-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}
    .card-header h3{margin:0;font-size:16px;color:#1f2937;font-weight:600;display:flex;align-items:center;gap:8px}
    .unit-badge{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:#fff;font-size:11px;padding:4px 12px;border-radius:12px;font-weight:600;box-shadow:0 2px 8px rgba(102,126,234,.3)}
    .value-row{display:flex;align-items:baseline;gap:8px;margin-bottom:8px}
    .value{font-weight:700;font-size:36px;color:#1f2937;line-height:1}
    .unit{font-size:16px;color:#6b7280;font-weight:500}
    .small{font-size:12px;color:#9ca3af;margin-bottom:16px;display:flex;align-items:center;gap:4px}
    .status-indicator{width:8px;height:8px;border-radius:50%;background:#10b981;animation:pulse 2s infinite}
    @keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
    .chart-container{position:relative;height:120px;width:100%;margin-top:12px;cursor:pointer;padding:4px;border-radius:8px;transition:background .2s}
    .chart-container:hover{background:rgba(102,126,234,.05)}
    .chart-zoom-hint{text-align:center;font-size:10px;color:#9ca3af;margin-top:4px}
    .log-panel{background:rgba(255,255,255,.95);backdrop-filter:blur(10px);padding:24px;border-radius:16px;border:1px solid rgba(255,255,255,.3);box-shadow:0 8px 32px rgba(0,0,0,.1);animation:slideLeft .8s}
    .log-panel h3{margin:0 0 16px 0;font-size:18px;color:#1f2937;font-weight:600}
    .tabs{display:flex;gap:6px;margin-bottom:16px;border-bottom:2px solid #e5e7eb;padding-bottom:8px;overflow-x:auto}
    .tab{padding:8px 14px;border:none;background:0 0;color:#6b7280;cursor:pointer;font-size:12px;font-weight:500;border-radius:8px 8px 0 0;transition:all .2s;white-space:nowrap;flex-shrink:0}
    .tab:hover{background:rgba(102,126,234,.1);color:#667eea}
    .tab.active{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:#fff}
    .log-content{display:none}
    .log-content.active{display:block}
    .log-table-wrapper{max-height:calc(100vh - 280px);overflow:auto;border:1px solid #e5e7eb;border-radius:8px;background:#fff}
    .log-table{width:100%;border-collapse:collapse;font-size:11px;background:#fff}
    .log-table thead{position:sticky;top:0;z-index:10}
    .log-table th{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:#fff;padding:10px 8px;text-align:left;font-weight:600;font-size:11px;white-space:nowrap}
    .log-table td{padding:8px;border-bottom:1px solid #f3f4f6;vertical-align:middle}
    .log-table tr:hover{background:#f9fafb}
    .log-table tr:last-child td{border-bottom:none}
    .time-cell{color:#6b7280;font-weight:500;white-space:nowrap}
    .direction-badge{display:inline-block;padding:3px 8px;border-radius:6px;font-size:9px;font-weight:600;white-space:nowrap}
    .dir-pubbroker{background:#fef3c7;color:#d97706}
    .dir-brokersub{background:#dbeafe;color:#2563eb}
    .dir-subbroker{background:#fce7f3;color:#db2777}
    .dir-brokerpub{background:#d1fae5;color:#059669}
    .topic-cell{font-weight:600;color:#374151;font-size:11px}
    .value-cell{font-weight:700;color:#1f2937;font-size:12px}
    .payload-cell{font-family:'Courier New',monospace;font-size:9px;color:#6b7280;max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .footer-note{margin-top:20px;text-align:center;font-size:13px;color:rgba(255,255,255,.9);background:rgba(255,255,255,.1);padding:12px;border-radius:8px;backdrop-filter:blur(10px)}
    .footer-note code{background:rgba(255,255,255,.2);padding:2px 8px;border-radius:4px;font-family:'Courier New',monospace}
    .modal{display:none;position:fixed;z-index:1000;left:0;top:0;width:100%;height:100%;background:rgba(0,0,0,.85);backdrop-filter:blur(5px);animation:fadeIn .3s}
    .modal.show{display:flex;align-items:center;justify-content:center}
    .modal-content{background:#fff;padding:30px;border-radius:16px;width:90%;max-width:1200px;max-height:85vh;overflow:auto;animation:scaleIn .3s;box-shadow:0 20px 60px rgba(0,0,0,.3)}
    .modal-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}
    .modal-header h2{color:#1f2937;font-size:24px;display:flex;align-items:center;gap:10px}
    .close-btn{background:#ef4444;color:#fff;border:none;padding:10px 20px;border-radius:8px;cursor:pointer;font-weight:600;transition:all .2s}
    .close-btn:hover{background:#dc2626;transform:scale(1.05)}
    .modal-chart-container{height:550px;position:relative}
    @keyframes fadeIn{from{opacity:0}to{opacity:1}}
    @keyframes slideUp{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)}}
    @keyframes slideLeft{from{opacity:0;transform:translateX(20px)}to{opacity:1;transform:translateX(0)}}
    @keyframes scaleIn{from{opacity:0;transform:scale(.9)}to{opacity:1;transform:scale(1)}}
    @media(max-width:1200px){.main-layout{grid-template-columns:1fr}.log-table-wrapper{max-height:400px}}
    @media(max-width:768px){body{padding:12px}.header h1{font-size:1.8rem}.sensors-grid{grid-template-columns:1fr}.modal-content{width:95%;padding:20px}.modal-chart-container{height:350px}.log-table th,.log-table td{padding:6px 4px;font-size:10px}}
  </style>
</head>
<body>
  <div class="header">
    <h1>🏠 MQTT Smart Home Dashboard</h1>
    <p>Real-time monitoring</p>
  </div>
  <div class="main-layout">
    <div>
      <div class="sensors-grid" id="cards"></div>
      <div class="footer-note">
      </div>
    </div>
    <div class="log-panel">
      <h3>📊 Event Monitoring</h3>
      <div class="tabs" id="tabs"></div>
      <div id="log-contents"></div>
    </div>
  </div>
  
  <div id="chartModal" class="modal">
    <div class="modal-content">
      <div class="modal-header">
        <h2 id="modalTitle">📈 Chart Detail</h2>
        <button class="close-btn" onclick="closeModal()">✕ Close</button>
      </div>
      <div class="modal-chart-container">
        <canvas id="modalChart"></canvas>
      </div>
    </div>
  </div>
  <script>
    const MAX_POINTS=30;
    const sensorConfig={'home/livingroom/temperature':{label:'Temperature',location:'Livingroom',unit:'°C',color:'#ef4444',min:15,max:35,icon:'🌡️'},'home/livingroom/humidity':{label:'Humidity',location:'Livingroom',unit:'%',color:'#3b82f6',min:0,max:100,icon:'💧'},'home/entrance/motion':{label:'Motion Sensor',location:'Entrance',unit:'',color:'#8b5cf6',min:0,max:1,icon:'👁️'},'home/livingroom/light':{label:'Light Level',location:'Livingroom',unit:'lux',color:'#f59e0b',min:0,max:1200,icon:'💡'},'home/entrance/door':{label:'Door Sensor',location:'Entrance',unit:'',color:'#10b981',min:0,max:1,icon:'🚪'}};
    const cards={},charts={},sensorLogs={};
    let modalChart=null;
    const cardsEl=document.getElementById('cards'),tabsEl=document.getElementById('tabs'),logContentsEl=document.getElementById('log-contents');
    for(let topic in sensorConfig){
      const cfg=sensorConfig[topic],id=topic.replace(/\\//g,'-'),card=document.createElement('div');
      card.className='card';card.id='card-'+id;
      card.innerHTML=`<div class="card-header"><h3><span class="sensor-icon">${cfg.icon}</span>${cfg.label}</h3><span class="unit-badge">${cfg.location}</span></div><div class="value-row"><span class="value" id="v-${id}">—</span><span class="unit">${cfg.unit}</span></div><div class="small"><span class="status-indicator"></span><span id="m-${id}">Waiting for data...</span></div><div class="chart-container" onclick="openModal('${topic}')"><canvas id="chart-${id}"></canvas><div class="chart-zoom-hint">🔍 Click to enlarge</div></div>`;
      cardsEl.appendChild(card);
      cards[topic]={v:document.getElementById('v-'+id),m:document.getElementById('m-'+id),data:[]};
      const ctx=document.getElementById('chart-'+id).getContext('2d');
      charts[topic]=new Chart(ctx,{type:'line',data:{labels:[],datasets:[{data:[],borderColor:cfg.color,backgroundColor:cfg.color+'30',borderWidth:3,fill:!0,tension:.4,pointRadius:3,pointHoverRadius:6,pointBackgroundColor:cfg.color,pointBorderColor:'#fff',pointBorderWidth:2}]},options:{responsive:!0,maintainAspectRatio:!1,animation:{duration:300},plugins:{legend:{display:!1},tooltip:{backgroundColor:'rgba(0,0,0,0.8)',titleColor:'#fff',bodyColor:'#fff',padding:12,displayColors:!1,callbacks:{label:c=>`Value: ${c.parsed.y} ${cfg.unit}`}}},scales:{x:{display:!1},y:{display:!0,min:cfg.min,max:cfg.max,grid:{color:'rgba(0,0,0,0.05)'},ticks:{font:{size:11,weight:'500'},color:'#6b7280',maxTicksLimit:5}}}}});
      const tab=document.createElement('button');
      tab.className='tab';tab.id='tab-'+id;tab.textContent=cfg.icon+' '+cfg.label;tab.onclick=()=>switchTab(id);
      tabsEl.appendChild(tab);
      const logContent=document.createElement('div');
      logContent.className='log-content';logContent.id='log-'+id;
      logContent.innerHTML=`<div class="log-table-wrapper"><table class="log-table"><thead><tr><th style="width:80px">Time</th><th style="width:100px">Direction</th><th style="width:80px">Topic</th><th style="width:70px">Value</th><th>Payload</th></tr></thead><tbody id="tbody-${id}"></tbody></table></div>`;
      logContentsEl.appendChild(logContent);
      sensorLogs[topic]={tbody:document.getElementById('tbody-'+id),events:[]};
    }
    if(tabsEl.firstChild){tabsEl.firstChild.classList.add('active');logContentsEl.firstChild.classList.add('active')}
    function switchTab(id){document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));document.querySelectorAll('.log-content').forEach(c=>c.classList.remove('active'));document.getElementById('tab-'+id).classList.add('active');document.getElementById('log-'+id).classList.add('active')}
    function updateChart(topic,value,timestamp){const chart=charts[topic],card=cards[topic];if(!chart||!card)return;const timeLabel=new Date(timestamp).toLocaleTimeString();card.data.push({t:timeLabel,v:value});if(card.data.length>MAX_POINTS)card.data.shift();chart.data.labels=card.data.map(d=>d.t);chart.data.datasets[0].data=card.data.map(d=>d.v);chart.update('none')}
    function formatValue(value,cfg){if(cfg.unit==='')return value===1||value==='active'||value==='motion'||value==='open'?'Active':'Inactive';else if(typeof value==='number')return value.toFixed(1);return value}
    function appendEventToTable(topic,item){const log=sensorLogs[topic];if(!log)return;const time=new Date(item.ts||Date.now()).toLocaleTimeString(),dir=item.direction||'';let dirClass='',dirText=dir;if(dir==='publisher->broker'){dirClass='dir-pubbroker';dirText='📤 Pub'}else if(dir==='broker->subscriber'){dirClass='dir-brokersub';dirText='📥 Del'}else if(dir==='subscriber->broker'){dirClass='dir-subbroker';dirText='📨 Ack'}else if(dir==='broker->publisher'){dirClass='dir-brokerpub';dirText='✅ Recv'}const payload=item.payload||{},cfg=sensorConfig[topic],topicShort=item.topic?item.topic.split('/').pop():'';let displayValue='—';if(payload.value!==undefined)displayValue=formatValue(payload.value,cfg);const payloadStr=JSON.stringify(payload),row=document.createElement('tr');row.innerHTML=`<td class="time-cell">${time}</td><td><span class="direction-badge ${dirClass}">${dirText}</span></td><td class="topic-cell">${topicShort}</td><td class="value-cell">${displayValue}</td><td class="payload-cell" title="${payloadStr}">${payloadStr}</td>`;log.tbody.insertBefore(row,log.tbody.firstChild);if(log.tbody.children.length>50)log.tbody.removeChild(log.tbody.lastChild)}
    function openModal(topic){const cfg=sensorConfig[topic],card=cards[topic];document.getElementById('modalTitle').innerHTML=`${cfg.icon} ${cfg.label} - ${cfg.location}`;const modal=document.getElementById('chartModal');modal.classList.add('show');if(modalChart)modalChart.destroy();const ctx=document.getElementById('modalChart').getContext('2d');modalChart=new Chart(ctx,{type:'line',data:{labels:card.data.map(d=>d.t),datasets:[{label:`${cfg.label} (${cfg.unit})`,data:card.data.map(d=>d.v),borderColor:cfg.color,backgroundColor:cfg.color+'20',borderWidth:4,fill:!0,tension:.4,pointRadius:5,pointHoverRadius:8,pointBackgroundColor:cfg.color,pointBorderColor:'#fff',pointBorderWidth:3}]},options:{responsive:!0,maintainAspectRatio:!1,animation:{duration:500},plugins:{legend:{display:!0,labels:{font:{size:14,weight:'bold'},color:'#1f2937'}},tooltip:{backgroundColor:'rgba(0,0,0,0.8)',titleColor:'#fff',bodyColor:'#fff',padding:15,displayColors:!0,titleFont:{size:14},bodyFont:{size:13},callbacks:{label:c=>`${cfg.label}: ${c.parsed.y} ${cfg.unit}`}}},scales:{x:{display:!0,grid:{color:'rgba(0,0,0,0.05)'},ticks:{font:{size:12},color:'#6b7280',maxTicksLimit:10}},y:{display:!0,min:cfg.min,max:cfg.max,grid:{color:'rgba(0,0,0,0.1)'},ticks:{font:{size:13,weight:'500'},color:'#374151',maxTicksLimit:10}}}}})}
    function closeModal(){const modal=document.getElementById('chartModal');modal.classList.remove('show');if(modalChart){modalChart.destroy();modalChart=null}}
    window.onclick=e=>{const modal=document.getElementById('chartModal');if(e.target===modal)closeModal()};
    document.addEventListener('keydown',e=>{if(e.key==='Escape')closeModal()});
    const es=new EventSource('/stream');
    es.onmessage=e=>{const item=JSON.parse(e.data),topic=item.topic;if(item.direction&&(item.direction==='publisher->broker'||item.direction==='broker->subscriber')){const payload=item.payload||{},card=cards[topic];if(card&&payload.value!==undefined){const cfg=sensorConfig[topic],displayVal=formatValue(payload.value,cfg);card.v.textContent=displayVal;card.m.textContent=`Last: ${new Date(payload.ts).toLocaleTimeString()} • ID: ${payload.id?payload.id.substr(0,8):'N/A'}`;const numValue=typeof payload.value==='number'?payload.value:displayVal==='Active'?1:0;updateChart(topic,numValue,payload.ts)}}for(let sensorTopic in sensorConfig)if(topic&&(topic.includes(sensorTopic)||topic.startsWith('ack/')&&item.payload&&item.payload.origId)){appendEventToTable(sensorTopic,item);break}};
    es.onerror=()=>console.warn('SSE connection error, will retry...');
    console.log('Dashboard initialized!');
  </script>
</body>
</html>
'''

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--broker', default='localhost')
    parser.add_argument('--port', type=int, default=1883)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--webport', type=int, default=5000)
    args = parser.parse_args()

    mqtt_client = start_mqtt(args.broker, args.port)

    print(f"✓ Starting Flask app on http://{args.host}:{args.webport}")
    print(f"✓ Connected to MQTT broker at {args.broker}:{args.port}")
    print(f"✓ Dashboard ready!")
    app.run(host=args.host, port=args.webport, debug=False, threaded=True)

if __name__ == '__main__':
    main()