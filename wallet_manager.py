from web3 import Web3
import logging
from datetime import datetime, timedelta
import asyncio
from eth_account import Account
from eth_account.signers.local import LocalAccount
from config import WALLET_CONFIG
import json

class WalletManager:
    def __init__(self, w3_provider):
        self.w3 = w3_provider
        self.logger = logging.getLogger(__name__)
        self.wallets = {}
        self.transactions = {}
        self.nonce_tracker = {}
        self.gas_prices = {}

    async def add_wallet(self, private_key: str, label: str = None):
        """Add a new wallet to manage."""
        try:
            account: LocalAccount = Account.from_key(private_key)
            address = account.address
            
            self.wallets[address] = {
                'account': account,
                'label': label or address[:10],
                'balance': await self._get_balance(address),
                'nonce': await self._get_nonce(address),
                'added_at': datetime.now().isoformat()
            }
            
            return address
        except Exception as e:
            self.logger.error(f"Error adding wallet: {e}")
            return None

    async def get_wallet_info(self, address: str):
        """Get wallet information and status."""
        try:
            if address not in self.wallets:
                return None
            
            wallet = self.wallets[address]
            
            info = {
                'address': address,
                'label': wallet['label'],
                'balance': await self._get_balance(address),
                'nonce': await self._get_nonce(address),
                'transaction_count': len(self.transactions.get(address, [])),
                'added_at': wallet['added_at']
            }
            
            return info
        except Exception as e:
            self.logger.error(f"Error getting wallet info: {e}")
            return None

    async def check_token_balance(self, wallet_address: str, token_address: str):
        """Check token balance for a wallet."""
        try:
            # Get token contract
            token_contract = self.w3.eth.contract(
                address=token_address,
                abi=self._get_erc20_abi()
            )
            
            # Get balance
            balance = await token_contract.functions.balanceOf(wallet_address).call()
            decimals = await token_contract.functions.decimals().call()
            
            return balance / (10 ** decimals)
        except Exception as e:
            self.logger.error(f"Error checking token balance: {e}")
            return 0

    async def prepare_transaction(self, from_address: str, to_address: str, 
                                value: int, data: bytes = None):
        """Prepare a transaction for signing."""
        try:
            if from_address not in self.wallets:
                raise ValueError("Wallet not found")
            
            nonce = await self._get_nonce(from_address)
            gas_price = await self._get_optimal_gas_price()
            
            # Estimate gas
            tx_params = {
                'from': from_address,
                'to': to_address,
                'value': value,
                'nonce': nonce,
                'gasPrice': gas_price
            }
            
            if data:
                tx_params['data'] = data
            
            # Estimate gas limit
            gas_limit = await self._estimate_gas(tx_params)
            tx_params['gas'] = gas_limit
            
            return tx_params
        except Exception as e:
            self.logger.error(f"Error preparing transaction: {e}")
            return None

    async def sign_transaction(self, tx_params: dict, wallet_address: str):
        """Sign a prepared transaction."""
        try:
            if wallet_address not in self.wallets:
                raise ValueError("Wallet not found")
            
            wallet = self.wallets[wallet_address]
            signed_tx = wallet['account'].sign_transaction(tx_params)
            
            return signed_tx
        except Exception as e:
            self.logger.error(f"Error signing transaction: {e}")
            return None

    async def send_transaction(self, signed_tx):
        """Send a signed transaction."""
        try:
            tx_hash = await self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            # Track transaction
            tx_data = {
                'hash': tx_hash.hex(),
                'timestamp': datetime.now().isoformat(),
                'status': 'pending'
            }
            
            from_address = self.w3.eth.get_transaction(tx_hash)['from']
            if from_address not in self.transactions:
                self.transactions[from_address] = []
            
            self.transactions[from_address].append(tx_data)
            
            return tx_hash.hex()
        except Exception as e:
            self.logger.error(f"Error sending transaction: {e}")
            return None

    async def monitor_transaction(self, tx_hash: str):
        """Monitor transaction status."""
        try:
            receipt = None
            retries = 0
            max_retries = WALLET_CONFIG['transaction_monitor']['max_retries']
            
            while not receipt and retries < max_retries:
                try:
                    receipt = await self.w3.eth.get_transaction_receipt(tx_hash)
                except:
                    await asyncio.sleep(WALLET_CONFIG['transaction_monitor']['retry_delay'])
                    retries += 1
            
            if receipt:
                # Update transaction status
                for address, txs in self.transactions.items():
                    for tx in txs:
                        if tx['hash'] == tx_hash:
                            tx['status'] = 'confirmed' if receipt['status'] else 'failed'
                            tx['receipt'] = receipt
                
                return receipt
            else:
                self.logger.warning(f"Transaction {tx_hash} not found after {max_retries} retries")
                return None
        except Exception as e:
            self.logger.error(f"Error monitoring transaction: {e}")
            return None

    async def approve_token(self, token_address: str, spender_address: str, 
                          wallet_address: str, amount: int = None):
        """Approve token spending."""
        try:
            if wallet_address not in self.wallets:
                raise ValueError("Wallet not found")
            
            # Get token contract
            token_contract = self.w3.eth.contract(
                address=token_address,
                abi=self._get_erc20_abi()
            )
            
            # Prepare approval transaction
            if amount is None:
                amount = 2**256 - 1  # Max uint256
            
            tx_data = token_contract.functions.approve(
                spender_address,
                amount
            ).build_transaction({
                'from': wallet_address,
                'nonce': await self._get_nonce(wallet_address)
            })
            
            # Sign and send transaction
            signed_tx = await self.sign_transaction(tx_data, wallet_address)
            if not signed_tx:
                return None
            
            tx_hash = await self.send_transaction(signed_tx)
            return tx_hash
        except Exception as e:
            self.logger.error(f"Error approving token: {e}")
            return None

    async def get_transaction_history(self, wallet_address: str, 
                                    start_time: datetime = None):
        """Get transaction history for a wallet."""
        try:
            if wallet_address not in self.transactions:
                return []
            
            txs = self.transactions[wallet_address]
            
            if start_time:
                txs = [
                    tx for tx in txs
                    if datetime.fromisoformat(tx['timestamp']) >= start_time
                ]
            
            return txs
        except Exception as e:
            self.logger.error(f"Error getting transaction history: {e}")
            return []

    async def cleanup_old_data(self):
        """Clean up old transaction data."""
        try:
            cutoff = datetime.now() - timedelta(days=WALLET_CONFIG['data_retention_days'])
            
            for address in self.transactions:
                self.transactions[address] = [
                    tx for tx in self.transactions[address]
                    if datetime.fromisoformat(tx['timestamp']) > cutoff
                ]
        except Exception as e:
            self.logger.error(f"Error cleaning up old data: {e}")

    async def _get_balance(self, address: str):
        """Get wallet balance."""
        try:
            balance = await self.w3.eth.get_balance(address)
            return self.w3.from_wei(balance, 'ether')
        except Exception as e:
            self.logger.error(f"Error getting balance: {e}")
            return 0

    async def _get_nonce(self, address: str):
        """Get next nonce for address."""
        try:
            nonce = await self.w3.eth.get_transaction_count(address)
            self.nonce_tracker[address] = nonce
            return nonce
        except Exception as e:
            self.logger.error(f"Error getting nonce: {e}")
            return None

    async def _get_optimal_gas_price(self):
        """Get optimal gas price based on network conditions."""
        try:
            base_fee = self.w3.eth.get_block('latest')['baseFeePerGas']
            priority_fee = self.w3.eth.max_priority_fee
            
            gas_price = base_fee + priority_fee
            self.gas_prices[datetime.now().isoformat()] = gas_price
            
            return gas_price
        except Exception as e:
            self.logger.error(f"Error getting optimal gas price: {e}")
            return None

    async def _estimate_gas(self, tx_params: dict):
        """Estimate gas for transaction."""
        try:
            gas_limit = await self.w3.eth.estimate_gas(tx_params)
            return int(gas_limit * WALLET_CONFIG['gas_limit_multiplier'])
        except Exception as e:
            self.logger.error(f"Error estimating gas: {e}")
            return None

    def _get_erc20_abi(self):
        """Get standard ERC20 ABI."""
        try:
            with open(WALLET_CONFIG['erc20_abi_path'], 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading ERC20 ABI: {e}")
            return None
