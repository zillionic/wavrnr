from datetime import datetime, timezone

from exchange import get_exchange


def fetch_candles(symbol="BTC/USDT", timeframe="5m", limit=10):
    exchange = get_exchange()
    return exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)


def main() -> None:
    candles = fetch_candles()
    print(f"{'time':<20} {'open':>10} {'high':>10} {'low':>10} {'close':>10} {'volume':>12}")
    for timestamp, open_, high, low, close, volume in candles:
        time = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
        print(f"{time.strftime('%Y-%m-%d %H:%M'):<20} {open_:>10} {high:>10} {low:>10} {close:>10} {volume:>12}")


if __name__ == "__main__":
    main()
