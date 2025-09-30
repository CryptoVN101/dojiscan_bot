import requests
import pandas as pd
from datetime import datetime, timezone, timedelta
from tabulate import tabulate

# ========== CẤU HÌNH ==========
# Danh sách các cặp coin cần backtest
SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]

# Khung thời gian
TIMEFRAMES = ["1h", "4h", "1d"]

# Tham số phát hiện Doji
DOJI_THRESHOLD_PERCENT = 7  # X% = 7%
VOLUME_RATIO_THRESHOLD = 0.8  # Volume <= 80%

# Số nến backtest
BACKTEST_CANDLES = 100

# ========== HÀM LẤY DỮ LIỆU LỊCH SỬ ==========
def get_historical_klines(symbol, interval, limit=100):
    """
    Lấy dữ liệu nến lịch sử từ Binance API
    """
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
def is_doji_with_low_volume(current_candle, previous_candle, threshold_percent=7, volume_ratio=0.8):
    """
    Kiểm tra nến Doji với điều kiện volume thấp
    """
    open_price = current_candle["open"]
    close_price = current_candle["close"]
    high_price = current_candle["high"]
    low_price = current_candle["low"]
    current_volume = current_candle["volume"]
    previous_volume = previous_candle["volume"]
    
    # Tính toán
    body = abs(close_price - open_price)
    full_range = high_price - low_price
    
    # Tránh chia cho 0
    if full_range == 0 or previous_volume == 0:
        return False, None
    
    # Kiểm tra điều kiện Doji
    threshold = (threshold_percent / 100) * full_range
    is_doji = body <= threshold
    
    # Kiểm tra điều kiện Volume
    is_low_volume = current_volume <= (volume_ratio * previous_volume)
    
    # Tính các chỉ số
    body_percent = (body / full_range) * 100 if full_range > 0 else 0
    volume_change_percent = ((current_volume - previous_volume) / previous_volume) * 100
    
    details = {
        "body_percent": round(body_percent, 2),
        "volume_change_percent": round(volume_change_percent, 2),
        "current_volume": current_volume,
        "previous_volume": previous_volume,
        "close": close_price,
        "open": open_price,
        "high": high_price,
        "low": low_price,
        "full_range": full_range,
        "body": body,
        "threshold": threshold
    }
    
    return (is_doji and is_low_volume), details

# ========== HÀM CHUYỂN ĐỔI THỜI GIAN ==========
def timestamp_to_datetime(timestamp_ms):
    """Chuyển timestamp milliseconds sang datetime string (giờ Việt Nam)"""
    dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
    dt_vietnam = dt + timedelta(hours=7)
    return dt_vietnam.strftime("%d/%m/%Y %H:%M")

def timeframe_to_text(timeframe):
    """Chuyển đổi timeframe sang text"""
    mapping = {
        "1h": "H1",
        "4h": "H4",
        "1d": "D1"
    }
    return mapping.get(timeframe, timeframe)

# ========== HÀM BACKTEST ==========
def backtest_symbol(symbol, timeframe, num_candles=100):
    """
    Backtest một symbol trên một timeframe
    Trả về danh sách các tín hiệu Doji tìm được
    """
    print(f"\n{'='*60}")
    print(f"🔍 Backtest: {symbol} - {timeframe_to_text(timeframe)}")
    print(f"{'='*60}")
    
    # Lấy dữ liệu (lấy thêm 1 nến để có previous candle cho nến đầu tiên)
    candles = get_historical_klines(symbol, timeframe, limit=num_candles + 1)
    
    if not candles or len(candles) < 2:
        print("❌ Không đủ dữ liệu để backtest")
        return []
    
    signals = []
    
    # Duyệt qua các nến (bỏ qua nến đầu tiên vì cần previous candle)
    for i in range(1, len(candles)):
        previous_candle = candles[i-1]
        current_candle = candles[i]
        
        is_signal, details = is_doji_with_low_volume(
            current_candle,
            previous_candle,
            threshold_percent=DOJI_THRESHOLD_PERCENT,
            volume_ratio=VOLUME_RATIO_THRESHOLD
        )
        
        if is_signal:
            signal = {
                "symbol": symbol,
                "timeframe": timeframe_to_text(timeframe),
                "close_time": timestamp_to_datetime(current_candle["close_time"]),
                "price": details["close"],
                "body_percent": details["body_percent"],
                "volume_change": details["volume_change_percent"],
                "open": details["open"],
                "high": details["high"],
                "low": details["low"],
                "close": details["close"],
                "body": details["body"],
                "range": details["full_range"],
                "threshold": details["threshold"]
            }
            signals.append(signal)
    
    # In kết quả
    if signals:
        print(f"\n✅ Tìm thấy {len(signals)} tín hiệu Doji hợp lệ:\n")
        
        # Tạo bảng hiển thị
        table_data = []
        for idx, sig in enumerate(signals, 1):
            table_data.append([
                idx,
                sig["close_time"],
                f"${sig['price']:.4f}",
                f"{sig['body_percent']:.2f}%",
                f"{sig['volume_change']:.2f}%"
            ])
        
        headers = ["#", "Thời gian đóng nến", "Giá", "Body %", "Volume Change"]
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
        
        # In chi tiết một vài tín hiệu
        print(f"\n📋 Chi tiết 3 tín hiệu đầu tiên:\n")
        for idx, sig in enumerate(signals[:3], 1):
            print(f"Tín hiệu #{idx}:")
            print(f"  • Thời gian: {sig['close_time']}")
            print(f"  • Giá: ${sig['price']:.4f}")
            print(f"  • Open: ${sig['open']:.4f}, High: ${sig['high']:.4f}, Low: ${sig['low']:.4f}, Close: ${sig['close']:.4f}")
            print(f"  • Body: ${sig['body']:.4f} (={sig['body_percent']:.2f}% của range)")
            print(f"  • Full Range: ${sig['range']:.4f}")
            print(f"  • Threshold (7% range): ${sig['threshold']:.4f}")
            print(f"  • Body <= Threshold? {sig['body']} <= {sig['threshold']:.4f} = {'✅ YES' if sig['body'] <= sig['threshold'] else '❌ NO'}")
            print(f"  • Volume change: {sig['volume_change']:.2f}%")
            print()
    else:
        print("\n❌ Không tìm thấy tín hiệu Doji nào trong khoảng thời gian này")
    
    return signals

# ========== HÀM BACKTEST TẤT CẢ ==========
def run_full_backtest():
    """
    Chạy backtest trên tất cả symbols và timeframes
    """
    print("\n" + "="*60)
    print("🚀 BẮT ĐẦU BACKTEST LOGIC NẾN DOJI")
    print("="*60)
    print(f"\n📊 Cấu hình:")
    print(f"  • Symbols: {', '.join(SYMBOLS)}")
    print(f"  • Timeframes: {', '.join([timeframe_to_text(tf) for tf in TIMEFRAMES])}")
    print(f"  • Số nến backtest: {BACKTEST_CANDLES}")
    print(f"  • Ngưỡng Doji: {DOJI_THRESHOLD_PERCENT}%")
    print(f"  • Ngưỡng Volume: {VOLUME_RATIO_THRESHOLD * 100}%")
    
    all_signals = []
    
    # Backtest từng symbol và timeframe
    for symbol in SYMBOLS:
        for timeframe in TIMEFRAMES:
            signals = backtest_symbol(symbol, timeframe, BACKTEST_CANDLES)
            all_signals.extend(signals)
    
    # Tổng kết
    print("\n" + "="*60)
    print("📈 TỔNG KẾT BACKTEST")
    print("="*60)
    print(f"\n✅ Tổng số tín hiệu tìm thấy: {len(all_signals)}")
    
    # Thống kê theo timeframe
    print(f"\n📊 Phân bố theo khung thời gian:")
    for tf in TIMEFRAMES:
        tf_text = timeframe_to_text(tf)
        count = len([s for s in all_signals if s["timeframe"] == tf_text])
        print(f"  • {tf_text}: {count} tín hiệu")
    
    # Thống kê theo symbol
    print(f"\n📊 Phân bố theo symbol:")
    for symbol in SYMBOLS:
        count = len([s for s in all_signals if s["symbol"] == symbol])
        print(f"  • {symbol}: {count} tín hiệu")
    
    # In tất cả tín hiệu dạng bảng
    if all_signals:
        print(f"\n📋 DANH SÁCH TẤT CẢ TÍN HIỆU:\n")
        table_data = []
        for idx, sig in enumerate(all_signals, 1):
            table_data.append([
                idx,
                sig["symbol"],
                sig["timeframe"],
                sig["close_time"],
                f"${sig['price']:.4f}",
                f"{sig['body_percent']:.2f}%",
                f"{sig['volume_change']:.2f}%"
            ])
        
        headers = ["#", "Symbol", "TF", "Thời gian", "Giá", "Body %", "Vol Change"]
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
        
        # Lưu kết quả ra file CSV
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