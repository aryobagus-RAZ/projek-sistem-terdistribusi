const MAX_POINTS = 30;

const sensorConfig = {
  'home/livingroom/temperature': {
    label: 'Temperature',
    location: 'Livingroom',
    unit: '°C',
    color: '#ef4444',
    min: 15,
    max: 35,
    icon: '🌡️'
  },
  'home/livingroom/humidity': {
    label: 'Humidity',
    location: 'Livingroom',
    unit: '%',
    color: '#3b82f6',
    min: 0,
    max: 100,
    icon: '💧'
  },
  'home/entrance/motion': {
    label: 'Motion Sensor',
    location: 'Entrance',
    unit: '',
    color: '#8b5cf6',
    min: 0,
    max: 1,
    icon: '👁️'
  },
  'home/livingroom/light': {
    label: 'Light Level',
    location: 'Livingroom',
    unit: 'lux',
    color: '#f59e0b',
    min: 0,
    max: 1200,
    icon: '💡'
  },
  'home/entrance/door': {
    label: 'Door Sensor',
    location: 'Entrance',
    unit: '',
    color: '#10b981',
    min: 0,
    max: 1,
    icon: '🚪'
  }
};

const cards = {};
const charts = {};
const sensorLogs = {};
let modalChart = null;

const cardsEl = document.getElementById('cards');
const tabsEl = document.getElementById('tabs');
const logContentsEl = document.getElementById('log-contents');

// Create sensor cards
for (let topic in sensorConfig) {
  const cfg = sensorConfig[topic];
  const id = topic.replace(/\//g, '-');
  
  const card = document.createElement('div');
  card.className = 'card';
  card.id = 'card-' + id;
  card.innerHTML = `
    <div class="card-header">
      <h3>
        <span class="sensor-icon">${cfg.icon}</span>
        ${cfg.label}
      </h3>
      <span class="unit-badge">${cfg.location}</span>
    </div>
    <div class="value-row">
      <span class="value" id="v-${id}">—</span>
      <span class="unit">${cfg.unit}</span>
    </div>
    <div class="small">
      <span class="status-indicator"></span>
      <span id="m-${id}">Waiting for data...</span>
    </div>
    <div class="chart-container" onclick="openModal('${topic}')">
      <canvas id="chart-${id}"></canvas>
      <div class="chart-zoom-hint">🔍 Click to enlarge</div>
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
        backgroundColor: cfg.color + '30',
        borderWidth: 3,
        fill: true,
        tension: 0.4,
        pointRadius: 3,
        pointHoverRadius: 6,
        pointBackgroundColor: cfg.color,
        pointBorderColor: '#ffffff',
        pointBorderWidth: 2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 300 },
      plugins: { 
        legend: { display: false },
        tooltip: {
          backgroundColor: 'rgba(0, 0, 0, 0.8)',
          titleColor: '#ffffff',
          bodyColor: '#ffffff',
          padding: 12,
          displayColors: false,
          callbacks: {
            label: function(context) {
              return `Value: ${context.parsed.y} ${cfg.unit}`;
            }
          }
        }
      },
      scales: {
        x: { display: false },
        y: {
          display: true,
          min: cfg.min,
          max: cfg.max,
          grid: { color: 'rgba(0,0,0,0.05)' },
          ticks: {
            font: { size: 11, weight: '500' },
            color: '#6b7280',
            maxTicksLimit: 5
          }
        }
      }
    }
  });

  // Create tab and log table for each sensor
  const tabId = 'tab-' + id;
  const tab = document.createElement('button');
  tab.className = 'tab';
  tab.id = tabId;
  tab.textContent = cfg.icon + ' ' + cfg.label;
  tab.onclick = () => switchTab(id);
  tabsEl.appendChild(tab);

  const logContent = document.createElement('div');
  logContent.className = 'log-content';
  logContent.id = 'log-' + id;
  logContent.innerHTML = `
    <div class="log-table-wrapper">
      <table class="log-table">
        <thead>
          <tr>
            <th style="width: 80px;">Time</th>
            <th style="width: 100px;">Direction</th>
            <th style="width: 80px;">Topic</th>
            <th style="width: 70px;">Value</th>
            <th>Payload</th>
          </tr>
        </thead>
        <tbody id="tbody-${id}"></tbody>
      </table>
    </div>
  `;
  logContentsEl.appendChild(logContent);

  sensorLogs[topic] = {
    tbody: document.getElementById('tbody-' + id),
    events: []
  };
}

// Activate first tab
if (tabsEl.firstChild) {
  tabsEl.firstChild.classList.add('active');
  logContentsEl.firstChild.classList.add('active');
}

function switchTab(id) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.log-content').forEach(c => c.classList.remove('active'));
  document.getElementById('tab-' + id).classList.add('active');
  document.getElementById('log-' + id).classList.add('active');
}

function updateChart(topic, value, timestamp) {
  const chart = charts[topic];
  const card = cards[topic];
  if (!chart || !card) return;

  const timeLabel = new Date(timestamp).toLocaleTimeString();
  card.data.push({ t: timeLabel, v: value });
  if (card.data.length > MAX_POINTS) card.data.shift();

  chart.data.labels = card.data.map(d => d.t);
  chart.data.datasets[0].data = card.data.map(d => d.v);
  chart.update('none');
}

function formatValue(value, cfg) {
  if (cfg.unit === '') {
    // Binary sensors
    return (value === 1 || value === 'active' || value === 'motion' || value === 'open') ? 'Active' : 'Inactive';
  } else if (typeof value === 'number') {
    return value.toFixed(1);
  }
  return value;
}

function appendEventToTable(topic, item) {
  const log = sensorLogs[topic];
  if (!log) return;

  const time = new Date(item.ts || Date.now()).toLocaleTimeString();
  const dir = item.direction || '';
  let dirClass = '';
  let dirText = dir;
  
  if (dir === 'publisher->broker') {
    dirClass = 'dir-pubbroker';
    dirText = '📤 Pub';
  } else if (dir === 'broker->subscriber') {
    dirClass = 'dir-brokersub';
    dirText = '📥 Del';
  } else if (dir === 'subscriber->broker') {
    dirClass = 'dir-subbroker';
    dirText = '📨 Ack';
  } else if (dir === 'broker->publisher') {
    dirClass = 'dir-brokerpub';
    dirText = '✅ Recv';
  }

  const payload = item.payload || {};
  const cfg = sensorConfig[topic];
  const topicShort = item.topic ? item.topic.split('/').pop() : '';
  
  // Extract value
  let displayValue = '—';
  if (payload.value !== undefined) {
    displayValue = formatValue(payload.value, cfg);
  }
  
  const payloadStr = JSON.stringify(payload);

  const row = document.createElement('tr');
  row.innerHTML = `
    <td class="time-cell">${time}</td>
    <td><span class="direction-badge ${dirClass}">${dirText}</span></td>
    <td class="topic-cell">${topicShort}</td>
    <td class="value-cell">${displayValue}</td>
    <td class="payload-cell" title="${payloadStr}">${payloadStr}</td>
  `;

  log.tbody.insertBefore(row, log.tbody.firstChild);
  
  // Keep only last 50 events per sensor
  if (log.tbody.children.length > 50) {
    log.tbody.removeChild(log.tbody.lastChild);
  }
}

// Modal functions
function openModal(topic) {
  const cfg = sensorConfig[topic];
  const card = cards[topic];
  
  document.getElementById('modalTitle').innerHTML = `${cfg.icon} ${cfg.label} - ${cfg.location}`;
  
  const modal = document.getElementById('chartModal');
  modal.classList.add('show');
  
  // Destroy previous modal chart if exists
  if (modalChart) {
    modalChart.destroy();
  }
  
  // Create new modal chart
  const ctx = document.getElementById('modalChart').getContext('2d');
  modalChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: card.data.map(d => d.t),
      datasets: [{
        label: `${cfg.label} (${cfg.unit})`,
        data: card.data.map(d => d.v),
        borderColor: cfg.color,
        backgroundColor: cfg.color + '20',
        borderWidth: 4,
        fill: true,
        tension: 0.4,
        pointRadius: 5,
        pointHoverRadius: 8,
        pointBackgroundColor: cfg.color,
        pointBorderColor: '#ffffff',
        pointBorderWidth: 3
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 500 },
      plugins: { 
        legend: { 
          display: true,
          labels: {
            font: { size: 14, weight: 'bold' },
            color: '#1f2937'
          }
        },
        tooltip: {
          backgroundColor: 'rgba(0, 0, 0, 0.8)',
          titleColor: '#ffffff',
          bodyColor: '#ffffff',
          padding: 15,
          displayColors: true,
          titleFont: { size: 14 },
          bodyFont: { size: 13 },
          callbacks: {
            label: function(context) {
              return `${cfg.label}: ${context.parsed.y} ${cfg.unit}`;
            }
          }
        }
      },
      scales: {
        x: { 
          display: true,
          grid: { color: 'rgba(0,0,0,0.05)' },
          ticks: {
            font: { size: 12 },
            color: '#6b7280',
            maxTicksLimit: 10
          }
        },
        y: {
          display: true,
          min: cfg.min,
          max: cfg.max,
          grid: { color: 'rgba(0,0,0,0.1)' },
          ticks: {
            font: { size: 13, weight: '500' },
            color: '#374151',
            maxTicksLimit: 10
          }
        }
      }
    }
  });
}

function closeModal() {
  const modal = document.getElementById('chartModal');
  modal.classList.remove('show');
  
  if (modalChart) {
    modalChart.destroy();
    modalChart = null;
  }
}

// Close modal when clicking outside
window.onclick = function(event) {
  const modal = document.getElementById('chartModal');
  if (event.target === modal) {
    closeModal();
  }
}

// Close modal with ESC key
document.addEventListener('keydown', function(event) {
  if (event.key === 'Escape') {
    closeModal();
  }
});

// SSE Connection
const es = new EventSource('/stream');

es.onmessage = function(e) {
  const item = JSON.parse(e.data);
  const topic = item.topic;

  // Update sensor cards and charts
  if (item.direction && (item.direction === 'publisher->broker' || item.direction === 'broker->subscriber')) {
    const payload = item.payload || {};
    const card = cards[topic];
    
    if (card && payload.value !== undefined) {
      const cfg = sensorConfig[topic];
      const displayVal = formatValue(payload.value, cfg);
      
      card.v.textContent = displayVal;
      card.m.textContent = `Last: ${new Date(payload.ts).toLocaleTimeString()} • ID: ${payload.id ? payload.id.substr(0, 8) : 'N/A'}`;
      
      const numValue = typeof payload.value === 'number' ? payload.value : (displayVal === 'Active' ? 1 : 0);
      updateChart(topic, numValue, payload.ts);
    }
  }

  // Add to appropriate sensor log table
  for (let sensorTopic in sensorConfig) {
    if (topic && (topic.includes(sensorTopic) || (topic.startsWith('ack/') && item.payload && item.payload.origId))) {
      appendEventToTable(sensorTopic, item);
      break;
    }
  }
};

es.onerror = function() {
  console.warn('SSE connection error, will retry...');
};

console.log('Dashboard initialized successfully!');