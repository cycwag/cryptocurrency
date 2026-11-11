from flask import Flask, render_template, jsonify, Response
from prometheus_client import Gauge, Counter, generate_latest, CONTENT_TYPE_LATEST
import requests
import threading
import time
import logging
from collections import deque

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- Custom Metrics ---
crypto_price = Gauge('crypto_price_usd', 'Current price of crypto in USD', ['symbol'])
price_fetch_total = Counter('price_fetch_total', 'Total price fetch attempts', ['status'])
fetch_latency = Gauge('price_fetch_latency_seconds', 'Latency of price fetch from upstream API')

prices_cache = {"bitcoin": 0.0, "ethereum": 0.0, "solana": 0.0, "dogecoin": 0.0, "ripple": 0.0, "chainlink": 0.0}
fail_mode = False

COINS = {"bitcoin": ("BTC", "Bitcoin"), "ethereum": ("ETH", "Ethereum"),
         "solana": ("SOL", "Solana"), "dogecoin": ("DOGE", "Dogecoin"),
         "ripple": ("XRP", "XRP"), "chainlink": ("LINK", "Chainlink")}

# Ember histori per koin: 288 bar 5-menit sehari + ruang titik live
history_cache = {coin: deque(maxlen=400) for coin in prices_cache}
history_mode = {}  # coin -> "24h" atau "session"

COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"
COINGECKO_PARAMS = {"ids": "bitcoin,ethereum,solana,dogecoin,ripple,chainlink", "vs_currencies": "usd"}
FETCH_INTERVAL = 30


def fetch_history(coin):
    """Download + validasi riwayat 24h satu koin. Tolak data terdegradasi."""
    try:
        r = requests.get(
            f"https://api.coingecko.com/api/v3/coins/{coin}/market_chart",
            params={"vs_currency": "usd", "days": 1},
            timeout=15,
        )
        r.raise_for_status()
        pts = [[int(ts), float(price)] for ts, price in r.json()["prices"]]
        if len(pts) < 2 or pts[-1][0] - pts[0][0] < 20 * 3600 * 1000:
            raise ValueError("span histori < 20 jam (respons terdegradasi?)")
        end = pts[-1][0]
        fresh = [p for p in history_cache[coin] if p[0] > end]
        history_cache[coin].clear()
        history_cache[coin].extend(pts)
        history_cache[coin].extend(fresh)
        history_mode[coin] = "24h"
        logger.info("history %s loaded: %d points (span tervalidasi)", coin, len(pts))
        return True
    except Exception as e:
        logger.warning("history %s gagal, mode sesi: %s", coin, e)
        history_mode[coin] = "session"
        return False


history_fetching = set()
history_attempt = {}


def ensure_history(coin):
    """Picu download riwayat di background saat halaman detail dibuka.
    Non-blocking; retry otomatis berjeda >= 60 detik."""
    if history_mode.get(coin) == "24h" or coin in history_fetching:
        return
    now = time.time()
    if now - history_attempt.get(coin, 0) < 60:
        return
    history_attempt[coin] = now
    history_fetching.add(coin)

    def _run():
        try:
            fetch_history(coin)
        finally:
            history_fetching.discard(coin)

    threading.Thread(target=_run, daemon=True).start()


def fetch_loop():
    global prices_cache
    while True:
        start = time.time()
        try:
            if fail_mode:
                raise Exception("simulated failure (fail_mode=on)")
            r = requests.get(COINGECKO_URL, params=COINGECKO_PARAMS, timeout=10)
            r.raise_for_status()
            data = r.json()
            prices_cache["bitcoin"] = float(data["bitcoin"]["usd"])
            prices_cache["ethereum"] = float(data["ethereum"]["usd"])
            prices_cache["solana"] = float(data["solana"]["usd"])
            prices_cache["dogecoin"] = float(data["dogecoin"]["usd"])
            prices_cache["ripple"] = float(data["ripple"]["usd"])
            prices_cache["chainlink"] = float(data["chainlink"]["usd"])
            crypto_price.labels(symbol="BTC").set(prices_cache["bitcoin"])
            crypto_price.labels(symbol="ETH").set(prices_cache["ethereum"])
            crypto_price.labels(symbol="SOL").set(prices_cache["solana"])
            crypto_price.labels(symbol="DOGE").set(prices_cache["dogecoin"])
            crypto_price.labels(symbol="XRP").set(prices_cache["ripple"])
            crypto_price.labels(symbol="LINK").set(prices_cache["chainlink"])
            price_fetch_total.labels(status="success").inc()
            # Teteskan titik live ke ember histori (satuan ms, samakan format)
            now_ms = int(time.time() * 1000)
            for coin in prices_cache:
                history_cache[coin].append([now_ms, prices_cache[coin]])
            logger.info("prices updated: %s", prices_cache)
        except Exception as e:
            logger.warning("fetch error: %s", e)
            price_fetch_total.labels(status="error").inc()
        finally:
            fetch_latency.set(time.time() - start)
        time.sleep(FETCH_INTERVAL)


# Start background workers at import time so they also run under gunicorn
# (which never executes the __main__ block below). Single gunicorn worker
# keeps one source of truth for cache/history; Pod-level redundancy (K8s
# replicas + probes) covers availability instead of extra workers.
threading.Thread(target=fetch_loop, daemon=True).start()


@app.route('/')
def index():
    return render_template('index.html', prices=prices_cache)


@app.route('/api/prices')
def api_prices():
    return jsonify(prices_cache)


@app.route('/api/history')
def api_history():
    return jsonify({
        coin: {"mode": history_mode.get(coin, "session"),
               "points": list(history_cache[coin])}
        for coin in prices_cache
    })


@app.route('/coin/<coin_id>')
def coin_detail(coin_id):
    if coin_id not in prices_cache:
        return "unknown coin", 404
    ensure_history(coin_id)  # lazy: unduh riwayat saat dibuka, bukan saat start
    sym, name = COINS[coin_id]
    return render_template('coin.html', coin_id=coin_id, symbol=sym,
                           name=name, price=prices_cache[coin_id])


@app.route('/metrics')
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


@app.route('/health')
def health():
    return jsonify(status="up"), 200


@app.route('/fail')
def fail():
    return "simulated failure", 500


@app.route('/toggle-fail/<state>')
def toggle_fail(state):
    global fail_mode
    fail_mode = (state == "on")
    return jsonify(fail_mode=fail_mode)


if __name__ == '__main__':
    # Binding to 0.0.0.0 is needed for container/network access
    app.run(host='0.0.0.0', port=5000)  # nosec B104
