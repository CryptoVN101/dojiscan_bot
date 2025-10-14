import requests
import asyncio
import time
from datetime import datetime, timezone, timedelta
from sr_calculator import SupportResistanceCalculator

class DojiDetector:
    def __init__(self, doji_threshold=10, volume_ratio=0.9):
        self.doji_threshold = doji_threshold
        self.volume_ratio = volume_ratio
        self.signal_cache = {}
        self.timeframes = ["1h", "2h", "4h", "1d"]
        self.sr_calculator = SupportResistanceCalculator()
        self.sr_cache = {}
        self.sr_cache_time = {}
        
        # Tham số cho True Doji
        self.min_body_position = 35  # Thân nến tối thiểu 35% từ Low
        self.max_body_position = 65  # Thân nến tối đa 65% từ Low
        self.min_shadow_percent = 5  # Mỗi bóng tối thiểu 5%
        
        # Tham số cho nến trước (CẢI TIẾN)
        self.prev_shadow_threshold = 65  # Bóng trên ≥ 65%
        self.prev_body_threshold = 65    # Body ≥ 70% (MỚI!)
    
    def get_klines(self, symbol, interval, limit=3):
        """Lấy dữ liệu nến từ Binance API"""
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
    
    def is_true_doji(self, candle):
        """
        Kiểm tra nến có THỰC SỰ là Doji không (tránh nhầm với Pinbar/Hammer)
        
        Điều kiện:
        1. Body nhỏ (≤ 10% range)
        2. Thân nến ở giữa (35-65% từ Low)
        3. Cả 2 bóng đều tồn tại (mỗi bóng ≥ 5%)
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
        
        if body_percent > self.doji_threshold:
            return False
        
        # Điều kiện 2: Thân nến ở giữa (35-65%)
        body_top = max(open_price, close_price)
        body_bottom = min(open_price, close_price)
        
        # Tính vị trí thân nến từ Low
        body_position_from_low = ((body_bottom - low_price) / price_range) * 100
        
        if body_position_from_low < self.min_body_position or body_position_from_low > self.max_body_position:
            return False
        
        # Điều kiện 3: Cả 2 bóng phải tồn tại
        upper_shadow = high_price - body_top
        lower_shadow = body_bottom - low_price
        
        upper_shadow_pct = (upper_shadow / price_range) * 100
        lower_shadow_pct = (lower_shadow / price_range) * 100
        
        if upper_shadow_pct < self.min_shadow_percent or lower_shadow_pct < self.min_shadow_percent:
            return False
        
        return True
    
    def is_doji_with_low_volume(self, current_candle, previous_candle, symbol, timeframe):
        """
        Kiểm tra nến Doji với điều kiện chính xác:
        1. True Doji (body nhỏ, ở giữa, có cả 2 bóng)
        2. Volume(Doji) ≤ 90% × Volume(Previous) [bỏ qua khung 1d]
        3a. Nến trước ĐỎ: High - Close > 65% VÀ Body ≥ 70% → LONG
        3b. Nến trước XANH: High - Open > 65% VÀ Body ≥ 70% → SHORT
        """
        
        # Thông tin nến hiện tại (Doji)
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
        
        # ============ ĐIỀU KIỆN 1: True Doji (cải tiến) ============
        if not self.is_true_doji(current_candle):
            return False, None
        
        # ============ ĐIỀU KIỆN 2: Volume thấp ============
        # Bỏ qua cho khung 1d
        if timeframe != "1d":
            is_low_volume = curr_volume <= (self.volume_ratio * prev_volume)
            if not is_low_volume:
                return False, None
        
        # ============ ĐIỀU KIỆN 3: Nến trước (CẢI TIẾN) ============
        signal_type = None
        upper_shadow = 0
        upper_shadow_percent = 0
        
        # Ngưỡng mới
        shadow_threshold = self.prev_shadow_threshold / 100
        body_threshold = self.prev_body_threshold / 100
        
        # Tính body nến trước
        prev_body = abs(prev_close - prev_open)
        prev_body_percent = (prev_body / prev_range) * 100
        
        # Kiểm tra nến trước là đỏ hay xanh
        if prev_close < prev_open:  # NẾN ĐỎ
            # Công thức: High - Close > 65% × (High - Low)
            upper_shadow = prev_high - prev_close
            upper_shadow_percent = (upper_shadow / prev_range) * 100
            
            # THÊM: Kiểm tra body ≥ 70%
            if upper_shadow > shadow_threshold * prev_range and \
               prev_body >= body_threshold * prev_range:
                signal_type = "LONG"
        
        elif prev_close > prev_open:  # NẾN XANH
            # Công thức: High - Open > 65% × (High - Low)
            upper_shadow = prev_high - prev_open
            upper_shadow_percent = (upper_shadow / prev_range) * 100
            
            # THÊM: Kiểm tra body ≥ 70%
            if upper_shadow > shadow_threshold * prev_range and \
               prev_body >= body_threshold * prev_range:
                signal_type = "SHORT"
        
        if signal_type is None:
            return False, None
        
        # ============ TRẢ VỀ KẾT QUẢ ============
        curr_body_percent = (curr_body / curr_range) * 100
        volume_change = ((curr_volume - prev_volume) / prev_volume) * 100
        
        details = {
            "close": curr_close,
            "close_time": current_candle["close_time"],
            "signal_type": signal_type,
            "curr_body_percent": round(curr_body_percent, 2),
            "upper_shadow_percent": round(upper_shadow_percent, 2),
            "prev_body_percent": round(prev_body_percent, 2),
            "volume_change": round(volume_change, 2)
        }
        
        return True, details
    
    def timestamp_to_datetime(self, timestamp_ms):
        """Chuyển timestamp sang datetime string (UTC+7)"""
        dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
        dt_vietnam = dt + timedelta(hours=7)
        return dt_vietnam.strftime("%d/%m/%Y %H:%M:%S")
    
    def timeframe_to_text(self, timeframe):
        """Chuyển timeframe sang text"""
        mapping = {
            "1h": "H1 (1 giờ)",
            "2h": "H2 (2 giờ)",
            "4h": "H4 (4 giờ)",
            "1d": "D1 (1 ngày)"
        }
        return mapping.get(timeframe, timeframe)
    
    def get_cache_key(self, symbol, timeframe, close_time):
        """Tạo key cho cache"""
        return f"{symbol}_{timeframe}_{close_time}"
    
    async def scan_symbols(self, symbols):
        """Quét tất cả symbols và trả về danh sách tín hiệu"""
        signals = []
        current_time = int(time.time() * 1000)
        
        for symbol in symbols:
            for timeframe in self.timeframes:
                candles = self.get_klines(symbol, timeframe, limit=3)
                
                if not candles or len(candles) < 3:
                    continue
                
                # Lấy nến vừa đóng (index -2)
                completed_candle = candles[-2]
                previous_candle = candles[-3]
                
                # TẠO CACHE KEY TRƯỚC
                cache_key = self.get_cache_key(symbol, timeframe, completed_candle["close_time"])
                
                # KIỂM TRA CACHE NGAY - BỎ QUA NẾU ĐÃ GỬI
                if cache_key in self.signal_cache:
                    continue
                
                # Kiểm tra nến có vừa đóng không
                time_since_close = current_time - completed_candle["close_time"]
                
                max_delay = {
                    "1h": 5 * 60 * 1000,
                    "2h": 10 * 60 * 1000,
                    "4h": 15 * 60 * 1000,
                    "1d": 30 * 60 * 1000
                }
                
                # NẾU QUÁ THỜI GIAN CHO PHÉP - BỎ QUA
                if time_since_close > max_delay.get(timeframe, 10 * 60 * 1000):
                    continue
                
                # QUAN TRỌNG: Chỉ xét nến đã đóng hoàn toàn (> 10 giây)
                if time_since_close < 10000:  # < 10 giây
                    continue  # Chưa đóng hoàn toàn, chờ lần quét sau
                
                # Kiểm tra điều kiện Doji
                is_signal, details = self.is_doji_with_low_volume(
                    completed_candle,
                    previous_candle,
                    symbol,
                    timeframe
                )
                
                # NẾU CÓ TÍN HIỆU
                if is_signal and details:
                    signal = {
                        "symbol": symbol,
                        "timeframe": self.timeframe_to_text(timeframe),
                        "close_time": self.timestamp_to_datetime(details["close_time"]),
                        "price": details["close"],
                        "signal_type": details["signal_type"]
                    }
                    
                    signals.append(signal)
                    
                    # LƯU CACHE NGAY SAU KHI TẠO TÍN HIỆU
                    self.signal_cache[cache_key] = True
                    print(f"✅ Signal: {symbol} {timeframe} {details['signal_type']} @ ${details['close']:.4f} "
                          f"(Prev body: {details['prev_body_percent']:.1f}%)")
                    
                    # Giới hạn cache
                    if len(self.signal_cache) > 1000:
                        oldest_key = list(self.signal_cache.keys())[0]
                        del self.signal_cache[oldest_key]
                
                await asyncio.sleep(0.3)
        
        return signals
    
    def calculate_wait_time(self):
        """Tính thời gian chờ thông minh"""
        from datetime import datetime
        
        now = datetime.utcnow()
        wait_times = []
        
        for timeframe in self.timeframes:
            if timeframe == "1h":
                minutes_left = 60 - now.minute
                seconds_left = minutes_left * 60 - now.second
                wait_times.append(max(seconds_left, 10))
            
            elif timeframe == "2h":
                current_hour = now.hour
                next_close_hour = ((current_hour // 2) + 1) * 2
                if next_close_hour >= 24:
                    next_close_hour = 0
                hours_left = (next_close_hour - current_hour) % 24
                minutes_left = 60 - now.minute if hours_left == 0 else 0
                seconds_left = hours_left * 3600 + minutes_left * 60 - now.second
                wait_times.append(max(seconds_left, 10))
            
            elif timeframe == "4h":
                current_hour = now.hour
                next_close_hour = ((current_hour // 4) + 1) * 4
                if next_close_hour >= 24:
                    next_close_hour = 0
                hours_left = (next_close_hour - current_hour) % 24
                minutes_left = 60 - now.minute if hours_left == 0 else 0
                seconds_left = hours_left * 3600 + minutes_left * 60 - now.second
                wait_times.append(max(seconds_left, 10))
            
            elif timeframe == "1d":
                hours_left = 24 - now.hour
                minutes_left = 60 - now.minute if hours_left == 0 else 0
                seconds_left = hours_left * 3600 + minutes_left * 60 - now.second
                wait_times.append(max(seconds_left, 10))
        
        min_wait = min(wait_times)
        
        if min_wait > 300:
            return 60
        elif min_wait > 120:
            return 30
        else:
            return 10