from web3 import Web3
import asyncio
import logging
from datetime import datetime, timedelta
from config import TRADING_CONFIG, SAFETY_CONFIG
import numpy as np

class RiskManager:
    def __init__(self, w3_provider, contract_analyzer):
        self.w3 = w3_provider
        self.contract_analyzer = contract_analyzer
        self.logger = logging.getLogger(__name__)
        self.risk_assessments = {}
        self.position_risks = {}
        self.portfolio_metrics = {
            'total_value': 0,
            'risk_exposure': 0,
            'max_drawdown': 0
        }

    async def assess_trade_risk(self, token_address, pair_address, amount):
        """Assess overall risk for a potential trade."""
        try:
            risk_factors = await asyncio.gather(
                self._assess_token_risk(token_address),
                self._assess_market_risk(pair_address),
                self._assess_position_risk(amount),
                self._assess_portfolio_risk()
            )

            token_risk, market_risk, position_risk, portfolio_risk = risk_factors
            
            # Calculate composite risk score
            risk_score = self._calculate_risk_score(risk_factors)
            
            # Generate risk assessment report
            assessment = {
                'risk_score': risk_score,
                'is_acceptable': risk_score <= TRADING_CONFIG['max_risk_score'],
                'factors': {
                    'token_risk': token_risk,
                    'market_risk': market_risk,
                    'position_risk': position_risk,
                    'portfolio_risk': portfolio_risk
                },
                'warnings': self._generate_risk_warnings(risk_factors),
                'timestamp': datetime.now().isoformat()
            }
            
            self.risk_assessments[token_address] = assessment
            return assessment
        except Exception as e:
            self.logger.error(f"Error assessing trade risk: {e}")
            return None

    async def monitor_position_risk(self, token_address, position_data):
        """Monitor risk for an active position."""
        try:
            current_risk = await self._calculate_position_risk(token_address, position_data)
            
            # Update position risk tracking
            self.position_risks[token_address] = {
                'current_risk': current_risk,
                'risk_history': self._update_risk_history(token_address, current_risk),
                'warnings': self._check_risk_thresholds(current_risk),
                'last_updated': datetime.now().isoformat()
            }
            
            return self.position_risks[token_address]
        except Exception as e:
            self.logger.error(f"Error monitoring position risk: {e}")
            return None

    async def check_portfolio_risk(self):
        """Check overall portfolio risk levels."""
        try:
            metrics = {
                'total_value': await self._calculate_portfolio_value(),
                'risk_exposure': self._calculate_risk_exposure(),
                'max_drawdown': self._calculate_max_drawdown(),
                'risk_distribution': self._analyze_risk_distribution(),
                'concentration_risk': self._analyze_concentration_risk()
            }
            
            self.portfolio_metrics = metrics
            return metrics
        except Exception as e:
            self.logger.error(f"Error checking portfolio risk: {e}")
            return None

    async def _assess_token_risk(self, token_address):
        """Assess token-specific risks."""
        try:
            contract_analysis = await self.contract_analyzer.analyze_contract(token_address)
            
            risk_factors = {
                'contract_risk': 1 - (contract_analysis['score'] / 100),
                'holder_risk': await self._analyze_holder_risk(token_address),
                'liquidity_risk': await self._analyze_liquidity_risk(token_address),
                'age_risk': await self._analyze_token_age_risk(token_address)
            }
            
            return self._normalize_risk_factors(risk_factors)
        except Exception as e:
            self.logger.error(f"Error assessing token risk: {e}")
            return 1.0  # Maximum risk on error

    async def _assess_market_risk(self, pair_address):
        """Assess market-related risks."""
        try:
            risk_factors = {
                'volatility_risk': await self._analyze_volatility_risk(pair_address),
                'liquidity_risk': await self._analyze_market_liquidity_risk(pair_address),
                'momentum_risk': await self._analyze_momentum_risk(pair_address),
                'correlation_risk': await self._analyze_correlation_risk(pair_address)
            }
            
            return self._normalize_risk_factors(risk_factors)
        except Exception as e:
            self.logger.error(f"Error assessing market risk: {e}")
            return 1.0

    async def _assess_position_risk(self, amount):
        """Assess position-specific risks."""
        try:
            risk_factors = {
                'size_risk': self._calculate_size_risk(amount),
                'concentration_risk': self._calculate_concentration_risk(amount),
                'exposure_risk': self._calculate_exposure_risk(amount),
                'timing_risk': await self._analyze_timing_risk()
            }
            
            return self._normalize_risk_factors(risk_factors)
        except Exception as e:
            self.logger.error(f"Error assessing position risk: {e}")
            return 1.0

    async def _assess_portfolio_risk(self):
        """Assess portfolio-wide risks."""
        try:
            risk_factors = {
                'diversification_risk': self._calculate_diversification_risk(),
                'correlation_risk': self._calculate_portfolio_correlation_risk(),
                'drawdown_risk': self._calculate_drawdown_risk(),
                'exposure_risk': self._calculate_total_exposure_risk()
            }
            
            return self._normalize_risk_factors(risk_factors)
        except Exception as e:
            self.logger.error(f"Error assessing portfolio risk: {e}")
            return 1.0

    def _calculate_risk_score(self, risk_factors):
        """Calculate composite risk score."""
        try:
            weights = {
                'token_risk': 0.3,
                'market_risk': 0.25,
                'position_risk': 0.25,
                'portfolio_risk': 0.2
            }
            
            weighted_risks = [risk * weights[factor] 
                            for factor, risk in zip(['token_risk', 'market_risk', 
                                                   'position_risk', 'portfolio_risk'], 
                                                  risk_factors)]
            
            return sum(weighted_risks)
        except Exception as e:
            self.logger.error(f"Error calculating risk score: {e}")
            return 1.0

    async def _calculate_position_risk(self, token_address, position_data):
        """Calculate current risk level for a position."""
        try:
            risk_factors = {
                'pnl_risk': self._calculate_pnl_risk(position_data),
                'duration_risk': self._calculate_duration_risk(position_data),
                'market_risk': await self._assess_market_risk(position_data['pair_address']),
                'liquidity_risk': await self._analyze_exit_liquidity(token_address)
            }
            
            return self._normalize_risk_factors(risk_factors)
        except Exception as e:
            self.logger.error(f"Error calculating position risk: {e}")
            return 1.0

    def _update_risk_history(self, token_address, current_risk):
        """Update risk history for a position."""
        try:
            history = self.position_risks.get(token_address, {}).get('risk_history', [])
            
            history.append({
                'timestamp': datetime.now().isoformat(),
                'risk_level': current_risk
            })
            
            # Keep only recent history (last 24 hours)
            cutoff = datetime.now() - timedelta(hours=24)
            history = [
                entry for entry in history
                if datetime.fromisoformat(entry['timestamp']) > cutoff
            ]
            
            return history
        except Exception as e:
            self.logger.error(f"Error updating risk history: {e}")
            return []

    def _check_risk_thresholds(self, risk_level):
        """Check if risk level exceeds thresholds."""
        try:
            warnings = []
            
            thresholds = {
                'critical': 0.8,
                'high': 0.7,
                'medium': 0.5
            }
            
            for level, threshold in thresholds.items():
                if risk_level >= threshold:
                    warnings.append(f"{level.capitalize()} risk level detected: {risk_level:.2f}")
            
            return warnings
        except Exception as e:
            self.logger.error(f"Error checking risk thresholds: {e}")
            return ["Error checking risk thresholds"]

    def _normalize_risk_factors(self, factors):
        """Normalize risk factors to 0-1 scale."""
        try:
            values = list(factors.values())
            return np.mean(values)
        except Exception as e:
            self.logger.error(f"Error normalizing risk factors: {e}")
            return 1.0

    def _generate_risk_warnings(self, risk_factors):
        """Generate warning messages based on risk factors."""
        try:
            warnings = []
            
            risk_thresholds = {
                'token_risk': 0.7,
                'market_risk': 0.7,
                'position_risk': 0.6,
                'portfolio_risk': 0.6
            }
            
            for factor, risk in zip(['token_risk', 'market_risk', 
                                   'position_risk', 'portfolio_risk'], 
                                  risk_factors):
                if risk >= risk_thresholds[factor]:
                    warnings.append(f"High {factor.replace('_', ' ')}: {risk:.2f}")
            
            return warnings
        except Exception as e:
            self.logger.error(f"Error generating risk warnings: {e}")
            return ["Error generating risk warnings"]

    async def _analyze_holder_risk(self, token_address):
        """Analyze token holder distribution risk."""
        # Implement holder analysis
        pass

    async def _analyze_liquidity_risk(self, token_address):
        """Analyze token liquidity risk."""
        # Implement liquidity analysis
        pass

    async def _analyze_token_age_risk(self, token_address):
        """Analyze risk based on token age."""
        # Implement age analysis
        pass

    async def _analyze_volatility_risk(self, pair_address):
        """Analyze price volatility risk."""
        # Implement volatility analysis
        pass

    async def _analyze_momentum_risk(self, pair_address):
        """Analyze price momentum risk."""
        # Implement momentum analysis
        pass
