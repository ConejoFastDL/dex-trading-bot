// WebSocket connection
let ws = null;
let botRunning = false;

// Initialize WebSocket connection
function initWebSocket() {
    ws = new WebSocket('ws://' + window.location.host + '/ws');
    
    ws.onmessage = function(event) {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
    };

    ws.onclose = function() {
        console.log('WebSocket connection closed');
        setTimeout(initWebSocket, 2000);  // Try to reconnect after 2 seconds
    };

    ws.onerror = function(error) {
        console.error('WebSocket error:', error);
        addLogEntry({type: 'error', message: 'Connection error'});
    };
}

// Handle incoming WebSocket messages
function handleWebSocketMessage(data) {
    if (data.type === 'update') {
        updateUI(data.data);
    } else if (data.type === 'log') {
        addLogEntry(data.data);
    } else if (data.type === 'settings') {
        // Update settings form with current values
        const settings = data.data;
        document.getElementById('max_investment_per_trade').value = settings.max_investment_per_trade;
        document.getElementById('min_profit_usd').value = settings.min_profit_usd;
        document.getElementById('max_loss_usd').value = settings.max_loss_usd;
        document.getElementById('max_slippage').value = settings.max_slippage;
        document.getElementById('gas_limit').value = settings.gas_limit;
        document.getElementById('max_gas_price').value = settings.max_gas_price;
        document.getElementById('min_liquidity').value = settings.min_liquidity;
        document.getElementById('min_volume').value = settings.min_volume;
        document.getElementById('min_price_change').value = settings.min_price_change;
    } else if (data.type === 'state') {
        updateUI(data.data);
    } else if (data.type === 'price_update') {
        updateTokenPrice(data.data.token_address, data.data.price);
    } else if (data.type === 'transaction') {
        addTransactionLog(data.data);
    } else {
        updateUI(data);
    }
}

// Update UI with received data
function updateUI(data) {
    if (data.wallet) {
        document.getElementById('wallet-address').textContent = data.wallet.address;
        document.getElementById('wallet-balance').textContent = `${data.wallet.balance} ETH`;
    }

    if (data.trading) {
        document.getElementById('total-trades').textContent = data.trading.total;
        document.getElementById('successful-trades').textContent = data.trading.successful;
        document.getElementById('pnl').textContent = `${data.trading.pnl} ETH`;
    }

    if (data.gas) {
        document.getElementById('gas-price').textContent = data.gas.current.toFixed(2);
        document.getElementById('gas-limit').textContent = data.gas.limit;
        document.getElementById('max-gas').textContent = data.gas.max;
    }

    if (data.pairs) {
        updateTradingPairs(data.pairs);
    }
}

// Add new log entry
function addLogEntry(log) {
    const logDiv = document.getElementById('activity-log');
    const entry = document.createElement('div');
    const timestamp = new Date().toLocaleTimeString();
    
    entry.className = `log-entry ${log.level}`;
    entry.innerHTML = `<span class="timestamp">${timestamp}</span> - ${log.message}`;
    
    // Add appropriate styling based on log level
    switch(log.level) {
        case 'error':
            entry.style.color = '#ff4444';
            break;
        case 'warning':
            entry.style.color = '#ffbb33';
            break;
        case 'success':
            entry.style.color = '#00C851';
            break;
        default:
            entry.style.color = '#ffffff';
    }
    
    logDiv.appendChild(entry);
    logDiv.scrollTop = logDiv.scrollHeight;
}

// Update trading pairs table
function updateTradingPairs(pairs) {
    const tbody = document.getElementById('trading-pairs');
    tbody.innerHTML = '';
    
    pairs.forEach(pair => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${pair.name}</td>
            <td>${pair.price}</td>
            <td class="${pair.change >= 0 ? 'text-success' : 'text-danger'}">${pair.change}%</td>
            <td>${pair.liquidity}</td>
            <td>
                <button class="btn btn-sm btn-primary me-1" onclick="trade('${pair.address}')">Trade</button>
                <button class="btn btn-sm btn-danger" onclick="removePair('${pair.address}')">Remove</button>
            </td>
        `;
        tbody.appendChild(row);
    });
}

// Update token price
function updateTokenPrice(tokenAddress, price) {
    const pairRow = document.querySelector(`tr[data-token-address="${tokenAddress}"]`);
    if (pairRow) {
        pairRow.cells[1].textContent = price;
    }
}

// Add transaction to log
function addTransactionLog(tx) {
    const tbody = document.getElementById('transaction-log');
    const row = document.createElement('tr');
    
    // Format timestamp
    const time = new Date(tx.timestamp).toLocaleString();
    
    // Create etherscan link for tx hash
    const txHashShort = tx.txHash ? `${tx.txHash.substring(0, 6)}...${tx.txHash.substring(tx.txHash.length - 4)}` : '';
    const txHashLink = tx.txHash ? `<a href="https://etherscan.io/tx/${tx.txHash}" target="_blank">${txHashShort}</a>` : '';
    
    row.innerHTML = `
        <td>${time}</td>
        <td>${tx.type}</td>
        <td><a href="https://etherscan.io/address/${tx.tokenAddress}" target="_blank">${shortenAddress(tx.tokenAddress)}</a></td>
        <td>${tx.amount} ETH</td>
        <td>$${tx.price}</td>
        <td>${tx.gasUsed} Gwei</td>
        <td><span class="badge ${tx.status === 'success' ? 'bg-success' : 'bg-danger'}">${tx.status}</span></td>
        <td>${txHashLink}</td>
    `;
    
    // Add new row at the top
    tbody.insertBefore(row, tbody.firstChild);
    
    // Keep only last 100 transactions
    while (tbody.children.length > 100) {
        tbody.removeChild(tbody.lastChild);
    }
}

// Bot control functions
function startBot() {
    if (!botRunning) {
        ws.send(JSON.stringify({action: 'start'}));
        addLogEntry({level: 'info', message: 'Starting bot...'});
    }
}

function stopBot() {
    if (botRunning) {
        ws.send(JSON.stringify({action: 'stop'}));
        addLogEntry({level: 'info', message: 'Stopping bot...'});
    }
}

function pauseBot() {
    ws.send(JSON.stringify({action: 'pause'}));
    addLogEntry({level: 'info', message: 'Pausing bot...'});
}

function showSettings() {
    // Request current settings
    ws.send(JSON.stringify({action: 'get_settings'}));
    
    // Create settings modal
    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.id = 'settingsModal';
    modal.innerHTML = `
        <div class="modal-dialog modal-lg">
            <div class="modal-content bg-dark text-light">
                <div class="modal-header">
                    <h5 class="modal-title">Bot Settings</h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <form id="settingsForm">
                        <div class="mb-3">
                            <label class="form-label">Maximum Investment per Trade ($)</label>
                            <input type="number" class="form-control" id="max_investment_per_trade">
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Minimum Profit Target ($)</label>
                            <input type="number" class="form-control" id="min_profit_usd">
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Maximum Loss Limit ($)</label>
                            <input type="number" class="form-control" id="max_loss_usd">
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Maximum Slippage (%)</label>
                            <input type="number" class="form-control" id="max_slippage">
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Gas Limit</label>
                            <input type="number" class="form-control" id="gas_limit">
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Maximum Gas Price (Gwei)</label>
                            <input type="number" class="form-control" id="max_gas_price">
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Minimum Liquidity ($)</label>
                            <input type="number" class="form-control" id="min_liquidity">
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Minimum Volume ($)</label>
                            <input type="number" class="form-control" id="min_volume">
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Minimum Price Change (%)</label>
                            <input type="number" class="form-control" id="min_price_change">
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                    <button type="button" class="btn btn-primary" onclick="saveSettings()">Save Changes</button>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Show modal
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
}

function saveSettings() {
    const settings = {
        max_investment_per_trade: parseFloat(document.getElementById('max_investment_per_trade').value),
        min_profit_usd: parseFloat(document.getElementById('min_profit_usd').value),
        max_loss_usd: parseFloat(document.getElementById('max_loss_usd').value),
        max_slippage: parseFloat(document.getElementById('max_slippage').value),
        gas_limit: parseInt(document.getElementById('gas_limit').value),
        max_gas_price: parseFloat(document.getElementById('max_gas_price').value),
        min_liquidity: parseFloat(document.getElementById('min_liquidity').value),
        min_volume: parseFloat(document.getElementById('min_volume').value),
        min_price_change: parseFloat(document.getElementById('min_price_change').value)
    };
    
    // Send settings to server
    ws.send(JSON.stringify({
        action: 'update_settings',
        settings: settings
    }));
    
    // Close modal
    const modal = bootstrap.Modal.getInstance(document.getElementById('settingsModal'));
    modal.hide();
    
    addLogEntry({level: 'success', message: 'Settings updated successfully'});
}

function addNewPair() {
    const address = prompt('Enter token address:');
    if (address) {
        ws.send(JSON.stringify({
            action: 'add_pair',
            address: address
        }));
        addLogEntry({level: 'info', message: `Adding new pair: ${address}`});
    }
}

function trade(address) {
    ws.send(JSON.stringify({
        action: 'trade',
        address: address
    }));
    addLogEntry({level: 'info', message: `Initiating trade for: ${address}`});
}

function removePair(address) {
    ws.send(JSON.stringify({
        action: 'remove_pair',
        address: address
    }));
    addLogEntry({level: 'info', message: `Removing pair: ${address}`});
}

// Add some styling
document.addEventListener('DOMContentLoaded', function() {
    // Add styles for log entries
    const style = document.createElement('style');
    style.textContent = `
        .log-entry {
            padding: 4px 8px;
            border-bottom: 1px solid #3d3d3d;
            font-family: monospace;
        }
        .timestamp {
            color: #888;
        }
        #activity-log {
            background-color: #1a1a1a;
            border: 1px solid #3d3d3d;
            border-radius: 4px;
        }
    `;
    document.head.appendChild(style);
    
    // Initialize WebSocket
    initWebSocket();
});
