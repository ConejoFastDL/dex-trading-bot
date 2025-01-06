// Global price cache
let tokenPrices = {};

// Update token price from WebSocket
function updateTokenPrice(tokenAddress, price) {
    tokenPrices[tokenAddress.toLowerCase()] = price;
}

// Get current token price
function getCurrentTokenPrice(tokenAddress) {
    return tokenPrices[tokenAddress.toLowerCase()];
}

// Limit Orders Management
let limitOrders = [];

document.getElementById('limit-order-form').addEventListener('submit', function(e) {
    e.preventDefault();
    
    const order = {
        id: Date.now(),
        type: document.getElementById('limit-order-type').value,
        tokenAddress: document.getElementById('limit-token-address').value,
        amount: parseFloat(document.getElementById('limit-amount').value),
        limitPrice: parseFloat(document.getElementById('limit-price').value) || 0, // 0 means market price
        expiry: Date.now() + (parseFloat(document.getElementById('limit-expiry').value) * 3600000), // Convert hours to milliseconds
        status: 'active'
    };
    
    // Execute immediately if it's a market buy order
    if (order.type === 'buy' && order.limitPrice === 0) {
        executeLimitOrder(order).then(result => {
            if (result.success) {
                showNotification('success', `Market buy executed: ${order.amount} ETH`);
            } else {
                showNotification('error', `Market buy failed: ${result.error}`);
                // Add to limit orders in case user wants to retry
                limitOrders.push(order);
                localStorage.setItem('limitOrders', JSON.stringify(limitOrders));
                monitorLimitOrder(order);
            }
        });
    } else {
        // Add order to local storage
        limitOrders.push(order);
        localStorage.setItem('limitOrders', JSON.stringify(limitOrders));
        // Start monitoring this order
        monitorLimitOrder(order);
    }
    
    // Update UI
    updateLimitOrdersTable();
    
    // Clear form
    document.getElementById('limit-order-form').reset();
});

function updateLimitOrdersTable() {
    const tbody = document.getElementById('limit-orders');
    tbody.innerHTML = '';
    
    limitOrders.forEach(order => {
        if (order.status === 'active') {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${order.type.toUpperCase()}</td>
                <td>${shortenAddress(order.tokenAddress)}</td>
                <td>${order.amount} ETH</td>
                <td>$${order.limitPrice}</td>
                <td>${formatTimeLeft(order.expiry)}</td>
                <td>
                    <button class="btn btn-sm btn-danger" onclick="cancelLimitOrder(${order.id})">Cancel</button>
                </td>
            `;
            tbody.appendChild(row);
        }
    });
}

function monitorLimitOrder(order) {
    const checkInterval = setInterval(async () => {
        try {
            // Get current price from WebSocket data
            const currentPrice = getCurrentTokenPrice(order.tokenAddress);
            
            if (!currentPrice) return;
            
            const shouldExecute = order.type === 'buy' ? 
                currentPrice <= order.limitPrice :
                currentPrice >= order.limitPrice;
                
            if (shouldExecute) {
                // Execute the trade
                const result = await executeLimitOrder(order);
                if (result.success) {
                    order.status = 'filled';
                    showNotification('success', `Limit order executed: ${order.type} ${order.amount} ETH at $${currentPrice}`);
                }
            }
            
            // Check expiry
            if (Date.now() >= order.expiry) {
                order.status = 'expired';
                showNotification('warning', `Limit order expired: ${order.type} ${order.amount} ETH at $${order.limitPrice}`);
                clearInterval(checkInterval);
            }
            
            // Update storage and UI
            localStorage.setItem('limitOrders', JSON.stringify(limitOrders));
            updateLimitOrdersTable();
            
        } catch (error) {
            console.error('Error monitoring limit order:', error);
        }
    }, 1000); // Check every second
}

async function executeLimitOrder(order) {
    try {
        const response = await fetch('/trade', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                action: order.type,
                token_address: order.tokenAddress,
                amount: order.amount
            })
        });
        
        const result = await response.json();
        return result;
        
    } catch (error) {
        console.error('Error executing limit order:', error);
        return { success: false, error: error.message };
    }
}

function cancelLimitOrder(orderId) {
    const order = limitOrders.find(o => o.id === orderId);
    if (order) {
        order.status = 'cancelled';
        localStorage.setItem('limitOrders', JSON.stringify(limitOrders));
        updateLimitOrdersTable();
        showNotification('info', `Limit order cancelled: ${order.type} ${order.amount} ETH at $${order.limitPrice}`);
    }
}

function formatTimeLeft(expiry) {
    const diff = expiry - Date.now();
    if (diff <= 0) return 'Expired';
    
    const hours = Math.floor(diff / 3600000);
    const minutes = Math.floor((diff % 3600000) / 60000);
    return `${hours}h ${minutes}m`;
}

function shortenAddress(address) {
    return `${address.slice(0, 6)}...${address.slice(-4)}`;
}

// Load saved orders on page load
document.addEventListener('DOMContentLoaded', function() {
    const saved = localStorage.getItem('limitOrders');
    if (saved) {
        limitOrders = JSON.parse(saved).filter(order => order.status === 'active');
        limitOrders.forEach(order => {
            if (order.status === 'active') {
                monitorLimitOrder(order);
            }
        });
        updateLimitOrdersTable();
    }
});
