from exchange import get_exchange


def main() -> None:
    exchange = get_exchange()
    ticker = exchange.fetch_ticker("BTC/USDT")
    print(f"BTC/USDT: {ticker['last']}")


if __name__ == "__main__":
    main()
