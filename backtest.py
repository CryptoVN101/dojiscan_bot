import requests
import pandas as pd
from datetime import datetime, timezone, timedelta
from tabulate import tabulate
from sr_calculator import SupportResistanceCalculator

# ========== CẤU HÌNH ==========
SYMBOLS = ["DYDXUSDT"]
TIMEFRAMES = ["1h", "2h", "4h", "1d"]
DOJI_THRESHOLD_PERCENT = 10
VOLUME_RATIO_THRESHOLD = 0.8
BACKTEST_CANDLES = 100

sr_calculator = SupportResistanceCalculator()

# ========== HÀM LẤY DỮ LIỆU LỊCH SỬ ==========
def get_historical_klines(symbol, interval, limit=100):
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
        print(f"❌ Lỗi khi lấy dữ liệu {symbol}: {e}")
        return None

# ========== HÀM PHÁT HIỆN NẾN DOJI ==========
def is_doji_with_low_volume(current_candle, previous_candle, symbol, timeframe, threshold_percent=10, volume_ratio=0.8):
    """Kiểm tra nến Doji với điều kiện volume thấp và bóng nến trước"""
    
    # Thông tin nến hiện tại
    curr_open = current_candle["open"]
    curr_close = current_candle["close"]
    curr_high = current_candle["high"]
    curr_low = current_candle["low"]
    curr_volume = current_candle["volume"]
    
    # Thông tin nến trước
    prev_open = previous_candle["open"]
    prev_close = previous_candle["close"]
    prev_high = previous_candle["high"]
    prev_low = previous_candle["low"]
    prev_volume = previous_candle["volume"]
    
    # Tính toán
    curr_body = abs(curr_close - curr_open)
    curr_range = curr_high - curr_low
    prev_range = prev_high - prev_low
    
    # Tránh chia cho 0
    if curr_range == 0 or prev_range == 0 or prev_volume == 0:
        return False, None
    
    # ĐIỀU KIỆN 1: Nến Doji
    doji_threshold = (threshold_percent / 100) * curr_range
    is_doji = curr_body <= doji_threshold
    
    if not is_doji:
        return False, None
    
    # ĐIỀU KIỆN 2: Volume thấp (BỎ QUA CHO KHUNG D)
    is_low_volume = curr_volume <= (volume_ratio * prev_volume)
    
    if timeframe != "1d" and not is_low_volume:
        return False, None
    
    # ĐIỀU KIỆN 3: Kiểm tra bóng trên của nến trước
    signal_type = None
    upper_shadow = 0
    upper_shadow_percent = 0
    
    if prev_close < prev_open:  # Nến đỏ
        # LONG: High - Close > 60% × Range
        upper_shadow = prev_high - prev_close
        upper_shadow_percent = (upper_shadow / prev_range) * 100
        
        if upper_shadow > 0.60 * prev_range:
            signal_type = "LONG"
    
    elif prev_close > prev_open:  # Nến xanh
        # SHORT: High - Open > 60% × Range
        upper_shadow = prev_high - prev_open
        upper_shadow_percent = (upper_shadow / prev_range) * 100
        
        if upper_shadow > 0.60 * prev_range:
            signal_type = "SHORT"
    
    if signal_type is None:
        return False, None
    
    # ĐIỀU KIỆN 4 & 5: Kiểm tra S/R
    signal_quality = "NORMAL"
    in_sr_zone = False
    sr_zone_info = "N/A"
    
    try:
        sr_data = sr_calculator.calculate_sr_levels(symbol, timeframe)
        
        if signal_type == "LONG":
            if sr_calculator.is_candle_touching_zone(
                curr_low, 
                curr_high, 
                sr_data['support_zones']
            ):
                signal_quality = "HIGH"
                in_sr_zone = True
                for low, high in sr_data['support_zones']:
                    if (low <= curr_low <= high) or \
                       (low <= curr_high <= high) or \
                       (curr_low <= low and curr_high >= high):
                        sr_zone_info = f"Support [${low:.2f}-${high:.2f}]"
                        break
        
        elif signal_type == "SHORT":
            if sr_calculator.is_candle_touching_zone(
                curr_low,
                curr_high,
                sr_data['resistance_zones']
            ):
                signal_quality = "HIGH"
                in_sr_zone = True
                for low, high in sr_data['resistance_zones']:
                    if (low <= curr_low <= high) or \
                       (low <= curr_high <= high) or \
                       (curr_low <= low and curr_high >= high):
                        sr_zone_info = f"Resistance [${low:.2f}-${high:.2f}]"
                        break
    
    except Exception as e:
        print(f"⚠️ Lỗi S/R cho {symbol}-{timeframe}: {e}")
    
    # CHỈ TRẢ VỀ TRUE NẾU CÓ S/R (HIGH quality)
    if signal_quality != "HIGH":
        return False, None
    
    curr_body_percent = (curr_body / curr_range) * 100
    volume_change_percent = ((curr_volume - prev_volume) / prev_volume) * 100
    
    details = {
        "curr_body_percent": round(curr_body_percent, 2),
        "upper_shadow_percent": round(upper_shadow_percent, 2),
        "volume_change_percent": round(volume_change_percent, 2),
        "current_volume": curr_volume,
        "previous_volume": prev_volume,
        "close": curr_close,
        "open": curr_open,
        "high": curr_high,
        "low": curr_low,
        "curr_body": curr_body,
        "curr_range": curr_range,
        "upper_shadow": upper_shadow,
        "prev_range": prev_range,
        "doji_threshold": doji_threshold,
        "signal_type": signal_type,
        "signal_quality": signal_quality,
        "in_sr_zone": in_sr_zone,
        "sr_zone_info": sr_zone_info
    }
    
    return True, details

# ========== HÀM CHUYỂN ĐỔI THỜI GIAN ==========
def timestamp_to_datetime(timestamp_ms):
    dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
    dt_vietnam = dt + timedelta(hours=7)
    return dt_vietnam.strftime("%d/%m/%Y %H:%M")

def timeframe_to_text(timeframe):
    mapping = {
        "1h": "H1",
        "2h": "H2",
        "4h": "H4",
        "1d": "D1"
    }
    return mapping.get(timeframe, timeframe)

# ========== HÀM BACKTEST ==========
def backtest_symbol(symbol, timeframe, num_candles=100):
    print(f"\n{'='*60}")
    print(f"🔍 Backtest: {symbol} - {timeframe_to_text(timeframe)}")
    print(f"{'='*60}")
    
    candles = get_historical_klines(symbol, timeframe, limit=num_candles + 1)
    
    if not candles or len(candles) < 2:
        print("❌ Không đủ dữ liệu để backtest")
        return []
    
    signals = []
    
    for i in range(1, len(candles)):
        previous_candle = candles[i-1]
        current_candle = candles[i]
        
        is_signal, details = is_doji_with_low_volume(
            current_candle,
            previous_candle,
            symbol,
            timeframe,
            threshold_percent=DOJI_THRESHOLD_PERCENT,
            volume_ratio=VOLUME_RATIO_THRESHOLD
        )
        
        if is_signal and details:
            signal = {
                "symbol": symbol,
                "timeframe": timeframe_to_text(timeframe),
                "close_time": timestamp_to_datetime(current_candle["close_time"]),
                "price": details["close"],
                "curr_body_percent": details["curr_body_percent"],
                "upper_shadow_percent": details["upper_shadow_percent"],
                "volume_change": details["volume_change_percent"],
                "signal_type": details["signal_type"],
                "sr_zone_info": details["sr_zone_info"],
                "open": details["open"],
                "high": details["high"],
                "low": details["low"],
                "close": details["close"],
                "curr_body": details["curr_body"],
                "curr_range": details["curr_range"],
                "upper_shadow": details["upper_shadow"],
                "prev_range": details["prev_range"],
                "doji_threshold": details["doji_threshold"]
            }
            signals.append(signal)
    
    if signals:
        print(f"\n✅ Tìm thấy {len(signals)} tín hiệu Doji hợp lệ (tại vùng S/R):\n")
        
        table_data = []
        for idx, sig in enumerate(signals, 1):
            table_data.append([
                idx,
                sig["close_time"],
                f"${sig['price']:.4f}",
                sig["signal_type"],
                f"{sig['curr_body_percent']:.2f}%",
                f"{sig['upper_shadow_percent']:.2f}%",
                f"{sig['volume_change']:.2f}%",
                sig["sr_zone_info"]
            ])
        
        headers = ["#", "Thời gian", "Giá", "Signal", "Doji", "Shadow", "Vol", "S/R Zone"]
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
    else:
        print("\n❌ Không tìm thấy tín hiệu Doji nào (tại vùng S/R)")
    
    return signals

# ========== HÀM BACKTEST TẤT CẢ ==========
def run_full_backtest():
    print("\n" + "="*60)
    print("🚀 BẮT ĐẦU BACKTEST LOGIC NẾN DOJI VỚI S/R")
    print("="*60)
    print(f"\n📊 Cấu hình:")
    print(f"  • Symbols: {', '.join(SYMBOLS)}")
    print(f"  • Timeframes: {', '.join([timeframe_to_text(tf) for tf in TIMEFRAMES])}")
    print(f"  • Số nến backtest: {BACKTEST_CANDLES}")
    print(f"  • Ngưỡng Doji: {DOJI_THRESHOLD_PERCENT}%")
    print(f"  • Ngưỡng Volume: {VOLUME_RATIO_THRESHOLD * 100}%")
    
    all_signals = []
    
    for symbol in SYMBOLS:
        for timeframe in TIMEFRAMES:
            signals = backtest_symbol(symbol, timeframe, BACKTEST_CANDLES)
            all_signals.extend(signals)
    
    print("\n" + "="*60)
    print("📈 TỔNG KẾT BACKTEST")
    print("="*60)
    
    if not all_signals:
        print("\n❌ Không tìm thấy tín hiệu nào (tại vùng S/R)!")
        return
    
    print(f"\n✅ Tổng số tín hiệu (tại vùng S/R): {len(all_signals)}")
    
    print(f"\n📊 Phân bố theo khung thời gian:")
    for tf in TIMEFRAMES:
        tf_text = timeframe_to_text(tf)
        tf_signals = [s for s in all_signals if s["timeframe"] == tf_text]
        print(f"  • {tf_text}: {len(tf_signals)} tín hiệu")
    
    print(f"\n📊 Phân bố theo hướng giao dịch:")
    long_signals = [s for s in all_signals if 'LONG' in s['signal_type']]
    short_signals = [s for s in all_signals if 'SHORT' in s['signal_type']]
    
    print(f"  • LONG: {len(long_signals)} tín hiệu")
    print(f"  • SHORT: {len(short_signals)} tín hiệu")
    
    try:
        df = pd.DataFrame(all_signals)
        filename = f"doji_backtest_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(filename, index=False)
        print(f"\n💾 Đã lưu kết quả vào file: {filename}")
    except Exception as e:
        print(f"\n⚠️ Không thể lưu file CSV: {e}")
    
    print("\n" + "="*60)
    print("✅ HOÀN THÀNH BACKTEST")
    print("="*60)

# ========== MAIN ==========
if __name__ == "__main__":
    try:
        run_full_backtest()
    except KeyboardInterrupt:
        print("\n\n⛔ Đã dừng backtest!")
    except Exception as e:
        print(f"\n\n❌ Lỗi: {e}")
        import traceback
        traceback.print_exc()