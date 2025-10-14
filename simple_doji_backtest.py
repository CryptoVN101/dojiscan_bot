"""
Backtest đơn giản: Chỉ Doji cơ bản
KHÔNG có điều kiện True Doji, KHÔNG có điều kiện nến trước
Chỉ để so sánh xem có bao nhiêu nến bị lọc bởi logic mới
"""
import requests
from datetime import datetime, timezone, timedelta
from tabulate import tabulate

# ========== CẤU HÌNH ==========
SYMBOLS = ["WUSDT"]
TIMEFRAMES = ["1h", "2h", "4h", "1d"]
DOJI_THRESHOLD_PERCENT = 10
VOLUME_RATIO_THRESHOLD = 0.9  # CẬP NHẬT: 80% → 90%
BACKTEST_CANDLES = 100

# ========== LẤY DỮ LIỆU ==========
def get_historical_klines(symbol, interval, limit=100):
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        candles = []
        for candle in data:
            candles.append({
                "open": float(candle[1]),
                "high": float(candle[2]),
                "low": float(candle[3]),
                "close": float(candle[4]),
                "volume": float(candle[5]),
                "close_time": candle[6]
            })
        return candles
    except Exception as e:
        print(f"Lỗi: {e}")
        return None

# ========== KIỂM TRA DOJI ĐƠN GIẢN ==========
def is_simple_doji(current, previous, timeframe):
    curr_body = abs(current["close"] - current["open"])
    curr_range = current["high"] - current["low"]
    
    if curr_range == 0 or previous["volume"] == 0:
        return False, None
    
    # Doji: Body ≤ 10%
    if curr_body > (DOJI_THRESHOLD_PERCENT / 100) * curr_range:
        return False, None
    
    # Volume thấp (bỏ qua khung 1d)
    if timeframe != "1d":
        if current["volume"] > (VOLUME_RATIO_THRESHOLD * previous["volume"]):
            return False, None
    
    body_pct = (curr_body / curr_range) * 100
    vol_change = ((current["volume"] - previous["volume"]) / previous["volume"]) * 100
    
    # Tính bóng
    body_top = max(current["open"], current["close"])
    body_bottom = min(current["open"], current["close"])
    upper = current["high"] - body_top
    lower = body_bottom - current["low"]
    
    details = {
        "close": current["close"],
        "body_percent": round(body_pct, 2),
        "upper_shadow_percent": round((upper / curr_range) * 100, 2),
        "lower_shadow_percent": round((lower / curr_range) * 100, 2),
        "volume_change": round(vol_change, 2)
    }
    
    return True, details

# ========== UTILS ==========
def timestamp_to_datetime(ts_ms):
    dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc) + timedelta(hours=7)
    return dt.strftime("%d/%m/%Y %H:%M")

def tf_text(tf):
    return {"1h": "H1", "2h": "H2", "4h": "H4", "1d": "D1"}.get(tf, tf)

# ========== BACKTEST ==========
def backtest(symbol, timeframe, num_candles=100):
    candles = get_historical_klines(symbol, timeframe, limit=num_candles + 1)
    if not candles or len(candles) < 2:
        return []
    
    signals = []
    for i in range(1, len(candles)):
        is_doji, details = is_simple_doji(candles[i], candles[i-1], timeframe)
        if is_doji:
            signals.append({
                "symbol": symbol,
                "timeframe": tf_text(timeframe),
                "time": timestamp_to_datetime(candles[i]["close_time"]),
                "price": details["close"],
                "body": details["body_percent"],
                "upper": details["upper_shadow_percent"],
                "lower": details["lower_shadow_percent"],
                "vol": details["volume_change"]
            })
    return signals

# ========== MAIN ==========
def run():
    print("\n" + "="*80)
    print("BACKTEST ĐƠN GIẢN - CHỈ BODY + VOLUME (KHÔNG KIỂM TRA THÂN Ở GIỮA)")
    print("="*80)
    print(f"\n📊 Config: {', '.join(SYMBOLS)}")
    print(f"   Điều kiện: Body ≤ {DOJI_THRESHOLD_PERCENT}%, Volume ≤ {VOLUME_RATIO_THRESHOLD*100}%\n")
    
    all_signals = []
    for symbol in SYMBOLS:
        for tf in TIMEFRAMES:
            all_signals.extend(backtest(symbol, tf, BACKTEST_CANDLES))
    
    if not all_signals:
        print("❌ Không tìm thấy nến Doji nào!")
        return
    
    print(f"✅ Tìm thấy {len(all_signals)} nến Doji (bao gồm cả Pinbar/Hammer):\n")
    
    table = []
    for idx, sig in enumerate(all_signals, 1):
        table.append([
            idx, sig["symbol"], sig["timeframe"], sig["time"],
            f"${sig['price']:.4f}", f"{sig['body']:.1f}%",
            f"{sig['upper']:.1f}%", f"{sig['lower']:.1f}%", f"{sig['vol']:.1f}%"
        ])
    
    headers = ["#", "Symbol", "TF", "Time", "Price", "Body%", "Upper%", "Lower%", "Vol%"]
    print(tabulate(table, headers=headers, tablefmt="grid"))
    print("\n💡 Lưu ý: Backtest này KHÔNG lọc thân nến ở giữa → có thể chứa Pinbar/Hammer")

if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\n\nĐã dừng!")