"""
Script test để kiểm tra S/R zones có chính xác không
So sánh với TradingView để verify
"""
from sr_calculator import SupportResistanceCalculator
import json

def test_sr_zones():
    """Test S/R zones cho nhiều symbols và timeframes"""
    
    # Symbols để test
    test_symbols = ["ZROUSDT"]
    timeframes = ["1h", "4h", "1d"]
    
    # Khởi tạo calculator
    sr_calc = SupportResistanceCalculator(
        pivot_period=10,
        channel_width_pct=5,
        min_strength=1,
        max_num_sr=6,
        loopback=290
    )
    
    print("\n" + "="*80)
    print("🧪 KIỂM TRA SUPPORT/RESISTANCE ZONES")
    print("="*80)
    
    all_results = {}
    
    for symbol in test_symbols:
        all_results[symbol] = {}
        
        print(f"\n{'='*80}")
        print(f"📊 Symbol: {symbol}")
        print(f"{'='*80}")
        
        for timeframe in timeframes:
            print(f"\n⏰ Timeframe: {timeframe}")
            print("-" * 80)
            
            # Tính S/R
            result = sr_calc.calculate_sr_levels(symbol, timeframe)
            
            current_price = result['current_price']
            support_zones = result['support_zones']
            resistance_zones = result['resistance_zones']
            all_zones = result['all_zones']
            
            print(f"\n💰 Giá hiện tại: ${current_price:.4f}")
            
            # Hiển thị Support zones
            print(f"\n🟢 SUPPORT ZONES (Dưới giá): {len(support_zones)}")
            if support_zones:
                for idx, (low, high) in enumerate(support_zones, 1):
                    mid = (low + high) / 2
                    distance = ((current_price - mid) / current_price) * 100
                    width = high - low
                    print(f"   {idx}. ${low:.4f} - ${high:.4f}")
                    print(f"      • Mid: ${mid:.4f}")
                    print(f"      • Width: ${width:.4f} ({(width/mid)*100:.2f}%)")
                    print(f"      • Distance: {distance:.2f}% dưới giá")
            else:
                print("   ❌ Không tìm thấy support zone")
            
            # Hiển thị Resistance zones
            print(f"\n🔴 RESISTANCE ZONES (Trên giá): {len(resistance_zones)}")
            if resistance_zones:
                for idx, (low, high) in enumerate(resistance_zones, 1):
                    mid = (low + high) / 2
                    distance = ((mid - current_price) / current_price) * 100
                    width = high - low
                    print(f"   {idx}. ${low:.4f} - ${high:.4f}")
                    print(f"      • Mid: ${mid:.4f}")
                    print(f"      • Width: ${width:.4f} ({(width/mid)*100:.2f}%)")
                    print(f"      • Distance: {distance:.2f}% trên giá")
            else:
                print("   ❌ Không tìm thấy resistance zone")
            
            # Hiển thị tất cả zones (bao gồm cả zones giá đang nằm trong)
            print(f"\n📊 TẤT CẢ S/R ZONES: {len(all_zones)}")
            for idx, zone in enumerate(all_zones, 1):
                low = zone['low']
                high = zone['high']
                mid = zone['mid']
                strength = zone['strength']
                
                # Xác định vị trí
                if high < current_price:
                    position = "🟢 Support"
                elif low > current_price:
                    position = "🔴 Resistance"
                else:
                    position = "🟡 Trong zone"
                
                print(f"   {idx}. {position} | ${low:.4f} - ${high:.4f} | Strength: {strength}")
            
            # Test giá cụ thể trong zone
            print(f"\n🔍 TEST: Kiểm tra vài mức giá")
            
            # Test giá hiện tại
            in_support = sr_calc.is_price_in_zone(current_price, support_zones)
            in_resistance = sr_calc.is_price_in_zone(current_price, resistance_zones)
            
            print(f"   Giá ${current_price:.4f}:")
            print(f"      • Trong Support? {'✅ YES' if in_support else '❌ NO'}")
            print(f"      • Trong Resistance? {'✅ YES' if in_resistance else '❌ NO'}")
            
            # Test giá thấp hơn 2%
            test_price_low = current_price * 0.98
            in_support_low = sr_calc.is_price_in_zone(test_price_low, support_zones)
            print(f"\n   Giá ${test_price_low:.4f} (-2%):")
            print(f"      • Trong Support? {'✅ YES' if in_support_low else '❌ NO'}")
            
            # Test giá cao hơn 2%
            test_price_high = current_price * 1.02
            in_resistance_high = sr_calc.is_price_in_zone(test_price_high, resistance_zones)
            print(f"\n   Giá ${test_price_high:.4f} (+2%):")
            print(f"      • Trong Resistance? {'✅ YES' if in_resistance_high else '❌ NO'}")
            
            # Lưu kết quả
            all_results[symbol][timeframe] = {
                'current_price': current_price,
                'support_count': len(support_zones),
                'resistance_count': len(resistance_zones),
                'support_zones': support_zones,
                'resistance_zones': resistance_zones
            }
            
            print("\n" + "-" * 80)
    
    # Lưu kết quả ra file JSON để tiện so sánh
    try:
        with open('sr_zones_result.json', 'w') as f:
            # Convert tuples to lists for JSON serialization
            json_results = {}
            for symbol, tf_data in all_results.items():
                json_results[symbol] = {}
                for tf, data in tf_data.items():
                    json_results[symbol][tf] = {
                        'current_price': data['current_price'],
                        'support_count': data['support_count'],
                        'resistance_count': data['resistance_count'],
                        'support_zones': [[low, high] for low, high in data['support_zones']],
                        'resistance_zones': [[low, high] for low, high in data['resistance_zones']]
                    }
            
            json.dump(json_results, f, indent=2)
        print("\n✅ Đã lưu kết quả vào file: sr_zones_result.json")
    except Exception as e:
        print(f"\n⚠️ Không thể lưu file JSON: {e}")
    
    # Tóm tắt
    print("\n" + "="*80)
    print("📈 TÓM TẮT KẾT QUẢ")
    print("="*80)
    
    for symbol in test_symbols:
        print(f"\n{symbol}:")
        for tf in timeframes:
            data = all_results[symbol][tf]
            print(f"  {tf}: ${data['current_price']:.2f} | "
                  f"Support: {data['support_count']} zones | "
                  f"Resistance: {data['resistance_count']} zones")
    
    print("\n" + "="*80)
    print("✅ HOÀN THÀNH TEST!")
    print("="*80)
    print("\n💡 Hướng dẫn verify:")
    print("1. Mở TradingView")
    print("2. Thêm indicator 'Support Resistance Channels' by LonesomeTheBlue")
    print("3. Settings: Pivot Period=10, Channel Width=5%, Minimum Strength=1")
    print("4. So sánh các vùng S/R với kết quả trên")
    print("5. Kiểm tra file sr_zones_result.json để xem chi tiết")

if __name__ == "__main__":
    try:
        test_sr_zones()
    except KeyboardInterrupt:
        print("\n\n⛔ Đã dừng test!")
    except Exception as e:
        print(f"\n\n❌ Lỗi: {e}")
        import traceback
        traceback.print_exc()