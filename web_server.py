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
            self.trader = None
            self.websockets = set()
            self.running = False
            self.price_update_interval = 60
            self.event_polling_interval = 30
            self.enable_price_alerts = True
            self.enable_position_alerts = True
            self.enable_gas_alerts = True

        async def initialize(self):
            """Initialize the trading bot server"""
            try:
                # Initialize trader
                self.trader = DexTrader(chain='ethereum')
                await self.trader.initialize()

                # Setup routes
                self.app.router.add_get('/', self.handle_index)
                self.app.router.add_get('/ws', self.handle_websocket)
                self.app.router.add_static('/static', self.base_path / 'static')

                return self
            except Exception as e:
                logger.error(f"Error initializing server: {str(e)}")
                raise

        async def handle_index(self, request):
            """Handle index page request"""
            try:
                index_path = self.base_path / 'templates' / 'index.html'
                with open(index_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                return web.Response(text=content, content_type='text/html')
            except Exception as e:
                logger.error(f"Error serving index page: {str(e)}")
                return web.Response(text="Error loading page", status=500)

        async def handle_websocket(self, request):
            """Handle WebSocket connections"""
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            self.websockets.add(ws)
            
            try:
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        try:
                            data = json.loads(msg.data)
                            # Handle different message types
                            if data['type'] == 'get_status':
                                await self.send_status(ws)
                            elif data['type'] == 'execute_trade':
                                await self.handle_trade(ws, data)
                        except json.JSONDecodeError:
                            logger.error("Invalid JSON received")
                        except Exception as e:
                            logger.error(f"Error handling message: {str(e)}")
            finally:
                self.websockets.remove(ws)
            return ws

        async def send_status(self, ws):
            """Send status update to client"""
            try:
                if not self.trader:
                    return
                
                status = {
                    'type': 'status',
                    'wallet': self.trader.account.address,
                    'network': 'Ethereum',
                    'timestamp': datetime.now().isoformat()
                }
                await ws.send_json(status)
            except Exception as e:
                logger.error(f"Error sending status: {str(e)}")

        async def handle_trade(self, ws, data):
            """Handle trade execution request"""
            try:
                if not self.trader:
                    await ws.send_json({
                        'type': 'error',
                        'message': 'Trader not initialized'
                    })
                    return

                # Execute trade logic here
                result = await self.trader.execute_trade(
                    data['token_address'],
                    int(data['amount']),
                    data.get('is_buy', True)
                )

                await ws.send_json({
                    'type': 'trade_result',
                    'success': bool(result),
                    'tx_hash': result if result else None
                })
            except Exception as e:
                logger.error(f"Error executing trade: {str(e)}")
                await ws.send_json({
                    'type': 'error',
                    'message': str(e)
                })

        async def start(self):
            """Start the trading bot server"""
            try:
                runner = web.AppRunner(self.app)
                await runner.setup()
                site = web.TCPSite(runner, 'localhost', 8081)
                await site.start()
                logger.info("Server started at http://localhost:8081")
            except Exception as e:
                logger.error(f"Error starting server: {str(e)}")
                raise

    async def main():
        """Main entry point"""
        server = TradingBotServer()
        await server.initialize()
        await server.start()
        
        # Keep the server running
        while True:
            await asyncio.sleep(3600)

    if __name__ == '__main__':
        asyncio.run(main())
except Exception as e:
    logger.error(f"Critical error during startup: {str(e)}")
    logger.error(traceback.format_exc())
    sys.exit(1)
