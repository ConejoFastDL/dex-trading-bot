import asyncio
import logging
from datetime import datetime, timedelta
from web3 import Web3
from typing import Dict, List, Optional, Set
from config import EVENT_CONFIG
import json
from collections import defaultdict

class EventMonitor:
    def __init__(self, w3_provider):
        self.w3 = w3_provider
        self.logger = logging.getLogger(__name__)
        self.monitored_events = defaultdict(set)
        self.event_filters = {}
        self.event_data = defaultdict(list)
        self.event_handlers = {}
        self.monitoring = False
        self.custom_filters = {}
        self.manual_mode = True

    async def start_monitoring(self, contract_address: str, events: List[str] = None):
        """Start monitoring contract events."""
        try:
            if contract_address in self.monitored_events and not events:
                return
            
            # Initialize contract
            contract = self._get_contract(contract_address)
            if not contract:
                return
            
            # Setup event filters
            if events:
                for event_name in events:
                    await self._setup_event_filter(contract_address, event_name)
            else:
                # Monitor all events
                events = self._get_contract_events(contract)
                for event_name in events:
                    await self._setup_event_filter(contract_address, event_name)
            
            self.monitored_events[contract_address].update(events)
            
            # Start event loop if not already running
            if not self.monitoring:
                self.monitoring = True
                asyncio.create_task(self._monitor_events())
            
            return True
        except Exception as e:
            self.logger.error(f"Error starting event monitoring: {e}")
            return False

    async def stop_monitoring(self, contract_address: str = None, 
                            event_name: str = None):
        """Stop monitoring specific or all events."""
        try:
            if contract_address and event_name:
                # Remove specific event
                self.monitored_events[contract_address].discard(event_name)
                filter_key = f"{contract_address}_{event_name}"
                self.event_filters.pop(filter_key, None)
            elif contract_address:
                # Remove all events for contract
                self.monitored_events.pop(contract_address, None)
                for key in list(self.event_filters.keys()):
                    if key.startswith(contract_address):
                        self.event_filters.pop(key)
            else:
                # Stop all monitoring
                self.monitoring = False
                self.monitored_events.clear()
                self.event_filters.clear()
            
            return True
        except Exception as e:
            self.logger.error(f"Error stopping event monitoring: {e}")
            return False

    async def add_event_handler(self, contract_address: str, event_name: str, 
                              handler_func, filter_params: Dict = None):
        """Add custom event handler with optional filtering."""
        try:
            handler_key = f"{contract_address}_{event_name}"
            
            self.event_handlers[handler_key] = {
                'handler': handler_func,
                'filters': filter_params
            }
            
            if filter_params:
                self.custom_filters[handler_key] = filter_params
            
            return True
        except Exception as e:
            self.logger.error(f"Error adding event handler: {e}")
            return False

    async def remove_event_handler(self, contract_address: str, event_name: str):
        """Remove custom event handler."""
        try:
            handler_key = f"{contract_address}_{event_name}"
            self.event_handlers.pop(handler_key, None)
            self.custom_filters.pop(handler_key, None)
            return True
        except Exception as e:
            self.logger.error(f"Error removing event handler: {e}")
            return False

    async def get_events(self, contract_address: str = None, event_name: str = None,
                        start_block: int = None, end_block: int = None):
        """Get historical events with optional filtering."""
        try:
            events = []
            
            if contract_address and event_name:
                # Get specific event type
                events = await self._get_specific_events(
                    contract_address, event_name, start_block, end_block
                )
            elif contract_address:
                # Get all events for contract
                for event_name in self.monitored_events[contract_address]:
                    events.extend(await self._get_specific_events(
                        contract_address, event_name, start_block, end_block
                    ))
            else:
                # Get all monitored events
                for addr in self.monitored_events:
                    for event_name in self.monitored_events[addr]:
                        events.extend(await self._get_specific_events(
                            addr, event_name, start_block, end_block
                        ))
            
            return sorted(events, key=lambda x: x['blockNumber'], reverse=True)
        except Exception as e:
            self.logger.error(f"Error getting events: {e}")
            return []

    async def set_manual_mode(self, enabled: bool = True):
        """Set manual mode for event handling."""
        try:
            self.manual_mode = enabled
            self.logger.info(f"Manual mode {'enabled' if enabled else 'disabled'}")
            return True
        except Exception as e:
            self.logger.error(f"Error setting manual mode: {e}")
            return False

    async def manually_process_event(self, event_data: Dict):
        """Manually process an event."""
        try:
            if not self.manual_mode:
                raise ValueError("Manual mode is not enabled")
            
            # Process event
            await self._process_event(event_data)
            return True
        except Exception as e:
            self.logger.error(f"Error manually processing event: {e}")
            return False

    async def add_custom_filter(self, contract_address: str, event_name: str, 
                              filter_params: Dict):
        """Add custom filter for events."""
        try:
            filter_key = f"{contract_address}_{event_name}"
            self.custom_filters[filter_key] = filter_params
            return True
        except Exception as e:
            self.logger.error(f"Error adding custom filter: {e}")
            return False

    async def remove_custom_filter(self, contract_address: str, event_name: str):
        """Remove custom filter for events."""
        try:
            filter_key = f"{contract_address}_{event_name}"
            self.custom_filters.pop(filter_key, None)
            return True
        except Exception as e:
            self.logger.error(f"Error removing custom filter: {e}")
            return False

    async def _monitor_events(self):
        """Monitor events in real-time."""
        try:
            while self.monitoring:
                for contract_address in self.monitored_events:
                    for event_name in self.monitored_events[contract_address]:
                        filter_key = f"{contract_address}_{event_name}"
                        event_filter = self.event_filters.get(filter_key)
                        
                        if event_filter:
                            # Get new events
                            events = event_filter.get_new_entries()
                            
                            for event in events:
                                if self.manual_mode:
                                    # Store event for manual processing
                                    self.event_data[filter_key].append(event)
                                else:
                                    # Process event automatically
                                    await self._process_event(event)
                
                await asyncio.sleep(EVENT_CONFIG['poll_interval'])
        except Exception as e:
            self.logger.error(f"Error monitoring events: {e}")
            self.monitoring = False

    async def _process_event(self, event):
        """Process a single event."""
        try:
            contract_address = event['address']
            event_name = event['event']
            handler_key = f"{contract_address}_{event_name}"
            
            # Check custom filters
            if not self._passes_filters(event, handler_key):
                return
            
            # Store event
            self.event_data[handler_key].append(event)
            
            # Call custom handler if exists
            handler = self.event_handlers.get(handler_key)
            if handler:
                await handler['handler'](event)
        except Exception as e:
            self.logger.error(f"Error processing event: {e}")

    async def _setup_event_filter(self, contract_address: str, event_name: str):
        """Setup event filter for monitoring."""
        try:
            contract = self._get_contract(contract_address)
            if not contract:
                return
            
            event_filter = getattr(contract.events, event_name).create_filter(
                fromBlock='latest'
            )
            
            filter_key = f"{contract_address}_{event_name}"
            self.event_filters[filter_key] = event_filter
            
            return True
        except Exception as e:
            self.logger.error(f"Error setting up event filter: {e}")
            return False

    async def _get_specific_events(self, contract_address: str, event_name: str,
                                 start_block: int = None, end_block: int = None):
        """Get specific historical events."""
        try:
            contract = self._get_contract(contract_address)
            if not contract:
                return []
            
            # Setup filter parameters
            filter_params = {
                'fromBlock': start_block or 0,
                'toBlock': end_block or 'latest'
            }
            
            # Get events
            event = getattr(contract.events, event_name)
            events = event.get_logs(**filter_params)
            
            return events
        except Exception as e:
            self.logger.error(f"Error getting specific events: {e}")
            return []

    def _get_contract(self, contract_address: str):
        """Get contract instance."""
        try:
            # Load ABI
            with open(EVENT_CONFIG['contract_abi_path'], 'r') as f:
                contract_abi = json.load(f)
            
            return self.w3.eth.contract(
                address=contract_address,
                abi=contract_abi
            )
        except Exception as e:
            self.logger.error(f"Error getting contract: {e}")
            return None

    def _get_contract_events(self, contract):
        """Get list of available contract events."""
        try:
            return [
                e['name'] for e in contract.abi 
                if e['type'] == 'event'
            ]
        except Exception as e:
            self.logger.error(f"Error getting contract events: {e}")
            return []

    def _passes_filters(self, event: Dict, handler_key: str):
        """Check if event passes custom filters."""
        try:
            filters = self.custom_filters.get(handler_key)
            if not filters:
                return True
            
            for key, value in filters.items():
                if event.get(key) != value:
                    return False
            
            return True
        except Exception as e:
            self.logger.error(f"Error checking filters: {e}")
            return False

    async def cleanup_old_data(self):
        """Clean up old event data."""
        try:
            retention_period = timedelta(days=EVENT_CONFIG['data_retention_days'])
            cutoff = datetime.now() - retention_period
            
            for key in self.event_data:
                self.event_data[key] = [
                    event for event in self.event_data[key]
                    if datetime.fromtimestamp(event['timestamp']) > cutoff
                ]
        except Exception as e:
            self.logger.error(f"Error cleaning up old data: {e}")
