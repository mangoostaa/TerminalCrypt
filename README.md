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
- Linux / macOS / Windows

## Install dependencies

```bash
pip install websocket-client requests rich
```

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

## Use Coinbase feed

```bash
python3 cryptex_terminal.py --source coinbase
```

## Use Kraken feed

```bash
python3 cryptex_terminal.py --source kraken
```

## One-time snapshot

```bash
python3 cryptex_terminal.py --once
```

## Price alerts

```bash
python3 cryptex_terminal.py --alert BTC 100000
```

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
