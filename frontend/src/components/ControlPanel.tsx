import { useState } from 'react';
import { Play, Square, Power, PowerOff, TrendingUp, TrendingDown, Loader2 } from 'lucide-react';

interface ControlPanelProps {
  isRunning: boolean;
  isTradingEnabled: boolean;
  loading: boolean;
  onStart: (apiToken: string) => void;
  onStop: () => void;
  onEnableTrading: () => void;
  onDisableTrading: () => void;
  onManualTrade: (direction: 'CALL' | 'PUT') => void;
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
}: ControlPanelProps) {
  const [apiToken, setApiToken] = useState('');
  const [showTokenInput, setShowTokenInput] = useState(false);

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
      </div>
    </div>
  );
}
