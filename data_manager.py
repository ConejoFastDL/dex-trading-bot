import logging
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Union
import json
import os
from config import DATA_CONFIG
import aiohttp
import asyncio
from decimal import Decimal

class DataManager:
    def __init__(self, storage_path: str = None):
        self.logger = logging.getLogger(__name__)
        self.storage_path = storage_path or DATA_CONFIG['storage_path']
        self.cache = {}
        self.data_sources = {}
        self.custom_indicators = {}
        self.manual_data = {}
        self._initialize_storage()

    def _initialize_storage(self):
        """Initialize data storage directory structure."""
        try:
            # Create main directories
            directories = [
                'price_data',
                'volume_data',
                'trade_history',
                'market_data',
                'custom_data',
                'analysis'
            ]
            
            for directory in directories:
                path = os.path.join(self.storage_path, directory)
                os.makedirs(path, exist_ok=True)
        except Exception as e:
            self.logger.error(f"Error initializing storage: {e}")

    async def store_price_data(self, pair_address: str, data: Union[Dict, pd.DataFrame],
                             timeframe: str = '1m'):
        """Store price data with specified timeframe."""
        try:
            # Convert to DataFrame if dict
            if isinstance(data, dict):
                df = pd.DataFrame([data])
            else:
                df = data.copy()
            
            # Ensure timestamp column exists
            if 'timestamp' not in df.columns:
                df['timestamp'] = datetime.now().isoformat()
            
            # Save data
            filename = f"price_{pair_address}_{timeframe}.csv"
            filepath = os.path.join(self.storage_path, 'price_data', filename)
            
            # Append or create new file
            if os.path.exists(filepath):
                existing_data = pd.read_csv(filepath)
                df = pd.concat([existing_data, df]).drop_duplicates(subset=['timestamp'])
            
            df.to_csv(filepath, index=False)
            
            # Update cache
            cache_key = f"price_{pair_address}_{timeframe}"
            self.cache[cache_key] = df
            
            return True
        except Exception as e:
            self.logger.error(f"Error storing price data: {e}")
            return False

    async def get_price_data(self, pair_address: str, timeframe: str = '1m',
                           start_time: datetime = None, end_time: datetime = None):
        """Get historical price data."""
        try:
            cache_key = f"price_{pair_address}_{timeframe}"
            
            # Check cache first
            if cache_key in self.cache:
                df = self.cache[cache_key]
            else:
                # Load from file
                filename = f"price_{pair_address}_{timeframe}.csv"
                filepath = os.path.join(self.storage_path, 'price_data', filename)
                
                if not os.path.exists(filepath):
                    return None
                
                df = pd.read_csv(filepath)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                self.cache[cache_key] = df
            
            # Apply time filters
            if start_time:
                df = df[df['timestamp'] >= start_time]
            if end_time:
                df = df[df['timestamp'] <= end_time]
            
            return df
        except Exception as e:
            self.logger.error(f"Error getting price data: {e}")
            return None

    async def store_trade_history(self, wallet_address: str, trade_data: Dict):
        """Store trade history for analysis."""
        try:
            filename = f"trades_{wallet_address}.json"
            filepath = os.path.join(self.storage_path, 'trade_history', filename)
            
            # Load existing trades
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    trades = json.load(f)
            else:
                trades = []
            
            # Add new trade
            trade_data['timestamp'] = datetime.now().isoformat()
            trades.append(trade_data)
            
            # Save updated trades
            with open(filepath, 'w') as f:
                json.dump(trades, f, indent=4)
            
            return True
        except Exception as e:
            self.logger.error(f"Error storing trade history: {e}")
            return False

    async def get_trade_history(self, wallet_address: str = None,
                              start_time: datetime = None,
                              end_time: datetime = None):
        """Get trading history with optional filters."""
        try:
            trades = []
            
            # Get all trade files if no wallet specified
            if wallet_address:
                filenames = [f"trades_{wallet_address}.json"]
            else:
                trade_dir = os.path.join(self.storage_path, 'trade_history')
                filenames = [f for f in os.listdir(trade_dir) if f.startswith('trades_')]
            
            # Load trades
            for filename in filenames:
                filepath = os.path.join(self.storage_path, 'trade_history', filename)
                if os.path.exists(filepath):
                    with open(filepath, 'r') as f:
                        wallet_trades = json.load(f)
                        trades.extend(wallet_trades)
            
            # Apply time filters
            if start_time or end_time:
                filtered_trades = []
                for trade in trades:
                    trade_time = datetime.fromisoformat(trade['timestamp'])
                    if start_time and trade_time < start_time:
                        continue
                    if end_time and trade_time > end_time:
                        continue
                    filtered_trades.append(trade)
                trades = filtered_trades
            
            return trades
        except Exception as e:
            self.logger.error(f"Error getting trade history: {e}")
            return []

    async def add_custom_indicator(self, name: str, calculation_func,
                                 parameters: Dict = None):
        """Add custom technical indicator."""
        try:
            self.custom_indicators[name] = {
                'function': calculation_func,
                'parameters': parameters or {}
            }
            return True
        except Exception as e:
            self.logger.error(f"Error adding custom indicator: {e}")
            return False

    async def calculate_indicator(self, name: str, data: pd.DataFrame,
                                parameters: Dict = None):
        """Calculate technical indicator value."""
        try:
            if name not in self.custom_indicators:
                raise ValueError(f"Indicator {name} not found")
            
            indicator = self.custom_indicators[name]
            params = parameters or indicator['parameters']
            
            result = indicator['function'](data, **params)
            return result
        except Exception as e:
            self.logger.error(f"Error calculating indicator: {e}")
            return None

    async def add_data_source(self, name: str, source_type: str,
                            connection_params: Dict):
        """Add external data source."""
        try:
            self.data_sources[name] = {
                'type': source_type,
                'params': connection_params,
                'last_update': None
            }
            return True
        except Exception as e:
            self.logger.error(f"Error adding data source: {e}")
            return False

    async def fetch_external_data(self, source_name: str, query_params: Dict = None):
        """Fetch data from external source."""
        try:
            if source_name not in self.data_sources:
                raise ValueError(f"Data source {source_name} not found")
            
            source = self.data_sources[source_name]
            
            if source['type'] == 'api':
                data = await self._fetch_api_data(source['params'], query_params)
            elif source['type'] == 'database':
                data = await self._fetch_database_data(source['params'], query_params)
            else:
                raise ValueError(f"Unsupported source type: {source['type']}")
            
            source['last_update'] = datetime.now()
            return data
        except Exception as e:
            self.logger.error(f"Error fetching external data: {e}")
            return None

    async def store_manual_data(self, key: str, data: Dict):
        """Store manually input data."""
        try:
            self.manual_data[key] = {
                'data': data,
                'timestamp': datetime.now().isoformat()
            }
            return True
        except Exception as e:
            self.logger.error(f"Error storing manual data: {e}")
            return False

    async def get_manual_data(self, key: str = None):
        """Retrieve manually stored data."""
        try:
            if key:
                return self.manual_data.get(key)
            return self.manual_data
        except Exception as e:
            self.logger.error(f"Error getting manual data: {e}")
            return None

    async def export_data(self, data_type: str, format: str = 'csv',
                         start_time: datetime = None, end_time: datetime = None):
        """Export data to specified format."""
        try:
            if data_type == 'price':
                data = await self._export_price_data(start_time, end_time)
            elif data_type == 'trades':
                data = await self._export_trade_data(start_time, end_time)
            elif data_type == 'manual':
                data = self.manual_data
            else:
                raise ValueError(f"Unsupported data type: {data_type}")
            
            if format == 'csv':
                return self._export_to_csv(data, data_type)
            elif format == 'json':
                return self._export_to_json(data, data_type)
            else:
                raise ValueError(f"Unsupported export format: {format}")
        except Exception as e:
            self.logger.error(f"Error exporting data: {e}")
            return None

    async def analyze_data(self, data_type: str, analysis_type: str,
                         parameters: Dict = None):
        """Perform data analysis."""
        try:
            if data_type == 'price':
                data = await self._get_price_data_for_analysis(parameters)
            elif data_type == 'trades':
                data = await self._get_trade_data_for_analysis(parameters)
            else:
                raise ValueError(f"Unsupported data type: {data_type}")
            
            if analysis_type == 'statistical':
                return self._perform_statistical_analysis(data, parameters)
            elif analysis_type == 'technical':
                return self._perform_technical_analysis(data, parameters)
            elif analysis_type == 'pattern':
                return self._perform_pattern_analysis(data, parameters)
            else:
                raise ValueError(f"Unsupported analysis type: {analysis_type}")
        except Exception as e:
            self.logger.error(f"Error analyzing data: {e}")
            return None

    async def cleanup_old_data(self):
        """Clean up old data based on retention policy."""
        try:
            retention_days = DATA_CONFIG['retention_days']
            cutoff = datetime.now() - timedelta(days=retention_days)
            
            # Clean up price data
            await self._cleanup_directory('price_data', cutoff)
            
            # Clean up trade history
            await self._cleanup_directory('trade_history', cutoff)
            
            # Clean up manual data
            self._cleanup_manual_data(cutoff)
            
            # Clean up cache
            self._cleanup_cache()
            
            return True
        except Exception as e:
            self.logger.error(f"Error cleaning up old data: {e}")
            return False

    async def _fetch_api_data(self, connection_params: Dict, query_params: Dict = None):
        """Fetch data from API source."""
        try:
            url = connection_params['url']
            headers = connection_params.get('headers', {})
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=query_params) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        raise Exception(f"API request failed with status {response.status}")
        except Exception as e:
            self.logger.error(f"Error fetching API data: {e}")
            return None

    async def _fetch_database_data(self, connection_params: Dict, query_params: Dict = None):
        """Fetch data from database source."""
        # Implement database connection and querying
        pass

    def _cleanup_manual_data(self, cutoff: datetime):
        """Clean up old manual data."""
        try:
            for key in list(self.manual_data.keys()):
                timestamp = datetime.fromisoformat(self.manual_data[key]['timestamp'])
                if timestamp < cutoff:
                    del self.manual_data[key]
        except Exception as e:
            self.logger.error(f"Error cleaning up manual data: {e}")

    def _cleanup_cache(self):
        """Clean up data cache."""
        try:
            self.cache.clear()
        except Exception as e:
            self.logger.error(f"Error cleaning up cache: {e}")

    async def _cleanup_directory(self, directory: str, cutoff: datetime):
        """Clean up files in a directory based on modification time."""
        try:
            directory_path = os.path.join(self.storage_path, directory)
            for filename in os.listdir(directory_path):
                filepath = os.path.join(directory_path, filename)
                if os.path.getmtime(filepath) < cutoff.timestamp():
                    os.remove(filepath)
        except Exception as e:
            self.logger.error(f"Error cleaning up directory: {e}")

    def _export_to_csv(self, data, data_type: str):
        """Export data to CSV format."""
        try:
            if isinstance(data, pd.DataFrame):
                filename = f"{data_type}_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                filepath = os.path.join(self.storage_path, 'analysis', filename)
                data.to_csv(filepath, index=False)
                return filepath
            else:
                df = pd.DataFrame(data)
                filename = f"{data_type}_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                filepath = os.path.join(self.storage_path, 'analysis', filename)
                df.to_csv(filepath, index=False)
                return filepath
        except Exception as e:
            self.logger.error(f"Error exporting to CSV: {e}")
            return None

    def _export_to_json(self, data, data_type: str):
        """Export data to JSON format."""
        try:
            filename = f"{data_type}_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            filepath = os.path.join(self.storage_path, 'analysis', filename)
            
            if isinstance(data, pd.DataFrame):
                data = data.to_dict(orient='records')
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=4)
            
            return filepath
        except Exception as e:
            self.logger.error(f"Error exporting to JSON: {e}")
            return None
