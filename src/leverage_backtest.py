from datetime import datetime, timezone

from candles import fetch_funding_history, fetch_history
from leverage import LEVERAGE, TAKER_FEE_PCT, LeveragedStrategy

DAYS = 365 * 5
TIMEFRAME = "5m"  # 1m would mean 2,600+ requests for 5 years — too slow
SEED_KRW = 1_000_000
KRW_PER_USD = 1417  # approximate USD/KRW rate (Aug 2026) — price data below is USDT-denominated
SEED_USDT = SEED_KRW / KRW_PER_USD


def krw(amount_usdt: float) -> str:
    """amount_usdt is in the strategy's native unit (USDT-equivalent); convert to KRW for display."""
    return f"{amount_usdt * KRW_PER_USD:,.0f}원"


def main() -> None:
    candles = fetch_history(timeframe=TIMEFRAME, days=DAYS)
    funding_events = fetch_funding_history(days=DAYS)
    strategy = LeveragedStrategy(seed=SEED_USDT)

    funding_idx = 0
    last_price = None
    for timestamp, open_, high, low, close, volume in candles:
        while funding_idx < len(funding_events) and funding_events[funding_idx]["timestamp"] <= timestamp:
            strategy.apply_funding(close, funding_events[funding_idx]["fundingRate"])
            funding_idx += 1

        time = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
        strategy.step(close, time)
        last_price = close

    cycles = strategy.cycles
    wins = [c for c in cycles if c.return_pct > 0]
    liquidations = [c for c in cycles if c.exit_reason == "liquidated"]
    stop_losses = [c for c in cycles if c.exit_reason == "stop_loss"]

    print(f"백테스트 기간: 최근 {DAYS}일 ({len(candles)}개 {TIMEFRAME}봉), 레버리지 {LEVERAGE}배")
    print(f"선물 수수료 {TAKER_FEE_PCT * 100:.3f}%/건, 펀딩비 {len(funding_events)}건 실데이터 반영")
    print(f"시작 자금: {krw(SEED_USDT)} (환율 {KRW_PER_USD}원/달러 가정)")
    print(f"완료된 사이클: {len(cycles)}건")

    if cycles:
        avg_return = sum(c.return_pct for c in cycles) / len(cycles)
        max_buys = max(c.num_buys for c in cycles)
        print(f"승률: {len(wins)}/{len(cycles)} ({len(wins) / len(cycles) * 100:.0f}%)")
        print(f"사이클당 평균 수익률: {avg_return:+.2f}%")
        print(f"사이클 내 최대 매수 횟수: {max_buys}회")
        print(f"손절로 종료된 사이클: {len(stop_losses)}건")
        print(f"청산으로 종료된 사이클: {len(liquidations)}건")

    if strategy.buy_count > 0:
        print(
            f"\n현재 미청산 포지션: {strategy.buy_count}회 매수, "
            f"평단가 {strategy.avg_entry_price:.2f}, 청산가(추정) {strategy.liquidation_price:.2f}"
        )

    final_equity = strategy.equity(last_price) if last_price is not None else strategy.cash
    total_return = (final_equity - SEED_USDT) / SEED_USDT * 100
    print(f"\n최종 잔고: {krw(final_equity)}  (누적 손익: {krw(final_equity - SEED_USDT)}, {total_return:+.2f}%)")

    if cycles:
        print("\n사이클별 상세 (손익금액 / 누적잔고):")
        running_balance = SEED_USDT
        for c in cycles:
            running_balance += c.pnl
            entry = c.entry_time.strftime("%Y-%m-%d %H:%M")
            exit_ = c.exit_time.strftime("%Y-%m-%d %H:%M")
            tag = {"stop_loss": " [손절]", "liquidated": " [청산!]"}.get(c.exit_reason, "")
            print(
                f"  {entry} ~ {exit_}  매수 {c.num_buys}회  {c.return_pct:+6.2f}%  "
                f"{krw(c.pnl):>14}  ->  잔고 {krw(running_balance)}{tag}"
            )


if __name__ == "__main__":
    main()
