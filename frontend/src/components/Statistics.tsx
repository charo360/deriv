import { TrendingUp, TrendingDown, Target, AlertTriangle, BarChart3, Percent } from 'lucide-react';
import { Statistics as StatsType } from '../types';

interface StatisticsProps {
  stats: StatsType;
}

export function Statistics({ stats }: StatisticsProps) {
  const statCards = [
    {
      label: 'Win Rate',
      value: `${stats.win_rate}%`,
      icon: Target,
      color: stats.win_rate >= 60 ? 'text-deriv-green' : stats.win_rate >= 50 ? 'text-yellow-500' : 'text-deriv-red',
    },
    {
      label: 'Total Profit',
      value: `$${stats.total_profit.toFixed(2)}`,
      icon: stats.total_profit >= 0 ? TrendingUp : TrendingDown,
      color: stats.total_profit >= 0 ? 'text-deriv-green' : 'text-deriv-red',
    },
    {
      label: 'Expectancy',
      value: `$${stats.expectancy.toFixed(2)}`,
      icon: BarChart3,
      color: stats.expectancy >= 0 ? 'text-deriv-green' : 'text-deriv-red',
    },
    {
      label: 'Max Drawdown',
      value: `${stats.max_drawdown.toFixed(1)}%`,
      icon: AlertTriangle,
      color: stats.max_drawdown <= 10 ? 'text-deriv-green' : stats.max_drawdown <= 20 ? 'text-yellow-500' : 'text-deriv-red',
    },
    {
      label: 'Profit Factor',
      value: stats.profit_factor === Infinity ? '∞' : stats.profit_factor.toFixed(2),
      icon: Percent,
      color: stats.profit_factor >= 1.5 ? 'text-deriv-green' : stats.profit_factor >= 1 ? 'text-yellow-500' : 'text-deriv-red',
    },
    {
      label: 'Total Trades',
      value: stats.total_trades.toString(),
      icon: BarChart3,
      color: 'text-blue-400',
    },
  ];

  return (
    <div className="bg-deriv-gray rounded-lg p-4 border border-deriv-light">
      <h2 className="text-lg font-semibold mb-4">Statistics</h2>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {statCards.map((stat) => (
          <div key={stat.label} className="bg-deriv-dark rounded-lg p-3">
            <div className="flex items-center gap-2 mb-1">
              <stat.icon className={`w-4 h-4 ${stat.color}`} />
              <span className="text-xs text-gray-400">{stat.label}</span>
            </div>
            <p className={`text-xl font-bold ${stat.color}`}>{stat.value}</p>
          </div>
        ))}
      </div>

      {/* Additional Info */}
      <div className="mt-4 pt-4 border-t border-deriv-light grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
        <div>
          <span className="text-gray-400">Wins/Losses:</span>
          <span className="ml-2 font-medium">
            <span className="text-deriv-green">{stats.wins}</span>
            {' / '}
            <span className="text-deriv-red">{stats.losses}</span>
          </span>
        </div>
        <div>
          <span className="text-gray-400">Daily Trades:</span>
          <span className="ml-2 font-medium">{stats.daily_trades}</span>
        </div>
        <div>
          <span className="text-gray-400">Daily P&L:</span>
          <span className={`ml-2 font-medium ${stats.daily_pnl >= 0 ? 'text-deriv-green' : 'text-deriv-red'}`}>
            ${stats.daily_pnl.toFixed(2)}
          </span>
        </div>
        <div>
          <span className="text-gray-400">Martingale Step:</span>
          <span className={`ml-2 font-medium ${stats.martingale_step > 0 ? 'text-yellow-500' : 'text-gray-300'}`}>
            {stats.martingale_step}/3
          </span>
        </div>
      </div>
    </div>
  );
}
