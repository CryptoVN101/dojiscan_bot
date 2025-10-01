"""
Support/Resistance Calculator - Version 2
Dựa trên code mẫu với 500 nến để đảm bảo chính xác
"""
import requests
import pandas as pd
from typing import List, Dict, Tuple, Optional


class SupportResistanceCalculator:
    """
    Tính toán Support/Resistance channels
    Tái tạo từ TradingView Pine Script với độ chính xác cao
    """
    
    def __init__(
        self,
        pivot_period: int = 10,
        channel_width_pct: int = 5,
        min_strength: int = 1,
        max_num_sr: int = 6,
        loopback: int = 290
    ):
        self.pivot_period = pivot_period
        self.channel_width_pct = channel_width_pct
        self.min_strength = min_strength
        self.max_num_sr = max_num_sr
        self.loopback = loopback
    
    def get_klines(self, symbol: str, interval: str, limit: int = 500) -> Optional[pd.DataFrame]:
        """
        Lấy dữ liệu 500 nến từ Binance
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
            
            df = pd.DataFrame(data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])
            
            df['open'] = df['open'].astype(float)
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)
            df['close'] = df['close'].astype(float)
            df['volume'] = df['volume'].astype(float)
            
            return df
        
        except Exception as e:
            print(f"Lỗi khi lấy dữ liệu {symbol}: {e}")
            return None
    
    def find_pivot_high(self, high_series: pd.Series) -> pd.Series:
        """Tìm Pivot High"""
        n = self.pivot_period
        pivot_high = pd.Series(False, index=high_series.index)
        
        for i in range(n, len(high_series) - n):
            is_pivot = True
            center = high_series.iloc[i]
            
            # Kiểm tra left bars
            for j in range(1, n + 1):
                if high_series.iloc[i - j] >= center:
                    is_pivot = False
                    break
            
            if not is_pivot:
                continue
            
            # Kiểm tra right bars
            for j in range(1, n + 1):
                if high_series.iloc[i + j] >= center:
                    is_pivot = False
                    break
            
            pivot_high.iloc[i] = is_pivot
        
        return pivot_high
    
    def find_pivot_low(self, low_series: pd.Series) -> pd.Series:
        """Tìm Pivot Low"""
        n = self.pivot_period
        pivot_low = pd.Series(False, index=low_series.index)
        
        for i in range(n, len(low_series) - n):
            is_pivot = True
            center = low_series.iloc[i]
            
            # Kiểm tra left bars
            for j in range(1, n + 1):
                if low_series.iloc[i - j] <= center:
                    is_pivot = False
                    break
            
            if not is_pivot:
                continue
            
            # Kiểm tra right bars
            for j in range(1, n + 1):
                if low_series.iloc[i + j] <= center:
                    is_pivot = False
                    break
            
            pivot_low.iloc[i] = is_pivot
        
        return pivot_low
    
    def calculate_channel_width(self, df: pd.DataFrame) -> float:
        """Tính độ rộng channel động dựa trên 300 nến gần nhất"""
        lookback = min(300, len(df))
        recent_data = df.iloc[-lookback:]
        
        highest = recent_data['high'].max()
        lowest = recent_data['low'].min()
        
        channel_width = (highest - lowest) * self.channel_width_pct / 100
        
        return channel_width
    
    def get_sr_vals(
        self,
        pivot_values: List[float],
        ind: int,
        channel_width: float
    ) -> Tuple[float, float, int]:
        """Tính channel cho 1 pivot point"""
        lo = pivot_values[ind]
        hi = pivot_values[ind]
        numpp = 0
        
        for y in range(len(pivot_values)):
            cpp = pivot_values[y]
            
            # Tính width nếu thêm pivot này
            if cpp <= hi:
                wdth = hi - cpp
            else:
                wdth = cpp - lo
            
            # Nếu vẫn trong channel width
            if wdth <= channel_width:
                if cpp <= hi:
                    lo = min(lo, cpp)
                else:
                    hi = max(hi, cpp)
                
                numpp += 20  # Mỗi pivot = 20 điểm
        
        return hi, lo, numpp
    
    def calculate_strength_from_bars(
        self,
        df: pd.DataFrame,
        hi: float,
        lo: float
    ) -> int:
        """Tính strength từ số lần price chạm channel"""
        strength = 0
        recent_data = df.iloc[-self.loopback:]
        
        for i in range(len(recent_data)):
            bar_high = recent_data['high'].iloc[i]
            bar_low = recent_data['low'].iloc[i]
            
            # Kiểm tra high/low có chạm channel không
            if (bar_high <= hi and bar_high >= lo) or \
               (bar_low <= hi and bar_low >= lo):
                strength += 1
        
        return strength
    
    def calculate_sr_levels(self, symbol: str, interval: str) -> Dict:
        """
        Tính toán Support/Resistance levels
        
        Returns:
            Dict với structure:
            {
                'support_zones': [(low, high), ...],
                'resistance_zones': [(low, high), ...],
                'current_price': float,
                'all_zones': [...]
            }
        """
        # Lấy 500 nến
        df = self.get_klines(symbol, interval, limit=500)
        
        if df is None or len(df) < self.loopback:
            return {
                'support_zones': [],
                'resistance_zones': [],
                'current_price': 0,
                'all_zones': []
            }
        
        current_price = df['close'].iloc[-1]
        
        # Tính channel width
        channel_width = self.calculate_channel_width(df)
        
        # Tìm pivot points trong loopback period
        recent_df = df.iloc[-self.loopback:]
        
        pivot_high_mask = self.find_pivot_high(recent_df['high'])
        pivot_low_mask = self.find_pivot_low(recent_df['low'])
        
        # Lấy giá trị pivots
        pivot_values = []
        
        for i in range(len(recent_df)):
            if pivot_high_mask.iloc[i]:
                pivot_values.append(recent_df['high'].iloc[i])
            elif pivot_low_mask.iloc[i]:
                pivot_values.append(recent_df['low'].iloc[i])
        
        if len(pivot_values) < 2:
            return {
                'support_zones': [],
                'resistance_zones': [],
                'current_price': current_price,
                'all_zones': []
            }
        
        # Tạo channels
        supres = []
        
        for x in range(len(pivot_values)):
            hi, lo, strength = self.get_sr_vals(pivot_values, x, channel_width)
            
            # Thêm strength từ bars
            bar_strength = self.calculate_strength_from_bars(df, hi, lo)
            total_strength = strength + bar_strength
            
            if total_strength >= self.min_strength * 20:
                supres.append({
                    'high': hi,
                    'low': lo,
                    'mid': (hi + lo) / 2,
                    'strength': total_strength
                })
        
        # Loại bỏ duplicate channels (giữ channel mạnh nhất)
        unique_channels = []
        seen_positions = set()
        
        for channel in supres:
            # Tạo key duy nhất (làm tròn 4 chữ số)
            key = (round(channel['low'], 4), round(channel['high'], 4))
            
            if key in seen_positions:
                # Tìm và update nếu mạnh hơn
                for idx, existing in enumerate(unique_channels):
                    existing_key = (round(existing['low'], 4), round(existing['high'], 4))
                    if existing_key == key:
                        if channel['strength'] > existing['strength']:
                            unique_channels[idx] = channel
                        break
            else:
                seen_positions.add(key)
                unique_channels.append(channel)
        
        # Sắp xếp theo strength
        unique_channels.sort(key=lambda x: x['strength'], reverse=True)
        
        # Giữ top channels
        top_channels = unique_channels[:self.max_num_sr]
        
        # Phân loại Support/Resistance
        support_zones = []
        resistance_zones = []
        
        for ch in top_channels:
            if ch['high'] < current_price:
                support_zones.append((ch['low'], ch['high']))
            elif ch['low'] > current_price:
                resistance_zones.append((ch['low'], ch['high']))
        
        return {
            'support_zones': support_zones,
            'resistance_zones': resistance_zones,
            'current_price': current_price,
            'all_zones': top_channels
        }
    
    def is_price_in_zone(self, price: float, zones: List[Tuple[float, float]]) -> bool:
        """Kiểm tra giá có nằm trong zone không"""
        for low, high in zones:
            if low <= price <= high:
                return True
        return False
    
    def is_candle_touching_zone(
        self, 
        candle_low: float, 
        candle_high: float, 
        zones: List[Tuple[float, float]]
    ) -> bool:
        """
        Kiểm tra nến có chạm vào zone không (linh hoạt hơn)
        Trả về True nếu bất kỳ phần nào của nến overlap với zone
        """
        for zone_low, zone_high in zones:
            # Kiểm tra overlap: nến chạm zone nếu:
            # 1. Low của nến nằm trong zone, HOẶC
            # 2. High của nến nằm trong zone, HOẶC
            # 3. Nến bao trùm toàn bộ zone
            if (zone_low <= candle_low <= zone_high) or \
               (zone_low <= candle_high <= zone_high) or \
               (candle_low <= zone_low and candle_high >= zone_high):
                return True
        return False
    
    def get_nearest_zone(self, price: float, zones: List[Tuple[float, float]]) -> Optional[Tuple[float, float]]:
        """Tìm zone gần nhất"""
        if not zones:
            return None
        
        nearest = None
        min_distance = float('inf')
        
        for low, high in zones:
            mid = (low + high) / 2
            distance = abs(price - mid)
            
            if distance < min_distance:
                min_distance = distance
                nearest = (low, high)
        
        return nearest