from dataclasses import dataclass
from datetime import datetime, timezone

from candles import fetch_candles

FIRST_DROP_PCT = 0.03
REBUY_DROP_PCT = 0.01
TAKE_PROFIT_PCT = 0.02  # off the first buy price (entry), not the average cost or last buy
STOP_LOSS_PCT = 0.04
MAX_BUYS = 10
SEED_FRACTION_PER_BUY = 0.10
FEE_PCT = 0.001  # Binance spot default taker fee, no BNB discount


@dataclass
class Trade:
    action: str  # "buy" or "sell"
    price: float
    time: datetime
    buy_count: int


@dataclass
class Cycle:
    entry_time: datetime
    exit_time: datetime
    num_buys: int
    invested: float
    proceeds: float
    exit_reason: str  # "target" or "stop_loss"
    seed: float  # total portfolio seed at the time, for portfolio-relative return

    @property
    def return_pct(self) -> float:
        """Return relative to the total seed (principal), not just the capital
        this cycle deployed — e.g. a cycle that used 10% of seed and made
        9.44% on that slice shows here as 0.94%."""
        return (self.proceeds - self.invested) / self.seed * 100


class DipBuyStrategy:
    def __init__(self, seed: float = 1.0):
        self.seed = seed
        self.cash = seed
        self.btc = 0.0
        self.day_high = None
        self.day_high_date = None
        self.first_buy_price = None
        self.last_buy_price = None
        self.buy_count = 0
        self.cycle_entry_time = None
        self.cycle_invested = 0.0
        self.trades: list[Trade] = []
        self.cycles: list[Cycle] = []

    def step(self, price: float, time: datetime) -> None:
        if self.buy_count == 0:
            self._update_day_high(price, time)
            if self.day_high is not None and price <= self.day_high * (1 - FIRST_DROP_PCT):
                self._buy(price, time)
            return

        if price >= self.first_buy_price * (1 + TAKE_PROFIT_PCT):
            self._sell(price, time, reason="target")
            return

        if price <= self.first_buy_price * (1 - STOP_LOSS_PCT):
            self._sell(price, time, reason="stop_loss")
            return

        if self.buy_count < MAX_BUYS and price <= self.last_buy_price * (1 - REBUY_DROP_PCT):
            self._buy(price, time)

    def equity(self, mark_price: float) -> float:
        return self.cash + self.btc * mark_price

    def _update_day_high(self, price: float, time: datetime) -> None:
        date = time.date()
        if self.day_high_date != date:
            self.day_high_date = date
            self.day_high = price
        else:
            self.day_high = max(self.day_high, price)

    def _buy(self, price: float, time: datetime) -> None:
        if self.buy_count == 0:
            self.first_buy_price = price
            self.cycle_entry_time = time
            self.cycle_invested = 0.0
        amount = self.seed * SEED_FRACTION_PER_BUY
        self.cash -= amount
        self.btc += (amount / price) * (1 - FEE_PCT)
        self.cycle_invested += amount
        self.buy_count += 1
        self.last_buy_price = price
        self.trades.append(Trade("buy", price, time, self.buy_count))

    def _sell(self, price: float, time: datetime, reason: str) -> None:
        proceeds = self.btc * price * (1 - FEE_PCT)
        self.cash += proceeds
        self.cycles.append(
            Cycle(self.cycle_entry_time, time, self.buy_count, self.cycle_invested, proceeds, reason, self.seed)
        )
        self.trades.append(Trade("sell", price, time, self.buy_count))
        self.btc = 0.0
        self.buy_count = 0
        self.first_buy_price = None
        self.last_buy_price = None
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
