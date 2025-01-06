import logging
import aiohttp
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TokenManager:
    def __init__(self):
        self.trending_cache = {}
        self.cache_duration = timedelta(minutes=5)  # Cache data for 5 minutes
        
    def _calculate_pair_score(self, pair: Dict) -> int:
        """Calculate a score for a trading pair based on various metrics."""
        score = 0
        
        try:
            # Liquidity score (0-30 points)
            liquidity = float(pair.get('liquidity', {}).get('usd', 0))
            if liquidity >= 1_000_000:  # $1M+
                score += 30
            elif liquidity >= 500_000:  # $500K+
                score += 20
            elif liquidity >= 100_000:  # $100K+
                score += 10
                
            # Volume score (0-30 points)
            volume = float(pair.get('volume', {}).get('h24', 0))
            if volume >= 1_000_000:  # $1M+
                score += 30
            elif volume >= 500_000:  # $500K+
                score += 20
            elif volume >= 100_000:  # $100K+
                score += 10
                
            # Price change score (0-20 points)
            price_change_5m = abs(float(pair.get('priceChange', {}).get('m5', 0)))
            if price_change_5m >= 5:  # 5%+ change
                score += 20
            elif price_change_5m >= 2:  # 2%+ change
                score += 15
            elif price_change_5m >= 1:  # 1%+ change
                score += 10
                
            # Age score (0-10 points)
            pair_created = datetime.fromtimestamp(int(pair.get('pairCreatedAt', 0)) / 1000)
            age_hours = (datetime.now() - pair_created).total_seconds() / 3600
            if age_hours >= 24:  # 24h+
                score += 10
            elif age_hours >= 12:  # 12h+
                score += 5
                
            # Dex score (0-10 points)
            dex_id = pair.get('dexId', '').lower()
            if dex_id in ['uniswap', 'sushiswap', 'pancakeswap']:
                score += 10
            elif dex_id:  # Any other DEX
                score += 5
                
        except Exception as e:
            logger.error(f"Error calculating pair score: {e}")
            return 0
            
        return score

    async def get_trending_pairs(self, chain="ethereum"):
        """Get trending pairs from DexScreener"""
        try:
            cache_key = f"trending_{chain}"
            if cache_key in self.trending_cache:
                cached_data = self.trending_cache[cache_key]
                if datetime.now() - cached_data['timestamp'] < self.cache_duration:
                    return cached_data['data']
            
            # Search for trending pairs on Ethereum using search endpoint
            url = "https://api.dexscreener.com/latest/dex/search?q=trending"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        pairs = []
                        seen_pairs = set()  # Track unique pairs
                        
                        if data.get('pairs'):
                            # Filter and sort pairs
                            for pair in data['pairs']:
                                # Only get Ethereum mainnet pairs
                                if pair.get('chainId') != "ethereum":
                                    continue
                                    
                                # Skip pairs where either token is WETH
                                base_address = pair['baseToken'].get('address', '').lower()
                                quote_address = pair['quoteToken'].get('address', '').lower()
                                weth_address = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2".lower()
                                if (base_address == weth_address or 
                                    quote_address == weth_address):
                                    continue
                                    
                                # Skip duplicate pairs
                                pair_key = f"{base_address}_{quote_address}"
                                if pair_key in seen_pairs:
                                    continue
                                seen_pairs.add(pair_key)
                                
                                # Calculate score based on metrics
                                score = self._calculate_pair_score(pair)
                                if score > 0:
                                    pairs.append({
                                        'token_address': base_address,
                                        'token_name': pair['baseToken'].get('name', 'Unknown'),
                                        'token_symbol': pair['baseToken'].get('symbol', 'Unknown'),
                                        'price_usd': float(pair.get('priceUsd', 0)),
                                        'price_change_5m': float(pair.get('priceChange', {}).get('m5', 0)),
                                        'price_change_1h': float(pair.get('priceChange', {}).get('h1', 0)),
                                        'liquidity_usd': float(pair.get('liquidity', {}).get('usd', 0)),
                                        'volume_24h': float(pair.get('volume', {}).get('h24', 0)),
                                        'pair_address': pair.get('pairAddress'),
                                        'dex_id': pair.get('dexId'),
                                        'score': score
                                    })
                            
                            # Sort by score
                            pairs.sort(key=lambda x: x['score'], reverse=True)
                            
                            # Cache the results
                            self.trending_cache[cache_key] = {
                                'data': pairs,
                                'timestamp': datetime.now()
                            }
                            
                            return pairs[:20]  # Return top 20 pairs
                            
                    logger.error(f"Error getting trending pairs: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error fetching trending pairs: {str(e)}")
            return []

    async def analyze_token(self, token_address: str) -> Optional[Dict]:
        """Analyze a specific token for trading potential."""
        try:
            url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if not data.get('pairs'):
                            return None
                            
                        # Get the most liquid pair for the token
                        eth_pairs = [p for p in data['pairs'] if p.get('chainId') == 'ethereum']
                        if not eth_pairs:
                            return None
                            
                        # Sort by liquidity and get the most liquid pair
                        eth_pairs.sort(key=lambda x: float(x.get('liquidity', {}).get('usd', 0)), reverse=True)
                        pair = eth_pairs[0]
                        
                        # Calculate score
                        score = self._calculate_pair_score(pair)
                        
                        return {
                            'token_address': token_address,
                            'token_name': pair['baseToken'].get('name', 'Unknown'),
                            'token_symbol': pair['baseToken'].get('symbol', 'Unknown'),
                            'price_usd': float(pair.get('priceUsd', 0)),
                            'price_change_5m': float(pair.get('priceChange', {}).get('m5', 0)),
                            'price_change_1h': float(pair.get('priceChange', {}).get('h1', 0)),
                            'liquidity_usd': float(pair.get('liquidity', {}).get('usd', 0)),
                            'volume_24h': float(pair.get('volume', {}).get('h24', 0)),
                            'pair_address': pair.get('pairAddress'),
                            'dex_id': pair.get('dexId'),
                            'score': score
                        }
                        
            return None
            
        except Exception as e:
            logger.error(f"Error analyzing token: {str(e)}")
            return None

    async def get_pair_data(self, token_address: str) -> Optional[Dict]:
        """Get pair data for a specific token."""
        try:
            url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if not data.get('pairs'):
                            return None
                            
                        # Get the most liquid pair for the token
                        eth_pairs = [p for p in data['pairs'] if p.get('chainId') == 'ethereum']
                        if not eth_pairs:
                            return None
                            
                        # Sort by liquidity and get the most liquid pair
                        eth_pairs.sort(key=lambda x: float(x.get('liquidity', {}).get('usd', 0)), reverse=True)
                        return eth_pairs[0]
                        
            return None
            
        except Exception as e:
            logger.error(f"Error getting pair data: {str(e)}")
            return None

    async def get_eth_price(self) -> Optional[float]:
        """Get current ETH price in USD."""
        try:
            # Use WETH address to get ETH price
            weth_address = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
            url = f"https://api.dexscreener.com/latest/dex/tokens/{weth_address}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if not data.get('pairs'):
                            return None
                            
                        # Get the most liquid WETH/USDC or WETH/USDT pair
                        eth_pairs = [p for p in data['pairs'] if p.get('chainId') == 'ethereum']
                        if not eth_pairs:
                            return None
                            
                        # Sort by liquidity and get the most liquid pair
                        eth_pairs.sort(key=lambda x: float(x.get('liquidity', {}).get('usd', 0)), reverse=True)
                        return float(eth_pairs[0].get('priceUsd', 0))
                        
            return None
            
        except Exception as e:
            logger.error(f"Error getting ETH price: {str(e)}")
            return None

    async def get_token_market_data(self, token_address):
        """Get token market data from DexScreener API."""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        pairs = data.get('pairs', [])
                        
                        if not pairs:
                            return {
                                'price': 0,
                                'liquidity': 0,
                                'volume_24h': 0,
                                'price_change_24h': 0
                            }
                            
                        # Get the pair with highest liquidity
                        best_pair = max(pairs, key=lambda x: float(x.get('liquidity', {}).get('usd', 0)))
                        
                        return {
                            'price': float(best_pair.get('priceUsd', 0)),
                            'liquidity': float(best_pair.get('liquidity', {}).get('usd', 0)),
                            'volume_24h': float(best_pair.get('volume', {}).get('h24', 0)),
                            'price_change_24h': float(best_pair.get('priceChange', {}).get('h24', 0))
                        }
                    else:
                        logger.error(f"Error fetching token data: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error getting token market data: {e}")
            return None
