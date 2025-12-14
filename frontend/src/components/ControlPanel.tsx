import { useState } from 'react';
import { Play, Square, Power, PowerOff, TrendingUp, TrendingDown, Loader2, Settings } from 'lucide-react';

interface ControlPanelProps {
  isRunning: boolean;
  isTradingEnabled: boolean;
  loading: boolean;
  onStart: (apiToken: string) => void;
  onStop: () => void;
  onEnableTrading: () => void;
  onDisableTrading: () => void;
  onManualTrade: (direction: 'CALL' | 'PUT') => void;
  onUpdateSettings: (settings: { max_daily_profit_target?: number; max_session_loss?: number }) => void;
  currentSettings?: { max_daily_profit_target?: number; max_session_loss?: number };
}

export function ControlPanel({
  isRunning,
  isTradingEnabled,
  loading,
  onStart,
  onStop,
  onEnableTrading,
  onDisableTrading,
  onManualTrade,
  onUpdateSettings,
  currentSettings,
}: ControlPanelProps) {
  const [apiToken, setApiToken] = useState('');
  const [showTokenInput, setShowTokenInput] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [profitTarget, setProfitTarget] = useState(currentSettings?.max_daily_profit_target?.toString() || '200');
  const [sessionLoss, setSessionLoss] = useState(currentSettings?.max_session_loss?.toString() || '100');

  const handleStart = () => {
    if (apiToken.trim()) {
      onStart(apiToken);
      setShowTokenInput(false);
    }
  };

  return (
    <div className="bg-deriv-gray rounded-lg p-4 border border-deriv-light">
      <h2 className="text-lg font-semibold mb-4">Controls</h2>

      {/* Start/Stop Bot */}
      <div className="space-y-3">
        {!isRunning ? (
          <>
            {showTokenInput ? (
              <div className="space-y-2">
                <input
                  type="password"
                  placeholder="Enter Deriv API Token"
                  value={apiToken}
                  onChange={(e) => setApiToken(e.target.value)}
                  className="w-full px-3 py-2 bg-deriv-dark border border-deriv-light rounded text-sm focus:outline-none focus:border-deriv-green"
                />
                <div className="flex gap-2">
                  <button
                    onClick={handleStart}
                    disabled={loading || !apiToken.trim()}
                    className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-deriv-green text-white rounded font-medium hover:bg-opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                    Connect
                  </button>
                  <button
                    onClick={() => setShowTokenInput(false)}
                    className="px-4 py-2 bg-deriv-light text-white rounded hover:bg-opacity-80"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <button
                onClick={() => setShowTokenInput(true)}
                className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-deriv-green text-white rounded font-medium hover:bg-opacity-90"
              >
                <Play className="w-5 h-5" />
                Start Bot
              </button>
            )}
          </>
        ) : (
          <button
            onClick={onStop}
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-deriv-red text-white rounded font-medium hover:bg-opacity-90 disabled:opacity-50"
          >
            {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Square className="w-5 h-5" />}
            Stop Bot
          </button>
        )}

        {/* Enable/Disable Trading */}
        {isRunning && (
          <button
            onClick={isTradingEnabled ? onDisableTrading : onEnableTrading}
            disabled={loading}
            className={`w-full flex items-center justify-center gap-2 px-4 py-3 rounded font-medium transition-colors ${
              isTradingEnabled
                ? 'bg-yellow-600 hover:bg-yellow-700'
                : 'bg-blue-600 hover:bg-blue-700'
            } text-white disabled:opacity-50`}
          >
            {isTradingEnabled ? (
              <>
                <PowerOff className="w-5 h-5" />
                Disable Auto-Trading
              </>
            ) : (
              <>
                <Power className="w-5 h-5" />
                Enable Auto-Trading
              </>
            )}
          </button>
        )}

        {/* Manual Trade Buttons */}
        {isRunning && (
          <div className="pt-4 border-t border-deriv-light">
            <p className="text-sm text-gray-400 mb-2">Manual Trade</p>
            <div className="flex gap-2">
              <button
                onClick={() => onManualTrade('CALL')}
                disabled={loading}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-deriv-green text-white rounded font-medium hover:bg-opacity-90 disabled:opacity-50"
              >
                <TrendingUp className="w-5 h-5" />
                RISE
              </button>
              <button
                onClick={() => onManualTrade('PUT')}
                disabled={loading}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-deriv-red text-white rounded font-medium hover:bg-opacity-90 disabled:opacity-50"
              >
                <TrendingDown className="w-5 h-5" />
                FALL
              </button>
            </div>
          </div>
        )}

        {/* TP/SL Settings */}
        <div className="pt-4 border-t border-deriv-light">
          <button
            onClick={() => setShowSettings(!showSettings)}
            className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-deriv-light text-white rounded hover:bg-opacity-80 text-sm"
          >
            <Settings className="w-4 h-4" />
            {showSettings ? 'Hide' : 'Show'} TP/SL Settings
          </button>

          {showSettings && (
            <div className="mt-3 space-y-3">
              <div>
                <label className="text-xs text-gray-400 block mb-1">Take Profit Target</label>
                <input
                  type="number"
                  value={profitTarget}
                  onChange={(e) => setProfitTarget(e.target.value)}
                  placeholder="200"
                  className="w-full px-3 py-2 bg-deriv-dark border border-deriv-light rounded text-sm focus:outline-none focus:border-deriv-green"
                />
              </div>
              <div>
                <label className="text-xs text-gray-400 block mb-1">Stop Loss Limit</label>
                <input
                  type="number"
                  value={sessionLoss}
                  onChange={(e) => setSessionLoss(e.target.value)}
                  placeholder="100"
                  className="w-full px-3 py-2 bg-deriv-dark border border-deriv-light rounded text-sm focus:outline-none focus:border-deriv-red"
                />
              </div>
              <button
                onClick={() => {
                  onUpdateSettings({
                    max_daily_profit_target: parseFloat(profitTarget) || 200,
                    max_session_loss: parseFloat(sessionLoss) || 100,
                  });
                  setShowSettings(false);
                }}
                disabled={loading}
                className="w-full px-4 py-2 bg-blue-600 text-white rounded text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
              >
                Save Settings
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
