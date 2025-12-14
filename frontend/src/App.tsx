import { useWebSocket } from './hooks/useWebSocket';
import { useApi } from './hooks/useApi';
import { Header } from './components/Header';
import { ControlPanel } from './components/ControlPanel';
import { Statistics } from './components/Statistics';
import { SignalPanel } from './components/SignalPanel';
import { TradeHistory } from './components/TradeHistory';
import { EquityChart } from './components/EquityChart';
import { AlertTriangle } from 'lucide-react';

function App() {
  const { state, isConnected } = useWebSocket();
  const {
    loading,
    error,
    clearError,
    startBot,
    stopBot,
    enableTrading,
    disableTrading,
    manualTrade,
    updateSettings,
    clearHistory,
  } = useApi();

  // Default values when not connected
  const defaultStats = {
    total_trades: 0,
    wins: 0,
    losses: 0,
    win_rate: 0,
    total_profit: 0,
    profit_factor: 0,
    expectancy: 0,
    max_drawdown: 0,
    current_balance: 0,
    consecutive_losses: 0,
    martingale_step: 0,
    daily_trades: 0,
    daily_pnl: 0,
  };

  return (
    <div className="min-h-screen bg-deriv-dark">
      <Header
        isConnected={isConnected}
        isRunning={state?.is_running ?? false}
        accountId={state?.account?.account_id ?? ''}
        balance={state?.account?.balance ?? 0}
        currency={state?.account?.currency ?? 'USD'}
      />

      <main className="container mx-auto px-4 py-6">
        {/* Error Alert */}
        {error && (
          <div className="mb-4 bg-deriv-red/20 border border-deriv-red rounded-lg p-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <AlertTriangle className="w-5 h-5 text-deriv-red" />
              <span className="text-deriv-red">{error}</span>
            </div>
            <button
              onClick={clearError}
              className="text-deriv-red hover:text-white text-sm px-2 py-1 rounded hover:bg-deriv-red/30"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Risk Warning */}
        {!state?.is_running && (
          <div className="mb-4 bg-yellow-500/20 border border-yellow-500 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-yellow-500 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-medium text-yellow-500">Risk Warning</p>
                <p className="text-sm text-gray-300 mt-1">
                  Trading synthetic indices involves significant risk. This bot uses a mean reversion 
                  strategy with capped Martingale. Always start with a demo account and never risk 
                  more than you can afford to lose. Expected drawdowns: 15-25%.
                </p>
              </div>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column - Controls & Signal */}
          <div className="space-y-6">
            <ControlPanel
              isRunning={state?.is_running ?? false}
              isTradingEnabled={state?.is_trading_enabled ?? false}
              loading={loading}
              onStart={startBot}
              onStop={stopBot}
              onEnableTrading={enableTrading}
              onDisableTrading={disableTrading}
              onManualTrade={manualTrade}
              onUpdateSettings={updateSettings}
              currentSettings={{
                max_daily_profit_target: state?.settings?.max_daily_profit_target,
                max_session_loss: state?.settings?.max_session_loss,
              }}
            />

            <SignalPanel
              signal={state?.current_signal ?? null}
              pendingContract={state?.pending_contract ?? null}
            />
          </div>

          {/* Middle Column - Statistics & Chart */}
          <div className="space-y-6">
            <Statistics stats={state?.statistics ?? defaultStats} />
            <EquityChart
              trades={state?.trade_history ?? []}
              initialBalance={state?.account?.balance ?? 1000}
            />
          </div>

          {/* Right Column - Trade History */}
          <div>
            <TradeHistory 
              trades={state?.trade_history ?? []} 
              onClearHistory={clearHistory}
            />
          </div>
        </div>

        {/* Strategy Info */}
        <div className="mt-6 bg-deriv-gray rounded-lg p-4 border border-deriv-light">
          <h2 className="text-lg font-semibold mb-3">Strategy: Enhanced Mean Reversion with Confluence</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
            <div>
              <p className="text-gray-400 mb-1">Indicators</p>
              <ul className="space-y-1">
                <li>• Bollinger Bands (20, 2.0)</li>
                <li>• RSI (14)</li>
                <li>• Stochastic (5, 3, 3)</li>
                <li>• EMA 200</li>
              </ul>
            </div>
            <div>
              <p className="text-gray-400 mb-1">Entry Conditions</p>
              <ul className="space-y-1">
                <li>• Price at BB extreme</li>
                <li>• RSI oversold/overbought</li>
                <li>• Stochastic cross</li>
                <li>• Multi-TF confluence</li>
              </ul>
            </div>
            <div>
              <p className="text-gray-400 mb-1">Risk Management</p>
              <ul className="space-y-1">
                <li>• 1-2% risk per trade</li>
                <li>• Capped Martingale (3 steps)</li>
                <li>• Daily loss limit: 10%</li>
                <li>• Max 10 trades/day</li>
              </ul>
            </div>
            <div>
              <p className="text-gray-400 mb-1">Expected Performance</p>
              <ul className="space-y-1">
                <li>• Win Rate: 65-75%</li>
                <li>• Expectancy: $2-4/trade</li>
                <li>• Max Drawdown: 15-25%</li>
                <li>• 2-4 trades/day</li>
              </ul>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-deriv-light mt-8 py-4">
        <div className="container mx-auto px-4 text-center text-sm text-gray-500">
          <p>Deriv Trading Bot v1.0 | Mean Reversion Strategy for V75</p>
          <p className="mt-1">⚠️ For educational purposes only. Trade at your own risk.</p>
        </div>
      </footer>
    </div>
  );
}

export default App;
