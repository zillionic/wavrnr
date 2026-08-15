import ccxt

from config import BINANCE_API_KEY, BINANCE_API_SECRET


def get_exchange() -> ccxt.binance:
    exchange = ccxt.binance({
        "apiKey": BINANCE_API_KEY,
        "secret": BINANCE_API_SECRET,
    })
    exchange.set_sandbox_mode(True)
    return exchange
