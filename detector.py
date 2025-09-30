import requests
import asyncio
import time
from datetime import datetime, timezone, timedelta

class DojiDetector:
    def __init__(self, doji_threshold=7, volume_ratio=0.8):
        self.doji_threshold = doji_threshold
        self.volume_ratio = volume_ratio
        self.signal_cache = {}
        self.timeframes = ["1h", "4h", "1d"]
    
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
    
    def is_doji_with_low_volume(self, current_candle, previous_candle):
        """Kiểm tra nến Doji với volume thấp"""
        open_price = current_candle["open"]
        close_price = current_candle["close"]
        high_price = current_candle["high"]
        low_price = current_candle["low"]
        current_volume = current_candle["volume"]
        previous_volume = previous_candle["volume"]
        
        body = abs(close_price - open_price)
        full_range = high_price - low_price
        
        if full_range == 0 or previous_volume == 0:
            return False, None
        
        threshold = (self.doji_threshold / 100) * full_range
        is_doji = body <= threshold
        is_low_volume = current_volume <= (self.volume_ratio * previous_volume)
        
        details = {
            "close": close_price,
            "close_time": current_candle["close_time"]
        }
        
        return (is_doji and is_low_volume), details
    
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
                    previous_candle
                )
                
                if is_signal:
                    signal = {
                        "symbol": symbol,
                        "timeframe": self.timeframe_to_text(timeframe),
                        "close_time": self.timestamp_to_datetime(details["close_time"]),
                        "price": details["close"]
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