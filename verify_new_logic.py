"""
Script kiểm tra logic mới với điều kiện bóng nến
"""
import requests
from datetime import datetime, timezone, timedelta

def get_klines(symbol, interval, limit=10):
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    
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
        print(f"Lỗi: {e}")
        return None

def timestamp_to_datetime(ts_ms):
    dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
    dt_vn = dt + timedelta(hours=7)
    return dt_vn.strftime("%d/%m/%Y %H:%M:%S")

print("="*80)
print("🧪 KIỂM TRA LOGIC MỚI - BÓN NẾN TRÊN DÀII")
print("="*80)
print("\nĐiều kiện mới:")
print("  1. Doji: |Close - Open| <= 7% × (High - Low)")
print("  2. Volume thấp: <= 80% nến trước")
print("  3. LONG: Nến trước ĐỎ + (High - Close) > 60% × Range")
print("  4. SHORT: Nến trước XANH + (High - Open) > 60% × Range")

# Test ZROUSDT H4
print("\n" + "="*80)
print("📊 Test: ZROUSDT H4 (tín hiệu 01/10 14:59)")
print("="*80)

candles = get_klines("ZROUSDT", "4h", limit=5)

if candles:
    # Kiểm tra nến #4 (14:59) với nến #3 trước đó
    current = candles[-2]  # Nến 14:59
    previous = candles[-3]  # Nến trước đó
    
    print(f"\n📍 Nến trước (nến #{3}):")
    print(f"   Close time: {timestamp_to_datetime(previous['close_time'])}")
    print(f"   O: ${previous['open']:.4f}")
    print(f"   H: ${previous['high']:.4f}")
    print(f"   L: ${previous['low']:.4f}")
    print(f"   C: ${previous['close']:.4f}")
    
    # Tính bóng trên
    prev_range = previous['high'] - previous['low']
    
    if previous['close'] < previous['open']:  # Nến đỏ
        upper_shadow = previous['high'] - previous['close']
        candle_type = "🔴 NẾN ĐỎ"
        check_type = "LONG"
    else:  # Nến xanh
        upper_shadow = previous['high'] - previous['open']
        candle_type = "🟢 NẾN XANH"
        check_type = "SHORT"
    
    upper_shadow_percent = (upper_shadow / prev_range * 100) if prev_range > 0 else 0
    
    print(f"\n   Type: {candle_type}")
    print(f"   Bóng trên: ${upper_shadow:.4f} ({upper_shadow_percent:.2f}% range)")
    print(f"   Range: ${prev_range:.4f}")
    print(f"   Threshold (60%): ${0.60 * prev_range:.4f}")
    print(f"   ✅ Điều kiện bóng: {upper_shadow:.4f} > {0.60 * prev_range:.4f}?")
    
    if upper_shadow > 0.60 * prev_range:
        print(f"      → ✅ YES! Tín hiệu {check_type}")
    else:
        print(f"      → ❌ NO! Bóng chỉ {upper_shadow_percent:.2f}% < 60%")
    
    print(f"\n📍 Nến hiện tại (Doji candidate):")
    print(f"   Close time: {timestamp_to_datetime(current['close_time'])}")
    
    curr_body = abs(current['close'] - current['open'])
    curr_range = current['high'] - current['low']
    curr_body_percent = (curr_body / curr_range * 100) if curr_range > 0 else 0
    
    print(f"   Body: ${curr_body:.4f} ({curr_body_percent:.2f}% range)")
    print(f"   ✅ Điều kiện Doji: <= 7%?")
    if curr_body_percent <= 7:
        print(f"      → ✅ YES! Là nến Doji")
    else:
        print(f"      → ❌ NO! Body {curr_body_percent:.2f}% > 7%")
    
    # Volume
    vol_change = ((current['volume'] - previous['volume']) / previous['volume'] * 100)
    print(f"\n   Volume change: {vol_change:.2f}%")
    print(f"   ✅ Điều kiện Volume: <= -20%?")
    if current['volume'] <= 0.8 * previous['volume']:
        print(f"      → ✅ YES! Volume thấp")
    else:
        print(f"      → ❌ NO! Volume không đủ thấp")
    
    print("\n" + "="*80)
    print("📋 KẾT QUẢ TỔNG HỢP")
    print("="*80)
    
    is_doji = curr_body_percent <= 7
    is_low_vol = current['volume'] <= 0.8 * previous['volume']
    has_shadow = upper_shadow > 0.60 * prev_range
    
    print(f"\n1. ✅ Nến Doji: {is_doji}")
    print(f"2. ✅ Volume thấp: {is_low_vol}")
    print(f"3. ✅ Bóng trên dài: {has_shadow}")
    
    if is_doji and is_low_vol and has_shadow:
        print(f"\n🎯 TẤT CẢ ĐIỀU KIỆN ĐẠT!")
        print(f"   → Tín hiệu {check_type} HỢP LỆ")
    else:
        print(f"\n❌ KHÔNG ĐẠT ĐỦ ĐIỀU KIỆN")

print("\n" + "="*80)