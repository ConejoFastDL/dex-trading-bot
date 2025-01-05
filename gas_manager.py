from web3 import Web3
import asyncio
import logging
import numpy as np
from config import TRADING_CONFIG
import time

class GasManager:
    def __init__(self, w3_provider):
        self.w3 = w3_provider
        self.logger = logging.getLogger(__name__)
        self.gas_price_history = []
        self.last_update = 0
        self.update_interval = 15  # Update every 15 seconds

    async def get_optimal_gas(self, transaction_type='swap'):
        """Get optimal gas price and limit based on network conditions."""
        try:
            gas_price = await self._get_optimal_gas_price()
            gas_limit = await self._estimate_gas_limit(transaction_type)
            
            return {
                'gas_price': gas_price,
                'gas_limit': gas_limit,
                'estimated_cost': gas_price * gas_limit / 10**18,  # in native token
                'is_high': self._is_gas_price_high(gas_price)
            }
        except Exception as e:
            self.logger.error(f"Error getting optimal gas: {e}")
            return None

    async def _get_optimal_gas_price(self):
        """Calculate optimal gas price based on network conditions."""
        try:
            await self._update_gas_price_history()
            
            # Get base fee from latest block
            base_fee = self.w3.eth.get_block('latest')['baseFeePerGas']
            
            # Calculate priority fee based on recent history
            priority_fee = await self._calculate_priority_fee()
            
            # Calculate optimal gas price with dynamic buffer
            buffer_multiplier = self._calculate_buffer_multiplier()
            optimal_gas_price = int(base_fee * buffer_multiplier) + priority_fee
            
            # Ensure within configured limits
            max_gas_price = TRADING_CONFIG['max_gas_price']
            return min(optimal_gas_price, max_gas_price)
        except Exception as e:
            self.logger.error(f"Error calculating optimal gas price: {e}")
            return self.w3.eth.gas_price

    async def _estimate_gas_limit(self, transaction_type):
        """Estimate gas limit based on transaction type."""
        try:
            base_limits = {
                'swap': 200000,
                'approve': 100000,
                'transfer': 65000
            }
            
            # Get base limit for transaction type
            base_limit = base_limits.get(transaction_type, 200000)
            
            # Add buffer based on network congestion
            congestion_multiplier = await self._get_network_congestion_multiplier()
            estimated_limit = int(base_limit * congestion_multiplier)
            
            return min(estimated_limit, TRADING_CONFIG['gas_limit'])
        except Exception as e:
            self.logger.error(f"Error estimating gas limit: {e}")
            return TRADING_CONFIG['gas_limit']

    async def _update_gas_price_history(self):
        """Update gas price history if needed."""
        try:
            current_time = time.time()
            if current_time - self.last_update < self.update_interval:
                return

            # Get current gas price
            current_price = self.w3.eth.gas_price
            
            # Add to history with timestamp
            self.gas_price_history.append({
                'timestamp': current_time,
                'price': current_price
            })
            
            # Keep last hour of history
            one_hour_ago = current_time - 3600
            self.gas_price_history = [
                entry for entry in self.gas_price_history 
                if entry['timestamp'] > one_hour_ago
            ]
            
            self.last_update = current_time
        except Exception as e:
            self.logger.error(f"Error updating gas price history: {e}")

    async def _calculate_priority_fee(self):
        """Calculate priority fee based on recent blocks."""
        try:
            recent_blocks = []
            latest_block = self.w3.eth.block_number
            
            # Get priority fees from recent blocks
            for i in range(10):  # Look at last 10 blocks
                block = self.w3.eth.get_block(latest_block - i)
                if 'baseFeePerGas' in block:
                    recent_blocks.append(block)

            if not recent_blocks:
                return self.w3.eth.max_priority_fee

            # Calculate median priority fee
            priority_fees = []
            for block in recent_blocks:
                base_fee = block['baseFeePerGas']
                for tx_hash in block['transactions']:
                    tx = self.w3.eth.get_transaction(tx_hash)
                    if 'maxFeePerGas' in tx:
                        priority_fee = tx['maxFeePerGas'] - base_fee
                        priority_fees.append(priority_fee)

            if priority_fees:
                return int(np.median(priority_fees))
            return self.w3.eth.max_priority_fee
        except Exception as e:
            self.logger.error(f"Error calculating priority fee: {e}")
            return self.w3.eth.max_priority_fee

    def _calculate_buffer_multiplier(self):
        """Calculate dynamic buffer multiplier based on price volatility."""
        try:
            if not self.gas_price_history:
                return 1.1  # Default 10% buffer

            # Calculate price volatility
            prices = [entry['price'] for entry in self.gas_price_history]
            if len(prices) < 2:
                return 1.1

            volatility = np.std(prices) / np.mean(prices)
            
            # Adjust buffer based on volatility
            base_buffer = 1.1
            volatility_adjustment = min(volatility * 2, 0.5)  # Cap at 50% additional buffer
            
            return base_buffer + volatility_adjustment
        except Exception as e:
            self.logger.error(f"Error calculating buffer multiplier: {e}")
            return 1.1

    async def _get_network_congestion_multiplier(self):
        """Calculate network congestion multiplier."""
        try:
            # Get latest block
            latest_block = self.w3.eth.get_block('latest')
            
            # Calculate block utilization
            gas_used = latest_block['gasUsed']
            gas_limit = latest_block['gasLimit']
            utilization = gas_used / gas_limit
            
            # Calculate multiplier based on utilization
            if utilization > 0.8:  # High congestion
                return 1.3
            elif utilization > 0.5:  # Medium congestion
                return 1.2
            else:  # Low congestion
                return 1.1
        except Exception as e:
            self.logger.error(f"Error calculating congestion multiplier: {e}")
            return 1.2

    def _is_gas_price_high(self, gas_price):
        """Determine if current gas price is considered high."""
        try:
            if not self.gas_price_history:
                return False

            # Calculate average gas price from history
            avg_price = np.mean([entry['price'] for entry in self.gas_price_history])
            
            # Consider high if 30% above average
            return gas_price > (avg_price * 1.3)
        except Exception as e:
            self.logger.error(f"Error checking if gas price is high: {e}")
            return False

    async def wait_for_better_gas(self, max_wait_time=300):
        """Wait for better gas prices within a time limit."""
        try:
            start_time = time.time()
            initial_gas = await self._get_optimal_gas_price()
            
            while time.time() - start_time < max_wait_time:
                current_gas = await self._get_optimal_gas_price()
                
                # If gas price has dropped by at least 20%
                if current_gas <= (initial_gas * 0.8):
                    return True
                
                await asyncio.sleep(15)  # Check every 15 seconds
            
            return False
        except Exception as e:
            self.logger.error(f"Error waiting for better gas: {e}")
            return False
