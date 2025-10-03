"""
Backtest đơn giản: Chỉ kiểm tra nến Doji với volume thấp
Không có điều kiện S/R, chỉ xác định xem đó có phải nến Doji không
"""
import requests
from datetime import datetime, timezone, timedelta
from tabulate import tabulate

# ========== CẤU HÌNH ==========
SYMBOLS = ["BBUSDT"]
TIMEFRAMES = ["1h", "4h", "1d"]
DOJI_THRESHOLD_PERCENT = 10  # Body <= 7% range
VOLUME_RATIO_THRESHOLD = 0.8  # Volume <= 80% nến trước
BACKTEST_CANDLES = 100

# ========== HÀM LẤY DỮ LIỆU ==========
def get_historical_klines(symbol, interval, limit=100):
    """Lấy dữ liệu từ Binance"""
    url = "https://api.binance.com/api/v3/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        candles = []
        for candle in data:
            candles.append({
                "open_time": candle[0],
                "open": float(candle[1]),
                "high": float(candle[2]),
                "low": float(candle[3]),
                "close": float(candle[4]),
                "volume": float(candle[5]),
                "close_time": candle[6]
            })
        return candles
    except Exception as e:
        print(f"Lỗi khi lấy dữ liệu {symbol}: {e}")
        return None

# ========== HÀM KIỂM TRA DOJI ==========
def is_doji_simple(current_candle, previous_candle, threshold_percent=7, volume_ratio=0.8):
    """
    Kiểm tra nến Doji đơn giản
    
    Chỉ 2 điều kiện:
    1. Body <= 7% × Range
    2. Volume <= 80% × Volume nến trước
    
    Returns:
        (is_doji, details)
    """
    curr_open = current_candle["open"]
    curr_close = current_candle["close"]
    curr_high = current_candle["high"]
    curr_low = current_candle["low"]
    curr_volume = current_candle["volume"]
    
    prev_volume = previous_candle["volume"]
    
    # Tính toán
    curr_body = abs(curr_close - curr_open)
    curr_range = curr_high - curr_low
    
    # Tránh chia cho 0
    if curr_range == 0 or prev_volume == 0:
        return False, None
    
    # Điều kiện 1: Doji
    doji_threshold = (threshold_percent / 100) * curr_range
    is_doji = curr_body <= doji_threshold
    
    # Điều kiện 2: Volume thấp
    is_low_volume = curr_volume <= (volume_ratio * prev_volume)
    
    # Phân loại màu nến
    if curr_close > curr_open:
        candle_color = "Xanh"
    elif curr_close < curr_open:
        candle_color = "Đỏ"
    else:
        candle_color = "Flat"
    
    curr_body_percent = (curr_body / curr_range) * 100
    volume_change_percent = ((curr_volume - prev_volume) / prev_volume) * 100
    
    # Tính upper và lower shadow
    if curr_close > curr_open:  # Nến xanh
        upper_shadow = curr_high - curr_close
        lower_shadow = curr_open - curr_low
    else:  # Nến đỏ
        upper_shadow = curr_high - curr_open
        lower_shadow = curr_close - curr_low
    
    upper_shadow_percent = (upper_shadow / curr_range * 100) if curr_range > 0 else 0
    lower_shadow_percent = (lower_shadow / curr_range * 100) if curr_range > 0 else 0
    
    details = {
        "open": curr_open,
        "high": curr_high,
        "low": curr_low,
        "close": curr_close,
        "body": curr_body,
        "range": curr_range,
        "body_percent": round(curr_body_percent, 2),
        "volume": curr_volume,
        "prev_volume": prev_volume,
        "volume_change_percent": round(volume_change_percent, 2),
        "candle_color": candle_color,
        "upper_shadow": upper_shadow,
        "lower_shadow": lower_shadow,
        "upper_shadow_percent": round(upper_shadow_percent, 2),
        "lower_shadow_percent": round(lower_shadow_percent, 2),
        "is_doji": is_doji,
        "is_low_volume": is_low_volume
    }
    
    # Cả 2 điều kiện phải thỏa
    return (is_doji and is_low_volume), details

# ========== CHUYỂN ĐỔI THỜI GIAN ==========
def timestamp_to_datetime(timestamp_ms):
    dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
    dt_vietnam = dt + timedelta(hours=7)
    return dt_vietnam.strftime("%d/%m/%Y %H:%M")

def timeframe_to_text(timeframe):
    mapping = {"1h": "H1", "4h": "H4", "1d": "D1"}
    return mapping.get(timeframe, timeframe)

# ========== BACKTEST ==========
def backtest_symbol(symbol, timeframe, num_candles=100):
    print(f"\n{'='*70}")
    print(f"Backtest: {symbol} - {timeframe_to_text(timeframe)}")
    print(f"{'='*70}")
    
    candles = get_historical_klines(symbol, timeframe, limit=num_candles + 1)
    
    if not candles or len(candles) < 2:
        print("Không đủ dữ liệu")
        return []
    
    doji_signals = []
    
    for i in range(1, len(candles)):
        previous = candles[i-1]
        current = candles[i]
        
        is_doji, details = is_doji_simple(
            current,
            previous,
            threshold_percent=DOJI_THRESHOLD_PERCENT,
            volume_ratio=VOLUME_RATIO_THRESHOLD
        )
        
        if is_doji and details:
            signal = {
                "symbol": symbol,
                "timeframe": timeframe_to_text(timeframe),
                "close_time": timestamp_to_datetime(current["close_time"]),
                "open": details["open"],
                "high": details["high"],
                "low": details["low"],
                "close": details["close"],
                "body_percent": details["body_percent"],
                "volume_change": details["volume_change_percent"],
                "candle_color": details["candle_color"],
                "upper_shadow_percent": details["upper_shadow_percent"],
                "lower_shadow_percent": details["lower_shadow_percent"]
            }
            doji_signals.append(signal)
    
    if doji_signals:
        print(f"\nTìm thấy {len(doji_signals)} nến Doji:\n")
        
        table_data = []
        for idx, sig in enumerate(doji_signals, 1):
            table_data.append([
                idx,
                sig["close_time"],
                f"${sig['close']:.4f}",
                sig["candle_color"],
                f"{sig['body_percent']:.2f}%",
                f"{sig['upper_shadow_percent']:.2f}%",
                f"{sig['lower_shadow_percent']:.2f}%",
                f"{sig['volume_change']:.2f}%"
            ])
        
        headers = ["#", "Thời gian", "Giá", "Màu", "Body%", "Bóng Trên%", "Bóng Dưới%", "Vol Change"]
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
        
        # Chi tiết 3 nến đầu
        print(f"\nChi tiết 3 nến Doji đầu tiên:\n")
        for idx, sig in enumerate(doji_signals[:3], 1):
            print(f"Nến Doji #{idx} - {sig['candle_color']}")
            print(f"  Thời gian: {sig['close_time']}")
            print(f"  OHLC: O=${sig['open']:.4f}, H=${sig['high']:.4f}, L=${sig['low']:.4f}, C=${sig['close']:.4f}")
            print(f"  Body: {sig['body_percent']:.2f}% (của range)")
            print(f"  Bóng trên: {sig['upper_shadow_percent']:.2f}%")
            print(f"  Bóng dưới: {sig['lower_shadow_percent']:.2f}%")
            print(f"  Volume: {sig['volume_change']:.2f}%")
            print()
    else:
        print("\nKhông tìm thấy nến Doji nào")
    
    return doji_signals

# ========== MAIN ==========
def run_backtest():
    print("\n" + "="*70)
    print("BACKTEST NẾN DOJI ĐƠN GIẢN")
    print("="*70)
    print(f"\nCấu hình:")
    print(f"  Symbols: {', '.join(SYMBOLS)}")
    print(f"  Timeframes: {', '.join([timeframe_to_text(tf) for tf in TIMEFRAMES])}")
    print(f"  Số nến: {BACKTEST_CANDLES}")
    print(f"  Điều kiện Doji: Body <= {DOJI_THRESHOLD_PERCENT}% range")
    print(f"  Điều kiện Volume: <= {VOLUME_RATIO_THRESHOLD * 100}% nến trước")
    
    all_signals = []
    
    for symbol in SYMBOLS:
        for timeframe in TIMEFRAMES:
            signals = backtest_symbol(symbol, timeframe, BACKTEST_CANDLES)
            all_signals.extend(signals)
    
    # Tổng kết
    print("\n" + "="*70)
    print("TỔNG KẾT")
    print("="*70)
    
    if not all_signals:
        print("\nKhông tìm thấy nến Doji nào!")
        return
    
    print(f"\nTổng số nến Doji tìm thấy: {len(all_signals)}")
    
    # Thống kê theo timeframe
    print(f"\nPhân bố theo timeframe:")
    for tf in TIMEFRAMES:
        tf_text = timeframe_to_text(tf)
        count = len([s for s in all_signals if s["timeframe"] == tf_text])
        print(f"  {tf_text}: {count} nến")
    
    # Thống kê theo symbol
    print(f"\nPhân bố theo symbol:")
    for symbol in SYMBOLS:
        count = len([s for s in all_signals if s["symbol"] == symbol])
        print(f"  {symbol}: {count} nến")
    
    # Thống kê theo màu
    print(f"\nPhân bố theo màu nến:")
    green_count = len([s for s in all_signals if s["candle_color"] == "Xanh"])
    red_count = len([s for s in all_signals if s["candle_color"] == "Đỏ"])
    flat_count = len([s for s in all_signals if s["candle_color"] == "Flat"])
    
    print(f"  Xanh: {green_count} nến")
    print(f"  Đỏ: {red_count} nến")
    print(f"  Flat: {flat_count} nến")
    
    print("\n" + "="*70)
    print("Để verify:")
    print("  1. Mở TradingView")
    print("  2. Kiểm tra từng nến có body nhỏ và volume thấp không")
    print("  3. Xác nhận đó có phải nến Doji không")
    print("="*70)

if __name__ == "__main__":
    try:
        run_backtest()
    except KeyboardInterrupt:
        print("\n\nĐã dừng!")
    except Exception as e:
        print(f"\n\nLỗi: {e}")
        import traceback
        traceback.print_exc()