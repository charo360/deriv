"""Trade recorder for logging trades with full indicator values."""

import csv
import os
import json
from datetime import datetime
from typing import Dict, Optional, List
from dataclasses import dataclass, asdict
import pytz
import logging

logger = logging.getLogger(__name__)

# Directory for trade records
RECORDS_DIR = os.path.join(os.path.dirname(__file__), "trade_records")


@dataclass
class TradeRecord:
    """Complete trade record with all indicator values."""
    
    # Trade identification
    contract_id: str
    timestamp: str
    symbol: str
    direction: str  # CALL or PUT
    
    # Trade outcome
    result: str  # win, loss, tie
    stake: float
    payout: float
    profit: float
    entry_price: float
    exit_price: float
    
    # Signal info
    confidence: float
    confluence_factors: str  # JSON string of factors
    
    # M1 Indicators (Trigger timeframe)
    m1_close: float
    m1_rsi: float
    m1_stoch_k: float
    m1_stoch_d: float
    m1_bb_upper: float
    m1_bb_middle: float
    m1_bb_lower: float
    m1_ema_200: float
    
    # M5 Indicators (Alert timeframe)
    m5_close: float
    m5_rsi: float
    m5_stoch_k: float
    m5_stoch_d: float
    m5_bb_upper: float
    m5_bb_middle: float
    m5_bb_lower: float
    m5_ema_200: float
    
    # M15 Indicators (Higher timeframe)
    m15_close: float
    m15_rsi: float
    m15_stoch_k: float
    m15_stoch_d: float
    m15_bb_upper: float
    m15_bb_middle: float
    m15_bb_lower: float
    m15_ema_200: float
    
    # Timeframe confirmations
    m1_confirmed: bool
    m5_confirmed: bool
    m15_confirmed: bool


class TradeRecorder:
    """Records trades to CSV files for analysis."""
    
    def __init__(self):
        # Create records directory if it doesn't exist
        os.makedirs(RECORDS_DIR, exist_ok=True)
        self.current_file = self._get_current_file()
        self._ensure_headers()
    
    def _get_current_file(self) -> str:
        """Get the current month's CSV file."""
        now = datetime.now(pytz.UTC)
        filename = f"trades_{now.strftime('%Y_%m')}.csv"
        return os.path.join(RECORDS_DIR, filename)
    
    def _ensure_headers(self):
        """Ensure the CSV file has headers."""
        if not os.path.exists(self.current_file):
            headers = [
                'contract_id', 'timestamp', 'symbol', 'direction',
                'result', 'stake', 'payout', 'profit', 'entry_price', 'exit_price',
                'confidence', 'confluence_factors',
                'm1_close', 'm1_rsi', 'm1_stoch_k', 'm1_stoch_d', 
                'm1_bb_upper', 'm1_bb_middle', 'm1_bb_lower', 'm1_ema_200',
                'm5_close', 'm5_rsi', 'm5_stoch_k', 'm5_stoch_d',
                'm5_bb_upper', 'm5_bb_middle', 'm5_bb_lower', 'm5_ema_200',
                'm15_close', 'm15_rsi', 'm15_stoch_k', 'm15_stoch_d',
                'm15_bb_upper', 'm15_bb_middle', 'm15_bb_lower', 'm15_ema_200',
                'm1_confirmed', 'm5_confirmed', 'm15_confirmed'
            ]
            with open(self.current_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
            logger.info(f"Created new trade records file: {self.current_file}")
    
    def record_trade(
        self,
        contract_id: str,
        symbol: str,
        direction: str,
        result: str,
        stake: float,
        payout: float,
        profit: float,
        entry_price: float,
        exit_price: float,
        signal_data: Optional[Dict] = None
    ):
        """
        Record a completed trade with all indicator values.
        
        Args:
            contract_id: Deriv contract ID
            symbol: Trading symbol
            direction: CALL or PUT
            result: win, loss, or tie
            stake: Amount staked
            payout: Payout received
            profit: Net profit/loss
            entry_price: Entry spot price
            exit_price: Exit spot price
            signal_data: Signal data containing indicators and confluence factors
        """
        # Check if we need a new file (new month)
        new_file = self._get_current_file()
        if new_file != self.current_file:
            self.current_file = new_file
            self._ensure_headers()
        
        # Extract indicator values from signal data
        indicators = signal_data.get('indicators', {}) if signal_data else {}
        m1 = indicators.get('m1', {})
        m5 = indicators.get('m5', {})
        m15 = indicators.get('m15', {})
        
        record = TradeRecord(
            contract_id=contract_id,
            timestamp=datetime.now(pytz.UTC).isoformat(),
            symbol=symbol,
            direction=direction,
            result=result,
            stake=stake,
            payout=payout,
            profit=profit,
            entry_price=entry_price,
            exit_price=exit_price,
            confidence=signal_data.get('confidence', 0) if signal_data else 0,
            confluence_factors=json.dumps(signal_data.get('confluence_factors', [])) if signal_data else '[]',
            
            # M1 indicators
            m1_close=m1.get('close', 0),
            m1_rsi=m1.get('rsi', 0),
            m1_stoch_k=m1.get('stoch_k', 0),
            m1_stoch_d=m1.get('stoch_d', 0),
            m1_bb_upper=m1.get('bb_upper', 0),
            m1_bb_middle=m1.get('bb_middle', 0),
            m1_bb_lower=m1.get('bb_lower', 0),
            m1_ema_200=m1.get('ema_200', 0),
            
            # M5 indicators
            m5_close=m5.get('close', 0),
            m5_rsi=m5.get('rsi', 0),
            m5_stoch_k=m5.get('stoch_k', 0),
            m5_stoch_d=m5.get('stoch_d', 0),
            m5_bb_upper=m5.get('bb_upper', 0),
            m5_bb_middle=m5.get('bb_middle', 0),
            m5_bb_lower=m5.get('bb_lower', 0),
            m5_ema_200=m5.get('ema_200', 0),
            
            # M15 indicators
            m15_close=m15.get('close', 0),
            m15_rsi=m15.get('rsi', 0),
            m15_stoch_k=m15.get('stoch_k', 0),
            m15_stoch_d=m15.get('stoch_d', 0),
            m15_bb_upper=m15.get('bb_upper', 0),
            m15_bb_middle=m15.get('bb_middle', 0),
            m15_bb_lower=m15.get('bb_lower', 0),
            m15_ema_200=m15.get('ema_200', 0),
            
            # Confirmations
            m1_confirmed=signal_data.get('m1_confirmed', False) if signal_data else False,
            m5_confirmed=signal_data.get('m5_confirmed', False) if signal_data else False,
            m15_confirmed=signal_data.get('m15_confirmed', False) if signal_data else False
        )
        
        # Write to CSV
        with open(self.current_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                record.contract_id, record.timestamp, record.symbol, record.direction,
                record.result, record.stake, record.payout, record.profit,
                record.entry_price, record.exit_price,
                record.confidence, record.confluence_factors,
                record.m1_close, record.m1_rsi, record.m1_stoch_k, record.m1_stoch_d,
                record.m1_bb_upper, record.m1_bb_middle, record.m1_bb_lower, record.m1_ema_200,
                record.m5_close, record.m5_rsi, record.m5_stoch_k, record.m5_stoch_d,
                record.m5_bb_upper, record.m5_bb_middle, record.m5_bb_lower, record.m5_ema_200,
                record.m15_close, record.m15_rsi, record.m15_stoch_k, record.m15_stoch_d,
                record.m15_bb_upper, record.m15_bb_middle, record.m15_bb_lower, record.m15_ema_200,
                record.m1_confirmed, record.m5_confirmed, record.m15_confirmed
            ])
        
        logger.info(f"Trade recorded: {contract_id} - {result} - ${profit:.2f}")
    
    def get_records_summary(self) -> Dict:
        """Get a summary of all recorded trades."""
        all_records = []
        
        # Read all CSV files in the records directory
        if os.path.exists(RECORDS_DIR):
            for filename in os.listdir(RECORDS_DIR):
                if filename.endswith('.csv'):
                    filepath = os.path.join(RECORDS_DIR, filename)
                    with open(filepath, 'r') as f:
                        reader = csv.DictReader(f)
                        all_records.extend(list(reader))
        
        if not all_records:
            return {
                'total_trades': 0,
                'wins': 0,
                'losses': 0,
                'win_rate': 0,
                'total_profit': 0,
                'avg_win_confidence': 0,
                'avg_loss_confidence': 0
            }
        
        wins = [r for r in all_records if r['result'] == 'win']
        losses = [r for r in all_records if r['result'] == 'loss']
        
        total_profit = sum(float(r['profit']) for r in all_records)
        avg_win_conf = sum(float(r['confidence']) for r in wins) / len(wins) if wins else 0
        avg_loss_conf = sum(float(r['confidence']) for r in losses) / len(losses) if losses else 0
        
        return {
            'total_trades': len(all_records),
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': (len(wins) / len(all_records) * 100) if all_records else 0,
            'total_profit': total_profit,
            'avg_win_confidence': avg_win_conf,
            'avg_loss_confidence': avg_loss_conf,
            'records_file': self.current_file
        }
    
    def get_recent_records(self, limit: int = 50) -> List[Dict]:
        """Get the most recent trade records."""
        all_records = []
        
        if os.path.exists(RECORDS_DIR):
            for filename in sorted(os.listdir(RECORDS_DIR), reverse=True):
                if filename.endswith('.csv'):
                    filepath = os.path.join(RECORDS_DIR, filename)
                    with open(filepath, 'r') as f:
                        reader = csv.DictReader(f)
                        all_records.extend(list(reader))
                    if len(all_records) >= limit:
                        break
        
        # Return most recent first
        return all_records[-limit:][::-1]
    
    def get_todays_records(self) -> List[Dict]:
        """Get all trade records from today."""
        today = datetime.now(pytz.UTC).date()
        all_records = []
        
        if os.path.exists(self.current_file):
            with open(self.current_file, 'r') as f:
                reader = csv.DictReader(f)
                for record in reader:
                    try:
                        # Parse timestamp and check if it's today
                        ts = datetime.fromisoformat(record['timestamp'].replace('Z', '+00:00'))
                        if ts.date() == today:
                            all_records.append(record)
                    except (ValueError, KeyError):
                        continue
        
        return all_records


# Global recorder instance
trade_recorder = TradeRecorder()
