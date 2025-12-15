export interface BotState {
  is_running: boolean;
  is_trading_enabled: boolean;
  symbol: string;
  account: AccountInfo;
  statistics: Statistics;
  current_signal: SignalInfo | null;
  pending_contract: string | null;
  trade_history: Trade[];
  settings: Settings;
}

export interface AccountInfo {
  connected: boolean;
  authorized: boolean;
  account_id: string;
  balance: number;
  currency: string;
  active_contracts: number;
}

export interface Statistics {
  total_trades: number;
  wins: number;
  losses: number;
  win_rate: number;
  total_profit: number;
  profit_factor: number;
  expectancy: number;
  max_drawdown: number;
  current_balance: number;
  consecutive_losses: number;
  martingale_step: number;
  daily_trades: number;
  daily_pnl: number;
}

export interface SignalInfo {
  signal: 'CALL' | 'PUT' | 'NONE';
  confidence: number;
  timestamp: string;
  price: number;
  confluence_factors: string[];
  m1_confirmed: boolean;
  m5_confirmed: boolean;
  m15_confirmed: boolean;
  indicators: {
    m1: IndicatorSet;
    m5: IndicatorSet;
    m15: IndicatorSet;
  };
}

export interface IndicatorSet {
  close: number;
  bb_upper: number;
  bb_middle: number;
  bb_lower: number;
  rsi: number;
  stoch_k: number;
  stoch_d: number;
  ema_50: number;
  ema_200: number;
  adx: number;
  plus_di: number;
  minus_di: number;
  macd: number;
  macd_signal: number;
  macd_histogram: number;
}

export interface Trade {
  id: string;
  timestamp: string;
  symbol: string;
  direction: string;
  stake: number;
  payout: number;
  result: 'win' | 'loss' | 'tie';
  profit: number;
  entry_price: number;
  exit_price: number;
}

export interface Settings {
  initial_stake: number;
  risk_percent: number;
  max_martingale_steps: number;
  trade_duration: number;
  trade_duration_unit: string;
  max_daily_profit_target: number;
  max_session_loss: number;
}

export interface WebSocketMessage {
  type: string;
  data: BotState;
  timestamp: string;
}
