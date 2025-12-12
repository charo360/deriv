import { Activity, Wifi, WifiOff } from 'lucide-react';

interface HeaderProps {
  isConnected: boolean;
  isRunning: boolean;
  accountId: string;
  balance: number;
  currency: string;
}

export function Header({ isConnected, isRunning, accountId, balance, currency }: HeaderProps) {
  return (
    <header className="bg-deriv-gray border-b border-deriv-light px-6 py-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Activity className="w-8 h-8 text-deriv-green" />
            <div>
              <h1 className="text-xl font-bold">Deriv Trading Bot</h1>
              <p className="text-xs text-gray-400">Mean Reversion Strategy</p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-6">
          {/* Connection Status */}
          <div className="flex items-center gap-2">
            {isConnected ? (
              <>
                <Wifi className="w-4 h-4 text-deriv-green" />
                <span className="text-sm text-deriv-green">Connected</span>
              </>
            ) : (
              <>
                <WifiOff className="w-4 h-4 text-deriv-red" />
                <span className="text-sm text-deriv-red">Disconnected</span>
              </>
            )}
          </div>

          {/* Bot Status */}
          <div className="flex items-center gap-2">
            <div
              className={`w-3 h-3 rounded-full ${
                isRunning ? 'bg-deriv-green pulse-green' : 'bg-gray-500'
              }`}
            />
            <span className="text-sm">{isRunning ? 'Running' : 'Stopped'}</span>
          </div>

          {/* Account Info */}
          {accountId && (
            <div className="text-right">
              <p className="text-xs text-gray-400">{accountId}</p>
              <p className="text-lg font-bold text-deriv-green">
                {currency} {balance.toFixed(2)}
              </p>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
