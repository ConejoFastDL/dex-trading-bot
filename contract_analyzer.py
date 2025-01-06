from web3 import Web3
import json
import aiohttp
import logging
from config import SAFETY_CONFIG, API_KEYS
import asyncio

class ContractAnalyzer:
    def __init__(self, w3_provider):
        self.w3 = w3_provider
        self.logger = logging.getLogger(__name__)
        self.verified_contracts = set()
        self.contract_cache = {}

    async def analyze_contract(self, token_address):
        """Analyze contract for security and functionality."""
        try:
            contract_data = await self._get_contract_data(token_address)
            if not contract_data:
                return {'is_safe': False, 'score': 0, 'warnings': ['Contract not verified']}

            analysis = {
                'verification': await self._check_verification(token_address),
                'code_analysis': await self._analyze_code(contract_data),
                'ownership': await self._check_ownership(contract_data),
                'functions': await self._analyze_functions(contract_data),
                'security': await self._check_security_features(contract_data)
            }

            score = self._calculate_safety_score(analysis)
            warnings = self._generate_warnings(analysis)

            return {
                'is_safe': score >= SAFETY_CONFIG['contract']['min_safety_score'],
                'score': score,
                'warnings': warnings
            }
        except Exception as e:
            self.logger.error(f"Error analyzing contract: {e}")
            return {'is_safe': False, 'score': 0, 'warnings': [str(e)]}

    async def _get_contract_data(self, token_address):
        """Fetch contract data from blockchain explorer."""
        try:
            if token_address in self.contract_cache:
                return self.contract_cache[token_address]

            async with aiohttp.ClientSession() as session:
                params = {
                    'address': token_address,
                    'apikey': API_KEYS['bscscan_api_key']
                }
                async with session.get('https://api.bscscan.com/api', params=params) as response:
                    data = await response.json()
                    if data['status'] == '1':
                        self.contract_cache[token_address] = data['result']
                        return data['result']
            return None
        except Exception as e:
            self.logger.error(f"Error fetching contract data: {e}")
            return None

    async def _check_verification(self, token_address):
        """Check if contract is verified."""
        try:
            if token_address in self.verified_contracts:
                return True

            contract_data = await self._get_contract_data(token_address)
            is_verified = contract_data is not None and 'SourceCode' in contract_data
            
            if is_verified:
                self.verified_contracts.add(token_address)
            
            return is_verified
        except Exception as e:
            self.logger.error(f"Error checking verification: {e}")
            return False

    async def _analyze_code(self, contract_data):
        """Analyze contract source code for vulnerabilities."""
        try:
            source_code = contract_data.get('SourceCode', '')
            if not source_code:
                return {'score': 0, 'issues': ['No source code available']}

            issues = []
            score = 100

            # Check for known vulnerability patterns
            vulnerability_patterns = {
                'selfdestruct': 10,
                'delegatecall': 5,
                'transfer.call': 5,
                'tx.origin': 8,
                'assembly': 3
            }

            for pattern, penalty in vulnerability_patterns.items():
                if pattern in source_code.lower():
                    issues.append(f'Found potentially dangerous pattern: {pattern}')
                    score -= penalty

            # Check for proper SafeMath usage
            if 'using SafeMath' not in source_code and 'pragma solidity ^0.8' not in source_code:
                issues.append('No SafeMath usage detected')
                score -= 10

            return {
                'score': max(0, score),
                'issues': issues
            }
        except Exception as e:
            self.logger.error(f"Error analyzing code: {e}")
            return {'score': 0, 'issues': [str(e)]}

    async def _check_ownership(self, contract_data):
        """Check contract ownership patterns."""
        try:
            source_code = contract_data.get('SourceCode', '')
            if not source_code:
                return {'is_safe': False, 'issues': ['No source code available']}

            issues = []
            is_safe = True

            # Check for ownership patterns
            ownership_patterns = {
                'onlyOwner': 'Owner-only functions found',
                'transferOwnership': 'Ownership transfer capability found',
                'renounceOwnership': 'Ownership renouncement capability found'
            }

            for pattern, warning in ownership_patterns.items():
                if pattern in source_code:
                    issues.append(warning)
                    is_safe = is_safe and pattern == 'renounceOwnership'

            return {
                'is_safe': is_safe,
                'issues': issues
            }
        except Exception as e:
            self.logger.error(f"Error checking ownership: {e}")
            return {'is_safe': False, 'issues': [str(e)]}

    async def _analyze_functions(self, contract_data):
        """Analyze contract functions for security concerns."""
        try:
            source_code = contract_data.get('SourceCode', '')
            if not source_code:
                return {'score': 0, 'issues': ['No source code available']}

            issues = []
            score = 100

            # Check for required functions
            for required_func in SAFETY_CONFIG['contract']['required_functions']:
                if required_func not in source_code:
                    issues.append(f'Missing required function: {required_func}')
                    score -= 20

            # Check for banned functions
            for banned_func in SAFETY_CONFIG['contract']['banned_functions']:
                if banned_func in source_code:
                    issues.append(f'Found banned function: {banned_func}')
                    score -= 30

            return {
                'score': max(0, score),
                'issues': issues
            }
        except Exception as e:
            self.logger.error(f"Error analyzing functions: {e}")
            return {'score': 0, 'issues': [str(e)]}

    async def _check_security_features(self, contract_data):
        """Check implementation of security features."""
        try:
            source_code = contract_data.get('SourceCode', '')
            if not source_code:
                return {'score': 0, 'issues': ['No source code available']}

            issues = []
            score = 100

            # Check for security features
            security_features = {
                'ReentrancyGuard': 'No reentrancy protection',
                'pausable': 'No pause functionality',
                'require(': 'Limited input validation',
                'assert(': 'Limited invariant checking'
            }

            for feature, warning in security_features.items():
                if feature not in source_code:
                    issues.append(warning)
                    score -= 15

            return {
                'score': max(0, score),
                'issues': issues
            }
        except Exception as e:
            self.logger.error(f"Error checking security features: {e}")
            return {'score': 0, 'issues': [str(e)]}

    def _calculate_safety_score(self, analysis):
        """Calculate overall contract safety score."""
        try:
            weights = {
                'verification': 20,
                'code_analysis': 25,
                'ownership': 20,
                'functions': 20,
                'security': 15
            }

            scores = {
                'verification': 100 if analysis['verification'] else 0,
                'code_analysis': analysis['code_analysis']['score'],
                'ownership': 100 if analysis['ownership']['is_safe'] else 50,
                'functions': analysis['functions']['score'],
                'security': analysis['security']['score']
            }

            weighted_score = sum(scores[k] * weights[k] / 100 for k in weights)
            return round(weighted_score, 2)
        except Exception as e:
            self.logger.error(f"Error calculating safety score: {e}")
            return 0

    def _generate_warnings(self, analysis):
        """Generate warning messages from analysis results."""
        try:
            warnings = []
            
            if not analysis['verification']:
                warnings.append('Contract is not verified')
            
            warnings.extend(analysis['code_analysis']['issues'])
            warnings.extend(analysis['ownership']['issues'])
            warnings.extend(analysis['functions']['issues'])
            warnings.extend(analysis['security']['issues'])
            
            return warnings
        except Exception as e:
            self.logger.error(f"Error generating warnings: {e}")
            return [str(e)]
