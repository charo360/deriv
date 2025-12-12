import { useMemo } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import { Trade } from '../types';

interface EquityChartProps {
  trades: Trade[];
  initialBalance: number;
}

export function EquityChart({ trades, initialBalance }: EquityChartProps) {
  const chartData = useMemo(() => {
    let balance = initialBalance;
    const data = [{ trade: 0, balance: initialBalance }];
    
    // Reverse to get chronological order
    const chronologicalTrades = [...trades].reverse();
    
    chronologicalTrades.forEach((trade, index) => {
      balance += trade.profit;
      data.push({
        trade: index + 1,
        balance: parseFloat(balance.toFixed(2)),
      });
    });
    
    return data;
  }, [trades, initialBalance]);

  if (trades.length === 0) {
    return (
      <div className="bg-deriv-gray rounded-lg p-4 border border-deriv-light">
        <h2 className="text-lg font-semibold mb-4">Equity Curve</h2>
        <div className="h-48 flex items-center justify-center text-gray-400">
          <p>No trade data to display</p>
        </div>
      </div>
    );
  }

  const currentBalance = chartData[chartData.length - 1]?.balance || initialBalance;
  const isProfit = currentBalance >= initialBalance;

  return (
    <div className="bg-deriv-gray rounded-lg p-4 border border-deriv-light">
      <h2 className="text-lg font-semibold mb-4">Equity Curve</h2>
      
      <div className="h-48">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
            <XAxis 
              dataKey="trade" 
              stroke="#666"
              tick={{ fill: '#666', fontSize: 10 }}
            />
            <YAxis 
              stroke="#666"
              tick={{ fill: '#666', fontSize: 10 }}
              domain={['auto', 'auto']}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#1a1a1a',
                border: '1px solid #2a2a2a',
                borderRadius: '8px',
              }}
              labelStyle={{ color: '#999' }}
              formatter={(value: number) => [`$${value.toFixed(2)}`, 'Balance']}
              labelFormatter={(label) => `Trade #${label}`}
            />
            <ReferenceLine 
              y={initialBalance} 
              stroke="#666" 
              strokeDasharray="3 3" 
            />
            <Line
              type="monotone"
              dataKey="balance"
              stroke={isProfit ? '#00a79e' : '#ff444f'}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, fill: isProfit ? '#00a79e' : '#ff444f' }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
