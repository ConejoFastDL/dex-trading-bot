import logging
from typing import Dict, List, Optional, Union
from decimal import Decimal
import asyncio
from datetime import datetime, timedelta
from web3 import Web3
import aiohttp
import json
from config import NETWORK_CONFIG

class NetworkManager:
    def __init__(self, w3_provider):
        self.w3 = w3_provider
        self.logger = logging.getLogger(__name__)
        self.rpc_endpoints = {}
        self.network_status = {}
        self.gas_prices = {}
        self.pending_transactions = {}
        self.manual_mode = True
        self.custom_gas_settings = {}
        self._load_network_config()

    def _load_network_config(self):
        """Load network configuration and RPC endpoints."""
        try:
            self.network_config = NETWORK_CONFIG
            self.default_rpc = NETWORK_CONFIG['default_rpc']
            self._load_rpc_endpoints()
        except Exception as e:
            self.logger.error(f"Error loading network config: {e}")

    def _load_rpc_endpoints(self):
        """Load RPC endpoints from configuration."""
        try:
            for network, config in NETWORK_CONFIG['networks'].items():
                self.rpc_endpoints[network] = {
                    'url': config['rpc_url'],
                    'chain_id': config['chain_id'],
                    'status': 'unknown'
                }
        except Exception as e:
            self.logger.error(f"Error loading RPC endpoints: {e}")

    async def add_rpc_endpoint(self, network: str, url: str, chain_id: int):
        """Add custom RPC endpoint."""
        try:
            # Validate RPC endpoint
            if not await self._validate_rpc(url, chain_id):
                return False

            self.rpc_endpoints[network] = {
                'url': url,
                'chain_id': chain_id,
                'status': 'active'
            }

            return True
        except Exception as e:
            self.logger.error(f"Error adding RPC endpoint: {e}")
            return False

    async def remove_rpc_endpoint(self, network: str):
        """Remove custom RPC endpoint."""
        try:
            if network in self.rpc_endpoints:
                del self.rpc_endpoints[network]
            return True
        except Exception as e:
            self.logger.error(f"Error removing RPC endpoint: {e}")
            return False

    async def set_active_network(self, network: str):
        """Set active network for transactions."""
        try:
            if network not in self.rpc_endpoints:
                raise ValueError(f"Network {network} not found")

            endpoint = self.rpc_endpoints[network]
            
            # Update web3 provider
            self.w3.provider = Web3.HTTPProvider(endpoint['url'])
            
            # Verify connection
            if not self.w3.is_connected():
                raise Exception("Failed to connect to new network")

            return True
        except Exception as e:
            self.logger.error(f"Error setting active network: {e}")
            return False

    async def get_gas_price(self, priority: str = 'medium'):
        """Get current gas price with priority level."""
        try:
            if not self.manual_mode:
                raise ValueError("Manual mode is not enabled")

            # Get latest gas prices
            await self._update_gas_prices()

            if priority in self.gas_prices:
                return self.gas_prices[priority]
            else:
                return await self._get_network_gas_price()
        except Exception as e:
            self.logger.error(f"Error getting gas price: {e}")
            return None

    async def set_custom_gas_price(self, gas_price: int, priority: str = 'custom'):
        """Set custom gas price for transactions."""
        try:
            if not self.manual_mode:
                raise ValueError("Manual mode is not enabled")

            self.custom_gas_settings[priority] = {
                'gas_price': gas_price,
                'timestamp': datetime.now().isoformat()
            }

            return True
        except Exception as e:
            self.logger.error(f"Error setting custom gas price: {e}")
            return False

    async def estimate_transaction_cost(self, tx_params: Dict):
        """Estimate transaction cost with current gas prices."""
        try:
            # Estimate gas usage
            gas_estimate = await self._estimate_gas(tx_params)
            if not gas_estimate:
                return None

            # Get current gas prices for different priorities
            gas_prices = await self._get_gas_prices()

            estimates = {}
            for priority, price in gas_prices.items():
                cost = gas_estimate * price
                estimates[priority] = {
                    'gas_limit': gas_estimate,
                    'gas_price': price,
                    'total_cost': cost
                }

            return estimates
        except Exception as e:
            self.logger.error(f"Error estimating transaction cost: {e}")
            return None

    async def monitor_transaction(self, tx_hash: str):
        """Monitor transaction status and gas usage."""
        try:
            if not Web3.is_checksum_address(tx_hash):
                raise ValueError("Invalid transaction hash")

            # Get transaction receipt
            receipt = await self._get_transaction_receipt(tx_hash)
            if not receipt:
                return None

            # Get transaction details
            tx = await self._get_transaction(tx_hash)
            if not tx:
                return None

            return {
                'status': receipt['status'],
                'block_number': receipt['blockNumber'],
                'gas_used': receipt['gasUsed'],
                'gas_price': tx['gasPrice'],
                'total_cost': receipt['gasUsed'] * tx['gasPrice'],
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            self.logger.error(f"Error monitoring transaction: {e}")
            return None

    async def check_network_status(self, network: str = None):
        """Check network status and performance metrics."""
        try:
            if network and network not in self.rpc_endpoints:
                raise ValueError(f"Network {network} not found")

            networks = [network] if network else self.rpc_endpoints.keys()
            
            status = {}
            for net in networks:
                endpoint = self.rpc_endpoints[net]
                
                # Check connection and latency
                connection_status = await self._check_connection(endpoint['url'])
                
                # Get network metrics
                metrics = await self._get_network_metrics(net)
                
                status[net] = {
                    'connection': connection_status,
                    'metrics': metrics,
                    'last_updated': datetime.now().isoformat()
                }

            self.network_status.update(status)
            return status
        except Exception as e:
            self.logger.error(f"Error checking network status: {e}")
            return None

    async def optimize_transaction(self, tx_params: Dict,
                                 optimization_type: str = 'gas'):
        """Optimize transaction parameters."""
        try:
            if optimization_type == 'gas':
                optimized = await self._optimize_gas_usage(tx_params)
            elif optimization_type == 'speed':
                optimized = await self._optimize_transaction_speed(tx_params)
            else:
                raise ValueError(f"Unsupported optimization type: {optimization_type}")

            return optimized
        except Exception as e:
            self.logger.error(f"Error optimizing transaction: {e}")
            return None

    async def _validate_rpc(self, url: str, chain_id: int):
        """Validate RPC endpoint connection and chain ID."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json={
                    "jsonrpc": "2.0",
                    "method": "eth_chainId",
                    "params": [],
                    "id": 1
                }) as response:
                    if response.status != 200:
                        return False
                    
                    data = await response.json()
                    if 'result' not in data:
                        return False
                    
                    rpc_chain_id = int(data['result'], 16)
                    return rpc_chain_id == chain_id
        except Exception as e:
            self.logger.error(f"Error validating RPC: {e}")
            return False

    async def _update_gas_prices(self):
        """Update current gas prices from various sources."""
        try:
            # Get prices from multiple sources
            network_price = await self._get_network_gas_price()
            oracle_prices = await self._get_gas_oracle_prices()
            
            # Combine and average prices
            self.gas_prices = {
                'low': min(network_price * 0.8, oracle_prices.get('low', network_price)),
                'medium': network_price,
                'high': max(network_price * 1.2, oracle_prices.get('high', network_price))
            }

            # Add custom gas prices
            self.gas_prices.update(self.custom_gas_settings)
            
            return self.gas_prices
        except Exception as e:
            self.logger.error(f"Error updating gas prices: {e}")
            return None

    async def _get_network_gas_price(self):
        """Get gas price from current network."""
        try:
            return self.w3.eth.gas_price
        except Exception as e:
            self.logger.error(f"Error getting network gas price: {e}")
            return None

    async def _get_gas_oracle_prices(self):
        """Get gas prices from external oracle."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(NETWORK_CONFIG['gas_oracle_url']) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            'low': data['safeLow'],
                            'medium': data['standard'],
                            'high': data['fast']
                        }
                    return {}
        except Exception as e:
            self.logger.error(f"Error getting oracle gas prices: {e}")
            return {}

    async def _estimate_gas(self, tx_params: Dict):
        """Estimate gas usage for transaction."""
        try:
            return self.w3.eth.estimate_gas(tx_params)
        except Exception as e:
            self.logger.error(f"Error estimating gas: {e}")
            return None

    async def _get_transaction_receipt(self, tx_hash: str):
        """Get transaction receipt from network."""
        try:
            return self.w3.eth.get_transaction_receipt(tx_hash)
        except Exception as e:
            self.logger.error(f"Error getting transaction receipt: {e}")
            return None

    async def _get_transaction(self, tx_hash: str):
        """Get transaction details from network."""
        try:
            return self.w3.eth.get_transaction(tx_hash)
        except Exception as e:
            self.logger.error(f"Error getting transaction: {e}")
            return None

    async def _check_connection(self, url: str):
        """Check RPC endpoint connection and latency."""
        try:
            start_time = datetime.now()
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json={
                    "jsonrpc": "2.0",
                    "method": "net_version",
                    "params": [],
                    "id": 1
                }) as response:
                    latency = (datetime.now() - start_time).total_seconds() * 1000
                    
                    return {
                        'status': 'connected' if response.status == 200 else 'error',
                        'latency_ms': latency
                    }
        except Exception as e:
            self.logger.error(f"Error checking connection: {e}")
            return {'status': 'error', 'latency_ms': None}

    async def _get_network_metrics(self, network: str):
        """Get network performance metrics."""
        try:
            # Get latest block
            latest_block = self.w3.eth.get_block('latest')
            
            # Calculate block time
            prev_block = self.w3.eth.get_block(latest_block['number'] - 1)
            block_time = latest_block['timestamp'] - prev_block['timestamp']
            
            return {
                'latest_block': latest_block['number'],
                'block_time': block_time,
                'gas_limit': latest_block['gasLimit'],
                'gas_used': latest_block['gasUsed'],
                'base_fee': latest_block.get('baseFeePerGas', None)
            }
        except Exception as e:
            self.logger.error(f"Error getting network metrics: {e}")
            return None

    async def _optimize_gas_usage(self, tx_params: Dict):
        """Optimize transaction for gas usage."""
        try:
            # Get current network state
            block = self.w3.eth.get_block('latest')
            base_fee = block.get('baseFeePerGas', None)
            
            # Calculate optimal gas settings
            if base_fee:
                max_priority_fee = self.w3.eth.max_priority_fee
                tx_params['maxFeePerGas'] = base_fee * 2
                tx_params['maxPriorityFeePerGas'] = max_priority_fee
            else:
                gas_price = await self.get_gas_price('low')
                tx_params['gasPrice'] = gas_price
            
            return tx_params
        except Exception as e:
            self.logger.error(f"Error optimizing gas usage: {e}")
            return None

    async def _optimize_transaction_speed(self, tx_params: Dict):
        """Optimize transaction for speed."""
        try:
            # Get current network state
            block = self.w3.eth.get_block('latest')
            base_fee = block.get('baseFeePerGas', None)
            
            # Calculate optimal gas settings for speed
            if base_fee:
                max_priority_fee = self.w3.eth.max_priority_fee * 1.5
                tx_params['maxFeePerGas'] = base_fee * 3
                tx_params['maxPriorityFeePerGas'] = max_priority_fee
            else:
                gas_price = await self.get_gas_price('high')
                tx_params['gasPrice'] = gas_price
            
            return tx_params
        except Exception as e:
            self.logger.error(f"Error optimizing transaction speed: {e}")
            return None
