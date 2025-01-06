from web3 import Web3
import asyncio
import logging
from config import TRADING_CONFIG, PROFIT_CONFIG
import numpy as np
from datetime import datetime

class HybridStrategy:
    def __init__(self, w3_provider, trader, analyzer, gas_manager):
        self.w3 = w3_provider
        self.trader = trader
        self.analyzer = analyzer
        self.gas_manager = gas_manager
        self.logger = logging.getLogger(__name__)
        self.active_trades = {}
        self.trade_history = []

    async def evaluate_trade_opportunity(self, token_address, pair_address):
        """Evaluate trading opportunity using hybrid analysis."""
        try:
            # Gather all necessary metrics
            metrics = await asyncio.gather(
                self._analyze_market_conditions(token_address, pair_address),
                self._analyze_technical_indicators(pair_address),
                self._analyze_momentum_signals(pair_address),
                self._check_safety_metrics(token_address)
            )

            market_conditions, technical_indicators, momentum_signals, safety_metrics = metrics
            
            # Calculate composite score
            score = self._calculate_opportunity_score(
                market_conditions,
                technical_indicators,
                momentum_signals,
                safety_metrics
            )

            # Generate trade recommendation
            recommendation = self._generate_trade_recommendation(score, token_address)
            
            return {
                'score': score,
                'recommendation': recommendation,
                'metrics': {
                    'market_conditions': market_conditions,
                    'technical_indicators': technical_indicators,
                    'momentum_signals': momentum_signals,
                    'safety_metrics': safety_metrics
                }
            }
        except Exception as e:
            self.logger.error(f"Error evaluating trade opportunity: {e}")
            return None

    async def execute_trade_strategy(self, token_address, pair_address, recommendation):
        """Execute trading strategy based on recommendation."""
        try:
            if not recommendation['should_trade']:
                return {'success': False, 'reason': 'Trade not recommended'}

            # Determine position size
            position_size = self._calculate_position_size(
                recommendation['score'],
                recommendation['metrics']['safety_metrics']['score']
            )

            # Execute entry strategy
            if recommendation['action'] == 'buy':
                entry_result = await self._execute_entry_strategy(
                    token_address,
                    pair_address,
                    position_size,
                    recommendation['metrics']
                )
                
                if entry_result['success']:
                    self._track_trade(token_address, 'buy', position_size, entry_result)
                
                return entry_result

            # Execute exit strategy
            elif recommendation['action'] == 'sell':
                exit_result = await self._execute_exit_strategy(
                    token_address,
                    pair_address,
                    position_size,
                    recommendation['metrics']
                )
                
                if exit_result['success']:
                    self._track_trade(token_address, 'sell', position_size, exit_result)
                
                return exit_result

        except Exception as e:
            self.logger.error(f"Error executing trade strategy: {e}")
            return {'success': False, 'error': str(e)}

    async def _analyze_market_conditions(self, token_address, pair_address):
        """Analyze current market conditions."""
        try:
            volume_data = await self._get_volume_data(pair_address)
            liquidity_data = await self._get_liquidity_data(pair_address)
            
            analysis = {
                'volume_quality': self._analyze_volume_quality(volume_data),
                'liquidity_depth': self._analyze_liquidity_depth(liquidity_data),
                'buy_sell_pressure': self._analyze_buy_sell_pressure(volume_data),
                'market_impact': self._estimate_market_impact(liquidity_data)
            }
            
            return self._normalize_market_metrics(analysis)
        except Exception as e:
            self.logger.error(f"Error analyzing market conditions: {e}")
            return None

    async def _analyze_technical_indicators(self, pair_address):
        """Analyze technical indicators."""
        try:
            price_data = await self._get_price_data(pair_address)
            
            indicators = {
                'trend': self._analyze_trend(price_data),
                'momentum': self._analyze_momentum(price_data),
                'volatility': self._analyze_volatility(price_data),
                'support_resistance': self._analyze_support_resistance(price_data)
            }
            
            return self._normalize_technical_metrics(indicators)
        except Exception as e:
            self.logger.error(f"Error analyzing technical indicators: {e}")
            return None

    async def _analyze_momentum_signals(self, pair_address):
        """Analyze momentum and breakout signals."""
        try:
            price_data = await self._get_price_data(pair_address)
            volume_data = await self._get_volume_data(pair_address)
            
            signals = {
                'price_momentum': self._calculate_price_momentum(price_data),
                'volume_momentum': self._calculate_volume_momentum(volume_data),
                'breakout_signals': self._detect_breakout_signals(price_data, volume_data),
                'reversal_signals': self._detect_reversal_signals(price_data)
            }
            
            return self._normalize_momentum_signals(signals)
        except Exception as e:
            self.logger.error(f"Error analyzing momentum signals: {e}")
            return None

    async def _check_safety_metrics(self, token_address):
        """Check safety and risk metrics."""
        try:
            contract_analysis = await self.analyzer.analyze_contract(token_address)
            
            metrics = {
                'contract_safety': contract_analysis['score'],
                'liquidity_safety': await self._analyze_liquidity_safety(token_address),
                'holder_distribution': await self._analyze_holder_distribution(token_address),
                'trading_risks': await self._analyze_trading_risks(token_address)
            }
            
            return self._normalize_safety_metrics(metrics)
        except Exception as e:
            self.logger.error(f"Error checking safety metrics: {e}")
            return None

    def _calculate_opportunity_score(self, market_conditions, technical_indicators, 
                                  momentum_signals, safety_metrics):
        """Calculate overall opportunity score."""
        try:
            weights = {
                'market_conditions': 0.3,
                'technical_indicators': 0.25,
                'momentum_signals': 0.25,
                'safety_metrics': 0.2
            }
            
            scores = {
                'market_conditions': self._aggregate_metrics(market_conditions),
                'technical_indicators': self._aggregate_metrics(technical_indicators),
                'momentum_signals': self._aggregate_metrics(momentum_signals),
                'safety_metrics': self._aggregate_metrics(safety_metrics)
            }
            
            weighted_score = sum(scores[k] * weights[k] for k in weights)
            return round(weighted_score * 100, 2)
        except Exception as e:
            self.logger.error(f"Error calculating opportunity score: {e}")
            return 0

    def _generate_trade_recommendation(self, score, token_address):
        """Generate trade recommendation based on analysis."""
        try:
            min_score = TRADING_CONFIG['entry_rules']['min_weighted_score']
            
            recommendation = {
                'should_trade': score >= min_score,
                'score': score,
                'action': 'buy' if score >= min_score else 'hold',
                'confidence': score / 100,
                'timestamp': datetime.now().isoformat()
            }
            
            if token_address in self.active_trades:
                # Adjust for exit conditions
                trade_data = self.active_trades[token_address]
                if self._should_exit_trade(trade_data, score):
                    recommendation['action'] = 'sell'
                    recommendation['should_trade'] = True
            
            return recommendation
        except Exception as e:
            self.logger.error(f"Error generating trade recommendation: {e}")
            return {'should_trade': False, 'action': 'hold', 'score': 0}

    def _calculate_position_size(self, opportunity_score, safety_score):
        """Calculate optimal position size based on scores."""
        try:
            base_size = TRADING_CONFIG['position_sizing']['base_size']
            
            # Get safety multiplier
            safety_multipliers = TRADING_CONFIG['position_sizing']['safety_multipliers']
            safety_mult = next((v for k, v in sorted(safety_multipliers.items(), reverse=True)
                              if safety_score >= k), safety_multipliers[0])
            
            # Adjust for opportunity quality
            opportunity_mult = min(opportunity_score / 100, 1)
            
            return base_size * safety_mult * opportunity_mult
        except Exception as e:
            self.logger.error(f"Error calculating position size: {e}")
            return TRADING_CONFIG['position_sizing']['base_size'] * 0.4  # Conservative fallback

    async def _execute_entry_strategy(self, token_address, pair_address, position_size, metrics):
        """Execute entry strategy with optimal timing."""
        try:
            # Check gas conditions
            gas_info = await self.gas_manager.get_optimal_gas()
            if gas_info['is_high']:
                await self.gas_manager.wait_for_better_gas()
            
            # Execute buy with calculated parameters
            entry_params = self._calculate_entry_parameters(position_size, metrics)
            
            # Convert to new parameter format
            amount_in_wei = self.w3.to_wei(entry_params['amount'], 'ether')
            max_slippage = TRADING_CONFIG['max_slippage']
            
            result = await self.trader.buy_token(
                token_address,
                amount_in_wei,  # Second parameter is now amount_in_wei
                max_slippage    # Third parameter is now max_slippage
            )
            
            if result and result.get('success'):
                self._update_trade_tracking(token_address, 'entry', entry_params, result)
            
            return result
        except Exception as e:
            self.logger.error(f"Error executing entry strategy: {e}")
            return {'success': False, 'error': str(e)}

    async def _execute_exit_strategy(self, token_address, pair_address, position_size, metrics):
        """Execute exit strategy with optimal timing."""
        try:
            # Check if we should scale out
            scale_out = self._should_scale_out(token_address)
            exit_amount = self._calculate_exit_amount(token_address, scale_out)
            
            # Execute sell with calculated parameters
            exit_params = self._calculate_exit_parameters(exit_amount, metrics)
            
            result = await self.trader.sell_token(
                token_address,
                pair_address,
                exit_params['amount']
            )
            
            if result and result.get('success'):
                self._update_trade_tracking(token_address, 'exit', exit_params, result)
            
            return result
        except Exception as e:
            self.logger.error(f"Error executing exit strategy: {e}")
            return {'success': False, 'error': str(e)}

    def _track_trade(self, token_address, action, amount, result):
        """Track trade for position management."""
        try:
            trade_data = {
                'token_address': token_address,
                'action': action,
                'amount': amount,
                'timestamp': datetime.now().isoformat(),
                'transaction_hash': result.get('transaction_hash'),
                'price': result.get('price'),
                'gas_used': result.get('gas_used')
            }
            
            self.trade_history.append(trade_data)
            
            if action == 'buy':
                self.active_trades[token_address] = trade_data
            elif action == 'sell':
                if token_address in self.active_trades:
                    del self.active_trades[token_address]
        except Exception as e:
            self.logger.error(f"Error tracking trade: {e}")

    def _aggregate_metrics(self, metrics):
        """Aggregate metrics into a single score."""
        if not metrics:
            return 0
        return np.mean(list(metrics.values()))
