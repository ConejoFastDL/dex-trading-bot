import logging
from typing import Dict, List, Optional, Union
from decimal import Decimal
import asyncio
from datetime import datetime, timedelta
from web3 import Web3
import json
import numpy as np
from config import LIQUIDITY_CONFIG

class LiquidityManager:
    def __init__(self, w3_provider, wallet_manager):
        self.w3 = w3_provider
        self.wallet_manager = wallet_manager
        self.logger = logging.getLogger(__name__)
        self.positions = {}
        self.pool_data = {}
        self.custom_strategies = {}
        self.manual_mode = True
        self.position_alerts = {}
        self._load_pool_contracts()

    def _load_pool_contracts(self):
        """Load pool contract ABIs and addresses."""
        try:
            with open(LIQUIDITY_CONFIG['pool_abi_path'], 'r') as f:
                self.pool_abi = json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading pool contracts: {e}")

    async def add_liquidity(self, pool_address: str, token_amounts: Dict[str, Decimal],
                          slippage_tolerance: float = 0.5, deadline: int = None):
        """Manually add liquidity to a pool."""
        try:
            if not self.manual_mode:
                raise ValueError("Manual mode is not enabled")

            # Get pool contract
            pool_contract = self._get_pool_contract(pool_address)
            if not pool_contract:
                return None

            # Validate token amounts
            if not await self._validate_token_amounts(pool_address, token_amounts):
                return None

            # Calculate minimum amounts with slippage
            min_amounts = self._calculate_min_amounts(token_amounts, slippage_tolerance)

            # Prepare transaction
            deadline = deadline or int(datetime.now().timestamp() + 3600)  # 1 hour default
            tx_params = await self._prepare_add_liquidity_tx(
                pool_contract, token_amounts, min_amounts, deadline
            )

            # Execute transaction if approved
            return await self._execute_transaction(tx_params)
        except Exception as e:
            self.logger.error(f"Error adding liquidity: {e}")
            return None

    async def remove_liquidity(self, pool_address: str, lp_token_amount: Decimal,
                             min_amounts: Dict[str, Decimal] = None,
                             deadline: int = None):
        """Manually remove liquidity from a pool."""
        try:
            if not self.manual_mode:
                raise ValueError("Manual mode is not enabled")

            # Get pool contract
            pool_contract = self._get_pool_contract(pool_address)
            if not pool_contract:
                return None

            # Get position info
            position = await self.get_position(pool_address)
            if not position:
                raise ValueError("No position found in pool")

            # Calculate minimum amounts if not provided
            if not min_amounts:
                min_amounts = await self._calculate_min_withdraw_amounts(
                    pool_address, lp_token_amount
                )

            # Prepare transaction
            deadline = deadline or int(datetime.now().timestamp() + 3600)
            tx_params = await self._prepare_remove_liquidity_tx(
                pool_contract, lp_token_amount, min_amounts, deadline
            )

            # Execute transaction if approved
            return await self._execute_transaction(tx_params)
        except Exception as e:
            self.logger.error(f"Error removing liquidity: {e}")
            return None

    async def get_position(self, pool_address: str):
        """Get current liquidity position details."""
        try:
            if pool_address not in self.positions:
                position = await self._fetch_position(pool_address)
                if position:
                    self.positions[pool_address] = position
            return self.positions.get(pool_address)
        except Exception as e:
            self.logger.error(f"Error getting position: {e}")
            return None

    async def get_pool_info(self, pool_address: str):
        """Get detailed pool information."""
        try:
            if pool_address not in self.pool_data:
                pool_info = await self._fetch_pool_info(pool_address)
                if pool_info:
                    self.pool_data[pool_address] = pool_info
            return self.pool_data.get(pool_address)
        except Exception as e:
            self.logger.error(f"Error getting pool info: {e}")
            return None

    async def calculate_impermanent_loss(self, pool_address: str,
                                       price_changes: Dict[str, float]):
        """Calculate impermanent loss for given price changes."""
        try:
            position = await self.get_position(pool_address)
            if not position:
                return None

            # Calculate IL using standard formula
            il = self._calculate_il(price_changes)

            # Calculate value impact
            value_impact = position['total_value'] * il

            return {
                'impermanent_loss_percentage': il * 100,
                'value_impact': value_impact,
                'position_details': position
            }
        except Exception as e:
            self.logger.error(f"Error calculating impermanent loss: {e}")
            return None

    async def set_position_alert(self, pool_address: str, alert_type: str,
                               threshold: Union[float, Dict]):
        """Set alerts for liquidity position."""
        try:
            if pool_address not in self.position_alerts:
                self.position_alerts[pool_address] = {}

            self.position_alerts[pool_address][alert_type] = {
                'threshold': threshold,
                'created_at': datetime.now().isoformat()
            }

            return True
        except Exception as e:
            self.logger.error(f"Error setting position alert: {e}")
            return False

    async def remove_position_alert(self, pool_address: str, alert_type: str = None):
        """Remove specific or all position alerts."""
        try:
            if alert_type:
                self.position_alerts[pool_address].pop(alert_type, None)
            else:
                self.position_alerts.pop(pool_address, None)
            return True
        except Exception as e:
            self.logger.error(f"Error removing position alert: {e}")
            return False

    async def add_custom_strategy(self, name: str, strategy_func,
                                parameters: Dict = None):
        """Add custom liquidity management strategy."""
        try:
            self.custom_strategies[name] = {
                'function': strategy_func,
                'parameters': parameters or {}
            }
            return True
        except Exception as e:
            self.logger.error(f"Error adding custom strategy: {e}")
            return False

    async def execute_custom_strategy(self, strategy_name: str,
                                    pool_address: str,
                                    parameters: Dict = None):
        """Execute custom liquidity strategy."""
        try:
            if not self.manual_mode:
                raise ValueError("Manual mode is not enabled")

            if strategy_name not in self.custom_strategies:
                raise ValueError(f"Strategy {strategy_name} not found")

            strategy = self.custom_strategies[strategy_name]
            params = parameters or strategy['parameters']

            result = await strategy['function'](
                self, pool_address, **params
            )

            return result
        except Exception as e:
            self.logger.error(f"Error executing custom strategy: {e}")
            return None

    async def analyze_pool_performance(self, pool_address: str,
                                     timeframe: str = '24h'):
        """Analyze pool performance metrics."""
        try:
            pool_info = await self.get_pool_info(pool_address)
            if not pool_info:
                return None

            # Calculate key metrics
            metrics = await self._calculate_pool_metrics(pool_address, timeframe)

            return {
                'pool_info': pool_info,
                'metrics': metrics
            }
        except Exception as e:
            self.logger.error(f"Error analyzing pool performance: {e}")
            return None

    async def estimate_mining_rewards(self, pool_address: str,
                                    lp_token_amount: Decimal,
                                    timeframe: str = '24h'):
        """Estimate mining rewards for liquidity provision."""
        try:
            pool_info = await self.get_pool_info(pool_address)
            if not pool_info:
                return None

            # Calculate estimated rewards
            rewards = await self._calculate_mining_rewards(
                pool_address, lp_token_amount, timeframe
            )

            return rewards
        except Exception as e:
            self.logger.error(f"Error estimating mining rewards: {e}")
            return None

    async def _fetch_position(self, pool_address: str):
        """Fetch current position details from blockchain."""
        try:
            pool_contract = self._get_pool_contract(pool_address)
            if not pool_contract:
                return None

            # Get position details
            wallet_address = await self.wallet_manager.get_active_wallet()
            balance = await pool_contract.functions.balanceOf(wallet_address).call()

            if balance == 0:
                return None

            # Get pool tokens and reserves
            token0 = await pool_contract.functions.token0().call()
            token1 = await pool_contract.functions.token1().call()
            reserves = await pool_contract.functions.getReserves().call()

            # Calculate position value
            total_supply = await pool_contract.functions.totalSupply().call()
            share = Decimal(balance) / Decimal(total_supply)

            position = {
                'pool_address': pool_address,
                'lp_token_balance': balance,
                'share_percentage': float(share * 100),
                'token_amounts': {
                    token0: share * Decimal(reserves[0]),
                    token1: share * Decimal(reserves[1])
                },
                'total_value': None  # To be calculated with current prices
            }

            return position
        except Exception as e:
            self.logger.error(f"Error fetching position: {e}")
            return None

    async def _fetch_pool_info(self, pool_address: str):
        """Fetch detailed pool information."""
        try:
            pool_contract = self._get_pool_contract(pool_address)
            if not pool_contract:
                return None

            # Get basic pool info
            token0 = await pool_contract.functions.token0().call()
            token1 = await pool_contract.functions.token1().call()
            reserves = await pool_contract.functions.getReserves().call()
            total_supply = await pool_contract.functions.totalSupply().call()

            # Get fee info if available
            try:
                fee = await pool_contract.functions.fee().call()
            except:
                fee = None

            pool_info = {
                'address': pool_address,
                'tokens': [token0, token1],
                'reserves': reserves,
                'total_supply': total_supply,
                'fee': fee,
                'updated_at': datetime.now().isoformat()
            }

            return pool_info
        except Exception as e:
            self.logger.error(f"Error fetching pool info: {e}")
            return None

    def _get_pool_contract(self, pool_address: str):
        """Get pool contract instance."""
        try:
            return self.w3.eth.contract(
                address=pool_address,
                abi=self.pool_abi
            )
        except Exception as e:
            self.logger.error(f"Error getting pool contract: {e}")
            return None

    async def _validate_token_amounts(self, pool_address: str,
                                    token_amounts: Dict[str, Decimal]):
        """Validate token amounts for liquidity provision."""
        try:
            pool_info = await self.get_pool_info(pool_address)
            if not pool_info:
                return False

            # Check if tokens match pool tokens
            if set(token_amounts.keys()) != set(pool_info['tokens']):
                return False

            # Check if user has sufficient balance
            for token, amount in token_amounts.items():
                balance = await self.wallet_manager.get_token_balance(token)
                if balance < amount:
                    return False

            return True
        except Exception as e:
            self.logger.error(f"Error validating token amounts: {e}")
            return False

    def _calculate_il(self, price_changes: Dict[str, float]):
        """Calculate impermanent loss percentage."""
        try:
            # Standard IL formula for price ratio changes
            price_ratio = list(price_changes.values())[0]
            il = 2 * (price_ratio ** 0.5) / (1 + price_ratio) - 1
            return abs(il)
        except Exception as e:
            self.logger.error(f"Error calculating IL: {e}")
            return None

    async def _calculate_pool_metrics(self, pool_address: str, timeframe: str):
        """Calculate pool performance metrics."""
        try:
            # Get historical data
            end_time = datetime.now()
            start_time = self._get_start_time(timeframe)

            # Calculate metrics
            metrics = {
                'volume': await self._calculate_volume(pool_address, start_time, end_time),
                'fees': await self._calculate_fees(pool_address, start_time, end_time),
                'apy': await self._calculate_apy(pool_address, start_time, end_time),
                'price_impact': await self._calculate_price_impact(pool_address),
                'liquidity_depth': await self._calculate_liquidity_depth(pool_address)
            }

            return metrics
        except Exception as e:
            self.logger.error(f"Error calculating pool metrics: {e}")
            return None

    def _get_start_time(self, timeframe: str):
        """Convert timeframe string to start datetime."""
        try:
            now = datetime.now()
            if timeframe == '24h':
                return now - timedelta(days=1)
            elif timeframe == '7d':
                return now - timedelta(days=7)
            elif timeframe == '30d':
                return now - timedelta(days=30)
            else:
                raise ValueError(f"Unsupported timeframe: {timeframe}")
        except Exception as e:
            self.logger.error(f"Error getting start time: {e}")
            return None
