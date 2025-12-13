"""Enhanced Mean Reversion Strategy with Confluence."""

from dataclasses import dataclass
from datetime import datetime, time
from enum import Enum
from typing import Optional, List, Dict
import pytz
import logging

from indicators import TechnicalIndicators, IndicatorValues
from config import trading_config

logger = logging.getLogger(__name__)


class Signal(Enum):
    RISE = "CALL"   # Predict price will go up
    FALL = "PUT"    # Predict price will go down
    NONE = "NONE"   # No signal


@dataclass
class TradeSignal:
    """A trading signal with all relevant data."""
    
    signal: Signal
    confidence: float  # 0-100
    timestamp: datetime
    price: float
    
    # Indicator values at signal time
    indicators: Dict
    
    # Confluence factors that triggered
    confluence_factors: List[str]
    
    # Timeframe confirmations
    m1_confirmed: bool
    m5_confirmed: bool
    m15_confirmed: bool


class MeanReversionStrategy:
    """
    Enhanced Mean Reversion Strategy for V75 Rise/Fall trading.
    
    Entry Conditions for RISE (Call):
    - M15: Price near support, above EMA 200 (bullish bias)
    - M5: Price touches lower Bollinger, RSI < 30, bullish divergence
    - M1: Stochastic crosses up from < 20, bullish candle pattern
    
    Entry Conditions for FALL (Put):
    - M15: Price near resistance, below EMA 200 (bearish bias)
    - M5: Price touches upper Bollinger, RSI > 70, bearish divergence
    - M1: Stochastic crosses down from > 80, bearish candle pattern
    """
    
    def __init__(self):
        self.indicators = TechnicalIndicators(
            bollinger_period=trading_config.bollinger_period,
            bollinger_std=trading_config.bollinger_std,
            rsi_period=trading_config.rsi_period,
            rsi_oversold=trading_config.rsi_oversold,
            rsi_overbought=trading_config.rsi_overbought,
            stochastic_k=trading_config.stochastic_k,
            stochastic_d=trading_config.stochastic_d,
            stochastic_smooth=trading_config.stochastic_smooth,
            stochastic_oversold=trading_config.stochastic_oversold,
            stochastic_overbought=trading_config.stochastic_overbought,
            ema_period=trading_config.ema_period
        )
        
        self.last_signal_time: Optional[datetime] = None
        self.min_signal_interval = 60  # Minimum seconds between signals
    
    def is_trading_allowed(self) -> tuple[bool, str]:
        """Check if trading is allowed (avoid server reset times)."""
        now = datetime.now(pytz.UTC)
        current_time = now.time()
        
        # Parse avoid times
        avoid_start = time(23, 55)
        avoid_end = time(0, 5)
        
        # Check if in avoid window (handles midnight crossing)
        if avoid_start <= current_time or current_time <= avoid_end:
            return False, "Server reset period - trading paused"
        
        return True, "OK"
    
    def analyze(
        self,
        candles_m1: List[dict],
        candles_m5: List[dict],
        candles_m15: List[dict]
    ) -> TradeSignal:
        """
        Analyze multiple timeframes and generate a trade signal.
        
        Args:
            candles_m1: 1-minute candles (trigger timeframe)
            candles_m5: 5-minute candles (alert timeframe)
            candles_m15: 15-minute candles (higher timeframe)
            
        Returns:
            TradeSignal with direction and confidence
        """
        # Check trading allowed
        allowed, reason = self.is_trading_allowed()
        if not allowed:
            return TradeSignal(
                signal=Signal.NONE,
                confidence=0,
                timestamp=datetime.now(pytz.UTC),
                price=0,
                indicators={},
                confluence_factors=[reason],
                m1_confirmed=False,
                m5_confirmed=False,
                m15_confirmed=False
            )
        
        # Calculate indicators for each timeframe
        ind_m1 = self.indicators.calculate(candles_m1)
        ind_m5 = self.indicators.calculate(candles_m5)
        ind_m15 = self.indicators.calculate(candles_m15)
        
        if not all([ind_m1, ind_m5, ind_m15]):
            return TradeSignal(
                signal=Signal.NONE,
                confidence=0,
                timestamp=datetime.now(pytz.UTC),
                price=0,
                indicators={},
                confluence_factors=["Insufficient data for indicators"],
                m1_confirmed=False,
                m5_confirmed=False,
                m15_confirmed=False
            )
        
        # Get divergence and candle patterns
        divergence = self.indicators.detect_divergence(candles_m5)
        patterns = self.indicators.detect_candle_pattern(candles_m1)
        
        # Analyze for RISE signal
        rise_signal = self._check_rise_signal(ind_m1, ind_m5, ind_m15, divergence, patterns)
        
        # Analyze for FALL signal
        fall_signal = self._check_fall_signal(ind_m1, ind_m5, ind_m15, divergence, patterns)
        
        # Log indicator values for debugging
        logger.info(f"=== SIGNAL ANALYSIS ===")
        logger.info(f"M1: close={ind_m1.close:.2f}, RSI={ind_m1.rsi:.1f}, Stoch_K={ind_m1.stoch_k:.1f}, BB_lower={ind_m1.bb_lower:.2f}, BB_upper={ind_m1.bb_upper:.2f}")
        logger.info(f"M5: close={ind_m5.close:.2f}, RSI={ind_m5.rsi:.1f}, at_lower_bb={ind_m5.price_at_lower_bb}, at_upper_bb={ind_m5.price_at_upper_bb}")
        logger.info(f"M15: close={ind_m15.close:.2f}, EMA200={ind_m15.ema_200:.2f}, above_ema={ind_m15.above_ema}, below_ema={ind_m15.below_ema}")
        logger.info(f"RISE confidence: {rise_signal.confidence}, FALL confidence: {fall_signal.confidence}")
        
        # Return the stronger signal (minimum 70% confidence required)
        if rise_signal.confidence > fall_signal.confidence and rise_signal.confidence >= 70:
            logger.info(f">>> SELECTED: RISE with {rise_signal.confidence}% confidence")
            return rise_signal
        elif fall_signal.confidence > rise_signal.confidence and fall_signal.confidence >= 70:
            logger.info(f">>> SELECTED: FALL with {fall_signal.confidence}% confidence")
            return fall_signal
        
        # No valid signal
        return TradeSignal(
            signal=Signal.NONE,
            confidence=0,
            timestamp=datetime.now(pytz.UTC),
            price=ind_m1.close,
            indicators=self._format_indicators(ind_m1, ind_m5, ind_m15),
            confluence_factors=["No confluence - waiting for setup"],
            m1_confirmed=False,
            m5_confirmed=False,
            m15_confirmed=False
        )
    
    def _check_rise_signal(
        self,
        ind_m1: IndicatorValues,
        ind_m5: IndicatorValues,
        ind_m15: IndicatorValues,
        divergence: dict,
        patterns: dict
    ) -> TradeSignal:
        """Check for RISE (Call) signal conditions."""
        confluence_factors = []
        confidence = 0
        
        # M15 Conditions (Higher Timeframe Bias)
        # For mean reversion RISE: price below EMA means better discount to buy
        m15_confirmed = False
        if ind_m15.below_ema:
            confluence_factors.append("M15: Below EMA 200 (price at discount)")
            confidence += 15
            m15_confirmed = True
        
        # M5 Conditions (Alert Timeframe)
        m5_confirmed = False
        
        if ind_m5.price_at_lower_bb:
            confluence_factors.append("M5: Price at lower Bollinger Band")
            confidence += 20
            m5_confirmed = True
        
        if ind_m5.rsi_oversold:
            confluence_factors.append(f"M5: RSI oversold ({ind_m5.rsi:.1f})")
            confidence += 20
            m5_confirmed = True
        
        if divergence.get('bullish_divergence'):
            confluence_factors.append("M5: Bullish RSI divergence")
            confidence += 15
        
        # M1 Conditions (Trigger Timeframe)
        m1_confirmed = False
        
        # Stochastic cross up from oversold
        if ind_m1.stoch_oversold and ind_m1.stoch_k > ind_m1.stoch_d:
            confluence_factors.append(f"M1: Stochastic bullish cross ({ind_m1.stoch_k:.1f})")
            confidence += 15
            m1_confirmed = True
        
        # Bullish candle patterns
        if patterns.get('hammer'):
            confluence_factors.append("M1: Hammer candle pattern")
            confidence += 10
            m1_confirmed = True
        
        if patterns.get('engulfing_bullish'):
            confluence_factors.append("M1: Bullish engulfing pattern")
            confidence += 10
            m1_confirmed = True
        
        # Bonus for full confluence
        if m15_confirmed and m5_confirmed and m1_confirmed:
            confidence += 10
            confluence_factors.append("Full multi-timeframe confluence!")
        
        return TradeSignal(
            signal=Signal.RISE if confidence >= 60 else Signal.NONE,
            confidence=min(confidence, 100),
            timestamp=datetime.now(pytz.UTC),
            price=ind_m1.close,
            indicators=self._format_indicators(ind_m1, ind_m5, ind_m15),
            confluence_factors=confluence_factors,
            m1_confirmed=m1_confirmed,
            m5_confirmed=m5_confirmed,
            m15_confirmed=m15_confirmed
        )
    
    def _check_fall_signal(
        self,
        ind_m1: IndicatorValues,
        ind_m5: IndicatorValues,
        ind_m15: IndicatorValues,
        divergence: dict,
        patterns: dict
    ) -> TradeSignal:
        """Check for FALL (Put) signal conditions."""
        confluence_factors = []
        confidence = 0
        
        # M15 Conditions (Higher Timeframe Bias)
        # For mean reversion FALL: price above EMA means extended/overbought
        m15_confirmed = False
        if ind_m15.above_ema:
            confluence_factors.append("M15: Above EMA 200 (price extended)")
            confidence += 15
            m15_confirmed = True
        
        # M5 Conditions (Alert Timeframe)
        m5_confirmed = False
        
        if ind_m5.price_at_upper_bb:
            confluence_factors.append("M5: Price at upper Bollinger Band")
            confidence += 20
            m5_confirmed = True
        
        if ind_m5.rsi_overbought:
            confluence_factors.append(f"M5: RSI overbought ({ind_m5.rsi:.1f})")
            confidence += 20
            m5_confirmed = True
        
        if divergence.get('bearish_divergence'):
            confluence_factors.append("M5: Bearish RSI divergence")
            confidence += 15
        
        # M1 Conditions (Trigger Timeframe)
        m1_confirmed = False
        
        # Stochastic cross down from overbought
        if ind_m1.stoch_overbought and ind_m1.stoch_k < ind_m1.stoch_d:
            confluence_factors.append(f"M1: Stochastic bearish cross ({ind_m1.stoch_k:.1f})")
            confidence += 15
            m1_confirmed = True
        
        # Bearish candle patterns
        if patterns.get('shooting_star'):
            confluence_factors.append("M1: Shooting star pattern")
            confidence += 10
            m1_confirmed = True
        
        if patterns.get('engulfing_bearish'):
            confluence_factors.append("M1: Bearish engulfing pattern")
            confidence += 10
            m1_confirmed = True
        
        # Bonus for full confluence
        if m15_confirmed and m5_confirmed and m1_confirmed:
            confidence += 10
            confluence_factors.append("Full multi-timeframe confluence!")
        
        return TradeSignal(
            signal=Signal.FALL if confidence >= 60 else Signal.NONE,
            confidence=min(confidence, 100),
            timestamp=datetime.now(pytz.UTC),
            price=ind_m1.close,
            indicators=self._format_indicators(ind_m1, ind_m5, ind_m15),
            confluence_factors=confluence_factors,
            m1_confirmed=m1_confirmed,
            m5_confirmed=m5_confirmed,
            m15_confirmed=m15_confirmed
        )
    
    def _format_indicators(
        self,
        ind_m1: IndicatorValues,
        ind_m5: IndicatorValues,
        ind_m15: IndicatorValues
    ) -> dict:
        """Format indicator values for output."""
        return {
            'm1': {
                'close': round(ind_m1.close, 5),
                'bb_upper': round(ind_m1.bb_upper, 5),
                'bb_middle': round(ind_m1.bb_middle, 5),
                'bb_lower': round(ind_m1.bb_lower, 5),
                'rsi': round(ind_m1.rsi, 2),
                'stoch_k': round(ind_m1.stoch_k, 2),
                'stoch_d': round(ind_m1.stoch_d, 2),
                'ema_200': round(ind_m1.ema_200, 5)
            },
            'm5': {
                'close': round(ind_m5.close, 5),
                'bb_upper': round(ind_m5.bb_upper, 5),
                'bb_middle': round(ind_m5.bb_middle, 5),
                'bb_lower': round(ind_m5.bb_lower, 5),
                'rsi': round(ind_m5.rsi, 2),
                'stoch_k': round(ind_m5.stoch_k, 2),
                'stoch_d': round(ind_m5.stoch_d, 2),
                'ema_200': round(ind_m5.ema_200, 5)
            },
            'm15': {
                'close': round(ind_m15.close, 5),
                'bb_upper': round(ind_m15.bb_upper, 5),
                'bb_middle': round(ind_m15.bb_middle, 5),
                'bb_lower': round(ind_m15.bb_lower, 5),
                'rsi': round(ind_m15.rsi, 2),
                'stoch_k': round(ind_m15.stoch_k, 2),
                'stoch_d': round(ind_m15.stoch_d, 2),
                'ema_200': round(ind_m15.ema_200, 5)
            }
        }
