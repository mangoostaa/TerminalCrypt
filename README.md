# ◈ AZ TERMINAL — Professional Crypto WebSocket Terminal

Real-time cryptocurrency terminal built for the command line.

AZ TERMINAL streams live market data from multiple exchanges using pure WebSockets (zero polling), calculates technical indicators in real time, and renders a professional TUI dashboard directly in the terminal.

---

## Preview

```bash
◈ AZ TERMINAL v3.2
BTC   $105,432 ▲2.41%
ETH   $5,201   ▲1.88%
SOL   $224     ▼0.42%

RSI · EMA Cross · MACD · Bollinger Bands · ATR
Fear & Greed · Market Dominance · Live News
```

---

# Features

## Real-Time WebSocket Architecture

- Binance WebSocket streams
- Coinbase Advanced Trade WebSocket
- Kraken WebSocket
- Automatic reconnect logic
- Exchange failover support
- Zero polling for market streams

Latency:
- Binance: typically <50ms
- Live tick rendering
- Incremental updates

---

# Technical Indicators

Built-in indicators calculated live:

| Indicator | Description |
|---|---|
| RSI(14) | Overbought / Oversold |
| EMA 9/21 | Trend crossover |
| MACD(12,26,9) | Momentum |
| Bollinger Bands | Volatility zones |
| ATR(14) | Relative volatility |
| Combined Signal Engine | LONG / SHORT scoring |

---

# Dashboard

Professional terminal dashboard using Rich:

- Live ticker strip
- Multi-category rotating market table
- Fear & Greed Index
- Global crypto market stats
- Live crypto news
- WebSocket diagnostics
- Spread & relative volume
- Sparkline mini charts
- Keyboard view switcher
- Coinbase Top 5 quantitative ranking
- Telegram surge alerts

---

# Supported Assets

~80+ pairs on Binance  
~50+ pairs on Coinbase  
~35+ pairs on Kraken

Categories:
- Mega Cap
- Layer 1 / Layer 2
- DeFi
- AI / Web3
- NFT / Gaming
- Memecoins
- Privacy coins

---

# Installation

## Requirements

- Python 3.10+
- Rust toolchain, for the accelerated indicator backend
- Linux / macOS / Windows

## Install dependencies

```bash
pip install websocket-client requests rich
```

## Install package

```bash
pip install -e .
```

TerminalCrypt builds the preferred Rust indicator backend with maturin. If the
Rust extension is not available, the app falls back to the older Cython backend
and then to pure Python.

```bash
pip install maturin
maturin build --release
pip install target/wheels/terminalcrypt-*.whl
```

## Configuration

Copy `terminalcrypt.toml.example` to `terminalcrypt.toml` to set local defaults:

```toml
[terminalcrypt]
source = "binance"
initial_view = "markets"
selected_symbol = "BTC"
refresh_per_second = 2
rest_enabled = true
telegram_enabled = true
log_file = "logs/terminalcrypt.log"
log_level = "INFO"
fg_interval = 300
global_interval = 120
news_interval = 180
```

Every key can also be overridden with an environment variable prefixed with
`TERMINALCRYPT_`, for example `TERMINALCRYPT_SOURCE=kraken`.

## Clone repository

```bash
git clone https://github.com/YOUR_USERNAME/az-terminal.git
cd az-terminal
```

---

# Usage

## Start live dashboard

```bash
python3 cryptex_terminal.py
```

## Start via package entrypoint

```bash
python -m terminalcrypt
```

## Use Coinbase feed

```bash
python3 cryptex_terminal.py --source coinbase
```

Press `TAB` or `I` in the live dashboard to switch between the rotating markets table and the Coinbase quantitative Top 5 view. Press `M` to return to markets.

## Use Kraken feed

```bash
python3 cryptex_terminal.py --source kraken
```

## Run tests

```bash
python -m unittest discover -s tests
```

## One-time snapshot

```bash
python3 cryptex_terminal.py --once
```

## Price alerts

```bash
python3 cryptex_terminal.py --alert BTC 100000
```

## Optional CoinGecko API key

CoinGecko requests use `COINGECKO_API_KEY` when the environment variable is set:

```bash
set COINGECKO_API_KEY=your_key_here
python3 cryptex_terminal.py
```

On Linux/macOS:

```bash
export COINGECKO_API_KEY=your_key_here
python3 cryptex_terminal.py
```

## Telegram surge alerts

Set a Telegram bot token and chat id to receive alerts when a symbol is rising fast:

```bash
set TELEGRAM_BOT_TOKEN=123456:bot_token_here
set TELEGRAM_CHAT_ID=123456789
python3 cryptex_terminal.py --source coinbase
```

On Linux/macOS:

```bash
export TELEGRAM_BOT_TOKEN=123456:bot_token_here
export TELEGRAM_CHAT_ID=123456789
python3 cryptex_terminal.py --source coinbase
```

Optional tuning:

```bash
set SURGE_ALERT_PCT=3
set SURGE_ALERT_WINDOW=12
set SURGE_ALERT_24H_PCT=8
set SURGE_ALERT_COOLDOWN=900
```

Defaults send one alert per symbol every 15 minutes when price rises at least 3% over the last 12 ticks, or when 24h momentum is at least 8% with short-term confirmation.

---

# Architecture

```text
WebSocket Streams
        │
        ▼
 MarketState Engine
        │
 ├── Indicators
 ├── Signal Engine
 ├── Alert System
 ├── News Feed
 └── Dashboard Renderer
        │
        ▼
     Rich TUI
```

---

# Design Goals

- Extremely low overhead
- Pure terminal experience
- Real-time responsiveness
- Minimal dependencies
- Exchange-agnostic architecture
- Easy extensibility

---

# Roadmap

- [ ] Order book depth
- [ ] Trade tape
- [ ] Configurable layouts
- [ ] Portfolio tracking
- [ ] Historical candles
- [ ] SQLite persistence
- [ ] Strategy backtesting
- [ ] Plugin system
- [ ] Docker image
- [ ] Asyncio migration

---

# Why this project exists

Most crypto dashboards are either:
- browser-heavy,
- slow,
- API polling based,
- or visually cluttered.

AZ TERMINAL focuses on:
- low latency,
- terminal-native workflows,
- efficient streaming,
- and trader-oriented signal visibility.

---

# Disclaimer

This software is for educational and informational purposes only.

It is NOT financial advice.

---

# License

MIT License

---

# Contributing

Pull requests, optimizations, and exchange integrations are welcome.

Ideas:
- new indicators
- better rendering
- async networking
- performance profiling
- additional exchanges
