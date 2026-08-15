from dataclasses import dataclass
from datetime import datetime, timezone

from candles import fetch_candles

FIRST_DROP_PCT = 0.015
REBUY_DROP_PCT = 0.025
MAX_BUYS = 10
SEED_FRACTION_PER_BUY = 0.10


@dataclass
class Trade:
    action: str  # "buy" or "sell"
    price: float
    time: datetime
    buy_count: int


class DipBuyStrategy:
    def __init__(self):
        self.day_high = None
        self.day_high_date = None
        self.target_high = None
        self.last_buy_price = None
        self.buy_count = 0
        self.trades: list[Trade] = []

    def step(self, price: float, time: datetime) -> None:
        if self.buy_count == 0:
            self._update_day_high(price, time)
            if self.day_high is not None and price <= self.day_high * (1 - FIRST_DROP_PCT):
                self._buy(price, time)
            return

        if price >= self.target_high:
            self._sell(price, time)
            return

        if self.buy_count < MAX_BUYS and price <= self.last_buy_price * (1 - REBUY_DROP_PCT):
            self._buy(price, time)

    def _update_day_high(self, price: float, time: datetime) -> None:
        date = time.date()
        if self.day_high_date != date:
            self.day_high_date = date
            self.day_high = price
        else:
            self.day_high = max(self.day_high, price)

    def _buy(self, price: float, time: datetime) -> None:
        if self.buy_count == 0:
            self.target_high = self.day_high
        self.buy_count += 1
        self.last_buy_price = price
        self.trades.append(Trade("buy", price, time, self.buy_count))

    def _sell(self, price: float, time: datetime) -> None:
        self.trades.append(Trade("sell", price, time, self.buy_count))
        self.buy_count = 0
        self.last_buy_price = None
        self.target_high = None
        self.day_high = None
        self.day_high_date = None


def simulate(candles) -> list[Trade]:
    strategy = DipBuyStrategy()
    for timestamp, open_, high, low, close, volume in candles:
        time = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
        strategy.step(close, time)
    return strategy.trades


def main() -> None:
    candles = fetch_candles(timeframe="5m", limit=500)
    trades = simulate(candles)

    if not trades:
        print("신호 없음 (이 구간 동안 매수/매도 조건이 발생하지 않음)")
        return

    for trade in trades:
        seed_used = trade.buy_count * SEED_FRACTION_PER_BUY * 100
        time_str = trade.time.strftime("%Y-%m-%d %H:%M")
        if trade.action == "buy":
            print(f"{time_str}  BUY  #{trade.buy_count:>2}  price={trade.price:<12} (누적 시드 {seed_used:.0f}%)")
        else:
            print(f"{time_str}  SELL      price={trade.price:<12} ({trade.buy_count}회 매수분 전량 청산)")


if __name__ == "__main__":
    main()
