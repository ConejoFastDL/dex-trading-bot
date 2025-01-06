from aiohttp import web
import aiohttp
import json
import asyncio
from trader import DexTrader
import logging
import warnings
from config import NETWORK, TRADING_CONFIG
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from web3 import Web3
import time

# Load environment variables
load_dotenv()

# Filter out eth_utils network warnings
warnings.filterwarnings('ignore', message='Network .* does not have a valid ChainId')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join('logs', 'bot.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Ensure required directories exist
os.makedirs('logs', exist_ok=True)
os.makedirs('data', exist_ok=True)

class TradingBotServer:
    def __init__(self):
        self.base_path = Path(__file__).parent
        self.app = web.Application()
        self.setup_routes()
        self.trader = DexTrader(chain='ethereum')
        self.websockets = set()
        self.running = False

    def setup_routes(self):
        self.app.router.add_get('/', self.handle_index)
        self.app.router.add_get('/ws', self.handle_websocket)
        self.app.router.add_get('/scan_tokens', self.handle_scan_tokens)
        self.app.router.add_post('/trade', self.handle_trade)  # Add trade route
        # Serve static files from the static directory
        self.app.router.add_static('/static/', path=self.base_path / 'static', name='static')

    async def handle_index(self, request):
        with open(self.base_path / 'templates' / 'index.html', 'r', encoding='utf-8') as f:
            html_content = f.read()
        return web.Response(text=html_content, content_type='text/html')

    async def handle_websocket(self, request):
        """Handle WebSocket connections with proper error handling."""
        ws = web.WebSocketResponse(heartbeat=30)
        try:
            await ws.prepare(request)
            self.websockets.add(ws)
            logger.info("New WebSocket connection established")
            
            # Send initial state
            await self.send_initial_state(ws)
            
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        await self.handle_ws_message(ws, data)
                    except json.JSONDecodeError:
                        await self.send_log(ws, 'error', 'Invalid JSON message')
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
                        await self.send_log(ws, 'error', f'Error: {str(e)}')
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f'WebSocket connection closed with exception {ws.exception()}')
                    
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            self.websockets.remove(ws)
            if not ws.closed:
                await ws.close()
            logger.info("WebSocket connection closed")
        return ws

    async def send_initial_state(self, ws):
        try:
            # Get wallet info
            balance = self.trader.w3.eth.get_balance(self.trader.account.address)
            balance_eth = self.trader.w3.from_wei(balance, 'ether')
            gas_price = self.trader.w3.eth.gas_price

            initial_state = {
                'wallet': {
                    'address': self.trader.account.address,
                    'balance': str(balance_eth),
                    'network': 'Ethereum Mainnet'
                },
                'trading': {
                    'total': 0,
                    'successful': 0,
                    'pnl': '0.00'
                },
                'gas': {
                    'current': float(gas_price) / 1e9,  # Convert to Gwei
                    'limit': 300000,
                    'max': 150
                },
                'pairs': [],  # Add some default pairs here
                'settings': TRADING_CONFIG  # Add trading settings
            }

            await ws.send_json({
                'type': 'state',
                'data': initial_state
            })
            await self.send_log(ws, 'info', 'Connected to trading bot')
        except Exception as e:
            logger.error(f"Error sending initial state: {e}")
            await self.send_log(ws, 'error', f'Error initializing: {str(e)}')

    async def handle_ws_message(self, ws, data):
        """Handle WebSocket messages."""
        try:
            if not isinstance(data, dict):
                await self.send_log(ws, 'error', 'Invalid message format')
                return
                
            action = data.get('action')
            if not action:
                await self.send_log(ws, 'error', 'Missing action in message')
                return
                
            logger.info(f"Received action: {action}")
            
            if action == 'start':
                if not self.running:
                    self.running = True
                    asyncio.create_task(self.run_bot())
                    asyncio.create_task(self.start_auto_trading())
                    await self.send_log(ws, 'success', 'Bot started successfully')
                else:
                    await self.send_log(ws, 'info', 'Bot is already running')
                    
            elif action == 'stop':
                if self.running:
                    self.running = False
                    await self.send_log(ws, 'info', 'Bot stopped')
                else:
                    await self.send_log(ws, 'info', 'Bot is already stopped')
                    
            elif action == 'pause':
                if self.running:
                    self.running = False
                    await self.send_log(ws, 'info', 'Bot paused')
                else:
                    await self.send_log(ws, 'info', 'Bot is already paused')
                    
            elif action == 'get_settings':
                await ws.send_json({
                    'type': 'settings',
                    'data': {
                        'trading': TRADING_CONFIG,
                        'network': NETWORK,
                        'status': {
                            'running': self.running,
                            'active_trades': len(self.trader.get_active_trades())
                        }
                    }
                })
                await self.send_log(ws, 'info', 'Settings retrieved successfully')
                
            elif action == 'update_settings':
                settings = data.get('settings', {})
                if not settings:
                    await self.send_log(ws, 'error', 'No settings provided')
                    return
                    
                # Update trading configuration
                for key, value in settings.items():
                    if key in TRADING_CONFIG:
                        TRADING_CONFIG[key] = value
                        
                await ws.send_json({
                    'type': 'settings',
                    'data': {
                        'trading': TRADING_CONFIG,
                        'network': NETWORK,
                        'status': {
                            'running': self.running,
                            'active_trades': len(self.trader.get_active_trades())
                        }
                    }
                })
                await self.send_log(ws, 'success', 'Settings updated successfully')
                
            elif action == 'add_pair':
                address = data.get('address')
                if not address:
                    await self.send_log(ws, 'error', 'No token address provided')
                    return
                    
                # Validate address format
                if not self.trader.w3.is_address(address):
                    await self.send_log(ws, 'error', 'Invalid token address format')
                    return
                    
                # Add pair to monitoring list
                try:
                    token_info = await self.trader.get_token_info(address)
                    self.trader.add_trading_pair(address, token_info)
                    await ws.send_json({
                        'type': 'pairs',
                        'data': self.trader.get_trading_pairs()
                    })
                    await self.send_log(ws, 'success', f'Added trading pair: {token_info.get("symbol", address)}')
                except Exception as e:
                    await self.send_log(ws, 'error', f'Failed to add trading pair: {str(e)}')
                    
            elif action == 'remove_pair':
                address = data.get('address')
                if not address:
                    await self.send_log(ws, 'error', 'No token address provided')
                    return
                    
                # Remove pair from monitoring list
                try:
                    self.trader.remove_trading_pair(address)
                    await ws.send_json({
                        'type': 'pairs',
                        'data': self.trader.get_trading_pairs()
                    })
                    await self.send_log(ws, 'success', f'Removed trading pair: {address}')
                except Exception as e:
                    await self.send_log(ws, 'error', f'Failed to remove trading pair: {str(e)}')
                    
            elif action == 'trade':
                address = data.get('address')
                if not address:
                    await self.send_log(ws, 'error', 'No token address provided')
                    return
                    
                # Execute manual trade
                try:
                    result = await self.trader.execute_trade(address)
                    if result.get('success'):
                        await self.send_log(ws, 'success', f'Trade executed: {result.get("tx_hash")}')
                    else:
                        await self.send_log(ws, 'error', f'Trade failed: {result.get("error")}')
                except Exception as e:
                    await self.send_log(ws, 'error', f'Failed to execute trade: {str(e)}')
                    
            else:
                await self.send_log(ws, 'warning', f'Unknown action: {action}')
                
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
            await self.send_log(ws, 'error', f'Error processing message: {str(e)}')

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
        """Broadcast message to all connected WebSocket clients."""
        disconnected = set()
        for ws in self.websockets:
            try:
                if not ws.closed:
                    await ws.send_json(message)
                else:
                    disconnected.add(ws)
            except Exception as e:
                logger.error(f"Error broadcasting message: {e}")
                disconnected.add(ws)
        
        # Remove disconnected clients
        self.websockets -= disconnected

    async def broadcast_log(self, level, message):
        """Broadcast log message to all clients."""
        try:
            log_msg = {
                'type': 'log',
                'data': {
                    'level': level,
                    'message': message,
                    'timestamp': str(datetime.now())
                }
            }
            await self.broadcast(log_msg)
        except Exception as e:
            logger.error(f"Error broadcasting log: {e}")

    async def broadcast_trade_update(self, action, pair, result):
        """Broadcast trade update to all connected clients."""
        try:
            # First broadcast the trade update
            for ws in self.websockets:
                if not ws.closed:
                    await ws.send_json({
                        'type': 'trade_update',
                        'data': {
                            'action': action,
                            'pair': pair,
                            'price': pair.get('price', 0),
                            'result': result
                        }
                    })
            
            # Then broadcast detailed transaction log
            tx_data = {
                'type': action,  # buy or sell
                'tokenAddress': pair.get('token_address'),
                'amount': result.get('amount_in_eth'),
                'price': pair.get('price', 0),
                'gasUsed': result.get('gas_used', 0),
                'status': 'success' if result.get('success') else 'failed',
                'txHash': result.get('tx_hash'),
                'timestamp': int(time.time() * 1000)  # current time in milliseconds
            }
            
            for ws in self.websockets:
                if not ws.closed:
                    await ws.send_json({
                        'type': 'transaction',
                        'data': tx_data
                    })
                    
        except Exception as e:
            logger.error(f"Error broadcasting trade update: {e}")

    async def broadcast_price_update(self, token_address, price):
        """Broadcast price update to all connected clients."""
        for ws in self.websockets:
            if not ws.closed:
                await ws.send_json({
                    'type': 'price_update',
                    'data': {
                        'token_address': token_address,
                        'price': price
                    }
                })

    async def run_bot(self):
        """Main bot loop for updating state and broadcasting."""
        while self.running:
            try:
                # Update gas prices
                gas_price = self.trader.w3.eth.gas_price
                gas_price_gwei = float(gas_price) / 1e9
                
                # Update wallet balance
                balance = self.trader.w3.eth.get_balance(self.trader.account.address)
                balance_eth = self.trader.w3.from_wei(balance, 'ether')

                # Update trading pairs
                pairs_data = {}
                for address, pair in self.trader.get_trading_pairs().items():
                    try:
                        token_info = await self.trader.get_token_info(address)
                        pairs_data[address] = {
                            **pair,
                            'price': token_info['price'],
                            'liquidity': token_info['liquidity'],
                            'volume_24h': token_info['volume_24h'],
                            'price_change_24h': token_info['price_change_24h'],
                            'last_updated': str(datetime.now())
                        }
                    except Exception as e:
                        logger.error(f"Error updating pair {address}: {e}")

                update = {
                    'type': 'update',
                    'data': {
                        'wallet': {
                            'balance': str(balance_eth),
                            'address': self.trader.account.address
                        },
                        'gas': {
                            'current': gas_price_gwei,
                            'max': TRADING_CONFIG['max_gas_price']
                        },
                        'trading': {
                            'active': self.running,
                            'pairs': pairs_data,
                            'active_trades': len(self.trader.get_active_trades())
                        }
                    }
                }

                await self.broadcast(update)
                await asyncio.sleep(5)  # Update every 5 seconds

            except Exception as e:
                logger.error(f"Error in bot loop: {e}")
                await self.broadcast_log('error', f'Bot error: {str(e)}')
                await asyncio.sleep(5)

    def _calculate_volume_score(self, pair):
        """Calculate volume score based on 24h volume."""
        try:
            volume = float(pair['volume_24h'])
            if volume >= 1_000_000:  # $1M+
                return 100
            elif volume >= 500_000:  # $500K+
                return 85
            elif volume >= 100_000:  # $100K+
                return 70
            elif volume >= 50_000:   # $50K+
                return 55
            else:
                return 40
        except:
            return 0
            
    def _calculate_safety_score(self, pair):
        """Calculate safety score based on liquidity and age."""
        try:
            score = 0
            
            # Liquidity score (0-50 points)
            liquidity = float(pair['liquidity_usd'])
            if liquidity >= 500_000:  # $500K+
                score += 50
            elif liquidity >= 250_000:  # $250K+
                score += 40
            elif liquidity >= 100_000:  # $100K+
                score += 30
            elif liquidity >= 50_000:   # $50K+
                score += 20
            
            # Age score (0-30 points)
            pair_created = datetime.fromtimestamp(int(pair.get('pairCreatedAt', 0)) / 1000)
            age_days = (datetime.now() - pair_created).total_seconds() / (24 * 3600)
            if age_days >= 30:  # 30+ days
                score += 30
            elif age_days >= 7:  # 7+ days
                score += 20
            elif age_days >= 1:  # 1+ day
                score += 10
            
            # DEX score (0-20 points)
            dex_id = pair.get('dexId', '').lower()
            if dex_id in ['uniswap']:
                score += 20
            elif dex_id in ['sushiswap']:
                score += 15
            elif dex_id:  # Any other DEX
                score += 10
                
            return score
            
        except:
            return 0
            
    def _calculate_entry_quality(self, pair):
        """Calculate entry quality score based on recent price action."""
        try:
            score = 0
            
            # Price change scores
            price_change_5m = abs(float(pair.get('price_change_5m', 0)))
            price_change_1h = abs(float(pair.get('price_change_1h', 0)))
            
            # 5-minute price change (0-40 points)
            if 2 <= price_change_5m <= 5:  # Ideal range
                score += 40
            elif 1 <= price_change_5m <= 10:  # Good range
                score += 30
            elif price_change_5m <= 15:  # Acceptable range
                score += 20
            
            # 1-hour price change (0-40 points)
            if 5 <= price_change_1h <= 15:  # Ideal range
                score += 40
            elif 2 <= price_change_1h <= 25:  # Good range
                score += 30
            elif price_change_1h <= 35:  # Acceptable range
                score += 20
            
            # Price trend (0-20 points)
            if price_change_5m > 0 and price_change_1h > 0:  # Uptrend
                score += 20
            elif price_change_5m > 0 or price_change_1h > 0:  # Mixed trend
                score += 10
                
            return score
            
        except:
            return 0
            
    def _calculate_weighted_score(self, pair):
        """Calculate weighted score based on all metrics."""
        try:
            weights = TRADING_CONFIG['analysis_weights']
            
            # Get individual scores
            volume_score = self._calculate_volume_score(pair) * weights['volume_metrics']
            safety_score = self._calculate_safety_score(pair) * weights['contract_metrics']
            entry_score = self._calculate_entry_quality(pair) * weights['price_metrics']
            
            # Calculate total weighted score
            total_weight = sum(weights.values())
            weighted_score = (volume_score + safety_score + entry_score) / total_weight
            
            return weighted_score
            
        except:
            return 0
            
    async def start_auto_trading(self):
        """Start automated trading with safety checks."""
        logger.info("Starting auto trading...")
        
        try:
            # Initial safety checks
            balance = self.trader.w3.eth.get_balance(self.trader.account.address)
            balance_eth = self.trader.w3.from_wei(balance, 'ether')
            gas_price = self.trader.w3.eth.gas_price
            
            if float(balance_eth) < TRADING_CONFIG['min_eth_balance']:
                logger.error("Insufficient ETH balance for trading")
                await self.broadcast_log('error', 'Insufficient ETH balance for trading')
                self.running = False
                return
                
            if float(gas_price) > TRADING_CONFIG['max_gas_price']:
                logger.warning("Gas price too high for trading")
                await self.broadcast_log('warning', 'Gas price too high for trading')
                self.running = False
                return
            
            while self.running:
                try:
                    # Monitor active trades
                    active_trades = self.trader.get_active_trades()
                    for trade in active_trades:
                        await self.check_trade_safety(trade)
                    
                    # Check for new opportunities
                    if len(active_trades) < TRADING_CONFIG['max_concurrent_trades']:
                        await self.find_trading_opportunities()
                    
                    await asyncio.sleep(10)  # Check every 10 seconds
                    
                except Exception as e:
                    logger.error(f"Error in trading loop: {e}")
                    await self.broadcast_log('error', f'Trading error: {str(e)}')
                    await asyncio.sleep(30)  # Wait before retrying
                    
        except Exception as e:
            logger.error(f"Fatal error in auto trading: {e}")
            await self.broadcast_log('error', f'Fatal trading error: {str(e)}')
            self.running = False
            
    async def check_trade_safety(self, trade):
        """Check if a trade is safe to continue."""
        try:
            token_info = await self.trader.get_token_info(trade['token_address'])
            current_price = token_info['price']
            entry_price = trade['entry_price']
            
            # Calculate profit/loss percentage
            if entry_price > 0:
                pnl_percent = ((current_price - entry_price) / entry_price) * 100
            else:
                pnl_percent = 0
                
            # Check stop loss and trailing stop
            if TRADING_CONFIG['exit_rules']['trailing_stop']:
                trailing_distance = TRADING_CONFIG['exit_rules']['trailing_distance']
                if pnl_percent <= -(trailing_distance):
                    logger.warning(f"Trailing stop triggered for {trade['token_address']}: {pnl_percent}%")
                    await self.broadcast_log('warning', f"Trailing stop triggered: {pnl_percent}%")
                    await self.close_trade(trade)
                    return
                    
            # Check profit lock levels
            for profit_level, lock_percent in TRADING_CONFIG['exit_rules']['profit_lock'].items():
                if pnl_percent >= profit_level:
                    logger.info(f"Profit lock triggered at {profit_level}% for {trade['token_address']}")
                    await self.broadcast_log('success', f"Locking {lock_percent}% of profits at {profit_level}% gain")
                    await self.close_partial_trade(trade, lock_percent)
                    return
                    
            # Check loss management
            if TRADING_CONFIG['position_management']['loss_management']['partial_exit']:
                partial_exit_threshold = TRADING_CONFIG['position_management']['loss_management']['partial_exit_threshold']
                if pnl_percent <= -partial_exit_threshold:
                    logger.warning(f"Partial exit triggered for {trade['token_address']}: {pnl_percent}%")
                    await self.broadcast_log('warning', f"Partial exit at {pnl_percent}% loss")
                    await self.close_partial_trade(trade, 50)  # Exit 50% of position
                    return
                    
            # Check liquidity
            if token_info['liquidity'] < TRADING_CONFIG['min_liquidity']:
                logger.warning(f"Low liquidity for {trade['token_address']}")
                await self.broadcast_log('warning', f"Low liquidity detected")
                await self.close_trade(trade)
                return
                
        except Exception as e:
            logger.error(f"Error checking trade safety: {e}")
            await self.broadcast_log('error', f"Error checking trade safety: {str(e)}")

    async def close_trade(self, trade):
        """Close an entire trade position."""
        try:
            result = await self.trader.sell_token(
                token_address=trade['token_address'],
                amount=trade['amount'],
                max_slippage=TRADING_CONFIG['max_slippage']
            )
            
            if result['success']:
                logger.info(f"Successfully closed trade: {trade['token_address']}")
                await self.broadcast_log('success', f'Closed trade: {trade["token_address"]}')
                # Get token info for UI update
                token_info = await self.trader.get_token_info(trade['token_address'])
                await self.broadcast_trade_update('sell', token_info, result)
                # Remove from active trades
                self.trader.remove_active_trade(trade['token_address'])
            else:
                logger.error(f"Failed to close trade: {result.get('error', 'Unknown error')}")
                await self.broadcast_log('error', f'Failed to close trade: {result.get("error")}')
                
        except Exception as e:
            logger.error(f"Error closing trade: {e}")
            await self.broadcast_log('error', f'Error closing trade: {str(e)}')

    async def close_partial_trade(self, trade, percentage):
        """Close a percentage of a trade position."""
        try:
            amount_to_sell = (trade['amount'] * percentage) // 100
            
            result = await self.trader.sell_token(
                token_address=trade['token_address'],
                amount=amount_to_sell,
                max_slippage=TRADING_CONFIG['max_slippage']
            )
            
            if result['success']:
                # Update remaining amount in trade
                trade['amount'] -= amount_to_sell
                logger.info(f"Successfully closed {percentage}% of trade: {trade['token_address']}")
                await self.broadcast_log('info', f'Partially closed trade: {percentage}% of {trade["token_address"]}')
            else:
                logger.error(f"Failed to close partial trade: {result.get('error', 'Unknown error')}")
                await self.broadcast_log('error', f'Failed to close partial trade: {result.get("error")}')
                
        except Exception as e:
            logger.error(f"Error closing partial trade: {e}")
            await self.broadcast_log('error', f'Error closing partial trade: {str(e)}')

    async def find_trading_opportunities(self):
        """Find and execute trading opportunities based on configured criteria."""
        try:
            # Get trending pairs from DexScreener
            trending_pairs = await self.trader.token_manager.get_trending_pairs()
            
            for pair in trending_pairs:
                try:
                    # Calculate scores
                    volume_score = self._calculate_volume_score(pair)
                    safety_score = self._calculate_safety_score(pair)
                    entry_score = self._calculate_entry_quality(pair)
                    weighted_score = self._calculate_weighted_score(pair)
                    
                    # Check if pair meets minimum criteria
                    if (volume_score >= TRADING_CONFIG['entry_rules']['min_volume_score'] and
                        safety_score >= TRADING_CONFIG['entry_rules']['min_safety_score'] and
                        entry_score >= TRADING_CONFIG['entry_rules']['min_entry_quality'] and
                        weighted_score >= TRADING_CONFIG['entry_rules']['min_weighted_score']):
                        
                        # Calculate position size based on safety score
                        base_size = TRADING_CONFIG['position_sizing']['base_size']
                        for threshold, multiplier in sorted(
                            TRADING_CONFIG['position_sizing']['safety_multipliers'].items(),
                            reverse=True
                        ):
                            if safety_score >= threshold:
                                position_size = base_size * multiplier
                                break
                        else:
                            position_size = base_size * 0.4  # Minimum size
                            
                        # Convert position size to Wei
                        amount_in_wei = self.trader.w3.to_wei(position_size, 'ether')
                        
                        # Execute the trade
                        result = await self.trader.buy_token(
                            token_address=pair['token_address'],
                            amount_in_wei=amount_in_wei,
                            max_slippage=TRADING_CONFIG['max_slippage']
                        )
                        
                        if result['success']:
                            logger.info(f"Successfully entered trade: {pair['token_address']}")
                            await self.broadcast_log('success', f'Entered new trade: {pair["token_address"]}')
                            await self.broadcast_trade_update('buy', pair, result)
                            return  # Only take one trade at a time
                            
                except Exception as e:
                    logger.error(f"Error processing pair {pair.get('token_address', 'unknown')}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error finding trading opportunities: {e}")
            await self.broadcast_log('error', f'Error finding opportunities: {str(e)}')

    async def handle_scan_tokens(self, request):
        """Handle token scanning request."""
        try:
            # Get trending pairs
            pairs = await self.trader.token_manager.get_trending_pairs()
            
            # Format response
            response = {
                'status': 'success',
                'data': pairs
            }
            
            return web.json_response(response)
        except Exception as e:
            logger.error(f"Error scanning tokens: {e}")
            return web.json_response({
                'status': 'error',
                'message': str(e)
            }, status=500)

    async def handle_trade(self, request):
        """Handle manual trading requests."""
        try:
            data = await request.json()
            action = data.get('action')
            token_address = data.get('token_address')
            pair_address = data.get('pair_address')  
            amount = float(data.get('amount', 0))
            
            if not all([action, token_address, amount]):
                return web.json_response({
                    'success': False,
                    'error': 'Missing required parameters'
                })
                
            # Convert amount to Wei
            amount_wei = self.trader.w3.to_wei(amount, 'ether')
            
            if action == 'buy':
                # Support both legacy and new trading methods
                if pair_address:
                    result = await self.trader.buy_token(
                        token_address=token_address,
                        pair_address=pair_address,
                        amount=amount_wei
                    )
                else:
                    result = await self.trader.buy_token(
                        token_address=token_address,
                        amount_in_wei=amount_wei,
                        max_slippage=TRADING_CONFIG['max_slippage']
                    )
                
                if result['success']:
                    await self.broadcast_log('success', f'Successfully bought token: {token_address}')
                    # Get token info for UI update
                    token_info = await self.trader.get_token_info(token_address)
                    await self.broadcast_trade_update('buy', token_info, result)
                else:
                    await self.broadcast_log('error', f'Failed to buy token: {result.get("error")}')
                    
            elif action == 'sell':
                # Support both legacy and new trading methods
                if pair_address:
                    result = await self.trader.sell_token(
                        token_address=token_address,
                        pair_address=pair_address,
                        amount=amount_wei
                    )
                else:
                    result = await self.trader.sell_token(
                        token_address=token_address,
                        amount=amount_wei,
                        max_slippage=TRADING_CONFIG['max_slippage']
                    )
                
                if result['success']:
                    await self.broadcast_log('success', f'Successfully sold token: {token_address}')
                    # Get token info for UI update
                    token_info = await self.trader.get_token_info(token_address)
                    await self.broadcast_trade_update('sell', token_info, result)
                else:
                    await self.broadcast_log('error', f'Failed to sell token: {result.get("error")}')
                    
            else:
                return web.json_response({
                    'success': False,
                    'error': 'Invalid action'
                })
                
            return web.json_response(result)
            
        except Exception as e:
            logger.error(f"Error handling trade: {e}")
            return web.json_response({
                'success': False,
                'error': str(e)
            })

def main():
    server = TradingBotServer()
    port = 8081
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            web.run_app(server.app, host='127.0.0.1', port=port)
            break
        except OSError as e:
            if e.errno == 10048:  # Port already in use
                logger.warning(f"Port {port} is in use. Attempting to free it...")
                try:
                    import socket
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    sock.bind(('127.0.0.1', port))
                    sock.close()
                    logger.info(f"Successfully freed port {port}")
                except Exception as bind_error:
                    logger.error(f"Failed to free port {port}: {bind_error}")
                    retry_count += 1
                    if retry_count >= max_retries:
                        logger.error("Maximum retries reached. Please ensure no other instances are running.")
                        raise
            else:
                raise

if __name__ == '__main__':
    main()
