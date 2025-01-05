from web3 import Web3
import logging
from datetime import datetime, timedelta
import asyncio
from decimal import Decimal
from config import ORDER_CONFIG
import json

class OrderManager:
    def __init__(self, w3_provider, wallet_manager, router_address):
        self.w3 = w3_provider
        self.wallet_manager = wallet_manager
        self.router_address = router_address
        self.logger = logging.getLogger(__name__)
        self.orders = {}
        self.order_history = {}
        self.pending_orders = set()
        self.router_contract = None
        self._initialize_router()

    def _initialize_router(self):
        """Initialize DEX router contract."""
        try:
            with open(ORDER_CONFIG['router_abi_path'], 'r') as f:
                router_abi = json.load(f)
            self.router_contract = self.w3.eth.contract(
                address=self.router_address,
                abi=router_abi
            )
        except Exception as e:
            self.logger.error(f"Error initializing router: {e}")

    async def create_buy_order(self, token_address, pair_address, amount, 
                             wallet_address, slippage=0.5):
        """Create a buy order."""
        try:
            # Generate order ID
            order_id = self._generate_order_id('buy', token_address, wallet_address)
            
            # Get token price and calculate amounts
            price_data = await self._get_token_price(pair_address)
            min_out = self._calculate_min_output(amount, price_data['price'], slippage)
            
            # Create order object
            order = {
                'id': order_id,
                'type': 'buy',
                'token_address': token_address,
                'pair_address': pair_address,
                'wallet_address': wallet_address,
                'amount': amount,
                'min_out': min_out,
                'price': price_data['price'],
                'slippage': slippage,
                'status': 'pending',
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            # Prepare transaction
            tx_data = await self._prepare_buy_transaction(order)
            if not tx_data:
                return None
            
            order['transaction'] = tx_data
            self.orders[order_id] = order
            self.pending_orders.add(order_id)
            
            # Execute order
            tx_hash = await self._execute_order(order)
            if tx_hash:
                order['tx_hash'] = tx_hash
                await self._monitor_order(order_id)
            
            return order_id
        except Exception as e:
            self.logger.error(f"Error creating buy order: {e}")
            return None

    async def create_sell_order(self, token_address, pair_address, amount, 
                              wallet_address, slippage=0.5):
        """Create a sell order."""
        try:
            # Generate order ID
            order_id = self._generate_order_id('sell', token_address, wallet_address)
            
            # Get token price and calculate amounts
            price_data = await self._get_token_price(pair_address)
            min_out = self._calculate_min_output(amount, price_data['price'], slippage)
            
            # Create order object
            order = {
                'id': order_id,
                'type': 'sell',
                'token_address': token_address,
                'pair_address': pair_address,
                'wallet_address': wallet_address,
                'amount': amount,
                'min_out': min_out,
                'price': price_data['price'],
                'slippage': slippage,
                'status': 'pending',
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            # Check token approval
            approved = await self._check_token_approval(order)
            if not approved:
                return None
            
            # Prepare transaction
            tx_data = await self._prepare_sell_transaction(order)
            if not tx_data:
                return None
            
            order['transaction'] = tx_data
            self.orders[order_id] = order
            self.pending_orders.add(order_id)
            
            # Execute order
            tx_hash = await self._execute_order(order)
            if tx_hash:
                order['tx_hash'] = tx_hash
                await self._monitor_order(order_id)
            
            return order_id
        except Exception as e:
            self.logger.error(f"Error creating sell order: {e}")
            return None

    async def cancel_order(self, order_id):
        """Cancel a pending order."""
        try:
            if order_id not in self.orders:
                raise ValueError("Order not found")
            
            order = self.orders[order_id]
            if order['status'] != 'pending':
                raise ValueError("Order cannot be cancelled")
            
            # Update order status
            order['status'] = 'cancelled'
            order['updated_at'] = datetime.now().isoformat()
            
            # Move to history
            self.order_history[order_id] = order
            del self.orders[order_id]
            self.pending_orders.discard(order_id)
            
            return True
        except Exception as e:
            self.logger.error(f"Error cancelling order: {e}")
            return False

    async def get_order_status(self, order_id):
        """Get current order status."""
        try:
            if order_id in self.orders:
                return self.orders[order_id]
            elif order_id in self.order_history:
                return self.order_history[order_id]
            else:
                return None
        except Exception as e:
            self.logger.error(f"Error getting order status: {e}")
            return None

    async def get_order_history(self, wallet_address=None, token_address=None,
                              start_time=None, end_time=None):
        """Get order history with optional filters."""
        try:
            history = list(self.order_history.values())
            
            # Apply filters
            if wallet_address:
                history = [order for order in history 
                          if order['wallet_address'] == wallet_address]
            
            if token_address:
                history = [order for order in history 
                          if order['token_address'] == token_address]
            
            if start_time:
                history = [order for order in history 
                          if datetime.fromisoformat(order['created_at']) >= start_time]
            
            if end_time:
                history = [order for order in history 
                          if datetime.fromisoformat(order['created_at']) <= end_time]
            
            return sorted(history, 
                         key=lambda x: datetime.fromisoformat(x['created_at']), 
                         reverse=True)
        except Exception as e:
            self.logger.error(f"Error getting order history: {e}")
            return []

    async def _prepare_buy_transaction(self, order):
        """Prepare buy transaction data."""
        try:
            # Get path for swap
            path = [ORDER_CONFIG['weth_address'], order['token_address']]
            
            # Get deadline
            deadline = int(datetime.now().timestamp() + ORDER_CONFIG['transaction_deadline'])
            
            # Prepare swap data
            swap_data = self.router_contract.functions.swapExactETHForTokens(
                order['min_out'],
                path,
                order['wallet_address'],
                deadline
            )
            
            # Get transaction parameters
            tx_params = {
                'from': order['wallet_address'],
                'value': order['amount'],
                'gas': 0,  # Will be estimated
                'gasPrice': await self.wallet_manager._get_optimal_gas_price()
            }
            
            # Add swap data
            tx_params['data'] = swap_data.build_transaction()['data']
            
            # Estimate gas
            tx_params['gas'] = await self.wallet_manager._estimate_gas(tx_params)
            
            return tx_params
        except Exception as e:
            self.logger.error(f"Error preparing buy transaction: {e}")
            return None

    async def _prepare_sell_transaction(self, order):
        """Prepare sell transaction data."""
        try:
            # Get path for swap
            path = [order['token_address'], ORDER_CONFIG['weth_address']]
            
            # Get deadline
            deadline = int(datetime.now().timestamp() + ORDER_CONFIG['transaction_deadline'])
            
            # Prepare swap data
            swap_data = self.router_contract.functions.swapExactTokensForETH(
                order['amount'],
                order['min_out'],
                path,
                order['wallet_address'],
                deadline
            )
            
            # Get transaction parameters
            tx_params = {
                'from': order['wallet_address'],
                'value': 0,
                'gas': 0,  # Will be estimated
                'gasPrice': await self.wallet_manager._get_optimal_gas_price()
            }
            
            # Add swap data
            tx_params['data'] = swap_data.build_transaction()['data']
            
            # Estimate gas
            tx_params['gas'] = await self.wallet_manager._estimate_gas(tx_params)
            
            return tx_params
        except Exception as e:
            self.logger.error(f"Error preparing sell transaction: {e}")
            return None

    async def _execute_order(self, order):
        """Execute prepared order transaction."""
        try:
            # Sign transaction
            signed_tx = await self.wallet_manager.sign_transaction(
                order['transaction'],
                order['wallet_address']
            )
            
            if not signed_tx:
                return None
            
            # Send transaction
            tx_hash = await self.wallet_manager.send_transaction(signed_tx)
            return tx_hash
        except Exception as e:
            self.logger.error(f"Error executing order: {e}")
            return None

    async def _monitor_order(self, order_id):
        """Monitor order transaction status."""
        try:
            order = self.orders[order_id]
            
            # Monitor transaction
            receipt = await self.wallet_manager.monitor_transaction(order['tx_hash'])
            
            if receipt:
                # Update order status
                order['status'] = 'completed' if receipt['status'] else 'failed'
                order['updated_at'] = datetime.now().isoformat()
                order['receipt'] = receipt
                
                # Move to history if finished
                if order['status'] in ['completed', 'failed']:
                    self.order_history[order_id] = order
                    del self.orders[order_id]
                    self.pending_orders.discard(order_id)
        except Exception as e:
            self.logger.error(f"Error monitoring order: {e}")

    async def _check_token_approval(self, order):
        """Check and handle token approval if needed."""
        try:
            # Get current allowance
            token_contract = self.w3.eth.contract(
                address=order['token_address'],
                abi=self._get_erc20_abi()
            )
            
            allowance = await token_contract.functions.allowance(
                order['wallet_address'],
                self.router_address
            ).call()
            
            if allowance < order['amount']:
                # Approve token spending
                tx_hash = await self.wallet_manager.approve_token(
                    order['token_address'],
                    self.router_address,
                    order['wallet_address']
                )
                
                if not tx_hash:
                    return False
                
                # Wait for approval confirmation
                receipt = await self.wallet_manager.monitor_transaction(tx_hash)
                return receipt and receipt['status']
            
            return True
        except Exception as e:
            self.logger.error(f"Error checking token approval: {e}")
            return False

    def _generate_order_id(self, order_type, token_address, wallet_address):
        """Generate unique order ID."""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        return f"{order_type}_{token_address[:6]}_{wallet_address[:6]}_{timestamp}"

    def _calculate_min_output(self, amount, price, slippage):
        """Calculate minimum output amount with slippage."""
        try:
            expected_out = Decimal(str(amount)) * Decimal(str(price))
            min_out = expected_out * (1 - Decimal(str(slippage)) / 100)
            return int(min_out)
        except Exception as e:
            self.logger.error(f"Error calculating min output: {e}")
            return 0

    async def _get_token_price(self, pair_address):
        """Get current token price from pair."""
        # Implement price fetching
        pass

    def _get_erc20_abi(self):
        """Get standard ERC20 ABI."""
        try:
            with open(ORDER_CONFIG['erc20_abi_path'], 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading ERC20 ABI: {e}")
            return None
