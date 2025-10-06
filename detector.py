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
        self.timeframes = ["1h", "2h", "4h", "1d"]
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
    
    def is_doji_with_low_volume(self, current_candle, previous_candle, symbol, timeframe):
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
        doji_threshold = (self.doji_threshold / 100) * curr_range
        is_doji = curr_body <= doji_threshold
        
        if not is_doji:
            return False, None
        
        # ĐIỀU KIỆN 2: Volume thấp (BỎ QUA CHO KHUNG D)
        is_low_volume = curr_volume <= (self.volume_ratio * prev_volume)
        
        if timeframe != "1d" and not is_low_volume:
            return False, None
        
        # ĐIỀU KIỆN 3: Kiểm tra bóng trên của nến trước
        signal_type = None
        upper_shadow = 0
        upper_shadow_percent = 0
        
        if prev_close < prev_open:  # Nến đỏ
            upper_shadow = prev_high - prev_close
            upper_shadow_percent = (upper_shadow / prev_range) * 100
            
            if upper_shadow > 0.60 * prev_range:
                signal_type = "LONG"
        
        elif prev_close > prev_open:  # Nến xanh
            upper_shadow = prev_high - prev_open
            upper_shadow_percent = (upper_shadow / prev_range) * 100
            
            if upper_shadow > 0.60 * prev_range:
                signal_type = "SHORT"
        
        if signal_type is None:
            return False, None
        
        # ĐỦ ĐIỀU KIỆN - TRẢ VỀ LUÔN
        curr_body_percent = (curr_body / curr_range) * 100
        volume_change = ((curr_volume - prev_volume) / prev_volume) * 100
        
        details = {
            "close": curr_close,
            "close_time": current_candle["close_time"],
            "signal_type": signal_type,
            "curr_body_percent": round(curr_body_percent, 2),
            "upper_shadow_percent": round(upper_shadow_percent, 2),
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
                    print(f"✅ Cached: {symbol} {timeframe} at {self.timestamp_to_datetime(completed_candle['close_time'])}")
                    
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