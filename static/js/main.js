// WebSocket connection
let ws;
let botRunning = false;
let settings = {
    trading: {
        maxSlippage: 2,
        gasLimit: 300000,
        maxGasPrice: 150
    },
    monitoring: {
        priceUpdateInterval: 60,
        eventPollingInterval: 30
    },
    alerts: {
        enablePriceAlerts: true,
        enablePositionAlerts: true,
        enableGasAlerts: true
    }
};

// Initialize WebSocket connection
function initWebSocket() {
    ws = new WebSocket(`ws://${window.location.host}/ws`);
    
    ws.onopen = () => {
        console.log('Connected to server');
        addLog('info', 'Connected to server');
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
    };

    ws.onclose = () => {
        console.log('Disconnected from server');
        addLog('error', 'Disconnected from server. Attempting to reconnect...');
        setTimeout(initWebSocket, 5000);
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        addLog('error', 'WebSocket error occurred');
    };
}

// Handle incoming WebSocket messages
function handleWebSocketMessage(data) {
    if (data.type === 'update') {
        updateUI(data.data);
    } else if (data.type === 'log') {
        addLog(data.data.level, data.data.message);
    }
}

// Update UI elements with new data
function updateUI(data) {
    if (data.wallet) {
        document.getElementById('walletBalance').textContent = parseFloat(data.wallet.balance).toFixed(4);
    }
    if (data.gas) {
        document.getElementById('gasPrice').textContent = parseFloat(data.gas.current).toFixed(1);
    }
    if (data.trading) {
        document.getElementById('totalTrades').textContent = data.trading.total;
        document.getElementById('successfulTrades').textContent = data.trading.successful;
        document.getElementById('pnl').textContent = data.trading.pnl;
    }
}

// Add log message to the console
function addLog(level, message) {
    const logDiv = document.getElementById('logMessages');
    const logEntry = document.createElement('div');
    logEntry.className = `log-entry ${level}`;
    
    const timestamp = new Date().toLocaleTimeString();
    logEntry.innerHTML = `<span class="timestamp">[${timestamp}]</span> ${message}`;
    
    logDiv.insertBefore(logEntry, logDiv.firstChild);
    if (logDiv.children.length > 100) {
        logDiv.removeChild(logDiv.lastChild);
    }
}

// Bot control functions
function startBot() {
    if (!botRunning) {
        ws.send(JSON.stringify({ action: 'start' }));
        botRunning = true;
        document.getElementById('startBtn').textContent = 'Stop Bot';
        addLog('info', 'Starting bot...');
    } else {
        ws.send(JSON.stringify({ action: 'stop' }));
        botRunning = false;
        document.getElementById('startBtn').textContent = 'Start Bot';
        addLog('info', 'Stopping bot...');
    }
}

function pauseBot() {
    ws.send(JSON.stringify({ action: 'pause' }));
    addLog('info', 'Pausing bot...');
}

// Settings functions
function openSettings() {
    // Load current settings into the modal
    document.getElementById('maxSlippage').value = settings.trading.maxSlippage;
    document.getElementById('gasLimit').value = settings.trading.gasLimit;
    document.getElementById('maxGasPrice').value = settings.trading.maxGasPrice;
    document.getElementById('priceUpdateInterval').value = settings.monitoring.priceUpdateInterval;
    document.getElementById('eventPollingInterval').value = settings.monitoring.eventPollingInterval;
    document.getElementById('enablePriceAlerts').checked = settings.alerts.enablePriceAlerts;
    document.getElementById('enablePositionAlerts').checked = settings.alerts.enablePositionAlerts;
    document.getElementById('enableGasAlerts').checked = settings.alerts.enableGasAlerts;

    // Show the modal
    const modal = new bootstrap.Modal(document.getElementById('settingsModal'));
    modal.show();
    addLog('info', 'Opening settings...');
}

function saveSettings() {
    // Update settings object with form values
    settings.trading.maxSlippage = parseFloat(document.getElementById('maxSlippage').value);
    settings.trading.gasLimit = parseInt(document.getElementById('gasLimit').value);
    settings.trading.maxGasPrice = parseInt(document.getElementById('maxGasPrice').value);
    settings.monitoring.priceUpdateInterval = parseInt(document.getElementById('priceUpdateInterval').value);
    settings.monitoring.eventPollingInterval = parseInt(document.getElementById('eventPollingInterval').value);
    settings.alerts.enablePriceAlerts = document.getElementById('enablePriceAlerts').checked;
    settings.alerts.enablePositionAlerts = document.getElementById('enablePositionAlerts').checked;
    settings.alerts.enableGasAlerts = document.getElementById('enableGasAlerts').checked;

    // Send settings to server
    ws.send(JSON.stringify({
        action: 'updateSettings',
        settings: settings
    }));

    // Close the modal
    const modal = bootstrap.Modal.getInstance(document.getElementById('settingsModal'));
    modal.hide();
    addLog('success', 'Settings saved successfully');
}

// Initialize WebSocket when page loads
document.addEventListener('DOMContentLoaded', () => {
    initWebSocket();
});
