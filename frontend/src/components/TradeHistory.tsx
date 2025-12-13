import { TrendingUp, TrendingDown, Download } from 'lucide-react';
import { Trade } from '../types';

interface TradeHistoryProps {
  trades: Trade[];
}

export function TradeHistory({ trades }: TradeHistoryProps) {
  const downloadCSV = () => {
    if (trades.length === 0) return;
    
    // CSV headers
    const headers = ['Time', 'Direction', 'Stake', 'Profit', 'Result', 'Entry Price', 'Exit Price', 'Confidence'];
    
    // CSV rows
    const rows = trades.map(trade => [
      new Date(trade.timestamp).toLocaleString(),
      trade.direction === 'CALL' ? 'RISE' : 'FALL',
      trade.stake.toFixed(2),
      trade.profit.toFixed(2),
      trade.result.toUpperCase(),
      trade.entry_price?.toFixed(5) || '',
      trade.exit_price?.toFixed(5) || '',
      trade.confidence?.toFixed(1) || ''
    ]);
    
    // Combine headers and rows
    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.join(','))
    ].join('\n');
    
    // Create and download file
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', `trade_history_${new Date().toISOString().split('T')[0]}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  if (trades.length === 0) {
    return (
      <div className="bg-deriv-gray rounded-lg p-4 border border-deriv-light">
        <h2 className="text-lg font-semibold mb-4">Trade History</h2>
        <div className="text-center py-8 text-gray-400">
          <p>No trades yet</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-deriv-gray rounded-lg p-4 border border-deriv-light">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-lg font-semibold">Trade History</h2>
        <button
          onClick={downloadCSV}
          className="flex items-center gap-2 px-3 py-1.5 bg-deriv-green/20 text-deriv-green rounded hover:bg-deriv-green/30 transition-colors text-sm"
        >
          <Download className="w-4 h-4" />
          Download CSV
        </button>
      </div>
      
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-gray-400 border-b border-deriv-light">
              <th className="text-left py-2 px-2">Time</th>
              <th className="text-left py-2 px-2">Direction</th>
              <th className="text-right py-2 px-2">Stake</th>
              <th className="text-right py-2 px-2">Profit</th>
              <th className="text-center py-2 px-2">Result</th>
            </tr>
          </thead>
          <tbody>
            {trades.map((trade) => {
              const time = new Date(trade.timestamp).toLocaleTimeString();
              const isWin = trade.result === 'win';
              
              return (
                <tr key={trade.id} className="border-b border-deriv-light/50 hover:bg-deriv-dark/50">
                  <td className="py-2 px-2 text-gray-400">{time}</td>
                  <td className="py-2 px-2">
                    <div className="flex items-center gap-1">
                      {trade.direction === 'CALL' ? (
                        <>
                          <TrendingUp className="w-4 h-4 text-deriv-green" />
                          <span className="text-deriv-green">RISE</span>
                        </>
                      ) : (
                        <>
                          <TrendingDown className="w-4 h-4 text-deriv-red" />
                          <span className="text-deriv-red">FALL</span>
                        </>
                      )}
                    </div>
                  </td>
                  <td className="py-2 px-2 text-right">${trade.stake.toFixed(2)}</td>
                  <td className={`py-2 px-2 text-right font-medium ${
                    trade.profit >= 0 ? 'text-deriv-green' : 'text-deriv-red'
                  }`}>
                    {trade.profit >= 0 ? '+' : ''}{trade.profit.toFixed(2)}
                  </td>
                  <td className="py-2 px-2 text-center">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                      isWin ? 'bg-deriv-green/20 text-deriv-green' : 'bg-deriv-red/20 text-deriv-red'
                    }`}>
                      {trade.result.toUpperCase()}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
