# wavrnr

바이낸스 API 기반 자체 개발 트레이딩 봇 (취미 프로젝트).

TradingView 없이, Python + [ccxt](https://github.com/ccxt/ccxt)로 직접 시세를 받아
전략을 판단하고 주문을 넣는 구조로 만듭니다.

## 진행 방식

천천히, 단계별로 쌓아갑니다.

1. [x] 프로젝트 뼈대 + 바이낸스 테스트넷 연결 확인
2. [x] 캔들 데이터 수집
3. [x] 전략 룰 작성 (고점 대비 하락폭 기반 분할매수 / 전고점 회복 시 전량매도)
4. [x] 백테스트 (손익 계산 포함)
5. [ ] 테스트넷 모의 주문
6. [ ] (검증되면) 실거래 소액 적용

## 전략 요약

- 시드를 10등분해서, 하루 고점 대비 -1.5% 하락 시 1차 매수
- 마지막 매수가 대비 추가 -2.5% 하락마다 다음 매수 (최대 10회 = 시드 100%)
- 최초 매수를 유발한 고점을 다시 넘으면 전량 매도, 처음부터 재시작
- 손절: 10회를 다 매수한 뒤에도 마지막 매수가에서 추가로 -2.5% 더 빠지면 전량 강제 매도 (무기한 보유 방지)

## 시작하기

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# .env에 바이낸스 테스트넷 API 키 입력 (아래 "테스트넷 키 발급" 참고)

python src/main.py
```

정상이면 BTC/USDT 현재가가 출력됩니다.

## 테스트넷 키 발급

실거래소가 아닌 [Binance Spot Testnet](https://testnet.binance.vision/)에서
가짜 자금으로 먼저 검증합니다. 실계좌 API 키와는 별개입니다.

1. https://testnet.binance.vision/ 접속 후 GitHub 계정으로 로그인
2. API Key 생성 (출금 권한 없음, 테스트넷 전용이라 안전)
3. `.env`에 `BINANCE_API_KEY`, `BINANCE_API_SECRET`으로 저장

## 주의

- 실거래 API 키는 절대 커밋하지 않습니다 (`.env`는 `.gitignore`에 포함).
- 실계좌 키를 쓸 경우 출금(withdraw) 권한은 반드시 꺼두세요.
