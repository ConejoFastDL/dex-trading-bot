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
        
    async def initialize(self):
        """Initialize async components of the trader"""
        chain_id = await self.w3.eth.chain_id
        logger.info(f"Connected to network: Chain ID {chain_id}")
        logger.info(f"Wallet address: {self.account.address}")
        return self

    async def get_token_contract(self, token_address):
        """Get token contract instance"""
        token_address = Web3.to_checksum_address(token_address)
        with open('abi/erc20.json', 'r') as f:
            token_abi = json.load(f)
        return self.w3.eth.contract(address=token_address, abi=token_abi)

    async def get_token_balance(self, token_address):
        """Get token balance for the connected wallet"""
        token_contract = await self.get_token_contract(token_address)
        balance = await token_contract.functions.balanceOf(self.account.address).call()
        return balance

    async def get_token_allowance(self, token_address, spender_address):
        """Get token allowance for a spender"""
        token_contract = await self.get_token_contract(token_address)
        allowance = await token_contract.functions.allowance(
            self.account.address,
            spender_address
        ).call()
        return allowance

    async def approve_token(self, token_address, spender_address, amount):
        """Approve token spending"""
        token_contract = await self.get_token_contract(token_address)
        
        # Build the transaction
        nonce = await self.w3.eth.get_transaction_count(self.account.address)
        gas_price = await self.w3.eth.gas_price
        
        txn = await token_contract.functions.approve(
            spender_address,
            amount
        ).build_transaction({
            'from': self.account.address,
            'gas': self.gas_limit,
            'gasPrice': gas_price,
            'nonce': nonce,
        })
        
        # Sign and send the transaction
        signed_txn = self.w3.eth.account.sign_transaction(txn, self.account.key)
        tx_hash = await self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        return tx_hash

    async def get_price_data(self, token_address, amount_in=Web3.to_wei(1, 'ether')):
        """Get token price data"""
        try:
            # Use router to get amounts out
            amounts = await self.router.functions.getAmountsOut(
                amount_in,
                [token_address, self.network_config['weth']]
            ).call()
            return amounts[1] / amount_in
        except Exception as e:
            logger.error(f"Error getting price data: {str(e)}")
            return None

    async def execute_trade(self, token_address, amount, is_buy=True):
        """Execute a trade"""
        try:
            path = [self.network_config['weth'], token_address] if is_buy else [token_address, self.network_config['weth']]
            
            # Get amounts out
            amounts = await self.router.functions.getAmountsOut(amount, path).call()
            min_amount_out = int(amounts[-1] * (1 - self.max_slippage / 100))
            
            # Build the transaction
            nonce = await self.w3.eth.get_transaction_count(self.account.address)
            gas_price = await self.w3.eth.gas_price
            
            deadline = int(datetime.now().timestamp()) + 300  # 5 minutes
            
            # Create the swap transaction
            txn = await self.router.functions.swapExactTokensForTokens(
                amount,
                min_amount_out,
                path,
                self.account.address,
                deadline
            ).build_transaction({
                'from': self.account.address,
                'gas': self.gas_limit,
                'gasPrice': gas_price,
                'nonce': nonce,
            })
            
            # Sign and send the transaction
            signed_txn = self.w3.eth.account.sign_transaction(txn, self.account.key)
            tx_hash = await self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            return tx_hash
        except Exception as e:
            logger.error(f"Error executing trade: {str(e)}")
            return None

async def main():
    """Main entry point for testing the trading bot"""
    try:
        trader = DexTrader()
        await trader.initialize()
        
        # Add your test code here
        
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
