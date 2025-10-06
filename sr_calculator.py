"""
Support/Resistance Calculator - Chính xác từ Pine Script
Sử dụng scipy.signal.argrelextrema để tìm pivot points
"""
import requests
import pandas as pd
import numpy as np
from scipy.signal import argrelextrema
from typing import List, Dict, Tuple, Optional


class SupportResistanceCalculator:
    
    def __init__(
        self,
        pivot_period: int = 10,
        channel_width_pct: int = 5,
        min_strength: int = 1,
        max_num_sr: int = 6,
        loopback: int = 290
    ):
        self.prd = pivot_period
        self.channel_width_pct = channel_width_pct
        self.min_strength = min_strength
        self.max_num_sr = max_num_sr
        self.loopback = loopback
    
    def get_klines(self, symbol: str, interval: str, limit: int = 500) -> Optional[pd.DataFrame]:
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
    
    def find_pivots(self, df):
        """Tìm pivot points sử dụng scipy"""
        src1 = df['high'].values
        src2 = df['low'].values
        
        # Tìm pivot highs
        ph_indices = argrelextrema(src1, np.greater_equal, order=self.prd)[0]
        pivot_highs = [(i, src1[i]) for i in ph_indices]
        
        # Tìm pivot lows
        pl_indices = argrelextrema(src2, np.less_equal, order=self.prd)[0]
        pivot_lows = [(i, src2[i]) for i in pl_indices]
        
        # Kết hợp và sắp xếp theo thời gian giảm dần
        all_pivots = [(i, val, 'H') for i, val in pivot_highs] + \
                     [(i, val, 'L') for i, val in pivot_lows]
        all_pivots.sort(key=lambda x: x[0], reverse=True)
        
        return all_pivots
    
    def get_sr_vals(self, pivots, ind, cwidth):
        """Tìm SR channel cho một pivot point"""
        lo = pivots[ind][1]
        hi = lo
        numpp = 0
        
        for y in range(len(pivots)):
            cpp = pivots[y][1]
            wdth = hi - cpp if cpp <= hi else cpp - lo
            
            if wdth <= cwidth:
                if cpp <= hi:
                    lo = min(lo, cpp)
                else:
                    hi = max(hi, cpp)
                numpp += 20
        
        return hi, lo, numpp
    
    def calculate_sr_levels(self, symbol: str, interval: str) -> Dict:
        """Tính toán Support/Resistance levels"""
        df = self.get_klines(symbol, interval, limit=500)
        
        if df is None or len(df) < self.loopback:
            return {
                'support_zones': [],
                'resistance_zones': [],
                'current_price': 0,
                'all_zones': []
            }
        
        current_idx = len(df) - 1
        current_price = df.iloc[-1]['close']
        
        # Tìm pivots
        pivots = self.find_pivots(df)
        
        # Lọc pivots trong loopback period
        pivots = [p for p in pivots if current_idx - p[0] <= self.loopback]
        
        if len(pivots) < 2:
            return {
                'support_zones': [],
                'resistance_zones': [],
                'current_price': current_price,
                'all_zones': []
            }
        
        # Tính channel width
        prdhighest = df['high'].tail(300).max()
        prdlowest = df['low'].tail(300).min()
        cwidth = (prdhighest - prdlowest) * self.channel_width_pct / 100
        
        # Tính SR levels và strengths
        supres = []
        for x in range(len(pivots)):
            hi, lo, strength = self.get_sr_vals(pivots, x, cwidth)
            
            # Thêm strength từ việc giá chạm vào channel
            s = 0
            for y in range(min(self.loopback, len(df))):
                idx = len(df) - 1 - y
                if idx >= 0:
                    if (df.loc[idx, 'high'] <= hi and df.loc[idx, 'high'] >= lo) or \
                       (df.loc[idx, 'low'] <= hi and df.loc[idx, 'low'] >= lo):
                        s += 1
            
            strength += s
            supres.append({'strength': strength, 'high': hi, 'low': lo})
        
        # Sắp xếp theo strength và lọc overlap
        supres.sort(key=lambda x: x['strength'], reverse=True)
        
        channels = []
        for sr in supres:
            if sr['strength'] >= self.min_strength * 20:
                # Kiểm tra overlap với channels đã có
                is_overlap = False
                for ch in channels:
                    if (sr['high'] <= ch['high'] and sr['high'] >= ch['low']) or \
                       (sr['low'] <= ch['high'] and sr['low'] >= ch['low']):
                        is_overlap = True
                        break
                
                if not is_overlap:
                    channels.append(sr)
                    
                if len(channels) >= self.max_num_sr:
                    break
        
        # Phân loại Support/Resistance
        support_zones = []
        resistance_zones = []
        
        for ch in channels:
            if ch['high'] < current_price:
                support_zones.append((ch['low'], ch['high']))
            elif ch['low'] > current_price:
                resistance_zones.append((ch['low'], ch['high']))
        
        return {
            'support_zones': support_zones,
            'resistance_zones': resistance_zones,
            'current_price': current_price,
            'all_zones': [{'low': ch['low'], 'high': ch['high'], 
                          'mid': (ch['low'] + ch['high'])/2, 
                          'strength': ch['strength']} for ch in channels]
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
        """Kiểm tra nến có chạm vào zone không"""
        for zone_low, zone_high in zones:
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