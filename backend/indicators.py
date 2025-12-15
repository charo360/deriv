"""Technical indicators for the mean reversion strategy."""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Optional, List
import ta
import logging

logger = logging.getLogger(__name__)


@dataclass
class IndicatorValues:
    """Container for all indicator values at a point in time."""
    
    # Price data
    close: float
    high: float
    low: float
    
    # Bollinger Bands
    bb_upper: float
    bb_middle: float
    bb_lower: float
    bb_percent: float  # %B indicator
    bb_width: float    # Band width (volatility measure)
    bb_squeeze: bool   # True when bands are narrow (low volatility)
    
    # RSI
    rsi: float
    
    # Stochastic
    stoch_k: float
    stoch_d: float
    
    # EMA
    ema_200: float
    ema_50: float
    
    # ADX - Trend Strength
    adx: float
    plus_di: float
    minus_di: float
    adx_slope: float      # ADX change over last 3 periods (positive = strengthening)
    adx_rising: bool      # True if ADX is rising (trend strengthening)
    adx_falling: bool     # True if ADX is falling (trend weakening)
    
    # MACD - Momentum
    macd: float
    macd_signal: float
    macd_histogram: float
    macd_bullish: bool  # MACD > Signal and histogram positive
    macd_bearish: bool  # MACD < Signal and histogram negative
    
    # Derived signals
    price_at_lower_bb: bool
    price_at_upper_bb: bool
    rsi_oversold: bool
    rsi_overbought: bool
    stoch_oversold: bool
    stoch_overbought: bool
    above_ema: bool
    below_ema: bool
    
    # Trend signals
    is_trending: bool  # ADX > 25
    is_ranging: bool   # ADX < 20
    trend_up: bool     # +DI > -DI and price above EMA50
    trend_down: bool   # -DI > +DI and price below EMA50


class TechnicalIndicators:
    """Calculate technical indicators for the mean reversion strategy."""
    
    def __init__(
        self,
        bollinger_period: int = 20,
        bollinger_std: float = 2.0,
        rsi_period: int = 14,
        rsi_oversold: float = 30.0,
        rsi_overbought: float = 70.0,
        stochastic_k: int = 5,
        stochastic_d: int = 3,
        stochastic_smooth: int = 3,
        stochastic_oversold: float = 20.0,
        stochastic_overbought: float = 80.0,
        ema_period: int = 200,
        adx_period: int = 14
    ):
        self.bollinger_period = bollinger_period
        self.bollinger_std = bollinger_std
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.stochastic_k = stochastic_k
        self.stochastic_d = stochastic_d
        self.stochastic_smooth = stochastic_smooth
        self.stochastic_oversold = stochastic_oversold
        self.stochastic_overbought = stochastic_overbought
        self.ema_period = ema_period
        self.adx_period = adx_period
    
    def _calculate_wilder_rsi(self, close_prices: pd.Series, period: int = 14) -> float:
        """
        Calculate RSI using Wilder's smoothing method (exact implementation).
        This matches the original RSI formula from Wilder's 1978 book.
        """
        # Calculate price changes
        delta = close_prices.diff()
        
        # Separate gains and losses
        gains = delta.copy()
        losses = delta.copy()
        gains[gains < 0] = 0
        losses[losses > 0] = 0
        losses = abs(losses)
        
        # First average is simple moving average
        avg_gain = gains.iloc[:period].mean()
        avg_loss = losses.iloc[:period].mean()
        
        # Subsequent values use Wilder's smoothing: (previous_avg * (period-1) + current) / period
        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains.iloc[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses.iloc[i]) / period
        
        # Calculate RS and RSI
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        logger.debug(f"RSI Details - AvgGain: {avg_gain:.4f}, AvgLoss: {avg_loss:.4f}, RS: {rs:.4f}, RSI: {rsi:.2f}")
        
        return rsi
    
    def _calculate_stochastic(self, high: pd.Series, low: pd.Series, close: pd.Series, k_period: int = 14, d_period: int = 3, smooth: int = 3) -> tuple:
        """
        Calculate Stochastic Oscillator to match Deriv platform.
        %K = (Current Close - Lowest Low) / (Highest High - Lowest Low) * 100 (raw Fast %K)
        %D = 3-period SMA of %K
        """
        # Calculate %K (Fast Stochastic)
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()
        
        # %K formula
        k_values = []
        for i in range(len(close)):
            if i < k_period - 1:
                k_values.append(0)
                continue
            
            ll = lowest_low.iloc[i]
            hh = highest_high.iloc[i]
            c = close.iloc[i]
            
            if hh - ll == 0:
                k = 50.0  # Avoid division by zero
            else:
                k = ((c - ll) / (hh - ll)) * 100
            
            k_values.append(k)
        
        # Convert to Series
        k_series = pd.Series(k_values, index=close.index)
        
        # %D = SMA of %K (no additional smoothing on %K)
        d_series = k_series.rolling(window=d_period).mean()
        
        # Get the last values
        stoch_k = k_series.iloc[-1]
        stoch_d = d_series.iloc[-1]
        
        logger.debug(f"Stochastic - Lowest Low: {lowest_low.iloc[-1]:.5f}, Highest High: {highest_high.iloc[-1]:.5f}")
        logger.debug(f"Stochastic - Current Close: {close.iloc[-1]:.5f}")
        logger.debug(f"Stochastic - %K: {stoch_k:.2f}, %D: {stoch_d:.2f}")
        
        return stoch_k, stoch_d
    
    def _calculate_wilder_adx(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> tuple:
        """
        Calculate ADX, +DI, -DI using Wilder's smoothing method.
        This matches the standard ADX calculation used by most trading platforms.
        """
        # Calculate True Range (TR)
        high_low = high - low
        high_close = abs(high - close.shift(1))
        low_close = abs(low - close.shift(1))
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        
        # Calculate Directional Movement
        high_diff = high.diff()
        low_diff = -low.diff()
        
        plus_dm = pd.Series(0.0, index=high.index)
        minus_dm = pd.Series(0.0, index=high.index)
        
        plus_dm[(high_diff > low_diff) & (high_diff > 0)] = high_diff
        minus_dm[(low_diff > high_diff) & (low_diff > 0)] = low_diff
        
        # Wilder's smoothing for TR, +DM, -DM
        # First value is sum of first 'period' values
        atr = tr.rolling(window=period).sum().iloc[period-1]
        smoothed_plus_dm = plus_dm.rolling(window=period).sum().iloc[period-1]
        smoothed_minus_dm = minus_dm.rolling(window=period).sum().iloc[period-1]
        
        # Subsequent values use Wilder's smoothing: prev - (prev/period) + current
        plus_di_values = []
        minus_di_values = []
        dx_values = []
        
        for i in range(period, len(tr)):
            atr = atr - (atr / period) + tr.iloc[i]
            smoothed_plus_dm = smoothed_plus_dm - (smoothed_plus_dm / period) + plus_dm.iloc[i]
            smoothed_minus_dm = smoothed_minus_dm - (smoothed_minus_dm / period) + minus_dm.iloc[i]
            
            # Calculate +DI and -DI
            plus_di = 100 * (smoothed_plus_dm / atr) if atr != 0 else 0
            minus_di = 100 * (smoothed_minus_dm / atr) if atr != 0 else 0
            
            plus_di_values.append(plus_di)
            minus_di_values.append(minus_di)
            
            # Calculate DX
            di_diff = abs(plus_di - minus_di)
            di_sum = plus_di + minus_di
            dx = 100 * (di_diff / di_sum) if di_sum != 0 else 0
            dx_values.append(dx)
        
        # Calculate ADX (smoothed DX using Wilder's method)
        if len(dx_values) >= period:
            # First ADX is simple average of first 'period' DX values
            adx = sum(dx_values[:period]) / period
            
            # Subsequent ADX values use Wilder's smoothing
            for i in range(period, len(dx_values)):
                adx = (adx * (period - 1) + dx_values[i]) / period
        else:
            adx = dx_values[-1] if dx_values else 0
        
        # Use the last calculated +DI and -DI
        plus_di = plus_di_values[-1] if plus_di_values else 0
        minus_di = minus_di_values[-1] if minus_di_values else 0
        
        logger.debug(f"Wilder ADX - ATR: {atr:.2f}, +DM: {smoothed_plus_dm:.2f}, -DM: {smoothed_minus_dm:.2f}")
        logger.debug(f"Wilder ADX - +DI: {plus_di:.2f}, -DI: {minus_di:.2f}, DX: {dx_values[-1] if dx_values else 0:.2f}, ADX: {adx:.2f}")
        
        return adx, plus_di, minus_di
    
    def calculate(self, candles: List[dict]) -> Optional[IndicatorValues]:
        """
        Calculate all indicators from OHLC candle data.
        
        Args:
            candles: List of candle dicts with 'open', 'high', 'low', 'close', 'epoch'
            
        Returns:
            IndicatorValues or None if insufficient data
        """
        if len(candles) < self.ema_period + 10:
            return None
        
        # Convert to DataFrame
        df = pd.DataFrame(candles)
        df['close'] = df['close'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['open'] = df['open'].astype(float)
        
        # Bollinger Bands
        bb = ta.volatility.BollingerBands(
            close=df['close'],
            window=self.bollinger_period,
            window_dev=self.bollinger_std
        )
        bb_upper = bb.bollinger_hband().iloc[-1]
        bb_middle = bb.bollinger_mavg().iloc[-1]
        bb_lower = bb.bollinger_lband().iloc[-1]
        bb_percent = bb.bollinger_pband().iloc[-1]
        bb_width = bb.bollinger_wband().iloc[-1]  # Band width as percentage of middle band
        
        # Calculate average BB width over last 20 periods to detect squeeze
        bb_width_series = bb.bollinger_wband()
        avg_bb_width = bb_width_series.iloc[-20:].mean()
        bb_squeeze = bb_width < (avg_bb_width * 0.75)  # Squeeze when width is 25% below average
        
        # RSI - Using Wilder's smoothing method (custom implementation)
        rsi = self._calculate_wilder_rsi(df['close'], self.rsi_period)
        
        # DEBUG: Log last 5 close prices used for RSI calculation
        last_5_closes = df['close'].tail(5).tolist()
        candle_count = len(df)
        logger.info(f"RSI Calculation [{candle_count} candles] - Last 5 closes: {[f'{c:.2f}' for c in last_5_closes]}, RSI: {rsi:.2f}")
        
        # Compare with ta library for debugging
        rsi_indicator = ta.momentum.RSIIndicator(
            close=df['close'],
            window=self.rsi_period
        )
        rsi_ta = rsi_indicator.rsi().iloc[-1]
        
        if abs(rsi - rsi_ta) > 0.1:
            logger.warning(f"RSI mismatch: Custom={rsi:.2f}, TA Library={rsi_ta:.2f}")
        
        # Stochastic Oscillator (using custom Slow Stochastic to match Deriv platform)
        stoch_k, stoch_d = self._calculate_stochastic(
            df['high'], 
            df['low'], 
            df['close'], 
            self.stochastic_k,
            self.stochastic_d,
            self.stochastic_smooth
        )
        
        # Log Stochastic calculation details
        logger.debug(f"Stochastic Calculation - Last 5 High: {df['high'].tail(5).tolist()}")
        logger.debug(f"Stochastic Calculation - Last 5 Low: {df['low'].tail(5).tolist()}")
        logger.debug(f"Stochastic Calculation - Last 5 Close: {df['close'].tail(5).tolist()}")
        logger.info(f"Stochastic (Custom) - %K: {stoch_k:.2f}, %D: {stoch_d:.2f}")
        
        # EMA 200
        ema = ta.trend.EMAIndicator(
            close=df['close'],
            window=self.ema_period
        )
        ema_200 = ema.ema_indicator().iloc[-1]
        
        # EMA 50 for trend direction
        ema_50_ind = ta.trend.EMAIndicator(
            close=df['close'],
            window=50
        )
        ema_50 = ema_50_ind.ema_indicator().iloc[-1]
        
        # ADX - Average Directional Index for trend strength (using custom Wilder's method)
        adx, plus_di, minus_di = self._calculate_wilder_adx(
            df['high'], 
            df['low'], 
            df['close'], 
            self.adx_period
        )
        
        # Log ADX calculation details
        logger.debug(f"ADX Calculation Details - Last 5 High: {df['high'].tail(5).tolist()}")
        logger.debug(f"ADX Calculation Details - Last 5 Low: {df['low'].tail(5).tolist()}")
        logger.debug(f"ADX Calculation Details - Last 5 Close: {df['close'].tail(5).tolist()}")
        logger.info(f"ADX Components (Wilder's) - ADX: {adx:.2f}, +DI: {plus_di:.2f}, -DI: {minus_di:.2f}")
        
        # ADX Slope - for now set to 0 since we're using custom calculation
        # TODO: Track ADX history to calculate slope
        adx_slope = 0
        adx_rising = False
        adx_falling = False
        
        # MACD - Momentum confirmation
        macd_indicator = ta.trend.MACD(
            close=df['close'],
            window_slow=26,
            window_fast=12,
            window_sign=9
        )
        macd = macd_indicator.macd().iloc[-1]
        macd_signal = macd_indicator.macd_signal().iloc[-1]
        macd_histogram = macd_indicator.macd_diff().iloc[-1]
        
        # MACD momentum signals
        macd_bullish = macd > macd_signal and macd_histogram > 0
        macd_bearish = macd < macd_signal and macd_histogram < 0
        
        # Current price
        close = df['close'].iloc[-1]
        high = df['high'].iloc[-1]
        low = df['low'].iloc[-1]
        
        # Derived signals
        price_at_lower_bb = close <= bb_lower
        price_at_upper_bb = close >= bb_upper
        rsi_oversold = rsi <= self.rsi_oversold
        rsi_overbought = rsi >= self.rsi_overbought
        stoch_oversold = stoch_k <= self.stochastic_oversold
        stoch_overbought = stoch_k >= self.stochastic_overbought
        above_ema = close > ema_200
        below_ema = close < ema_200
        
        # Trend signals
        is_trending = adx > 25
        is_ranging = adx < 20
        trend_up = plus_di > minus_di and close > ema_50
        trend_down = minus_di > plus_di and close < ema_50
        
        return IndicatorValues(
            close=close,
            high=high,
            low=low,
            bb_upper=bb_upper,
            bb_middle=bb_middle,
            bb_lower=bb_lower,
            bb_percent=bb_percent,
            bb_width=bb_width,
            bb_squeeze=bb_squeeze,
            rsi=rsi,
            stoch_k=stoch_k,
            stoch_d=stoch_d,
            ema_200=ema_200,
            ema_50=ema_50,
            adx=adx,
            plus_di=plus_di,
            minus_di=minus_di,
            adx_slope=adx_slope,
            adx_rising=adx_rising,
            adx_falling=adx_falling,
            macd=macd,
            macd_signal=macd_signal,
            macd_histogram=macd_histogram,
            macd_bullish=macd_bullish,
            macd_bearish=macd_bearish,
            price_at_lower_bb=price_at_lower_bb,
            price_at_upper_bb=price_at_upper_bb,
            rsi_oversold=rsi_oversold,
            rsi_overbought=rsi_overbought,
            stoch_oversold=stoch_oversold,
            stoch_overbought=stoch_overbought,
            above_ema=above_ema,
            below_ema=below_ema,
            is_trending=is_trending,
            is_ranging=is_ranging,
            trend_up=trend_up,
            trend_down=trend_down
        )
    
    def detect_divergence(
        self,
        candles: List[dict],
        lookback: int = 14
    ) -> dict:
        """
        Detect RSI divergence (bullish/bearish).
        
        Returns:
            dict with 'bullish_divergence' and 'bearish_divergence' bools
        """
        if len(candles) < self.rsi_period + lookback:
            return {'bullish_divergence': False, 'bearish_divergence': False}
        
        df = pd.DataFrame(candles)
        df['close'] = df['close'].astype(float)
        
        rsi_indicator = ta.momentum.RSIIndicator(
            close=df['close'],
            window=self.rsi_period
        )
        rsi_series = rsi_indicator.rsi()
        
        # Get recent lows/highs
        recent_close = df['close'].iloc[-lookback:]
        recent_rsi = rsi_series.iloc[-lookback:]
        
        # Bullish divergence: price makes lower low, RSI makes higher low
        price_lower_low = recent_close.iloc[-1] < recent_close.min()
        rsi_higher_low = recent_rsi.iloc[-1] > recent_rsi.min()
        bullish_divergence = price_lower_low and rsi_higher_low and rsi_series.iloc[-1] < 40
        
        # Bearish divergence: price makes higher high, RSI makes lower high
        price_higher_high = recent_close.iloc[-1] > recent_close.max()
        rsi_lower_high = recent_rsi.iloc[-1] < recent_rsi.max()
        bearish_divergence = price_higher_high and rsi_lower_high and rsi_series.iloc[-1] > 60
        
        return {
            'bullish_divergence': bullish_divergence,
            'bearish_divergence': bearish_divergence
        }
    
    def detect_candle_pattern(self, candles: List[dict]) -> dict:
        """
        Detect reversal candle patterns.
        
        Returns:
            dict with pattern signals
        """
        if len(candles) < 3:
            return {'hammer': False, 'shooting_star': False, 'engulfing_bullish': False, 'engulfing_bearish': False}
        
        current = candles[-1]
        prev = candles[-2]
        
        o, h, l, c = float(current['open']), float(current['high']), float(current['low']), float(current['close'])
        body = abs(c - o)
        upper_wick = h - max(o, c)
        lower_wick = min(o, c) - l
        total_range = h - l if h != l else 0.0001
        
        # Hammer: small body at top, long lower wick
        hammer = (
            lower_wick > body * 2 and
            upper_wick < body * 0.5 and
            c > o  # Bullish close
        )
        
        # Shooting star: small body at bottom, long upper wick
        shooting_star = (
            upper_wick > body * 2 and
            lower_wick < body * 0.5 and
            c < o  # Bearish close
        )
        
        # Engulfing patterns
        prev_o, prev_c = float(prev['open']), float(prev['close'])
        engulfing_bullish = (
            prev_c < prev_o and  # Previous bearish
            c > o and  # Current bullish
            o < prev_c and c > prev_o  # Engulfs previous
        )
        engulfing_bearish = (
            prev_c > prev_o and  # Previous bullish
            c < o and  # Current bearish
            o > prev_c and c < prev_o  # Engulfs previous
        )
        
        return {
            'hammer': hammer,
            'shooting_star': shooting_star,
            'engulfing_bullish': engulfing_bullish,
            'engulfing_bearish': engulfing_bearish
        }
