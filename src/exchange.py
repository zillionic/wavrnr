import ccxt

from config import BINANCE_API_KEY, BINANCE_API_SECRET


def get_exchange() -> ccxt.binance:
    exchange = ccxt.binance({
        "apiKey": BINANCE_API_KEY,
        "secret": BINANCE_API_SECRET,
    })
    exchange.set_sandbox_mode(True)
    return exchange


def get_public_exchange() -> ccxt.binance:
    """Mainnet, no API key. Market data (candles) is public and free —
    testnet is skipped here because its history is shallow and gets
    periodically wiped, which makes it unfit for backtesting."""
    return ccxt.binance()
