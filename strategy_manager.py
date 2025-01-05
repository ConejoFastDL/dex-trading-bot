import asyncio
import logging
from datetime import datetime, timedelta
import numpy as np
from decimal import Decimal
from config import STRATEGY_CONFIG
import json
from typing import Dict, List, Optional

class StrategyManager:
    def __init__(self, price_monitor, volume_monitor, risk_manager, position_manager):
        self.price_monitor = price_monitor
        self.volume_monitor = volume_monitor
        self.risk_manager = risk_manager
        self.position_manager = position_manager
        self.logger = logging.getLogger(__name__)
        self.active_strategies = {}
        self.strategy_results = {}
        self.strategy_signals = {}
        self.monitoring = False

    async def start_strategy(self, strategy_name: str, pair_address: str, 
                           parameters: Dict = None):
        """Start a trading strategy."""
        try:
            # Generate strategy ID
            strategy_id = self._generate_strategy_id(strategy_name, pair_address)
            
            # Initialize strategy with parameters
            strategy = {
                'id': strategy_id,
                'name': strategy_name,
                'pair_address': pair_address,
                'parameters': parameters or self._get_default_parameters(strategy_name),
                'status': 'active',
                'started_at': datetime.now().isoformat(),
                'signals': [],
                'positions': [],
                'performance': {
                    'total_trades': 0,
                    'winning_trades': 0,
                    'total_profit': 0,
                    'max_drawdown': 0
                }
            }
            
            self.active_strategies[strategy_id] = strategy
            
            # Start strategy monitoring
            await self._monitor_strategy(strategy_id)
            
            return strategy_id
        except Exception as e:
            self.logger.error(f"Error starting strategy: {e}")
            return None

    async def stop_strategy(self, strategy_id: str):
        """Stop a running strategy."""
        try:
            if strategy_id not in self.active_strategies:
                raise ValueError("Strategy not found")
            
            strategy = self.active_strategies[strategy_id]
            
            # Close any open positions
            for position_id in strategy['positions']:
                if await self._is_position_open(position_id):
                    await self.position_manager.close_position(position_id)
            
            # Update strategy status
            strategy['status'] = 'stopped'
            strategy['stopped_at'] = datetime.now().isoformat()
            
            # Move to results
            self.strategy_results[strategy_id] = strategy
            del self.active_strategies[strategy_id]
            
            return True
        except Exception as e:
            self.logger.error(f"Error stopping strategy: {e}")
            return False

    async def update_strategy_parameters(self, strategy_id: str, parameters: Dict):
        """Update strategy parameters."""
        try:
            if strategy_id not in self.active_strategies:
                raise ValueError("Strategy not found")
            
            strategy = self.active_strategies[strategy_id]
            
            # Validate parameters
            if not self._validate_parameters(strategy['name'], parameters):
                raise ValueError("Invalid parameters")
            
            # Update parameters
            strategy['parameters'] = parameters
            strategy['updated_at'] = datetime.now().isoformat()
            
            return True
        except Exception as e:
            self.logger.error(f"Error updating strategy parameters: {e}")
            return False

    async def get_strategy_performance(self, strategy_id: str):
        """Get strategy performance metrics."""
        try:
            strategy = self.active_strategies.get(strategy_id) or self.strategy_results.get(strategy_id)
            
            if not strategy:
                return None
            
            # Calculate additional metrics
            metrics = await self._calculate_performance_metrics(strategy)
            
            return {
                'basic_metrics': strategy['performance'],
                'advanced_metrics': metrics
            }
        except Exception as e:
            self.logger.error(f"Error getting strategy performance: {e}")
            return None

    async def get_strategy_signals(self, strategy_id: str):
        """Get recent trading signals from strategy."""
        try:
            if strategy_id not in self.strategy_signals:
                return []
            
            return sorted(
                self.strategy_signals[strategy_id],
                key=lambda x: datetime.fromisoformat(x['timestamp']),
                reverse=True
            )
        except Exception as e:
            self.logger.error(f"Error getting strategy signals: {e}")
            return []

    async def _monitor_strategy(self, strategy_id: str):
        """Monitor and execute strategy logic."""
        try:
            strategy = self.active_strategies[strategy_id]
            
            while strategy['status'] == 'active':
                # Get market data
                price_data = await self.price_monitor.get_price_data(
                    strategy['pair_address']
                )
                volume_data = await self.volume_monitor.analyze_volume(
                    strategy['pair_address']
                )
                
                # Generate signals
                signals = await self._generate_signals(
                    strategy['name'],
                    price_data,
                    volume_data,
                    strategy['parameters']
                )
                
                # Process signals
                if signals:
                    await self._process_signals(strategy_id, signals)
                
                # Update performance
                await self._update_performance(strategy_id)
                
                await asyncio.sleep(STRATEGY_CONFIG['update_interval'])
        except Exception as e:
            self.logger.error(f"Error monitoring strategy: {e}")
            strategy['status'] = 'error'

    async def _generate_signals(self, strategy_name: str, price_data, volume_data, 
                              parameters: Dict):
        """Generate trading signals based on strategy."""
        try:
            signals = []
            
            if strategy_name == 'momentum':
                signals = await self._momentum_strategy(price_data, volume_data, parameters)
            elif strategy_name == 'mean_reversion':
                signals = await self._mean_reversion_strategy(price_data, volume_data, parameters)
            elif strategy_name == 'breakout':
                signals = await self._breakout_strategy(price_data, volume_data, parameters)
            elif strategy_name == 'hybrid':
                signals = await self._hybrid_strategy(price_data, volume_data, parameters)
            
            return signals
        except Exception as e:
            self.logger.error(f"Error generating signals: {e}")
            return []

    async def _process_signals(self, strategy_id: str, signals: List):
        """Process and execute trading signals."""
        try:
            strategy = self.active_strategies[strategy_id]
            
            for signal in signals:
                # Validate signal
                if not self._validate_signal(signal):
                    continue
                
                # Check risk parameters
                risk_assessment = await self.risk_manager.assess_trade_risk(
                    signal['token_address'],
                    strategy['pair_address'],
                    signal['amount']
                )
                
                if not risk_assessment['is_acceptable']:
                    continue
                
                # Execute trade
                if signal['action'] == 'buy':
                    position_id = await self._execute_buy(strategy_id, signal)
                    if position_id:
                        strategy['positions'].append(position_id)
                elif signal['action'] == 'sell':
                    await self._execute_sell(strategy_id, signal)
                
                # Record signal
                signal['timestamp'] = datetime.now().isoformat()
                signal['risk_assessment'] = risk_assessment
                
                if strategy_id not in self.strategy_signals:
                    self.strategy_signals[strategy_id] = []
                self.strategy_signals[strategy_id].append(signal)
        except Exception as e:
            self.logger.error(f"Error processing signals: {e}")

    async def _momentum_strategy(self, price_data, volume_data, parameters: Dict):
        """Momentum trading strategy implementation."""
        try:
            signals = []
            
            # Calculate momentum indicators
            rsi = self._calculate_rsi(price_data, parameters['rsi_period'])
            macd = self._calculate_macd(price_data, parameters['macd_fast'], 
                                      parameters['macd_slow'])
            volume_trend = self._analyze_volume_trend(volume_data)
            
            # Generate buy signals
            if (rsi < parameters['oversold_threshold'] and 
                macd['histogram'] > 0 and 
                volume_trend['increasing']):
                signals.append({
                    'action': 'buy',
                    'strength': self._calculate_signal_strength([
                        rsi, macd['histogram'], volume_trend['strength']
                    ]),
                    'indicators': {
                        'rsi': rsi,
                        'macd': macd,
                        'volume_trend': volume_trend
                    }
                })
            
            # Generate sell signals
            if (rsi > parameters['overbought_threshold'] and 
                macd['histogram'] < 0):
                signals.append({
                    'action': 'sell',
                    'strength': self._calculate_signal_strength([
                        rsi, abs(macd['histogram'])
                    ]),
                    'indicators': {
                        'rsi': rsi,
                        'macd': macd
                    }
                })
            
            return signals
        except Exception as e:
            self.logger.error(f"Error in momentum strategy: {e}")
            return []

    async def _mean_reversion_strategy(self, price_data, volume_data, parameters: Dict):
        """Mean reversion trading strategy implementation."""
        try:
            signals = []
            
            # Calculate mean reversion indicators
            bollinger = self._calculate_bollinger_bands(price_data, 
                                                      parameters['bb_period'],
                                                      parameters['bb_std'])
            price_deviation = self._calculate_price_deviation(price_data, bollinger)
            
            # Generate buy signals
            if price_deviation < -parameters['deviation_threshold']:
                signals.append({
                    'action': 'buy',
                    'strength': abs(price_deviation),
                    'indicators': {
                        'bollinger': bollinger,
                        'deviation': price_deviation
                    }
                })
            
            # Generate sell signals
            if price_deviation > parameters['deviation_threshold']:
                signals.append({
                    'action': 'sell',
                    'strength': abs(price_deviation),
                    'indicators': {
                        'bollinger': bollinger,
                        'deviation': price_deviation
                    }
                })
            
            return signals
        except Exception as e:
            self.logger.error(f"Error in mean reversion strategy: {e}")
            return []

    async def _breakout_strategy(self, price_data, volume_data, parameters: Dict):
        """Breakout trading strategy implementation."""
        try:
            signals = []
            
            # Calculate breakout indicators
            support_resistance = self._calculate_support_resistance(price_data)
            volume_breakout = self._detect_volume_breakout(volume_data)
            price_channels = self._calculate_price_channels(price_data)
            
            # Generate buy signals
            if (self._is_resistance_breakout(price_data, support_resistance) and 
                volume_breakout['confirmed']):
                signals.append({
                    'action': 'buy',
                    'strength': volume_breakout['strength'],
                    'indicators': {
                        'support_resistance': support_resistance,
                        'volume_breakout': volume_breakout,
                        'price_channels': price_channels
                    }
                })
            
            # Generate sell signals
            if self._is_support_breakdown(price_data, support_resistance):
                signals.append({
                    'action': 'sell',
                    'strength': volume_breakout['strength'],
                    'indicators': {
                        'support_resistance': support_resistance,
                        'price_channels': price_channels
                    }
                })
            
            return signals
        except Exception as e:
            self.logger.error(f"Error in breakout strategy: {e}")
            return []

    async def _hybrid_strategy(self, price_data, volume_data, parameters: Dict):
        """Hybrid trading strategy combining multiple approaches."""
        try:
            signals = []
            
            # Get signals from each strategy
            momentum_signals = await self._momentum_strategy(
                price_data, volume_data, parameters['momentum']
            )
            mean_rev_signals = await self._mean_reversion_strategy(
                price_data, volume_data, parameters['mean_reversion']
            )
            breakout_signals = await self._breakout_strategy(
                price_data, volume_data, parameters['breakout']
            )
            
            # Combine and weight signals
            all_signals = (
                [(s, parameters['weights']['momentum']) for s in momentum_signals] +
                [(s, parameters['weights']['mean_reversion']) for s in mean_rev_signals] +
                [(s, parameters['weights']['breakout']) for s in breakout_signals]
            )
            
            # Process combined signals
            for signal, weight in all_signals:
                signal['strength'] *= weight
                signals.append(signal)
            
            return signals
        except Exception as e:
            self.logger.error(f"Error in hybrid strategy: {e}")
            return []

    async def _execute_buy(self, strategy_id: str, signal: Dict):
        """Execute buy order based on signal."""
        try:
            strategy = self.active_strategies[strategy_id]
            
            # Calculate position size
            position_size = self._calculate_position_size(
                strategy['parameters']['position_sizing'],
                signal['strength']
            )
            
            # Open position
            position_id = await self.position_manager.open_position(
                signal['token_address'],
                strategy['pair_address'],
                position_size,
                strategy['parameters']['wallet_address']
            )
            
            if position_id:
                # Set stop loss and take profit
                await self.position_manager.set_stop_loss(
                    position_id,
                    percentage=strategy['parameters']['stop_loss']
                )
                
                await self.position_manager.set_take_profit(
                    position_id,
                    strategy['parameters']['take_profit']
                )
            
            return position_id
        except Exception as e:
            self.logger.error(f"Error executing buy: {e}")
            return None

    async def _execute_sell(self, strategy_id: str, signal: Dict):
        """Execute sell order based on signal."""
        try:
            strategy = self.active_strategies[strategy_id]
            
            # Close all positions for the pair
            for position_id in strategy['positions']:
                if await self._is_position_open(position_id):
                    await self.position_manager.close_position(position_id)
            
            return True
        except Exception as e:
            self.logger.error(f"Error executing sell: {e}")
            return False

    def _generate_strategy_id(self, strategy_name: str, pair_address: str):
        """Generate unique strategy ID."""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        return f"{strategy_name}_{pair_address[:6]}_{timestamp}"

    def _get_default_parameters(self, strategy_name: str):
        """Get default parameters for strategy."""
        return STRATEGY_CONFIG['strategies'].get(strategy_name, {})

    def _validate_parameters(self, strategy_name: str, parameters: Dict):
        """Validate strategy parameters."""
        try:
            required_params = STRATEGY_CONFIG['strategies'][strategy_name]['required_params']
            return all(param in parameters for param in required_params)
        except Exception as e:
            self.logger.error(f"Error validating parameters: {e}")
            return False

    def _validate_signal(self, signal: Dict):
        """Validate trading signal."""
        required_fields = ['action', 'strength', 'indicators']
        return all(field in signal for field in required_fields)

    async def _is_position_open(self, position_id: str):
        """Check if position is still open."""
        position_info = await self.position_manager.get_position_info(position_id)
        return position_info and position_info['status'] == 'open'

    def _calculate_signal_strength(self, indicators: List):
        """Calculate overall signal strength."""
        try:
            return np.mean([float(i) for i in indicators])
        except Exception as e:
            self.logger.error(f"Error calculating signal strength: {e}")
            return 0.0

    def _calculate_position_size(self, sizing_params: Dict, signal_strength: float):
        """Calculate position size based on parameters and signal strength."""
        try:
            base_size = sizing_params['base_size']
            max_size = sizing_params['max_size']
            
            size = base_size * (1 + signal_strength * sizing_params['strength_multiplier'])
            return min(size, max_size)
        except Exception as e:
            self.logger.error(f"Error calculating position size: {e}")
            return 0.0
