"""
Dynamic Crypto Ticker Fetcher
Fetches available trading pairs from multiple exchanges and maintains an up-to-date list.
Refreshes daily to catch new listings.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Set, Optional
import httpx

logger = logging.getLogger(__name__)

# Cache file location
TICKER_CACHE_FILE = os.path.join(
    os.getenv("ANALYTICS_DATA_DIR", "data"),
    "crypto_tickers_cache.json"
)

# Fallback static list (used if all API calls fail)
FALLBACK_TICKERS = {
    'btc', 'eth', 'sol', 'xrp', 'bnb', 'ada', 'doge', 'dot', 'matic', 'link',
    'avax', 'shib', 'ltc', 'atom', 'uni', 'xlm', 'etc', 'hbar', 'fil', 'apt',
    'near', 'arb', 'vet', 'op', 'inj', 'grt', 'imx', 'rune', 'aave', 'algo',
    'sui', 'sei', 'tia', 'jup', 'pyth', 'pepe', 'bonk', 'wif', 'floki', 'ton',
    'trx', 'bch', 'leo', 'okb', 'kas', 'render', 'fet', 'ar', 'stx', 'mnt',
    'zec', 'xmr', 'eos', 'flow', 'sand', 'mana', 'axs', 'gala', 'enj', 'chz',
}


class TickerFetcher:
    """Fetches and caches crypto tickers from multiple exchanges."""
    
    def __init__(self):
        self.tickers: Set[str] = set()
        self.last_fetch: Optional[datetime] = None
        self.fetch_interval_hours = 24  # Refresh once per day
        self._lock = asyncio.Lock()
    
    async def get_tickers(self) -> Set[str]:
        """Get current tickers, fetching if needed."""
        async with self._lock:
            # Check if we need to refresh
            if self._should_refresh():
                await self._fetch_all_tickers()
            
            # Return cached tickers or fallback
            if self.tickers:
                return self.tickers
            
            # Try loading from cache file
            cached = self._load_from_cache()
            if cached:
                self.tickers = cached
                return self.tickers
            
            # Ultimate fallback
            logger.warning("Using fallback ticker list")
            return FALLBACK_TICKERS
    
    def _should_refresh(self) -> bool:
        """Check if we should refresh tickers."""
        if not self.last_fetch:
            return True
        elapsed = datetime.now() - self.last_fetch
        return elapsed > timedelta(hours=self.fetch_interval_hours)
    
    async def _fetch_all_tickers(self) -> None:
        """Fetch tickers from all exchanges."""
        logger.info("🔄 Fetching crypto tickers from exchanges...")
        
        all_tickers: Set[str] = set()
        
        # Fetch from multiple sources in parallel
        results = await asyncio.gather(
            self._fetch_exchange_1(),  # First exchange
            self._fetch_exchange_2(),  # Second exchange
            return_exceptions=True
        )
        
        for result in results:
            if isinstance(result, set):
                all_tickers.update(result)
            elif isinstance(result, Exception):
                logger.error(f"Exchange fetch error: {result}")
        
        if all_tickers:
            self.tickers = all_tickers
            self.last_fetch = datetime.now()
            self._save_to_cache()
            logger.info(f"✅ Fetched {len(all_tickers)} unique tickers from exchanges")
        else:
            logger.warning("⚠️ Failed to fetch tickers from any exchange")
    
    async def _fetch_exchange_1(self) -> Set[str]:
        """Fetch tickers from first exchange (spot market)."""
        tickers: Set[str] = set()
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Spot tickers
                response = await client.get(
                    "https://api.bybit.com/v5/market/tickers",
                    params={"category": "spot"}
                )
                data = response.json()
                
                if data.get('retCode') == 0:
                    for item in data.get('result', {}).get('list', []):
                        symbol = item.get('symbol', '')
                        ticker = self._extract_ticker(symbol)
                        if ticker:
                            tickers.add(ticker)
                
                # Also fetch linear (futures) for more coverage
                response = await client.get(
                    "https://api.bybit.com/v5/market/tickers",
                    params={"category": "linear"}
                )
                data = response.json()
                
                if data.get('retCode') == 0:
                    for item in data.get('result', {}).get('list', []):
                        symbol = item.get('symbol', '')
                        ticker = self._extract_ticker(symbol)
                        if ticker:
                            tickers.add(ticker)
                
                logger.info(f"📊 Exchange 1: {len(tickers)} tickers")
                
        except Exception as e:
            logger.error(f"Exchange 1 fetch error: {e}")
        
        return tickers
    
    async def _fetch_exchange_2(self) -> Set[str]:
        """Fetch tickers from second exchange."""
        tickers: Set[str] = set()
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Binance exchange info endpoint
                response = await client.get(
                    "https://api.binance.com/api/v3/exchangeInfo"
                )
                data = response.json()
                
                for symbol_info in data.get('symbols', []):
                    base = symbol_info.get('baseAsset', '').lower()
                    if 2 <= len(base) <= 10:
                        tickers.add(base)
                
                logger.info(f"📊 Exchange 2: {len(tickers)} tickers")
                
        except Exception as e:
            logger.error(f"Exchange 2 fetch error: {e}")
        
        return tickers
    
    def _extract_ticker(self, symbol: str) -> Optional[str]:
        """Extract base ticker from trading pair symbol."""
        # Common quote currencies to strip
        suffixes = ['USDT', 'USDC', 'USD', 'BUSD', 'BTC', 'ETH', 'EUR', 'DAI', 'TUSD', 'PERP']
        
        symbol_upper = symbol.upper()
        for suffix in suffixes:
            if symbol_upper.endswith(suffix):
                ticker = symbol_upper[:-len(suffix)].lower()
                # Valid ticker: 2-10 chars, alphanumeric
                if 2 <= len(ticker) <= 10 and ticker.isalnum():
                    return ticker
        
        return None
    
    def _save_to_cache(self) -> None:
        """Save tickers to cache file."""
        try:
            os.makedirs(os.path.dirname(TICKER_CACHE_FILE), exist_ok=True)
            cache_data = {
                'tickers': list(self.tickers),
                'last_fetch': self.last_fetch.isoformat() if self.last_fetch else None,
                'count': len(self.tickers)
            }
            with open(TICKER_CACHE_FILE, 'w') as f:
                json.dump(cache_data, f, indent=2)
            logger.debug(f"💾 Cached {len(self.tickers)} tickers to {TICKER_CACHE_FILE}")
        except Exception as e:
            logger.error(f"Error saving ticker cache: {e}")
    
    def _load_from_cache(self) -> Optional[Set[str]]:
        """Load tickers from cache file."""
        try:
            if os.path.exists(TICKER_CACHE_FILE):
                with open(TICKER_CACHE_FILE, 'r') as f:
                    cache_data = json.load(f)
                
                # Check if cache is still valid (less than 48 hours old)
                last_fetch_str = cache_data.get('last_fetch')
                if last_fetch_str:
                    last_fetch = datetime.fromisoformat(last_fetch_str)
                    if datetime.now() - last_fetch < timedelta(hours=48):
                        tickers = set(cache_data.get('tickers', []))
                        self.last_fetch = last_fetch
                        logger.info(f"📂 Loaded {len(tickers)} tickers from cache")
                        return tickers
                    else:
                        logger.info("⏰ Cache expired, will refresh")
        except Exception as e:
            logger.error(f"Error loading ticker cache: {e}")
        
        return None
    
    async def force_refresh(self) -> int:
        """Force refresh tickers (admin command)."""
        async with self._lock:
            self.last_fetch = None  # Force refresh
            await self._fetch_all_tickers()
            return len(self.tickers)
    
    def is_valid_ticker(self, ticker: str) -> bool:
        """Check if a string is a valid crypto ticker."""
        ticker_lower = ticker.lower().strip()
        
        # Check against our dynamic list
        if self.tickers and ticker_lower in self.tickers:
            return True
        
        # Check against fallback
        if ticker_lower in FALLBACK_TICKERS:
            return True
        
        return False


# Global instance
ticker_fetcher = TickerFetcher()


async def get_crypto_tickers() -> Set[str]:
    """Get current crypto tickers (convenience function)."""
    return await ticker_fetcher.get_tickers()


async def is_crypto_ticker(ticker: str) -> bool:
    """Check if string is a valid crypto ticker."""
    tickers = await ticker_fetcher.get_tickers()
    return ticker.lower().strip() in tickers


async def refresh_tickers() -> int:
    """Force refresh tickers and return count."""
    return await ticker_fetcher.force_refresh()
