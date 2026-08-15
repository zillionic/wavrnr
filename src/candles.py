from datetime import datetime, timezone

from exchange import get_exchange, get_futures_exchange, get_public_exchange


def fetch_candles(symbol="BTC/USDT", timeframe="5m", limit=10):
    exchange = get_exchange()
    return exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)


def fetch_history(symbol="BTC/USDT", timeframe="5m", days=30):
    """Paginate through mainnet public candles to cover a multi-day range."""
    exchange = get_public_exchange()
    timeframe_ms = exchange.parse_timeframe(timeframe) * 1000
    since = exchange.milliseconds() - days * 24 * 60 * 60 * 1000

    all_candles = []
    while True:
        batch = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=1000)
        if not batch:
            break
        all_candles += batch
        since = batch[-1][0] + timeframe_ms
        if len(batch) < 1000:
            break
    return all_candles


def fetch_funding_history(symbol="BTC/USDT:USDT", days=30):
    """Paginate through real historical funding rates for a USDT-margined
    perpetual (charged/paid roughly every 8h). Returns ccxt's unified
    [{timestamp, fundingRate, ...}, ...] sorted oldest first."""
    exchange = get_futures_exchange()
    since = exchange.milliseconds() - days * 24 * 60 * 60 * 1000

    all_rates = []
    while True:
        batch = exchange.fetch_funding_rate_history(symbol, since=since, limit=1000)
        if not batch:
            break
        all_rates += batch
        since = batch[-1]["timestamp"] + 1
        if len(batch) < 1000:
            break
    return all_rates


def main() -> None:
    candles = fetch_candles()
    print(f"{'time':<20} {'open':>10} {'high':>10} {'low':>10} {'close':>10} {'volume':>12}")
    for timestamp, open_, high, low, close, volume in candles:
        time = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
        print(f"{time.strftime('%Y-%m-%d %H:%M'):<20} {open_:>10} {high:>10} {low:>10} {close:>10} {volume:>12}")


if __name__ == "__main__":
    main()
