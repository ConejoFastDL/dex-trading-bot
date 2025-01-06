from web3 import Web3
import logging
from datetime import datetime, timedelta
import asyncio
from decimal import Decimal
from config import POSITION_CONFIG
import numpy as np

class PositionManager:
    def __init__(self, w3_provider, wallet_manager, risk_manager):
        self.w3 = w3_provider
        self.wallet_manager = wallet_manager
        self.risk_manager = risk_manager
        self.logger = logging.getLogger(__name__)
        self.positions = {}
        self.position_history = {}
        self.active_stops = {}
        self.profit_targets = {}

    async def open_position(self, token_address, pair_address, amount, 
                          wallet_address, entry_price=None):
        """Open a new trading position."""
        try:
            # Generate position ID
            position_id = self._generate_position_id(token_address, wallet_address)
            
            # Check if position already exists
            if position_id in self.positions:
                raise ValueError("Position already exists")
            
            # Get current price if not provided
            if not entry_price:
                entry_price = await self._get_current_price(pair_address)
            
            # Create position object
            position = {
                'id': position_id,
                'token_address': token_address,
                'pair_address': pair_address,
                'wallet_address': wallet_address,
                'amount': amount,
                'entry_price': entry_price,
                'current_price': entry_price,
                'entry_time': datetime.now().isoformat(),
                'last_update': datetime.now().isoformat(),
                'status': 'open',
                'pnl': 0,
                'roi': 0
            }
            
            # Add position tracking
            self.positions[position_id] = position
            
            # Set up monitoring
            await self._setup_position_monitoring(position_id)
            
            return position_id
        except Exception as e:
            self.logger.error(f"Error opening position: {e}")
            return None

    async def close_position(self, position_id, exit_price=None):
        """Close an existing position."""
        try:
            if position_id not in self.positions:
                raise ValueError("Position not found")
            
            position = self.positions[position_id]
            
            # Get current price if not provided
            if not exit_price:
                exit_price = await self._get_current_price(position['pair_address'])
            
            # Calculate final P&L
            final_pnl = self._calculate_pnl(position, exit_price)
            
            # Update position
            position['exit_price'] = exit_price
            position['exit_time'] = datetime.now().isoformat()
            position['final_pnl'] = final_pnl
            position['status'] = 'closed'
            
            # Move to history
            self.position_history[position_id] = position
            del self.positions[position_id]
            
            # Clean up monitoring
            await self._cleanup_position_monitoring(position_id)
            
            return final_pnl
        except Exception as e:
            self.logger.error(f"Error closing position: {e}")
            return None

    async def update_position(self, position_id):
        """Update position with current market data."""
        try:
            if position_id not in self.positions:
                raise ValueError("Position not found")
            
            position = self.positions[position_id]
            
            # Get current price
            current_price = await self._get_current_price(position['pair_address'])
            
            # Update position data
            position['current_price'] = current_price
            position['pnl'] = self._calculate_pnl(position, current_price)
            position['roi'] = self._calculate_roi(position)
            position['last_update'] = datetime.now().isoformat()
            
            # Check stops and targets
            await self._check_position_limits(position_id)
            
            return position
        except Exception as e:
            self.logger.error(f"Error updating position: {e}")
            return None

    async def set_stop_loss(self, position_id, price=None, percentage=None):
        """Set stop loss for a position."""
        try:
            if position_id not in self.positions:
                raise ValueError("Position not found")
            
            position = self.positions[position_id]
            
            # Calculate stop price
            if price:
                stop_price = price
            elif percentage:
                entry_price = Decimal(str(position['entry_price']))
                stop_price = float(entry_price * (1 - Decimal(str(percentage)) / 100))
            else:
                raise ValueError("Must provide either price or percentage")
            
            # Set stop loss
            self.active_stops[position_id] = {
                'type': 'stop_loss',
                'price': stop_price,
                'created_at': datetime.now().isoformat()
            }
            
            return stop_price
        except Exception as e:
            self.logger.error(f"Error setting stop loss: {e}")
            return None

    async def set_take_profit(self, position_id, targets):
        """Set take profit targets for a position."""
        try:
            if position_id not in self.positions:
                raise ValueError("Position not found")
            
            position = self.positions[position_id]
            
            # Validate targets
            if not self._validate_profit_targets(targets):
                raise ValueError("Invalid profit targets")
            
            # Set profit targets
            self.profit_targets[position_id] = {
                'targets': targets,
                'created_at': datetime.now().isoformat()
            }
            
            return True
        except Exception as e:
            self.logger.error(f"Error setting take profit: {e}")
            return False

    async def get_position_info(self, position_id):
        """Get detailed position information."""
        try:
            if position_id not in self.positions:
                return None
            
            position = self.positions[position_id]
            
            # Get additional data
            token_balance = await self.wallet_manager.check_token_balance(
                position['wallet_address'],
                position['token_address']
            )
            
            risk_assessment = await self.risk_manager.assess_trade_risk(
                position['token_address'],
                position['pair_address'],
                position['amount']
            )
            
            info = {
                **position,
                'token_balance': token_balance,
                'risk_assessment': risk_assessment,
                'stops': self.active_stops.get(position_id),
                'targets': self.profit_targets.get(position_id)
            }
            
            return info
        except Exception as e:
            self.logger.error(f"Error getting position info: {e}")
            return None

    async def get_position_history(self, wallet_address=None, 
                                 start_time=None, end_time=None):
        """Get historical position data."""
        try:
            history = self.position_history.values()
            
            # Filter by wallet
            if wallet_address:
                history = [pos for pos in history 
                          if pos['wallet_address'] == wallet_address]
            
            # Filter by time range
            if start_time:
                history = [pos for pos in history 
                          if datetime.fromisoformat(pos['entry_time']) >= start_time]
            
            if end_time:
                history = [pos for pos in history 
                          if datetime.fromisoformat(pos['exit_time']) <= end_time]
            
            return sorted(history, 
                         key=lambda x: datetime.fromisoformat(x['entry_time']), 
                         reverse=True)
        except Exception as e:
            self.logger.error(f"Error getting position history: {e}")
            return []

    async def _setup_position_monitoring(self, position_id):
        """Set up monitoring for a position."""
        try:
            position = self.positions[position_id]
            
            # Start monitoring task
            asyncio.create_task(self._monitor_position(position_id))
            
            # Set up risk monitoring
            await self.risk_manager.monitor_position_risk(
                position['token_address'],
                position
            )
        except Exception as e:
            self.logger.error(f"Error setting up position monitoring: {e}")

    async def _cleanup_position_monitoring(self, position_id):
        """Clean up monitoring for a closed position."""
        try:
            # Remove stops and targets
            self.active_stops.pop(position_id, None)
            self.profit_targets.pop(position_id, None)
        except Exception as e:
            self.logger.error(f"Error cleaning up position monitoring: {e}")

    async def _monitor_position(self, position_id):
        """Monitor an active position."""
        try:
            while position_id in self.positions:
                await self.update_position(position_id)
                await asyncio.sleep(POSITION_CONFIG['update_interval'])
        except Exception as e:
            self.logger.error(f"Error monitoring position: {e}")

    async def _check_position_limits(self, position_id):
        """Check if position has hit any stops or targets."""
        try:
            position = self.positions[position_id]
            current_price = position['current_price']
            
            # Check stop loss
            if position_id in self.active_stops:
                stop = self.active_stops[position_id]
                if current_price <= stop['price']:
                    await self.close_position(position_id, current_price)
                    return
            
            # Check take profit targets
            if position_id in self.profit_targets:
                targets = self.profit_targets[position_id]['targets']
                for target in targets:
                    if current_price >= target['price']:
                        if target['percentage'] == 100:
                            await self.close_position(position_id, current_price)
                        else:
                            # Partial close implementation would go here
                            pass
        except Exception as e:
            self.logger.error(f"Error checking position limits: {e}")

    def _generate_position_id(self, token_address, wallet_address):
        """Generate unique position ID."""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        return f"{token_address[:6]}_{wallet_address[:6]}_{timestamp}"

    def _calculate_pnl(self, position, current_price):
        """Calculate position P&L."""
        try:
            entry_price = Decimal(str(position['entry_price']))
            current_price = Decimal(str(current_price))
            amount = Decimal(str(position['amount']))
            
            return float((current_price - entry_price) * amount)
        except Exception as e:
            self.logger.error(f"Error calculating PnL: {e}")
            return 0

    def _calculate_roi(self, position):
        """Calculate position ROI."""
        try:
            entry_value = Decimal(str(position['entry_price'])) * Decimal(str(position['amount']))
            if entry_value == 0:
                return 0
            
            pnl = Decimal(str(position['pnl']))
            return float((pnl / entry_value) * 100)
        except Exception as e:
            self.logger.error(f"Error calculating ROI: {e}")
            return 0

    def _validate_profit_targets(self, targets):
        """Validate profit target configuration."""
        try:
            total_percentage = sum(target['percentage'] for target in targets)
            return total_percentage <= 100
        except Exception as e:
            self.logger.error(f"Error validating profit targets: {e}")
            return False

    async def _get_current_price(self, pair_address):
        """Get current token price."""
        # Implement price fetching
        pass
