from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from candles import fetch_candles

FIRST_DROP_PCT = 0.015
WIDE_FIRST_DROP_PCT = 0.03  # entry threshold while in "downtrend" mode
LOSS_STREAK_TO_WIDEN = 3  # this many stop-losses in a row switches to WIDE_FIRST_DROP_PCT
WIN_STREAK_TO_NORMALIZE = 2  # this many wins in a row switches back to FIRST_DROP_PCT
REBUY_DROP_PCT = 0.01
TAKE_PROFIT_PCT = 0.01  # off the day's high, not the buy price
STOP_LOSS_PCT = 0.05  # off the day's high, not the buy price
WIDE_STOP_LOSS_PCT = 0.065  # stop-loss in downtrend mode — keeps the same 3.5pp gap as normal mode
MAX_BUYS = 10
SEED_INCREMENT_PCT = 0.10  # buy N uses N * this fraction of seed (10%, 20%, 30%, ...)
FEE_PCT = 0.001  # Binance spot default taker fee, no BNB discount
COOLDOWN = timedelta(hours=4)  # no re-entry for this long after a stop-loss


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
        self.cooldown_until = None
        self.entry_drop_pct = FIRST_DROP_PCT
        self.stop_loss_pct = STOP_LOSS_PCT
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.trades: list[Trade] = []
        self.cycles: list[Cycle] = []

    def step(self, price: float, time: datetime) -> None:
        if self.buy_count == 0:
            self._update_day_high(price, time)
            if self.cooldown_until is not None and time < self.cooldown_until:
                return
            if self.day_high is not None and price <= self.day_high * (1 - self.entry_drop_pct):
                self._buy(price, time)
            return

        if price >= self.day_high * (1 + TAKE_PROFIT_PCT):
            self._sell(price, time, reason="target")
            return

        if price <= self.day_high * (1 - self.stop_loss_pct):
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
        buy_number = self.buy_count + 1
        amount = self.seed * SEED_INCREMENT_PCT * buy_number
        if amount > self.cash + 1e-9:
            return
        amount = min(amount, self.cash)
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
        if reason == "stop_loss":
            self.cooldown_until = time + COOLDOWN
            self.consecutive_losses += 1
            self.consecutive_wins = 0
            if self.consecutive_losses >= LOSS_STREAK_TO_WIDEN:
                self.entry_drop_pct = WIDE_FIRST_DROP_PCT
                self.stop_loss_pct = WIDE_STOP_LOSS_PCT
        else:
            self.consecutive_wins += 1
            self.consecutive_losses = 0
            if self.consecutive_wins >= WIN_STREAK_TO_NORMALIZE:
                self.entry_drop_pct = FIRST_DROP_PCT
                self.stop_loss_pct = STOP_LOSS_PCT
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
        n = trade.buy_count
        seed_used = SEED_INCREMENT_PCT * 100 * n * (n + 1) / 2
        time_str = trade.time.strftime("%Y-%m-%d %H:%M")
        if trade.action == "buy":
            print(f"{time_str}  BUY  #{trade.buy_count:>2}  price={trade.price:<12} (누적 시드 {seed_used:.0f}%)")
        else:
            print(f"{time_str}  SELL      price={trade.price:<12} ({trade.buy_count}회 매수분 전량 청산)")


if __name__ == "__main__":
    main()
