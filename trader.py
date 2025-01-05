import os
import json
import asyncio
from web3 import Web3, AsyncWeb3
from web3.middleware import geth_poa_middleware
from eth_account import Account
from dotenv import load_dotenv
import logging
from datetime import datetime
from config import NETWORK

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DexTrader:
    def __init__(self, chain='ethereum'):
        load_dotenv()
        
        # Network setup
        self.rpc_url = os.getenv('ETHEREUM_RPC_URL')
        if not self.rpc_url:
            raise ValueError("ETHEREUM_RPC_URL not found in environment variables")
        
        # Initialize Web3
        self.w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(self.rpc_url))
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        
        # Account setup
        private_key = os.getenv('PRIVATE_KEY')
        if not private_key:
            raise ValueError("PRIVATE_KEY not found in environment variables")
        self.account = Account.from_key(private_key)
        
        # Trading parameters
        self.max_slippage = float(os.getenv('MAX_SLIPPAGE', '2'))  # 2% default
        self.gas_limit = int(os.getenv('GAS_LIMIT', '300000'))
        self.max_gas_price = int(os.getenv('MAX_GAS_PRICE', '150'))  # in Gwei
        
        # Load network specific configurations
        self.network_config = NETWORK.get(chain.lower())
        if not self.network_config:
            raise ValueError(f"Network configuration not found for chain: {chain}")
        
        # Initialize contract interfaces
        self.router_address = Web3.to_checksum_address(self.network_config['router'])
        with open('abi/router.json', 'r') as f:
            router_abi = json.load(f)
        self.router = self.w3.eth.contract(address=self.router_address, abi=router_abi)
        
        logger.info(f"DexTrader initialized for {chain}")
        logger.info(f"Connected to network: {self.w3.eth.chain_id}")
        logger.info(f"Wallet address: {self.account.address}")

    async def get_token_price(self, token_address, amount_in=Web3.to_wei(1, 'ether')):
        """Get token price in ETH"""
        try:
            token_address = Web3.to_checksum_address(token_address)
            path = [token_address, self.network_config['weth']]
            
            amounts_out = await self.router.functions.getAmountsOut(
                amount_in,
                path
            ).call()
            
            return amounts_out[1]
        except Exception as e:
            logger.error(f"Error getting token price: {e}")
            return 0

    async def get_gas_estimate(self, token_address, amount):
        """Estimate gas for a trade"""
        try:
            token_address = Web3.to_checksum_address(token_address)
            path = [self.network_config['weth'], token_address]
            deadline = int(datetime.now().timestamp()) + 300  # 5 minutes
            
            gas_estimate = await self.router.functions.swapExactETHForTokens(
                0,  # min amount out
                path,
                self.account.address,
                deadline
            ).estimate_gas({
                'from': self.account.address,
                'value': amount
            })
            
            return gas_estimate
        except Exception as e:
            logger.error(f"Error estimating gas: {e}")
            return self.gas_limit

    async def execute_trade(self, token_address, amount_in, min_amount_out):
        """Execute a trade"""
        try:
            token_address = Web3.to_checksum_address(token_address)
            path = [self.network_config['weth'], token_address]
            deadline = int(datetime.now().timestamp()) + 300  # 5 minutes
            
            # Get current gas price
            gas_price = await self.w3.eth.gas_price
            if gas_price > Web3.to_wei(self.max_gas_price, 'gwei'):
                raise ValueError(f"Gas price too high: {Web3.from_wei(gas_price, 'gwei')} Gwei")
            
            # Build transaction
            transaction = await self.router.functions.swapExactETHForTokens(
                min_amount_out,
                path,
                self.account.address,
                deadline
            ).build_transaction({
                'from': self.account.address,
                'value': amount_in,
                'gas': self.gas_limit,
                'gasPrice': gas_price,
                'nonce': await self.w3.eth.get_transaction_count(self.account.address)
            })
            
            # Sign and send transaction
            signed_txn = self.w3.eth.account.sign_transaction(transaction, self.account.key)
            tx_hash = await self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            # Wait for transaction receipt
            receipt = await self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt['status'] == 1:
                logger.info(f"Trade successful! Transaction hash: {tx_hash.hex()}")
                return True, tx_hash.hex()
            else:
                logger.error(f"Trade failed! Transaction hash: {tx_hash.hex()}")
                return False, tx_hash.hex()
            
        except Exception as e:
            logger.error(f"Error executing trade: {e}")
            return False, str(e)

    async def check_token_approval(self, token_address, amount):
        """Check if token is approved for trading"""
        try:
            token_address = Web3.to_checksum_address(token_address)
            token_contract = self.w3.eth.contract(
                address=token_address,
                abi=json.loads(open('abi/erc20.json', 'r').read())
            )
            
            allowance = await token_contract.functions.allowance(
                self.account.address,
                self.router_address
            ).call()
            
            return allowance >= amount
        except Exception as e:
            logger.error(f"Error checking token approval: {e}")
            return False

    async def approve_token(self, token_address):
        """Approve token for trading"""
        try:
            token_address = Web3.to_checksum_address(token_address)
            token_contract = self.w3.eth.contract(
                address=token_address,
                abi=json.loads(open('abi/erc20.json', 'r').read())
            )
            
            # Get current gas price
            gas_price = await self.w3.eth.gas_price
            if gas_price > Web3.to_wei(self.max_gas_price, 'gwei'):
                raise ValueError(f"Gas price too high: {Web3.from_wei(gas_price, 'gwei')} Gwei")
            
            # Build approval transaction
            transaction = await token_contract.functions.approve(
                self.router_address,
                Web3.to_wei(2**64 - 1, 'ether')  # Unlimited approval
            ).build_transaction({
                'from': self.account.address,
                'gas': 100000,  # Standard gas limit for approvals
                'gasPrice': gas_price,
                'nonce': await self.w3.eth.get_transaction_count(self.account.address)
            })
            
            # Sign and send transaction
            signed_txn = self.w3.eth.account.sign_transaction(transaction, self.account.key)
            tx_hash = await self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            # Wait for transaction receipt
            receipt = await self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt['status'] == 1:
                logger.info(f"Token approval successful! Transaction hash: {tx_hash.hex()}")
                return True, tx_hash.hex()
            else:
                logger.error(f"Token approval failed! Transaction hash: {tx_hash.hex()}")
                return False, tx_hash.hex()
            
        except Exception as e:
            logger.error(f"Error approving token: {e}")
            return False, str(e)

async def main():
    """Main entry point for the trading bot."""
    try:
        # Initialize the trader
        trader = DexTrader(chain='ethereum')  # Using Ethereum network
        logger.info(f"Bot initialized successfully!")
        logger.info(f"Connected to Ethereum network: {trader.w3.eth.chain_id}")
        logger.info(f"Wallet address: {trader.account.address}")
        
        # Example: Monitor wallet balance
        balance = await trader.w3.eth.get_balance(trader.account.address)
        logger.info(f"Wallet balance: {Web3.from_wei(balance, 'ether')} ETH")
        
        # Keep the bot running
        while True:
            # Add your trading logic here
            await asyncio.sleep(60)  # Sleep for 60 seconds between checks
            
    except KeyboardInterrupt:
        logger.info("\nBot stopped by user")
    except Exception as e:
        logger.error(f"Error in main loop: {e}")

if __name__ == "__main__":
    asyncio.run(main())
