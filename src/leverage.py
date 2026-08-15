from dataclasses import dataclass
from datetime import datetime, timezone

from strategy import (
    COOLDOWN,
    FIRST_DROP_PCT,
    MAX_BUYS,
    REBUY_DROP_PCT,
    SEED_INCREMENT_PCT,
    STOP_LOSS_PCT,
    TAKE_PROFIT_PCT,
)

LEVERAGE = 5
TAKER_FEE_PCT = 0.0004  # Binance USDS-M futures taker fee, no BNB/VIP discount
MAINTENANCE_MARGIN_PCT = 0.005  # flat approximation — real rate is tiered by position notional


@dataclass
class Cycle:
    entry_time: datetime
    exit_time: datetime
    num_buys: int
    margin_used: float
    pnl: float  # net of entry/exit fees and funding paid during the hold
    exit_reason: str  # "target", "stop_loss", or "liquidated"
    seed: float

    @property
    def return_pct(self) -> float:
        return self.pnl / self.seed * 100


class LeveragedStrategy:
    def __init__(self, seed: float = 1.0):
        self.seed = seed
        self.cash = seed
        self.day_high = None
        self.day_high_date = None
        self.last_buy_price = None
        self.buy_count = 0
        self.cycle_entry_time = None
        self.margin_used = 0.0
        self.notional_invested = 0.0  # sum of (margin * leverage) across tranches
        self.position_btc = 0.0
        self.fees_paid = 0.0
        self.funding_paid = 0.0
        self.cycle_seed = None  # balance at this cycle's first buy — the 100% basis for its sizing
        self.cooldown_until = None
        self.cycles: list[Cycle] = []

    @property
    def avg_entry_price(self) -> float:
        return self.notional_invested / self.position_btc

    @property
    def liquidation_price(self) -> float:
        return self.avg_entry_price * (1 - (1 / LEVERAGE - MAINTENANCE_MARGIN_PCT))

    def step(self, price: float, time: datetime) -> None:
        if self.buy_count == 0:
            self._update_day_high(price, time)
            if self.cooldown_until is not None and time < self.cooldown_until:
                return
            if self.day_high is not None and price <= self.day_high * (1 - FIRST_DROP_PCT):
                self._buy(price, time)
            return

        if price <= self.liquidation_price:
            self._close(price, time, reason="liquidated", total_loss=True)
            return

        if price >= self.day_high * (1 + TAKE_PROFIT_PCT):
            self._close(price, time, reason="target")
            return

        if price <= self.day_high * (1 - STOP_LOSS_PCT):
            self._close(price, time, reason="stop_loss")
            return

        if self.buy_count < MAX_BUYS and price <= self.last_buy_price * (1 - REBUY_DROP_PCT):
            self._buy(price, time)

    def apply_funding(self, price: float, funding_rate: float) -> None:
        """A positive rate means longs pay shorts (a cost to us)."""
        if self.buy_count == 0:
            return
        cost = self.position_btc * price * funding_rate
        self.cash -= cost
        self.funding_paid += cost

    def equity(self, mark_price: float) -> float:
        if self.buy_count == 0:
            return self.cash
        unrealized = self.position_btc * mark_price - self.notional_invested
        return self.cash + self.margin_used + unrealized

    def _update_day_high(self, price: float, time: datetime) -> None:
        date = time.date()
        if self.day_high_date != date:
            self.day_high_date = date
            self.day_high = price
        else:
            self.day_high = max(self.day_high, price)

    def _buy(self, price: float, time: datetime) -> None:
        if self.buy_count == 0:
            self.cycle_entry_time = time
            self.margin_used = 0.0
            self.notional_invested = 0.0
            self.position_btc = 0.0
            self.fees_paid = 0.0
            self.funding_paid = 0.0
            self.cycle_seed = self.cash

        buy_number = self.buy_count + 1
        margin_amount = self.cycle_seed * SEED_INCREMENT_PCT * buy_number
        if margin_amount > self.cash + 1e-9:
            return
        margin_amount = min(margin_amount, self.cash)

        notional_amount = margin_amount * LEVERAGE
        fee = notional_amount * TAKER_FEE_PCT

        self.cash -= margin_amount
        self.cash -= fee
        self.margin_used += margin_amount
        self.notional_invested += notional_amount
        self.position_btc += notional_amount / price
        self.fees_paid += fee
        self.buy_count += 1
        self.last_buy_price = price

    def _close(self, price: float, time: datetime, reason: str, total_loss: bool = False) -> None:
        if total_loss:
            pnl = -self.margin_used - self.fees_paid - self.funding_paid
        else:
            exit_notional = self.position_btc * price
            exit_fee = exit_notional * TAKER_FEE_PCT
            price_pnl = exit_notional - self.notional_invested
            self.cash += self.margin_used + price_pnl - exit_fee
            pnl = price_pnl - exit_fee - self.fees_paid - self.funding_paid

        self.cycles.append(
            Cycle(self.cycle_entry_time, time, self.buy_count, self.margin_used, pnl, reason, self.seed)
        )
        if reason in ("stop_loss", "liquidated"):
            self.cooldown_until = time + COOLDOWN

        self.buy_count = 0
        self.last_buy_price = None
        self.margin_used = 0.0
        self.notional_invested = 0.0
        self.position_btc = 0.0
        self.fees_paid = 0.0
        self.funding_paid = 0.0
        self.day_high = None
        self.day_high_date = None
