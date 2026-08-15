from datetime import datetime, timezone

from candles import fetch_history
from strategy import TAKE_PROFIT_PCT, DipBuyStrategy

DAYS = 365


def main() -> None:
    candles = fetch_history(timeframe="5m", days=DAYS)
    strategy = DipBuyStrategy(seed=1.0)

    last_price = None
    for timestamp, open_, high, low, close, volume in candles:
        time = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
        strategy.step(close, time)
        last_price = close

    cycles = strategy.cycles
    wins = [c for c in cycles if c.return_pct > 0]

    print(f"백테스트 기간: 최근 {DAYS}일 ({len(candles)}개 5분봉)")
    print(f"완료된 사이클: {len(cycles)}건")

    if cycles:
        avg_return = sum(c.return_pct for c in cycles) / len(cycles)
        max_buys = max(c.num_buys for c in cycles)
        stop_losses = [c for c in cycles if c.exit_reason == "stop_loss"]
        print(f"승률: {len(wins)}/{len(cycles)} ({len(wins) / len(cycles) * 100:.0f}%)")
        print(f"사이클당 평균 수익률: {avg_return:+.2f}%")
        print(f"사이클 내 최대 매수 횟수: {max_buys}회")
        print(f"손절로 종료된 사이클: {len(stop_losses)}건")

    if strategy.buy_count > 0:
        avg_price = strategy.cycle_invested / strategy.btc
        target_price = strategy.first_buy_price * (1 + TAKE_PROFIT_PCT)
        print(
            f"\n현재 미청산 포지션: {strategy.buy_count}회 매수, "
            f"마지막 매수가 {strategy.last_buy_price}, 첫 매수가 {strategy.first_buy_price}, 평단가 {avg_price:.2f}, "
            f"목표 매도가(첫 매수가 +{TAKE_PROFIT_PCT * 100:.0f}%) {target_price:.2f}"
        )

    if last_price is not None:
        final_equity = strategy.equity(last_price)
        total_return = (final_equity - strategy.seed) / strategy.seed * 100
        print(f"\n전체 기간 수익률(미실현 포함): {total_return:+.2f}%")

    if cycles:
        print("\n사이클별 상세:")
        for c in cycles:
            entry = c.entry_time.strftime("%Y-%m-%d %H:%M")
            exit_ = c.exit_time.strftime("%Y-%m-%d %H:%M")
            tag = " [손절]" if c.exit_reason == "stop_loss" else ""
            print(f"  {entry} ~ {exit_}  매수 {c.num_buys}회  수익률 {c.return_pct:+.2f}%{tag}")


if __name__ == "__main__":
    main()
