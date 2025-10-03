import requests
import asyncio
import time
from datetime import datetime, timezone, timedelta
from sr_calculator import SupportResistanceCalculator

class DojiDetector:
    def __init__(self, doji_threshold=10, volume_ratio=0.8):
        self.doji_threshold = doji_threshold
        self.volume_ratio = volume_ratio
        self.signal_cache = {}
        self.timeframes = ["1h", "4h", "1d"]
        self.sr_calculator = SupportResistanceCalculator()
        self.sr_cache = {}
        self.sr_cache_time = {}
    
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
    
    def get_sr_levels(self, symbol, timeframe):
        """
        Lấy S/R levels, sử dụng cache để tránh tính toán lại liên tục
        Cache timeout: 1h cho H1, 4h cho H4, 1d cho D
        """
        cache_key = f"{symbol}_{timeframe}"
        current_time = time.time()
        
        # Xác định cache timeout
        cache_timeout = {
            "1h": 3600,      # 1 giờ
            "4h": 14400,     # 4 giờ
            "1d": 86400      # 1 ngày
        }
        
        timeout = cache_timeout.get(timeframe, 3600)
        
        # Kiểm tra cache
        if cache_key in self.sr_cache and cache_key in self.sr_cache_time:
            if current_time - self.sr_cache_time[cache_key] < timeout:
                return self.sr_cache[cache_key]
        
        # Tính toán S/R mới
        sr_data = self.sr_calculator.calculate_sr_levels(symbol, timeframe)
        
        # Lưu cache
        self.sr_cache[cache_key] = sr_data
        self.sr_cache_time[cache_key] = current_time
        
        return sr_data
    
    def is_doji_with_low_volume(self, current_candle, previous_candle, symbol, timeframe):
        """
        Kiểm tra nến Doji với volume thấp và điều kiện bóng nến trước
        
        Điều kiện cơ bản:
        1. Nến hiện tại là Doji: |Close - Open| <= 7% × (High - Low)
        2. Volume thấp: Volume(Doji) <= 80% × Volume(Previous)
        3. Nến trước có bóng trên dài:
           - LONG: High - Close > 60% × (High - Low) & Close < Open (nến đỏ)
           - SHORT: High - Open > 60% × (High - Low) & Close > Open (nến xanh)
        
        Điều kiện nâng cao (bắt buộc để gửi tín hiệu):
        4. LONG: Nến Doji chạm vùng Support
        5. SHORT: Nến Doji chạm vùng Resistance
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
        
        # Tính toán nến hiện tại
        curr_body = abs(curr_close - curr_open)
        curr_range = curr_high - curr_low
        
        # Tính toán nến trước
        prev_range = prev_high - prev_low
        
        # Tránh chia cho 0
        if curr_range == 0 or prev_range == 0 or prev_volume == 0:
            return False, None
        
        # ĐIỀU KIỆN 1: Nến hiện tại là Doji
        doji_threshold = (self.doji_threshold / 100) * curr_range
        is_doji = curr_body <= doji_threshold
        
        # ĐIỀU KIỆN 2: Volume thấp
        is_low_volume = curr_volume <= (self.volume_ratio * prev_volume)
        
        # ĐIỀU KIỆN 3: Kiểm tra bóng trên của nến trước
        signal_type = None
        upper_shadow_percent = 0
        
        # Tính bóng trên theo từng trường hợp
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
        
        # Kiểm tra điều kiện cơ bản
        basic_conditions = (
            is_doji and 
            is_low_volume and 
            signal_type is not None
        )
        
        if not basic_conditions:
            return False, None
        
        # ĐIỀU KIỆN 4 & 5: Kiểm tra S/R để nâng chất lượng tín hiệu
        signal_quality = "NORMAL"
        in_sr_zone = False
        sr_zone_info = "N/A"
        
        try:
            sr_data = self.get_sr_levels(symbol, timeframe)
            
            if signal_type == "LONG":
                # Kiểm tra nến Doji có chạm vùng Support không
                if self.sr_calculator.is_candle_touching_zone(
                    curr_low,
                    curr_high,
                    sr_data['support_zones']
                ):
                    signal_quality = "HIGH"
                    in_sr_zone = True
                    signal_type = "🟢 LONG"
                    # Tìm zone cụ thể
                    for low, high in sr_data['support_zones']:
                        if (low <= curr_low <= high) or \
                           (low <= curr_high <= high) or \
                           (curr_low <= low and curr_high >= high):
                            sr_zone_info = f"Support [${low:.2f}-${high:.2f}]"
                            break
            
            elif signal_type == "SHORT":
                # Kiểm tra nến Doji có chạm vùng Resistance không
                if self.sr_calculator.is_candle_touching_zone(
                    curr_low,
                    curr_high,
                    sr_data['resistance_zones']
                ):
                    signal_quality = "HIGH"
                    in_sr_zone = True
                    signal_type = "🔴 SHORT"
                    # Tìm zone cụ thể
                    for low, high in sr_data['resistance_zones']:
                        if (low <= curr_low <= high) or \
                           (low <= curr_high <= high) or \
                           (curr_low <= low and curr_high >= high):
                            sr_zone_info = f"Resistance [${low:.2f}-${high:.2f}]"
                            break
        
        except Exception as e:
            print(f"⚠️ Lỗi khi tính S/R cho {symbol}: {e}")
            # Nếu lỗi S/R, không gửi tín hiệu
            return False, None
        
        curr_body_percent = (curr_body / curr_range) * 100
        volume_change = ((curr_volume - prev_volume) / prev_volume) * 100
        
        details = {
            "close": curr_close,
            "close_time": current_candle["close_time"],
            "signal_type": signal_type,
            "signal_quality": signal_quality,
            "curr_body_percent": round(curr_body_percent, 2),
            "upper_shadow_percent": round(upper_shadow_percent, 2),
            "volume_change": round(volume_change, 2),
            "curr_low": curr_low,
            "curr_high": curr_high,
            "in_sr_zone": in_sr_zone,
            "sr_zone_info": sr_zone_info
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
            "4h": "H4 (4 giờ)",
            "1d": "D1 (1 ngày)"
        }
        return mapping.get(timeframe, timeframe)
    
    def get_cache_key(self, symbol, timeframe, close_time):
        """Tạo key cho cache"""
        return f"{symbol}_{timeframe}_{close_time}"
    
    async def scan_symbols(self, symbols):
        """
        Quét tất cả symbols và trả về danh sách tín hiệu
        CHỈ TRẢ VỀ TÍN HIỆU HIGH QUALITY (tại vùng S/R)
        """
        signals = []
        current_time = int(time.time() * 1000)
        
        for symbol in symbols:
            for timeframe in self.timeframes:
                candles = self.get_klines(symbol, timeframe, limit=3)
                
                if not candles or len(candles) < 3:
                    continue
                
                completed_candle = candles[-2]
                previous_candle = candles[-3]
                
                cache_key = self.get_cache_key(symbol, timeframe, completed_candle["close_time"])
                
                if cache_key in self.signal_cache:
                    continue
                
                # Kiểm tra nến có vừa đóng không
                time_since_close = current_time - completed_candle["close_time"]
                
                max_delay = {
                    "1h": 5 * 60 * 1000,
                    "4h": 15 * 60 * 1000,
                    "1d": 30 * 60 * 1000
                }
                
                if time_since_close > max_delay.get(timeframe, 10 * 60 * 1000):
                    continue
                
                # Kiểm tra điều kiện Doji
                is_signal, details = self.is_doji_with_low_volume(
                    completed_candle,
                    previous_candle,
                    symbol,
                    timeframe
                )
                
                # CHỈ GỬI TÍN HIỆU KHI CÓ S/R (HIGH quality)
                if is_signal and details and details.get('signal_quality') == 'HIGH':
                    signal = {
                        "symbol": symbol,
                        "timeframe": self.timeframe_to_text(timeframe),
                        "close_time": self.timestamp_to_datetime(details["close_time"]),
                        "price": details["close"],
                        "signal_type": details["signal_type"]
                    }
                    
                    signals.append(signal)
                    self.signal_cache[cache_key] = True
                    
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