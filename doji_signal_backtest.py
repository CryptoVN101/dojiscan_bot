"""
Backtest Tín Hiệu Doji - CHÍNH XÁC 100% như Bot Live
Test ĐẦY ĐỦ các điều kiện:
1. True Doji: Body ≤ 10%, thân ở 35-65% từ Low, cả 2 bóng ≥ 5%
2. Volume(Doji) ≤ 90% × Volume(Previous) [bỏ qua khung 1d]
3. Nến TRƯỚC nến Doji:
   - LONG: Nến đỏ với High - Close > 65% × Range
   - SHORT: Nến xanh với High - Open > 65% × Range
"""
import requests
from datetime import datetime, timezone, timedelta
from tabulate import tabulate

# ========== CẤU HÌNH ==========
SYMBOLS = ["BTCUSDT"]
TIMEFRAMES = ["1h", "2h", "4h", "1d"]
DOJI_THRESHOLD_PERCENT = 10
VOLUME_RATIO_THRESHOLD = 0.9
MIN_BODY_POSITION = 35  # Thân nến tối thiểu 35% từ Low
MAX_BODY_POSITION = 65  # Thân nến tối đa 65% từ Low
MIN_SHADOW_PERCENT = 5   # Mỗi bóng tối thiểu 5%
PREV_SHADOW_THRESHOLD = 65  # Bóng trên nến trước > 65%
BACKTEST_CANDLES = 100

# ========== HÀM LẤY DỮ LIỆU ==========
def get_historical_klines(symbol, interval, limit=100):
    """Lấy dữ liệu từ Binance API"""
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

# ========== KIỂM TRA TRUE DOJI ==========
def is_true_doji(candle):
    """
    Kiểm tra nến có THỰC SỰ là Doji không
    Tránh nhầm lẫn với Pinbar, Hammer, Shooting Star
    
    Điều kiện:
    1. Body ≤ 10% range
    2. Thân nến ở giữa (35-65% từ Low)
    3. Cả 2 bóng đều tồn tại (≥ 5%)
    """
    open_price = candle["open"]
    close_price = candle["close"]
    high_price = candle["high"]
    low_price = candle["low"]
    
    price_range = high_price - low_price
    
    if price_range == 0:
        return False
    
    # Điều kiện 1: Body nhỏ
    body = abs(close_price - open_price)
    body_percent = (body / price_range) * 100
    
    if body_percent > DOJI_THRESHOLD_PERCENT:
        return False
    
    # Điều kiện 2: Thân nến ở giữa (35-65% từ Low)
    body_top = max(open_price, close_price)
    body_bottom = min(open_price, close_price)
    body_position = ((body_bottom - low_price) / price_range) * 100
    
    if body_position < MIN_BODY_POSITION or body_position > MAX_BODY_POSITION:
        return False
    
    # Điều kiện 3: Cả 2 bóng phải tồn tại
    upper_shadow = high_price - body_top
    lower_shadow = body_bottom - low_price
    
    upper_shadow_pct = (upper_shadow / price_range) * 100
    lower_shadow_pct = (lower_shadow / price_range) * 100
    
    if upper_shadow_pct < MIN_SHADOW_PERCENT or lower_shadow_pct < MIN_SHADOW_PERCENT:
        return False
    
    return True

# ========== KIỂM TRA NẾN TRƯỚC ==========
PREV_BODY_THRESHOLD = 65  # Body nến trước ≥ 70%

def check_previous_candle(previous_candle):
    """
    Kiểm tra nến trước có bóng trên dài VÀ body lớn không
    
    Điều kiện MỚI:
    - LONG: Nến Đỏ với High - Close > 65% VÀ Body ≥ 70%
    - SHORT: Nến Xanh với High - Open > 65% VÀ Body ≥ 70%
    
    Returns:
        (signal_type, details) hoặc (None, None) nếu không hợp lệ
    """
    prev_open = previous_candle["open"]
    prev_close = previous_candle["close"]
    prev_high = previous_candle["high"]
    prev_low = previous_candle["low"]
    
    prev_range = prev_high - prev_low
    
    if prev_range == 0:
        return None, None
    
    shadow_threshold = PREV_SHADOW_THRESHOLD / 100
    body_threshold = PREV_BODY_THRESHOLD / 100
    
    prev_body = abs(prev_close - prev_open)
    prev_body_percent = (prev_body / prev_range) * 100
    
    # Kiểm tra nến đỏ (LONG signal)
    if prev_close < prev_open:
        # Điều kiện 1: High - Close > 65% × Range
        upper_shadow = prev_high - prev_close
        upper_shadow_percent = (upper_shadow / prev_range) * 100
        
        # Điều kiện 2: Body ≥ 70% × Range
        body_check = prev_body >= body_threshold * prev_range
        
        if upper_shadow > shadow_threshold * prev_range and body_check:
            return "LONG", {
                "candle_color": "Đỏ",
                "upper_shadow": upper_shadow,
                "upper_shadow_percent": upper_shadow_percent,
                "body_percent": prev_body_percent,
                "prev_open": prev_open,
                "prev_close": prev_close,
                "prev_high": prev_high,
                "prev_low": prev_low
            }
    
    # Kiểm tra nến xanh (SHORT signal)
    elif prev_close > prev_open:
        # Điều kiện 1: High - Open > 65% × Range
        upper_shadow = prev_high - prev_open
        upper_shadow_percent = (upper_shadow / prev_range) * 100
        
        # Điều kiện 2: Body ≥ 70% × Range
        body_check = prev_body >= body_threshold * prev_range
        
        if upper_shadow > shadow_threshold * prev_range and body_check:
            return "SHORT", {
                "candle_color": "Xanh",
                "upper_shadow": upper_shadow,
                "upper_shadow_percent": upper_shadow_percent,
                "body_percent": prev_body_percent,
                "prev_open": prev_open,
                "prev_close": prev_close,
                "prev_high": prev_high,
                "prev_low": prev_low
            }
    
    return None, None

# ========== KIỂM TRA TÍN HIỆU DOJI ĐẦY ĐỦ ==========
def check_doji_signal(current_candle, previous_candle, timeframe):
    """
    Kiểm tra ĐẦY ĐỦ điều kiện tín hiệu Doji
    
    Returns:
        (is_valid, details) hoặc (False, reason)
    """
    
    curr_volume = current_candle["volume"]
    prev_volume = previous_candle["volume"]
    
    curr_range = current_candle["high"] - current_candle["low"]
    
    if curr_range == 0 or prev_volume == 0:
        return False, "Range = 0 hoặc Volume = 0"
    
    # ============ BƯỚC 1: Kiểm tra True Doji ============
    if not is_true_doji(current_candle):
        # Debug: Tại sao không phải True Doji?
        body = abs(current_candle["close"] - current_candle["open"])
        body_percent = (body / curr_range) * 100
        
        body_top = max(current_candle["open"], current_candle["close"])
        body_bottom = min(current_candle["open"], current_candle["close"])
        body_position = ((body_bottom - current_candle["low"]) / curr_range) * 100
        
        upper_shadow = current_candle["high"] - body_top
        lower_shadow = body_bottom - current_candle["low"]
        upper_pct = (upper_shadow / curr_range) * 100
        lower_pct = (lower_shadow / curr_range) * 100
        
        reason = f"Không phải True Doji: "
        if body_percent > DOJI_THRESHOLD_PERCENT:
            reason += f"Body {body_percent:.1f}% > 10%"
        elif body_position < MIN_BODY_POSITION or body_position > MAX_BODY_POSITION:
            reason += f"Thân ở {body_position:.1f}% (cần 35-65%)"
        elif upper_pct < MIN_SHADOW_PERCENT or lower_pct < MIN_SHADOW_PERCENT:
            reason += f"Bóng trên {upper_pct:.1f}%, dưới {lower_pct:.1f}% (cần ≥5%)"
        
        return False, reason
    
    # ============ BƯỚC 2: Kiểm tra Volume thấp ============
    if timeframe != "1d":
        if curr_volume > (VOLUME_RATIO_THRESHOLD * prev_volume):
            vol_ratio = (curr_volume / prev_volume) * 100
            return False, f"Volume {vol_ratio:.1f}% > 90%"
    
    # ============ BƯỚC 3: Kiểm tra nến TRƯỚC ============
    signal_type, prev_details = check_previous_candle(previous_candle)
    
    if signal_type is None:
        # Debug: Tại sao nến trước không hợp lệ?
        prev_range = previous_candle["high"] - previous_candle["low"]
        
        if prev_range == 0:
            return False, "Nến trước: Range = 0"
        
        if previous_candle["close"] < previous_candle["open"]:
            # Nến đỏ
            upper = previous_candle["high"] - previous_candle["close"]
            upper_pct = (upper / prev_range) * 100
            return False, f"Nến trước (Đỏ): Bóng trên {upper_pct:.1f}% < 65%"
        elif previous_candle["close"] > previous_candle["open"]:
            # Nến xanh
            upper = previous_candle["high"] - previous_candle["open"]
            upper_pct = (upper / prev_range) * 100
            return False, f"Nến trước (Xanh): Bóng trên {upper_pct:.1f}% < 65%"
        else:
            return False, "Nến trước: Doji (không có hướng rõ ràng)"
    
    # ============ TÍN HIỆU HỢP LỆ ============
    curr_body = abs(current_candle["close"] - current_candle["open"])
    curr_body_percent = (curr_body / curr_range) * 100
    volume_change = ((curr_volume - prev_volume) / prev_volume) * 100
    
    # Tính thân nến ở đâu
    body_top = max(current_candle["open"], current_candle["close"])
    body_bottom = min(current_candle["open"], current_candle["close"])
    body_position = ((body_bottom - current_candle["low"]) / curr_range) * 100
    
    details = {
        "close": current_candle["close"],
        "signal_type": signal_type,
        
        # Thông tin nến Doji
        "doji_body_percent": round(curr_body_percent, 2),
        "doji_body_position": round(body_position, 2),
        "volume_change": round(volume_change, 2),
        
        # Thông tin nến trước
        "prev_candle_color": prev_details["candle_color"],
        "prev_upper_shadow_percent": round(prev_details["upper_shadow_percent"], 2),
        "prev_open": prev_details["prev_open"],
        "prev_close": prev_details["prev_close"],
        "prev_high": prev_details["prev_high"],
        "prev_low": prev_details["prev_low"]
    }
    
    return True, details

# ========== CHUYỂN ĐỔI ==========
def timestamp_to_datetime(timestamp_ms):
    dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
    dt_vietnam = dt + timedelta(hours=7)
    return dt_vietnam.strftime("%d/%m/%Y %H:%M")

def timeframe_to_text(timeframe):
    mapping = {"1h": "H1", "2h": "H2", "4h": "H4", "1d": "D1"}
    return mapping.get(timeframe, timeframe)

# ========== BACKTEST ==========
def backtest_symbol(symbol, timeframe, num_candles=100, show_failures=False):
    """
    Backtest một symbol với một timeframe
    
    Args:
        show_failures: Nếu True, hiển thị cả những nến KHÔNG đạt điều kiện
    """
    candles = get_historical_klines(symbol, timeframe, limit=num_candles + 1)
    
    if not candles or len(candles) < 2:
        return [], []
    
    valid_signals = []
    failed_signals = []
    
    for i in range(1, len(candles)):
        previous = candles[i-1]
        current = candles[i]
        
        is_valid, result = check_doji_signal(current, previous, timeframe)
        
        if is_valid:
            signal = {
                "symbol": symbol,
                "timeframe": timeframe_to_text(timeframe),
                "time": timestamp_to_datetime(current["close_time"]),
                "price": result["close"],
                "signal_type": result["signal_type"],
                "doji_body": result["doji_body_percent"],
                "doji_position": result["doji_body_position"],
                "prev_color": result["prev_candle_color"],
                "prev_shadow": result["prev_upper_shadow_percent"],
                "volume_change": result["volume_change"],
                # Thêm OHLC để debug
                "prev_open": result["prev_open"],
                "prev_close": result["prev_close"],
                "prev_high": result["prev_high"],
                "prev_low": result["prev_low"]
            }
            valid_signals.append(signal)
        elif show_failures:
            # Lưu lại tín hiệu thất bại để debug
            failed_signals.append({
                "symbol": symbol,
                "timeframe": timeframe_to_text(timeframe),
                "time": timestamp_to_datetime(current["close_time"]),
                "price": current["close"],
                "reason": result  # Lý do thất bại
            })
    
    return valid_signals, failed_signals

# ========== MAIN ==========
def run_backtest(show_failures=False):
    """
    Chạy backtest cho tất cả symbols và timeframes
    
    Args:
        show_failures: Hiển thị những nến KHÔNG đạt điều kiện (để debug)
    """
    print("\n" + "="*100)
    print("🔍 BACKTEST TÍN HIỆU DOJI - CHÍNH XÁC 100% NHƯ BOT LIVE")
    print("="*100)
    
    print(f"\n📊 Cấu hình:")
    print(f"  • Symbols: {', '.join(SYMBOLS)}")
    print(f"  • Timeframes: {', '.join([timeframe_to_text(tf) for tf in TIMEFRAMES])}")
    print(f"  • Số nến backtest: {BACKTEST_CANDLES}")
    
    print(f"\n✅ Điều kiện (giống Bot Live 100%):")
    print(f"  1. True Doji:")
    print(f"     - Body ≤ {DOJI_THRESHOLD_PERCENT}%")
    print(f"     - Thân nến ở {MIN_BODY_POSITION}-{MAX_BODY_POSITION}% từ Low")
    print(f"     - Cả 2 bóng ≥ {MIN_SHADOW_PERCENT}%")
    print(f"  2. Volume ≤ {VOLUME_RATIO_THRESHOLD * 100}% (bỏ qua khung 1d)")
    print(f"  3. Nến TRƯỚC nến Doji:")
    print(f"     - LONG: Nến Đỏ với High - Close > {PREV_SHADOW_THRESHOLD}%")
    print(f"     - SHORT: Nến Xanh với High - Open > {PREV_SHADOW_THRESHOLD}%")
    
    all_valid = []
    all_failed = []
    
    for symbol in SYMBOLS:
        for timeframe in TIMEFRAMES:
            valid, failed = backtest_symbol(symbol, timeframe, BACKTEST_CANDLES, show_failures)
            all_valid.extend(valid)
            all_failed.extend(failed)
    
    # ========== HIỂN THỊ TÍN HIỆU HỢP LỆ ==========
    print("\n" + "="*100)
    print("📈 TÍN HIỆU HỢP LỆ (sẽ được gửi lên channel)")
    print("="*100)
    
    if not all_valid:
        print("\n❌ Không tìm thấy tín hiệu hợp lệ nào!")
        print("💡 Logic mới rất nghiêm ngặt - chỉ lấy tín hiệu chất lượng cao")
    else:
        print(f"\n✅ Tổng số: {len(all_valid)} tín hiệu\n")
        
        # Bảng tín hiệu
        table_data = []
        for idx, sig in enumerate(all_valid, 1):
            table_data.append([
                idx,
                sig["symbol"],
                sig["timeframe"],
                sig["time"],
                f"${sig['price']:.4f}",
                sig["signal_type"],
                f"{sig['doji_body']:.1f}%",
                f"{sig['doji_position']:.1f}%",
                sig["prev_color"],
                f"{sig['prev_shadow']:.1f}%",
                f"{sig['volume_change']:.1f}%"
            ])
        
        headers = ["#", "Symbol", "TF", "Thời gian", "Giá", "Signal", 
                   "Doji%", "Vị trí", "Nến trước", "Shadow%", "Vol%"]
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
        
        # Chi tiết 3 tín hiệu đầu
        print(f"\n📋 Chi tiết 3 tín hiệu đầu tiên:\n")
        for idx, sig in enumerate(all_valid[:3], 1):
            print(f"Tín hiệu #{idx} - {sig['signal_type']}")
            print(f"  ⏰ {sig['symbol']} {sig['timeframe']} - {sig['time']}")
            print(f"  💰 Giá Doji: ${sig['price']:.4f}")
            print(f"  📊 Nến Doji: Body {sig['doji_body']:.2f}%, Vị trí {sig['doji_position']:.1f}%")
            print(f"  📉 Volume: {sig['volume_change']:.2f}%")
            print(f"  🕯️  Nến trước ({sig['prev_color']}): Bóng trên {sig['prev_shadow']:.2f}%")
            print(f"     OHLC: O=${sig['prev_open']:.4f}, H=${sig['prev_high']:.4f}, "
                  f"L=${sig['prev_low']:.4f}, C=${sig['prev_close']:.4f}")
            print()
        
        # Thống kê
        print(f"📊 Phân bố:")
        
        # Theo timeframe
        print(f"\n  Theo Timeframe:")
        for tf in TIMEFRAMES:
            tf_text = timeframe_to_text(tf)
            count = len([s for s in all_valid if s["timeframe"] == tf_text])
            if count > 0:
                print(f"    • {tf_text}: {count}")
        
        # Theo signal type
        long_count = len([s for s in all_valid if s["signal_type"] == "LONG"])
        short_count = len([s for s in all_valid if s["signal_type"] == "SHORT"])
        
        print(f"\n  Theo Hướng:")
        print(f"    • LONG: {long_count} ({long_count/len(all_valid)*100:.1f}%)")
        print(f"    • SHORT: {short_count} ({short_count/len(all_valid)*100:.1f}%)")
    
    # ========== HIỂN THỊ TÍN HIỆU THẤT BẠI (NẾU BẬT) ==========
    if show_failures and all_failed:
        print("\n" + "="*100)
        print("❌ TÍN HIỆU KHÔNG ĐẠT (Debug)")
        print("="*100)
        print(f"\nTổng số: {len(all_failed)} nến không đạt điều kiện\n")
        
        # Nhóm theo lý do thất bại
        reasons = {}
        for failed in all_failed:
            reason = failed["reason"]
            if reason not in reasons:
                reasons[reason] = []
            reasons[reason].append(failed)
        
        print("📊 Phân bố lý do thất bại:\n")
        for reason, items in sorted(reasons.items(), key=lambda x: len(x[1]), reverse=True):
            print(f"  • {reason}: {len(items)} nến")
        
        # Hiển thị 5 ví dụ đầu
        print(f"\n💡 5 ví dụ đầu tiên:\n")
        for idx, failed in enumerate(all_failed[:5], 1):
            print(f"{idx}. {failed['symbol']} {failed['timeframe']} - {failed['time']}")
            print(f"   Giá: ${failed['price']:.4f}")
            print(f"   Lý do: {failed['reason']}\n")
    
    print("\n" + "="*100)
    print("✅ HOÀN THÀNH BACKTEST")
    print("="*100)
    
    if all_valid:
        print(f"\n🎯 Kết luận: Tìm thấy {len(all_valid)} tín hiệu ĐẠT ĐỦ điều kiện")
        print("📢 Những tín hiệu này sẽ được bot gửi lên channel khi chạy live")
    else:
        print("\n⚠️  Không có tín hiệu nào đạt đủ điều kiện trong khoảng thời gian test")
        print("💡 Thử:")
        print("   - Tăng BACKTEST_CANDLES lên 200-500")
        print("   - Thêm nhiều symbols khác")
        print("   - Giảm PREV_SHADOW_THRESHOLD từ 65% xuống 60%")

if __name__ == "__main__":
    try:
        # Chạy backtest
        # Để hiển thị cả tín hiệu thất bại (debug), dùng: run_backtest(show_failures=True)
        run_backtest(show_failures=False)
        
    except KeyboardInterrupt:
        print("\n\n⛔ Đã dừng!")
    except Exception as e:
        print(f"\n\n❌ Lỗi: {e}")
        import traceback
        traceback.print_exc()