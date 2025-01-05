from aiohttp import web
import aiohttp
import json
import asyncio
from trader import DexTrader
import logging
import sys
import os
from pathlib import Path
from web3.eth import AsyncEth
import traceback
from datetime import datetime

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Configure logging
log_format = '%(asctime)s - %(levelname)s - %(message)s'
file_handler = logging.FileHandler('logs/bot.log', mode='a', encoding='utf-8')
console_handler = logging.StreamHandler(sys.stdout)

# Set formatter for both handlers
formatter = logging.Formatter(log_format)
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Configure root logger
logging.root.setLevel(logging.INFO)
logging.root.addHandler(file_handler)
logging.root.addHandler(console_handler)

logger = logging.getLogger(__name__)

# Log startup information
logger.info("="*50)
logger.info(f"Bot starting at {datetime.now()}")
logger.info("="*50)

try:
    class TradingBotServer:
        def __init__(self):
            self.base_path = Path(__file__).parent
            self.app = web.Application()
            self.trader = DexTrader(chain='ethereum')
            self.websockets = set()
            self.running = False
            self.price_update_interval = 60
            self.event_polling_interval = 30
            self.enable_price_alerts = True
            self.enable_position_alerts = True
            self.enable_gas_alerts = True
            self.setup_routes()

        def setup_routes(self):
            self.app.router.add_get('/', self.handle_index)
            self.app.router.add_get('/ws', self.handle_websocket)
            self.app.router.add_static('/static/', path=self.base_path / 'static', name='static')

        async def handle_index(self, request):
            with open(self.base_path / 'templates' / 'index.html', 'r', encoding='utf-8') as f:
                html_content = f.read()
            return web.Response(text=html_content, content_type='text/html')

        async def handle_websocket(self, request):
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            self.websockets.add(ws)

            try:
                # Send initial state
                await self.send_initial_state(ws)

                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        try:
                            data = json.loads(msg.data)
                            await self.handle_ws_message(ws, data)
                        except json.JSONDecodeError:
                            logger.error(f"Invalid JSON received: {msg.data}")
                        except Exception as e:
                            logger.error(f"Error handling message: {e}")
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        logger.error(f'WebSocket connection closed with exception {ws.exception()}')

            finally:
                if ws in self.websockets:
                    self.websockets.remove(ws)
            return ws

        async def get_gas_price(self):
            """Get current gas price in Gwei"""
            try:
                gas_price = await self.trader.w3.eth.gas_price
                return float(self.trader.w3.from_wei(gas_price, 'gwei'))
            except Exception as e:
                logger.error(f"Error getting gas price: {e}")
                return 0

        async def get_wallet_balance(self):
            """Get wallet balance in ETH"""
            try:
                balance = await self.trader.w3.eth.get_balance(self.trader.account.address)
                return float(self.trader.w3.from_wei(balance, 'ether'))
            except Exception as e:
                logger.error(f"Error getting wallet balance: {e}")
                return 0

        async def send_initial_state(self, ws):
            try:
                # Get wallet info
                balance = await self.get_wallet_balance()
                gas_price = await self.get_gas_price()

                initial_state = {
                    'wallet': {
                        'address': self.trader.account.address,
                        'balance': str(balance),
                        'network': 'Ethereum Mainnet'
                    },
                    'trading': {
                        'total': 0,
                        'successful': 0,
                        'pnl': '0.00'
                    },
                    'gas': {
                        'current': gas_price,
                        'limit': 300000,
                        'max': 150
                    },
                    'pairs': []  # Add some default pairs here
                }

                await ws.send_json(initial_state)
                await self.send_log(ws, 'info', 'Connected to trading bot')
            except Exception as e:
                logger.error(f"Error sending initial state: {e}")
                await self.send_log(ws, 'error', f'Error initializing: {str(e)}')

        async def handle_ws_message(self, ws, data):
            action = data.get('action')
            try:
                if action == 'start':
                    if not self.running:
                        self.running = True
                        asyncio.create_task(self.run_bot())
                        await self.send_log(ws, 'success', 'Bot started successfully')
                elif action == 'stop':
                    if self.running:
                        self.running = False
                        await self.send_log(ws, 'info', 'Bot stopped')
                elif action == 'pause':
                    if self.running:
                        self.running = False
                        await self.send_log(ws, 'info', 'Bot paused')
                elif action == 'updateSettings':
                    settings = data.get('settings')
                    if settings:
                        await self.update_settings(ws, settings)
                elif action == 'trade':
                    token_address = data.get('address')
                    if token_address:
                        await self.send_log(ws, 'info', f'Trading token: {token_address}')
                else:
                    await self.send_log(ws, 'warning', f'Unknown action: {action}')
            except Exception as e:
                await self.send_log(ws, 'error', f'Error processing action {action}: {str(e)}')

        async def update_settings(self, ws, settings):
            """Update bot settings"""
            try:
                # Update trading settings
                trading = settings.get('trading', {})
                self.trader.max_slippage = trading.get('maxSlippage', 2)
                self.trader.gas_limit = trading.get('gasLimit', 300000)
                self.trader.max_gas_price = trading.get('maxGasPrice', 150)

                # Update monitoring settings
                monitoring = settings.get('monitoring', {})
                self.price_update_interval = monitoring.get('priceUpdateInterval', 60)
                self.event_polling_interval = monitoring.get('eventPollingInterval', 30)

                # Update alert settings
                alerts = settings.get('alerts', {})
                self.enable_price_alerts = alerts.get('enablePriceAlerts', True)
                self.enable_position_alerts = alerts.get('enablePositionAlerts', True)
                self.enable_gas_alerts = alerts.get('enableGasAlerts', True)

                await self.send_log(ws, 'success', 'Settings updated successfully')
            except Exception as e:
                await self.send_log(ws, 'error', f'Error updating settings: {str(e)}')

        async def send_log(self, ws, level, message):
            log_message = {
                'type': 'log',
                'data': {
                    'level': level,
                    'message': message,
                    'timestamp': asyncio.get_event_loop().time()
                }
            }
            if ws in self.websockets:
                await ws.send_json(log_message)

        async def broadcast(self, message):
            if self.websockets:
                await asyncio.gather(
                    *[ws.send_json(message) for ws in self.websockets if not ws.closed]
                )

        async def run_bot(self):
            while self.running:
                try:
                    # Update gas prices and wallet balance
                    gas_price = await self.get_gas_price()
                    balance = await self.get_wallet_balance()

                    update = {
                        'type': 'update',
                        'data': {
                            'wallet': {
                                'balance': str(balance)
                            },
                            'gas': {
                                'current': gas_price
                            }
                        }
                    }

                    await self.broadcast(update)
                    await asyncio.sleep(5)  # Update every 5 seconds

                except Exception as e:
                    logger.error(f"Error in bot loop: {e}")
                    await self.broadcast({
                        'type': 'log',
                        'data': {
                            'level': 'error',
                            'message': f'Bot error: {str(e)}',
                            'timestamp': asyncio.get_event_loop().time()
                        }
                    })
                    await asyncio.sleep(5)

    def main():
        server = TradingBotServer()
        web.run_app(server.app, host='127.0.0.1', port=8081)

    if __name__ == '__main__':
        main()
except Exception as e:
    logger.error(f"Critical error during startup: {str(e)}")
    logger.error(traceback.format_exc())
    sys.exit(1)
