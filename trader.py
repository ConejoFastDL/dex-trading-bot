import logging
from web3 import Web3
from eth_account import Account
import json
import os
from config import TRADING_CONFIG, NETWORK
from token_manager import TokenManager
import asyncio
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/bot.log'),
        logging.StreamHandler()
    ]
)

class DexTrader:
    def __init__(self, chain='ethereum'):
        self.chain = chain
        self.active_trades = []
        self.trading_pairs = {}
        
        # Initialize Web3 with default RPC
        try:
            if not NETWORK[chain].get('rpc_url'):
                raise ValueError(f"No RPC URL configured for chain {chain}")
            self.w3 = Web3(Web3.HTTPProvider(NETWORK[chain]['rpc_url']))
            if not self.w3.is_connected():
                raise ConnectionError("Could not connect to RPC")
        except Exception as e:
            logging.error(f"Error connecting to RPC: {e}")
            raise
            
        # Load private key and create account
        private_key = os.getenv('PRIVATE_KEY')
        if not private_key:
            raise ValueError("PRIVATE_KEY not found in environment variables")
        self.account = Account.from_key(private_key)
        logging.info(f"Initialized wallet: {self.account.address}")
        
        self.router_address = NETWORK[chain].get('router')
        
        # Initialize managers
        self.token_manager = TokenManager()
        
        # Load standard DEX ABI (e.g., Uniswap V2 Router)
        self.router_abi = self._load_router_abi()
        self.token_abi = self._load_token_abi()

    def get_gas_price(self):
        """Get current gas price in Wei."""
        return self.w3.eth.gas_price

    def get_balance(self, address):
        """Get balance for address in Wei."""
        return self.w3.eth.get_balance(address)

    def _load_router_abi(self):
        """Load DEX router ABI."""
        router_abi = [
            {
                "inputs": [
                    {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                    {"internalType": "address[]", "name": "path", "type": "address[]"}
                ],
                "name": "swapExactETHForTokens",
                "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
                "stateMutability": "payable",
                "type": "function"
            },
            {
                "inputs": [
                    {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                    {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
                    {"internalType": "address[]", "name": "path", "type": "address[]"},
                    {"internalType": "address", "name": "to", "type": "address"},
                    {"internalType": "uint256", "name": "deadline", "type": "uint256"}
                ],
                "name": "swapExactTokensForETH",
                "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ]
        return router_abi

    def _load_token_abi(self):
        """Load standard ERC20 token ABI."""
        token_abi = [
            {
                "constant": True,
                "inputs": [],
                "name": "decimals",
                "outputs": [{"name": "", "type": "uint8"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function"
            },
            {
                "constant": False,
                "inputs": [
                    {"name": "_spender", "type": "address"},
                    {"name": "_value", "type": "uint256"}
                ],
                "name": "approve",
                "outputs": [{"name": "", "type": "bool"}],
                "type": "function"
            }
        ]
        return token_abi

    def get_token_price(self, token_address):
        """Get current token price in USD."""
        try:
            # Get price from DexScreener API
            pair_data = self.token_manager.get_pair_data(token_address)
            if pair_data and 'priceUsd' in pair_data:
                return float(pair_data['priceUsd'])
            return None
        except Exception as e:
            logging.error(f"Error getting token price: {e}")
            return None

    async def get_eth_price(self):
        """Get current ETH price in USD."""
        try:
            # Get ETH/USD price from DexScreener
            eth_price = await self.token_manager.get_eth_price()
            return float(eth_price)
        except Exception as e:
            logging.error(f"Error getting ETH price: {e}")
            return None

    async def get_trending_pairs(self):
        """Get trending pairs from DexScreener."""
        try:
            return await self.token_manager.get_trending_pairs()
        except Exception as e:
            logging.error(f"Error getting trending pairs: {e}")
            return []

    def is_token_in_active_trades(self, token_address):
        """Check if token is in active trades."""
        return token_address.lower() in [t['token_address'].lower() for t in self.active_trades]

    def get_active_trades(self):
        """Get list of active trades."""
        return self.active_trades

    async def set_take_profit(self, token_address, take_profit_percent, trailing=False, trailing_distance=None):
        """Set take profit order for a token."""
        token_address = token_address.lower()
        for trade in self.active_trades:
            if trade['token_address'].lower() == token_address:
                trade['take_profit'] = take_profit_percent
                trade['trailing_stop'] = trailing
                trade['trailing_distance'] = trailing_distance
                trade['highest_price'] = await self.get_token_price(token_address)
                break

    async def set_stop_loss(self, token_address, stop_loss_percent):
        """Set stop loss order for a token."""
        token_address = token_address.lower()
        for trade in self.active_trades:
            if trade['token_address'].lower() == token_address:
                trade['stop_loss'] = stop_loss_percent
                break

    def buy_token(self, token_address, pair_address=None, amount=None, max_slippage=None):
        """
        Execute token purchase. Supports both legacy and new async trading.
        
        Legacy mode: buy_token(token_address, pair_address, amount)
        New mode: buy_token(token_address, amount_in_wei, max_slippage)
        """
        # Detect which version is being called based on arguments
        if pair_address is not None and isinstance(pair_address, str):
            # Legacy version
            return self._buy_token_legacy(token_address, pair_address, amount)
        else:
            # New version (async)
            amount_in_wei = pair_address  # In new version, second arg is amount_in_wei
            return asyncio.run(self._buy_token_async(token_address, amount_in_wei, amount))  # amount is max_slippage in new version
            
    def _buy_token_legacy(self, token_address, pair_address, amount):
        """Legacy synchronous token purchase method."""
        try:
            # Get token contract
            token_contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=self.token_abi
            )
            
            # Get router contract
            router_contract = self.w3.eth.contract(
                address=self.router_address,
                abi=self.router_abi
            )
            
            # Calculate minimum tokens to receive (using default slippage)
            min_tokens = self._calculate_min_tokens(amount, token_contract, TRADING_CONFIG['max_slippage'])
            
            # Build transaction
            nonce = self.w3.eth.get_transaction_count(self.account.address)
            gas_price = self._get_optimal_gas_price()
            
            # Add swap function call data
            deadline = self.w3.eth.get_block('latest')['timestamp'] + 300  # 5 minutes
            
            # Get the path for the swap (ETH -> Token)
            path = [NETWORK['ethereum']['weth'], token_address]
            
            # Create transaction
            transaction = router_contract.functions.swapExactETHForTokens(
                min_tokens,  # Minimum tokens to receive
                path,        # Swap path
                self.account.address,  # Recipient
                deadline    # Transaction deadline
            ).build_transaction({
                'from': self.account.address,
                'value': amount,  # Amount of ETH to swap
                'gas': TRADING_CONFIG['gas_limit'],
                'gasPrice': gas_price,
                'nonce': nonce
            })
            
            # Sign and send transaction
            signed_txn = self.w3.eth.account.sign_transaction(transaction, self.account.key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            # Wait for transaction confirmation
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt['status'] == 1:
                return {
                    'success': True,
                    'receipt': receipt,
                    'amount': amount
                }
            else:
                return {
                    'success': False,
                    'error': 'Transaction failed'
                }
                
        except Exception as e:
            logging.error(f"Error in legacy buy: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def _buy_token_async(self, token_address, amount_in_wei, max_slippage):
        """Async token purchase with improved error handling and slippage protection."""
        try:
            # Get token contract
            token_contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=self.token_abi
            )
            
            # Get router contract
            router_contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(self.router_address),
                abi=self.router_abi
            )
            
            # Calculate minimum tokens to receive based on slippage
            min_tokens = self._calculate_min_tokens(amount_in_wei, token_contract, max_slippage)
            
            # Build transaction
            tx = await self._build_buy_transaction(router_contract, token_address, amount_in_wei, min_tokens)
            
            # Sign and send transaction
            signed_tx = self.w3.eth.account.sign_transaction(tx, self.account.key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            # Wait for confirmation
            receipt = await self._wait_for_transaction(tx_hash)
            
            if receipt['status'] == 1:
                # Add to active trades
                entry_price = await self.get_token_price(token_address)
                self.active_trades.append({
                    'token_address': token_address,
                    'token_symbol': await token_contract.functions.symbol().call(),
                    'entry_price': entry_price,
                    'amount': amount_in_wei,
                    'balance': await self.get_token_balance(token_address),
                    'take_profit': None,
                    'stop_loss': None,
                    'trailing_stop': False,
                    'trailing_distance': None,
                    'highest_price': entry_price
                })
                
                return {
                    'success': True,
                    'tx_hash': tx_hash.hex(),
                    'amount': amount_in_wei
                }
            else:
                return {
                    'success': False,
                    'error': 'Transaction failed'
                }
                
        except Exception as e:
            logging.error(f"Error buying token: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _calculate_min_tokens(self, amount_in, token_contract, max_slippage):
        """Calculate minimum tokens to receive based on slippage."""
        # Implement price impact and slippage calculations
        slippage = max_slippage / 100
        return int(amount_in * (1 - slippage))

    async def _build_buy_transaction(self, router_contract, token_address, amount_in, min_tokens):
        """Build buy transaction."""
        # Implement transaction building logic
        nonce = self.w3.eth.get_transaction_count(self.account.address)
        
        # Get gas price
        gas_price = self.get_gas_price()

        # Build transaction
        transaction = {
            'nonce': nonce,
            'gas': TRADING_CONFIG['gas_limit'],
            'gasPrice': gas_price,
            'from': self.account.address,
            'value': amount_in,
            # Add other necessary transaction parameters
        }

        # Add swap function call data
        deadline = self.w3.eth.get_block('latest')['timestamp'] + 300  # 5 minutes
        
        # Get the path for the swap (ETH -> Token)
        path = [NETWORK['ethereum']['weth'], token_address]
        
        # Add swap function parameters
        transaction.update(
            router_contract.functions.swapExactETHForTokens(
                min_tokens,  # Minimum tokens to receive
                path,        # Swap path
                self.account.address,  # Recipient
                deadline    # Transaction deadline
            ).build_transaction({
                'from': self.account.address,
                'value': amount_in  # Amount of ETH to swap
            })
        )

        return transaction

    async def sell_token(self, token_address, amount, max_slippage):
        """Execute token sale with improved error handling and slippage protection."""
        try:
            # Get token contract
            token_contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=self.token_abi
            )
            
            # Check allowance and approve if needed
            if not await self.check_token_allowance(token_address):
                await self.approve_token(token_address, self.router_address)
            
            # Get router contract
            router_contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(self.router_address),
                abi=self.router_abi
            )
            
            # Calculate minimum ETH to receive based on slippage
            min_eth = await self._calculate_min_eth(amount, token_contract, max_slippage)
            
            # Build transaction
            tx = await self._build_sell_transaction(router_contract, token_address, amount, min_eth)
            
            # Sign and send transaction
            signed_tx = self.w3.eth.account.sign_transaction(tx, self.account.key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            # Wait for confirmation
            receipt = await self._wait_for_transaction(tx_hash)
            
            if receipt['status'] == 1:
                # Remove from active trades
                self.active_trades = [t for t in self.active_trades if t['token_address'].lower() != token_address.lower()]
                
                return {
                    'success': True,
                    'tx_hash': tx_hash.hex(),
                    'amount': amount
                }
            else:
                return {
                    'success': False,
                    'error': 'Transaction failed'
                }
                
        except Exception as e:
            logging.error(f"Error selling token: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _get_optimal_gas_price(self):
        """Get optimal gas price based on network conditions."""
        try:
            base_fee = self.w3.eth.get_block('latest')['baseFeePerGas']
            priority_fee = self.w3.eth.max_priority_fee
            
            # Calculate optimal gas price with 10% buffer
            optimal_gas_price = int(base_fee * 1.1) + priority_fee
            
            return min(optimal_gas_price, TRADING_CONFIG['max_gas_price'])
        except Exception as e:
            # Fallback to network's suggested gas price
            logging.error(f"Error getting optimal gas price: {e}")
            return self.w3.eth.gas_price

    async def check_token_allowance(self, token_address):
        """Check if token is approved for trading."""
        try:
            token_contract = self.w3.eth.contract(
                address=token_address,
                abi=self.token_abi
            )
            allowance = token_contract.functions.allowance(
                self.account.address,
                self.router_address
            ).call()
            return allowance
        except Exception as e:
            logging.error(f"Error checking allowance: {e}")
            return 0

    async def approve_token(self, token_address, router_address, amount=None):
        """Approve router to spend tokens."""
        try:
            token_contract = self.w3.eth.contract(
                address=token_address,
                abi=self.token_abi
            )
            
            if amount is None:
                amount = 2**256 - 1  # Max uint256
                
            nonce = self.w3.eth.get_transaction_count(self.account.address)
            gas_price = self.get_gas_price()
            
            approve_txn = token_contract.functions.approve(
                router_address,
                amount
            ).build_transaction({
                'nonce': nonce,
                'gas': 100000,  # Standard gas limit for approvals
                'gasPrice': gas_price
            })
            
            signed_txn = self.w3.eth.account.sign_transaction(approve_txn, self.account.key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            return tx_hash
        except Exception as e:
            logging.error(f"Error approving token: {e}")
            return None

    async def get_token_balance(self, token_address):
        """Get token balance for the current account."""
        try:
            token_contract = self.w3.eth.contract(
                address=token_address,
                abi=self.token_abi
            )
            balance = token_contract.functions.balanceOf(self.account.address).call()
            return balance
        except Exception as e:
            logging.error(f"Error getting token balance: {e}")
            return 0

    async def _wait_for_transaction(self, tx_hash):
        """Wait for transaction confirmation with timeout."""
        start_time = 0
        while True:
            try:
                receipt = self.w3.eth.get_transaction_receipt(tx_hash)
                if receipt:
                    if receipt['status'] == 1:
                        return {'success': True, 'receipt': receipt}
                    return {'success': False, 'error': 'Transaction failed'}
                
                if 60 < start_time:
                    return {'success': False, 'error': 'Transaction timeout'}
                
                start_time += 1
            except Exception as e:
                logging.error(f"Error waiting for transaction: {e}")
                return {'success': False, 'error': str(e)}

    def add_trading_pair(self, address, token_info):
        """Add a trading pair to monitor."""
        self.trading_pairs[address] = {
            'address': address,
            'symbol': token_info.get('symbol', ''),
            'name': token_info.get('name', ''),
            'decimals': token_info.get('decimals', 18),
            'price': token_info.get('price', 0),
            'liquidity': token_info.get('liquidity', 0),
            'volume_24h': token_info.get('volume_24h', 0),
            'price_change_24h': token_info.get('price_change_24h', 0),
            'last_updated': datetime.now()
        }
        
    def remove_trading_pair(self, address):
        """Remove a trading pair from monitoring."""
        if address in self.trading_pairs:
            del self.trading_pairs[address]
            
    def get_trading_pairs(self):
        """Get all monitored trading pairs."""
        return self.trading_pairs
        
    async def get_token_info(self, address):
        """Get token information including price and metadata."""
        try:
            # Create token contract
            token_contract = self.w3.eth.contract(
                address=self.w3.to_checksum_address(address),
                abi=self.token_abi
            )
            
            # Get basic token info
            symbol = await token_contract.functions.symbol().call()
            name = await token_contract.functions.name().call()
            decimals = await token_contract.functions.decimals().call()
            
            # Get price and market data from DexScreener
            market_data = await self.token_manager.get_token_market_data(address)
            
            return {
                'symbol': symbol,
                'name': name,
                'decimals': decimals,
                'price': market_data.get('price', 0),
                'liquidity': market_data.get('liquidity', 0),
                'volume_24h': market_data.get('volume_24h', 0),
                'price_change_24h': market_data.get('price_change_24h', 0)
            }
            
        except Exception as e:
            logging.error(f"Error getting token info: {e}")
            raise
            
    async def execute_trade(self, address):
        """Execute a manual trade for a token."""
        try:
            # Get token info and current price
            token_info = await self.get_token_info(address)
            current_price = token_info['price']
            
            if current_price <= 0:
                return {'success': False, 'error': 'Invalid token price'}
                
            # Calculate trade amount based on settings
            amount_in_eth = TRADING_CONFIG['max_investment_per_trade']
            amount_in_wei = self.w3.to_wei(amount_in_eth, 'ether')
            
            # Execute buy transaction
            tx_hash = await self.buy_token(
                token_address=address,
                amount=amount_in_wei,
                max_slippage=TRADING_CONFIG['max_slippage']
            )
            
            if tx_hash:
                # Add to active trades
                self.active_trades[address] = {
                    'token_address': address,
                    'entry_price': current_price,
                    'amount': amount_in_wei,
                    'timestamp': datetime.now(),
                    'type': 'manual'
                }
                
                return {'success': True, 'tx_hash': tx_hash}
            else:
                return {'success': False, 'error': 'Transaction failed'}
                
        except Exception as e:
            logging.error(f"Error executing trade: {e}")
            return {'success': False, 'error': str(e)}

def main():
    """Main entry point for the trading bot."""
    try:
        # Initialize the trader
        trader = DexTrader(chain='ethereum')  # Using Ethereum network
        logging.info(f"Bot initialized successfully!")
        logging.info(f"Connected to Ethereum network: {trader.w3.is_connected()}")
        logging.info(f"Wallet address: {trader.account.address}")
        
        # Example: Monitor wallet balance
        balance = trader.get_balance(trader.account.address)
        logging.info(f"Wallet balance: {trader.w3.from_wei(balance, 'ether')} ETH")
        
        # Keep the bot running
        while True:
            # Add your trading logic here
            pass
            
    except KeyboardInterrupt:
        logging.info("\nBot stopped by user")
    except Exception as e:
        logging.error(f"Error in main loop: {e}")

if __name__ == "__main__":
    main()
