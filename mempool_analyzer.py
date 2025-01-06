from web3 import Web3
import asyncio
import logging
from datetime import datetime, timedelta
import numpy as np
from collections import defaultdict

class MempoolAnalyzer:
    def __init__(self, w3_provider):
        self.w3 = w3_provider
        self.logger = logging.getLogger(__name__)
        self.pending_transactions = {}
        self.transaction_patterns = defaultdict(list)
        self.suspicious_addresses = set()
        self.last_block = None
        self.monitoring = False

    async def start_monitoring(self):
        """Start monitoring the mempool."""
        try:
            if self.monitoring:
                return
            
            self.monitoring = True
            self.last_block = self.w3.eth.block_number
            
            while self.monitoring:
                await self._process_new_transactions()
                await asyncio.sleep(0.1)  # Small delay to prevent high CPU usage
        except Exception as e:
            self.logger.error(f"Error starting mempool monitoring: {e}")
            self.monitoring = False

    async def stop_monitoring(self):
        """Stop monitoring the mempool."""
        self.monitoring = False

    async def analyze_transaction(self, tx_hash):
        """Analyze a specific transaction in the mempool."""
        try:
            tx = await self._get_transaction(tx_hash)
            if not tx:
                return None

            analysis = {
                'basic_info': self._get_basic_info(tx),
                'patterns': await self._analyze_patterns(tx),
                'risk_assessment': await self._assess_risks(tx),
                'gas_analysis': self._analyze_gas(tx),
                'related_transactions': await self._find_related_transactions(tx)
            }

            return analysis
        except Exception as e:
            self.logger.error(f"Error analyzing transaction: {e}")
            return None

    async def _process_new_transactions(self):
        """Process new transactions in the mempool."""
        try:
            current_block = self.w3.eth.block_number
            if current_block > self.last_block:
                # Process new block
                block = self.w3.eth.get_block(current_block, full_transactions=True)
                await self._analyze_block_transactions(block)
                self.last_block = current_block

            # Get pending transactions
            pending = self.w3.eth.get_block('pending', full_transactions=True)
            if pending and pending.transactions:
                for tx in pending.transactions:
                    if tx.hash not in self.pending_transactions:
                        await self._process_transaction(tx)
        except Exception as e:
            self.logger.error(f"Error processing new transactions: {e}")

    async def _process_transaction(self, transaction):
        """Process and analyze a single transaction."""
        try:
            tx_hash = transaction.hash
            
            # Basic analysis
            analysis = {
                'timestamp': datetime.now(),
                'basic_info': self._get_basic_info(transaction),
                'patterns': await self._analyze_patterns(transaction),
                'risk_level': await self._assess_risks(transaction)
            }
            
            self.pending_transactions[tx_hash] = analysis
            
            # Check for suspicious patterns
            if analysis['risk_level'] > 0.7:  # High risk threshold
                self.suspicious_addresses.add(transaction['from'])
                await self._alert_suspicious_activity(tx_hash, analysis)
            
            # Update transaction patterns
            self._update_transaction_patterns(transaction)
            
            return analysis
        except Exception as e:
            self.logger.error(f"Error processing transaction: {e}")
            return None

    async def _analyze_block_transactions(self, block):
        """Analyze transactions in a new block."""
        try:
            block_patterns = defaultdict(list)
            
            for tx in block.transactions:
                # Remove from pending if present
                self.pending_transactions.pop(tx.hash, None)
                
                # Analyze transaction patterns
                patterns = await self._analyze_patterns(tx)
                if patterns:
                    for pattern in patterns:
                        block_patterns[pattern].append(tx.hash)
            
            # Detect block-level patterns
            if block_patterns:
                await self._analyze_block_patterns(block_patterns, block.number)
        except Exception as e:
            self.logger.error(f"Error analyzing block transactions: {e}")

    def _get_basic_info(self, transaction):
        """Get basic transaction information."""
        try:
            return {
                'hash': transaction.hash.hex(),
                'from': transaction['from'],
                'to': transaction['to'],
                'value': transaction.value,
                'gas_price': transaction.gasPrice,
                'nonce': transaction.nonce
            }
        except Exception as e:
            self.logger.error(f"Error getting basic transaction info: {e}")
            return {}

    async def _analyze_patterns(self, transaction):
        """Analyze transaction for known patterns."""
        try:
            patterns = []
            
            # Check for sandwich attack pattern
            if await self._check_sandwich_pattern(transaction):
                patterns.append('sandwich_attack')
            
            # Check for front-running pattern
            if await self._check_frontrunning_pattern(transaction):
                patterns.append('frontrunning')
            
            # Check for arbitrage pattern
            if await self._check_arbitrage_pattern(transaction):
                patterns.append('arbitrage')
            
            return patterns
        except Exception as e:
            self.logger.error(f"Error analyzing patterns: {e}")
            return []

    async def _assess_risks(self, transaction):
        """Assess transaction risks."""
        try:
            risk_factors = {
                'address_reputation': await self._check_address_reputation(transaction['from']),
                'contract_interaction': await self._analyze_contract_interaction(transaction),
                'value_risk': self._assess_value_risk(transaction),
                'gas_risk': self._assess_gas_risk(transaction)
            }
            
            # Calculate weighted risk score
            weights = {
                'address_reputation': 0.3,
                'contract_interaction': 0.3,
                'value_risk': 0.2,
                'gas_risk': 0.2
            }
            
            risk_score = sum(score * weights[factor] 
                           for factor, score in risk_factors.items())
            
            return risk_score
        except Exception as e:
            self.logger.error(f"Error assessing risks: {e}")
            return 1.0  # Return maximum risk on error

    def _analyze_gas(self, transaction):
        """Analyze gas parameters of the transaction."""
        try:
            return {
                'gas_price': transaction.gasPrice,
                'gas_limit': transaction.gas,
                'estimated_cost': transaction.gasPrice * transaction.gas,
                'is_high_priority': self._is_high_priority_transaction(transaction)
            }
        except Exception as e:
            self.logger.error(f"Error analyzing gas: {e}")
            return {}

    async def _find_related_transactions(self, transaction):
        """Find transactions related to the given transaction."""
        try:
            related = []
            
            # Check recent transactions from same address
            for tx_hash, tx_data in self.pending_transactions.items():
                if tx_data['basic_info']['from'] == transaction['from']:
                    related.append(tx_hash)
                
                # Check for interactions with same contract
                if tx_data['basic_info']['to'] == transaction['to']:
                    related.append(tx_hash)
            
            return related
        except Exception as e:
            self.logger.error(f"Error finding related transactions: {e}")
            return []

    async def _check_sandwich_pattern(self, transaction):
        """Check for sandwich attack pattern."""
        try:
            # Look for buy before and sell after pattern
            recent_txs = self._get_recent_transactions(transaction['to'])
            
            if len(recent_txs) < 3:
                return False
            
            # Check for buy-target-sell pattern
            return self._match_sandwich_pattern(recent_txs, transaction)
        except Exception as e:
            self.logger.error(f"Error checking sandwich pattern: {e}")
            return False

    async def _check_frontrunning_pattern(self, transaction):
        """Check for front-running pattern."""
        try:
            # Compare gas price with pending transactions
            pending_gas_prices = [tx['gasPrice'] for tx in self.pending_transactions.values()]
            if not pending_gas_prices:
                return False
            
            avg_gas_price = np.mean(pending_gas_prices)
            return transaction.gasPrice > (avg_gas_price * 1.5)  # 50% higher than average
        except Exception as e:
            self.logger.error(f"Error checking frontrunning pattern: {e}")
            return False

    def _update_transaction_patterns(self, transaction):
        """Update tracked transaction patterns."""
        try:
            address = transaction['from']
            self.transaction_patterns[address].append({
                'timestamp': datetime.now(),
                'hash': transaction.hash.hex(),
                'type': self._determine_transaction_type(transaction)
            })
            
            # Keep only recent patterns (last hour)
            cutoff = datetime.now() - timedelta(hours=1)
            self.transaction_patterns[address] = [
                pattern for pattern in self.transaction_patterns[address]
                if pattern['timestamp'] > cutoff
            ]
        except Exception as e:
            self.logger.error(f"Error updating transaction patterns: {e}")

    async def _alert_suspicious_activity(self, tx_hash, analysis):
        """Alert about suspicious activity."""
        try:
            alert = {
                'timestamp': datetime.now().isoformat(),
                'transaction': tx_hash,
                'risk_level': analysis['risk_level'],
                'patterns': analysis['patterns'],
                'address': analysis['basic_info']['from']
            }
            
            self.logger.warning(f"Suspicious activity detected: {alert}")
            # Implement additional alert mechanisms as needed
        except Exception as e:
            self.logger.error(f"Error alerting suspicious activity: {e}")

    def _determine_transaction_type(self, transaction):
        """Determine the type of transaction."""
        try:
            if not transaction['to']:
                return 'contract_creation'
            elif transaction.input and len(transaction.input) > 2:
                return 'contract_interaction'
            else:
                return 'transfer'
        except Exception as e:
            self.logger.error(f"Error determining transaction type: {e}")
            return 'unknown'
