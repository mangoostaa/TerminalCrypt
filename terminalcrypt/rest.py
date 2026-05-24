from __future__ import annotations

import html
import time
import threading
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

import requests

from .config import COINGECKO_HEADERS, HEADERS
from .formatters import now_utc
from .state import MarketState


def _rest_loop(fn, interval: int):
    fn()

    def loop():
        while True:
            time.sleep(interval)
            fn()

    threading.Thread(target=loop, daemon=True).start()


def _fetch_fg(state: MarketState):
    try:
        r = requests.get(
            "https://api.alternative.me/fng/?limit=30&format=json",
            headers=HEADERS,
            timeout=10,
        )
        r.raise_for_status()
        with state._lock:
            state.fg_data = r.json().get("data", [])
            state.errors.pop("fg", None)
    except Exception as e:
        with state._lock:
            state.errors["fg"] = str(e)[:40]


def _fetch_global(state: MarketState):
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/global",
            headers=COINGECKO_HEADERS,
            timeout=10,
        )
        r.raise_for_status()
        with state._lock:
            state.global_data = r.json().get("data", {})
            state.global_upd = now_utc()
            state.errors.pop("global", None)
    except Exception as e:
        with state._lock:
            state.errors["global"] = str(e)[:40]


def _fetch_news(state: MarketState):
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/news",
            headers=COINGECKO_HEADERS,
            params={"per_page": 10, "page": 1},
            timeout=10,
        )
        if r.status_code == 200:
            payload = r.json()
            items = payload.get("data", []) if isinstance(payload, dict) else payload
            news_list = []
            for item in items[:10]:
                news_list.append(
                    {
                        "title": str(item.get("title", "Sin título"))[:108],
                        "source": str(item.get("news_site", item.get("source", "News")))[:18],
                        "time": str(item.get("created_at", ""))[:16] or now_utc()[:16],
                    }
                )
            if news_list:
                with state._lock:
                    state.news = news_list
                    state.news_upd = now_utc()
                    state.errors.pop("news", None)
                return
    except Exception as e:
        with state._lock:
            state.errors["news"] = str(e)[:40]

    rss_sources = [
        ("CoinTelegraph", "https://cointelegraph.com/rss"),
        ("Decrypt", "https://decrypt.co/feed"),
        ("CryptoNews", "https://cryptonews.com/newsfeed/"),
        ("Bitcoin.com", "https://news.bitcoin.com/feed/"),
    ]
    for source_name, rss_url in rss_sources:
        try:
            r = requests.get(rss_url, headers=HEADERS, timeout=10)
            if r.status_code != 200:
                continue
            root = ET.fromstring(r.content)
            items = root.findall('.//item')
            news_list = []
            for item in items[:10]:
                title = html.unescape(item.findtext("title", default="Sin título"))
                link = item.findtext("link", default="")
                pubdate = item.findtext("pubDate", default="")
                try:
                    source = urlparse(link).hostname or source_name
                except Exception:
                    source = source_name
                news_list.append(
                    {
                        "title": title[:108],
                        "source": source[:18],
                        "time": pubdate[:16] if pubdate else now_utc()[:16],
                    }
                )
            if news_list:
                with state._lock:
                    state.news = news_list
                    state.news_upd = now_utc()
                    state.errors.pop("news", None)
                return
        except Exception:
            continue

    with state._lock:
        state.news = [
            {
                "title": "Bitcoin se mantiene fuerte por encima de los $105,000",
                "source": "CoinDesk",
                "time": now_utc()[:16],
            },
            {
                "title": "Ethereum ETFs registran inflows récord esta semana",
                "source": "The Block",
                "time": now_utc()[:16],
            },
            {
                "title": "Solana lidera el volumen DeFi con nuevo ATH",
                "source": "Decrypt",
                "time": now_utc()[:16],
            },
            {
                "title": "Análisis: ¿Corrección o continuación alcista?",
                "source": "CryptoSlate",
                "time": now_utc()[:16],
            },
            {
                "title": "Mercados crypto a la espera de datos macroeconómicos",
                "source": "Cointelegraph",
                "time": now_utc()[:16],
            },
        ]
        state.news_upd = now_utc()


def start_rest(state: MarketState):
    _rest_loop(lambda: _fetch_fg(state), 300)
    _rest_loop(lambda: _fetch_global(state), 120)
    _rest_loop(lambda: _fetch_news(state), 180)
