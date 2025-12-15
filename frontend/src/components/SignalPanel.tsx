import { TrendingUp, TrendingDown, Clock, CheckCircle, XCircle } from 'lucide-react';
import { SignalInfo } from '../types';

interface SignalPanelProps {
  signal: SignalInfo | null;
  pendingContract: string | null;
}

export function SignalPanel({ signal, pendingContract }: SignalPanelProps) {
  if (!signal) {
    return (
      <div className="bg-deriv-gray rounded-lg p-4 border border-deriv-light">
        <h2 className="text-lg font-semibold mb-4">Current Signal</h2>
        <div className="text-center py-8 text-gray-400">
          <Clock className="w-12 h-12 mx-auto mb-2 opacity-50" />
          <p>Waiting for market data...</p>
        </div>
      </div>
    );
  }

  const isRise = signal.signal === 'CALL';
  const isFall = signal.signal === 'PUT';
  const hasSignal = isRise || isFall;

  return (
    <div className="bg-deriv-gray rounded-lg p-4 border border-deriv-light">
      <h2 className="text-lg font-semibold mb-4">Current Signal</h2>

      {/* Signal Display */}
      <div className={`rounded-lg p-4 mb-4 ${
        isRise ? 'bg-deriv-green/20 border border-deriv-green' :
        isFall ? 'bg-deriv-red/20 border border-deriv-red' :
        'bg-deriv-dark border border-deriv-light'
      }`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {isRise && <TrendingUp className="w-8 h-8 text-deriv-green" />}
            {isFall && <TrendingDown className="w-8 h-8 text-deriv-red" />}
            {!hasSignal && <Clock className="w-8 h-8 text-gray-400" />}
            <div>
              <p className={`text-2xl font-bold ${
                isRise ? 'text-deriv-green' : isFall ? 'text-deriv-red' : 'text-gray-400'
              }`}>
                {isRise ? 'RISE' : isFall ? 'FALL' : 'NO SIGNAL'}
              </p>
              <p className="text-sm text-gray-400">
                Price: {signal.price.toFixed(4)}
              </p>
            </div>
          </div>
          
          <div className="text-right">
            <p className="text-sm text-gray-400">Confidence</p>
            <p className={`text-2xl font-bold ${
              signal.confidence >= 80 ? 'text-deriv-green' :
              signal.confidence >= 60 ? 'text-yellow-500' : 'text-gray-400'
            }`}>
              {signal.confidence}%
            </p>
          </div>
        </div>
      </div>

      {/* RSI Display - M1 (matches Deriv platform) */}
      {signal.indicators && signal.indicators.m1 && signal.indicators.m5 && (
        <div className="bg-deriv-dark rounded-lg p-3 mb-4 border border-deriv-light">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-gray-400 mb-1">M1 RSI (Deriv Platform)</p>
              <p className={`text-3xl font-bold ${
                signal.indicators.m1.rsi < 35 ? 'text-deriv-green' :
                signal.indicators.m1.rsi > 65 ? 'text-deriv-red' : 'text-yellow-500'
              }`}>
                {signal.indicators.m1.rsi.toFixed(1)}
              </p>
            </div>
            <div className="text-right text-sm">
              {signal.indicators.m1.rsi < 35 ? (
                <div className="text-deriv-green">
                  <p className="font-semibold">OVERSOLD ✓</p>
                  <p className="text-xs opacity-75">{(35 - signal.indicators.m1.rsi).toFixed(1)} below threshold</p>
                </div>
              ) : signal.indicators.m1.rsi > 65 ? (
                <div className="text-deriv-red">
                  <p className="font-semibold">OVERBOUGHT ✓</p>
                  <p className="text-xs opacity-75">{(signal.indicators.m1.rsi - 65).toFixed(1)} above threshold</p>
                </div>
              ) : (
                <div className="text-gray-400">
                  <p className="font-semibold">NEUTRAL</p>
                  <p className="text-xs">
                    {signal.indicators.m1.rsi < 50 
                      ? `${(35 - signal.indicators.m1.rsi).toFixed(1)} to oversold`
                      : `${(signal.indicators.m1.rsi - 65).toFixed(1)} to overbought`
                    }
                  </p>
                </div>
              )}
            </div>
          </div>
          <div className="mt-2 pt-2 border-t border-deriv-light/30 text-xs text-gray-400">
            <span>M5 RSI (Strategy): </span>
            <span className={`font-medium ${
              signal.indicators.m5.rsi < 35 ? 'text-deriv-green' :
              signal.indicators.m5.rsi > 65 ? 'text-deriv-red' : 'text-gray-300'
            }`}>{signal.indicators.m5.rsi.toFixed(1)}</span>
          </div>
        </div>
      )}

      {/* ADX Display - Trend Strength (M5) */}
      {signal.indicators && signal.indicators.m5 && (
        <div className="bg-deriv-dark rounded-lg p-3 mb-4 border border-deriv-light">
          <p className="text-xs text-gray-400 mb-2">ADX - Trend Strength (M5)</p>
          <div className="grid grid-cols-3 gap-3">
            <div className="text-center">
              <p className="text-xs text-gray-400 mb-1">ADX</p>
              <p className={`text-2xl font-bold ${
                signal.indicators.m5.adx > 25 ? 'text-deriv-green' :
                signal.indicators.m5.adx < 20 ? 'text-yellow-500' : 'text-gray-300'
              }`}>
                {signal.indicators.m5.adx.toFixed(2)}
              </p>
              <p className="text-xs text-gray-400 mt-1">
                {signal.indicators.m5.adx > 25 ? 'Trending' : signal.indicators.m5.adx < 20 ? 'Ranging' : 'Neutral'}
              </p>
            </div>
            <div className="text-center">
              <p className="text-xs text-gray-400 mb-1">+DI</p>
              <p className="text-2xl font-bold text-deriv-green">
                {signal.indicators.m5.plus_di.toFixed(2)}
              </p>
              <p className="text-xs text-gray-400 mt-1">Bullish</p>
            </div>
            <div className="text-center">
              <p className="text-xs text-gray-400 mb-1">-DI</p>
              <p className="text-2xl font-bold text-deriv-red">
                {signal.indicators.m5.minus_di.toFixed(2)}
              </p>
              <p className="text-xs text-gray-400 mt-1">Bearish</p>
            </div>
          </div>
        </div>
      )}

      {/* ADX Display - M1 Pullback Momentum */}
      {signal.indicators && signal.indicators.m1 && (
        <div className="bg-deriv-dark rounded-lg p-3 mb-4 border border-deriv-light">
          <p className="text-xs text-gray-400 mb-2">M1 ADX - Pullback Momentum</p>
          <div className="grid grid-cols-3 gap-3">
            <div className="text-center">
              <p className="text-xs text-gray-400 mb-1">ADX</p>
              <p className={`text-xl font-bold ${
                signal.indicators.m1.adx < 20 ? 'text-deriv-green' :
                signal.indicators.m1.adx > 25 ? 'text-deriv-red' : 'text-yellow-500'
              }`}>
                {signal.indicators.m1.adx.toFixed(2)}
              </p>
              <p className="text-xs text-gray-400 mt-1">
                {signal.indicators.m1.adx < 20 ? 'Weak' : signal.indicators.m1.adx > 25 ? 'Strong' : 'Moderate'}
              </p>
            </div>
            <div className="text-center">
              <p className="text-xs text-gray-400 mb-1">+DI</p>
              <p className="text-xl font-bold text-deriv-green">
                {signal.indicators.m1.plus_di.toFixed(2)}
              </p>
            </div>
            <div className="text-center">
              <p className="text-xs text-gray-400 mb-1">-DI</p>
              <p className="text-xl font-bold text-deriv-red">
                {signal.indicators.m1.minus_di.toFixed(2)}
              </p>
            </div>
          </div>
          <div className="mt-2 pt-2 border-t border-deriv-light/30 text-xs text-gray-400">
            <p>
              {signal.indicators.m1.adx < 20 
                ? '✓ Low M1 ADX = Pullback exhausting, good for entry'
                : signal.indicators.m1.adx > 25
                ? '⚠ High M1 ADX = Pullback has momentum, wait'
                : 'Moderate M1 ADX = Acceptable entry conditions'
              }
            </p>
          </div>
        </div>
      )}

      {/* Pending Contract */}
      {pendingContract && (
        <div className="bg-blue-500/20 border border-blue-500 rounded-lg p-3 mb-4">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-blue-500 rounded-full animate-pulse" />
            <span className="text-sm">Contract Active: {pendingContract}</span>
          </div>
        </div>
      )}

      {/* Timeframe Confirmations */}
      <div className="mb-4">
        <p className="text-sm text-gray-400 mb-2">Timeframe Confluence</p>
        <div className="flex gap-2">
          {[
            { label: 'M15', confirmed: signal.m15_confirmed },
            { label: 'M5', confirmed: signal.m5_confirmed },
            { label: 'M1', confirmed: signal.m1_confirmed },
          ].map((tf) => (
            <div
              key={tf.label}
              className={`flex items-center gap-1 px-3 py-1 rounded ${
                tf.confirmed ? 'bg-deriv-green/20 text-deriv-green' : 'bg-deriv-dark text-gray-400'
              }`}
            >
              {tf.confirmed ? (
                <CheckCircle className="w-4 h-4" />
              ) : (
                <XCircle className="w-4 h-4" />
              )}
              <span className="text-sm font-medium">{tf.label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Confluence Factors */}
      <div>
        <p className="text-sm text-gray-400 mb-2">Confluence Factors</p>
        <div className="space-y-1 max-h-32 overflow-y-auto">
          {signal.confluence_factors.map((factor, i) => (
            <div key={i} className="flex items-start gap-2 text-sm">
              <CheckCircle className="w-4 h-4 text-deriv-green flex-shrink-0 mt-0.5" />
              <span>{factor}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Indicators */}
      {signal.indicators && hasSignal && (
        <div className="mt-4 pt-4 border-t border-deriv-light">
          <p className="text-sm text-gray-400 mb-2">M5 Indicators</p>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div>
              <span className="text-gray-400">RSI:</span>
              <span className={`ml-2 font-medium ${
                signal.indicators.m5.rsi < 35 ? 'text-deriv-green' :
                signal.indicators.m5.rsi > 65 ? 'text-deriv-red' : 'text-gray-300'
              }`}>
                {signal.indicators.m5.rsi.toFixed(1)}
              </span>
            </div>
            <div>
              <span className="text-gray-400">Stoch K:</span>
              <span className={`ml-2 font-medium ${
                signal.indicators.m5.stoch_k < 20 ? 'text-deriv-green' :
                signal.indicators.m5.stoch_k > 80 ? 'text-deriv-red' : 'text-gray-300'
              }`}>
                {signal.indicators.m5.stoch_k.toFixed(1)}
              </span>
            </div>
            <div>
              <span className="text-gray-400">BB Upper:</span>
              <span className="ml-2 font-medium">{signal.indicators.m5.bb_upper.toFixed(2)}</span>
            </div>
            <div>
              <span className="text-gray-400">BB Lower:</span>
              <span className="ml-2 font-medium">{signal.indicators.m5.bb_lower.toFixed(2)}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
