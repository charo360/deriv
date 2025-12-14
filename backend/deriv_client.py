"""Deriv WebSocket API client for trading synthetic indices."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional, Callable, Dict, List, Any
from dataclasses import dataclass
import websockets
from websockets.exceptions import ConnectionClosed
import pytz

from config import trading_config

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


@dataclass
class ContractResult:
    """Result of a completed contract."""
    contract_id: str
    buy_price: float
    sell_price: float
    profit: float
    entry_spot: float
    exit_spot: float
    is_win: bool
    is_sold: bool


class DerivClient:
    """
    WebSocket client for Deriv API.
    
    Handles:
    - Authentication
    - Real-time tick/candle streaming
    - Contract purchase and monitoring
    - Account balance updates
    """
    
    DERIV_WS_URL = "wss://ws.derivws.com/websockets/v3"
    
    def __init__(
        self,
        api_token: str,
        app_id: int = 1089,
        on_tick: Optional[Callable] = None,
        on_candle: Optional[Callable] = None,
        on_balance: Optional[Callable] = None,
        on_contract_update: Optional[Callable] = None
    ):
        self.api_token = api_token
        self.app_id = app_id
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False
        self.is_authorized = False
        
        # Callbacks
        self.on_tick = on_tick
        self.on_candle = on_candle
        self.on_balance = on_balance
        self.on_contract_update = on_contract_update
        
        # State
        self.balance = 0.0
        self.currency = "USD"
        self.account_id = ""
        self.subscriptions: Dict[str, str] = {}
        self.pending_requests: Dict[int, asyncio.Future] = {}
        self.request_id = 0
        
        # Candle storage
        self.candles_m1: List[dict] = []
        self.candles_m5: List[dict] = []
        self.candles_m15: List[dict] = []
        
        # Current tick data for building incomplete candles
        self.current_tick_price: float = 0.0
        self.current_tick_epoch: int = 0
        
        # Active contracts
        self.active_contracts: Dict[str, dict] = {}
    
    def _next_req_id(self) -> int:
        """Generate unique request ID."""
        self.request_id += 1
        return self.request_id
    
    async def connect(self):
        """Establish WebSocket connection."""
        url = f"{self.DERIV_WS_URL}?app_id={self.app_id}"
        
        try:
            self.ws = await websockets.connect(url, ping_interval=30)
            self.is_connected = True
            logger.info("Connected to Deriv WebSocket")
            
            # Start message handler
            self._handler_task = asyncio.create_task(self._message_handler())
            
            # Give the handler task a chance to start
            await asyncio.sleep(0.1)
            
            # Authorize
            await self._authorize()
            
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self.is_connected = False
            raise
    
    async def disconnect(self):
        """Close WebSocket connection."""
        if self.ws:
            await self.ws.close()
            self.is_connected = False
            self.is_authorized = False
            logger.info("Disconnected from Deriv")
    
    async def _send(self, request: dict) -> dict:
        """Send request and wait for response."""
        if not self.ws or not self.is_connected:
            raise ConnectionError("Not connected to Deriv")
        
        req_id = self._next_req_id()
        request["req_id"] = req_id
        
        # Create future for response
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self.pending_requests[req_id] = future
        
        logger.info(f"Sending request {req_id}: {request.get('msg_type', list(request.keys())[0])}")
        await self.ws.send(json.dumps(request))
        
        try:
            response = await asyncio.wait_for(future, timeout=30)
            logger.info(f"Got response for request {req_id}")
            return response
        except asyncio.TimeoutError:
            logger.error(f"Request {req_id} timed out. Pending: {list(self.pending_requests.keys())}")
            if req_id in self.pending_requests:
                del self.pending_requests[req_id]
            raise TimeoutError(f"Request {req_id} timed out")
    
    async def _message_handler(self):
        """Handle incoming WebSocket messages."""
        try:
            async for message in self.ws:
                try:
                    data = json.loads(message)
                    await self._process_message(data)
                except Exception as e:
                    # Log but continue processing messages
                    logger.error(f"Error processing message: {e}")
                    continue
        except ConnectionClosed:
            logger.warning("WebSocket connection closed")
            self.is_connected = False
        except Exception as e:
            logger.error(f"Message handler error: {e}")
            self.is_connected = False
    
    async def _process_message(self, data: dict):
        """Process incoming message."""
        msg_type = data.get("msg_type")
        req_id = data.get("req_id")
        
        logger.debug(f"Received msg_type={msg_type}, req_id={req_id} (type={type(req_id).__name__})")
        
        # Convert req_id to int if it's a string (API may return either)
        if req_id is not None:
            try:
                req_id = int(req_id)
            except (ValueError, TypeError):
                pass
        
        logger.debug(f"After conversion req_id={req_id}, pending={list(self.pending_requests.keys())}")
        
        # Handle errors
        if "error" in data:
            logger.error(f"API Error: {data['error']}")
            if req_id and req_id in self.pending_requests:
                self.pending_requests[req_id].set_exception(
                    Exception(data["error"].get("message", "Unknown error"))
                )
                del self.pending_requests[req_id]
            return
        
        # Resolve pending request
        if req_id and req_id in self.pending_requests:
            self.pending_requests[req_id].set_result(data)
            del self.pending_requests[req_id]
        
        # Handle specific message types
        if msg_type == "tick":
            await self._handle_tick(data)
        elif msg_type == "ohlc":
            await self._handle_candle(data)
        elif msg_type == "balance":
            await self._handle_balance(data)
        elif msg_type == "proposal_open_contract":
            await self._handle_contract_update(data)
        elif msg_type == "buy":
            await self._handle_buy_response(data)
    
    async def _authorize(self):
        """Authorize with API token."""
        response = await self._send({
            "authorize": self.api_token
        })
        
        if "authorize" in response:
            auth = response["authorize"]
            self.balance = float(auth.get("balance", 0))
            self.currency = auth.get("currency", "USD")
            self.account_id = auth.get("loginid", "")
            self.is_authorized = True
            logger.info(f"Authorized: {self.account_id}, Balance: {self.balance} {self.currency}")
            
            # Subscribe to balance updates
            await self._subscribe_balance()
        else:
            raise Exception("Authorization failed")
    
    async def _subscribe_balance(self):
        """Subscribe to balance updates."""
        await self._send({
            "balance": 1,
            "subscribe": 1
        })
    
    async def subscribe_ticks(self, symbol: str):
        """Subscribe to real-time ticks."""
        response = await self._send({
            "ticks": symbol,
            "subscribe": 1
        })
        
        if "subscription" in response:
            self.subscriptions[f"ticks_{symbol}"] = response["subscription"]["id"]
            logger.info(f"Subscribed to ticks: {symbol}")
    
    async def subscribe_candles(self, symbol: str, granularity: int):
        """
        Subscribe to OHLC candles.
        
        Args:
            symbol: Trading symbol (e.g., "R_75")
            granularity: Candle period in seconds (60, 300, 900)
        """
        response = await self._send({
            "ticks_history": symbol,
            "adjust_start_time": 1,
            "count": 250,  # Get enough history for EMA 200
            "end": "latest",
            "granularity": granularity,
            "style": "candles",
            "subscribe": 1
        })
        
        if "candles" in response:
            candles = response["candles"]
            
            # Store candles by timeframe
            if granularity == 60:
                self.candles_m1 = candles
            elif granularity == 300:
                self.candles_m5 = candles
            elif granularity == 900:
                self.candles_m15 = candles
            
            logger.info(f"Received {len(candles)} candles for {symbol} ({granularity}s)")
        
        if "subscription" in response:
            self.subscriptions[f"candles_{symbol}_{granularity}"] = response["subscription"]["id"]
    
    async def _handle_tick(self, data: dict):
        """Handle incoming tick."""
        tick = data.get("tick", {})
        
        # Store current tick for building incomplete candles (round to 4 decimals)
        self.current_tick_price = round(float(tick.get("quote", 0)), 4)
        self.current_tick_epoch = tick.get("epoch", 0)
        
        if self.on_tick:
            await self.on_tick({
                "symbol": tick.get("symbol"),
                "quote": self.current_tick_price,
                "epoch": self.current_tick_epoch
            })
    
    async def _handle_candle(self, data: dict):
        """Handle incoming candle update."""
        ohlc = data.get("ohlc", {})
        granularity = int(ohlc.get("granularity", 60))
        
        candle = {
            "epoch": ohlc.get("epoch"),
            "open": round(float(ohlc.get("open", 0)), 4),
            "high": round(float(ohlc.get("high", 0)), 4),
            "low": round(float(ohlc.get("low", 0)), 4),
            "close": round(float(ohlc.get("close", 0)), 4)
        }
        
        # Update appropriate candle list
        if granularity == 60:
            self._update_candle_list(self.candles_m1, candle)
        elif granularity == 300:
            self._update_candle_list(self.candles_m5, candle)
        elif granularity == 900:
            self._update_candle_list(self.candles_m15, candle)
        
        if self.on_candle:
            await self.on_candle({
                "granularity": granularity,
                "candle": candle
            })
    
    def _update_candle_list(self, candles: List[dict], new_candle: dict):
        """Update candle list with new candle."""
        if candles and candles[-1]["epoch"] == new_candle["epoch"]:
            # Update existing candle
            candles[-1] = new_candle
        else:
            # Add new candle
            candles.append(new_candle)
            # Keep only last 250 candles
            if len(candles) > 250:
                candles.pop(0)
    
    async def _handle_balance(self, data: dict):
        """Handle balance update."""
        balance_data = data.get("balance", {})
        self.balance = float(balance_data.get("balance", self.balance))
        self.currency = balance_data.get("currency", self.currency)
        
        if self.on_balance:
            await self.on_balance({
                "balance": self.balance,
                "currency": self.currency
            })
    
    async def _handle_contract_update(self, data: dict):
        """Handle contract status update."""
        contract = data.get("proposal_open_contract", {})
        contract_id = str(contract.get("contract_id", ""))
        
        if not contract_id:
            logger.debug("Contract update with no contract_id, skipping")
            return
        
        # Check if contract is settled
        is_sold = contract.get("is_sold", 0) == 1
        is_expired = contract.get("is_expired", 0) == 1
        is_valid_to_sell = contract.get("is_valid_to_sell", 0) == 1
        status = contract.get("status", "")
        
        logger.info(f"Contract {contract_id} update: is_sold={is_sold}, is_expired={is_expired}, status={status}")
        
        self.active_contracts[contract_id] = contract
        
        if is_sold or is_expired:
            # Contract is complete
            profit = float(contract.get("profit", 0))
            result = ContractResult(
                contract_id=contract_id,
                buy_price=float(contract.get("buy_price", 0)),
                sell_price=float(contract.get("sell_price", 0)),
                profit=profit,
                entry_spot=float(contract.get("entry_spot", 0)),
                exit_spot=float(contract.get("exit_spot", 0)),
                is_win=profit > 0,
                is_sold=is_sold
            )
            
            logger.info(f"Contract {contract_id} SETTLED: profit={profit}, is_win={result.is_win}")
            
            if self.on_contract_update:
                await self.on_contract_update(result)
            
            # Remove from active
            if contract_id in self.active_contracts:
                del self.active_contracts[contract_id]
    
    async def _handle_buy_response(self, data: dict):
        """Handle buy contract response."""
        buy = data.get("buy", {})
        contract_id = str(buy.get("contract_id", ""))
        
        if contract_id:
            logger.info(f"Contract purchased: {contract_id}")
            
            # Subscribe to contract updates
            await self._send({
                "proposal_open_contract": 1,
                "contract_id": contract_id,
                "subscribe": 1
            })
    
    async def buy_contract(
        self,
        symbol: str,
        contract_type: str,  # "CALL" or "PUT"
        amount: float,
        duration: int,
        duration_unit: str = "s"
    ) -> dict:
        """
        Purchase a Rise/Fall contract.
        
        Args:
            symbol: Trading symbol (e.g., "R_75")
            contract_type: "CALL" for Rise, "PUT" for Fall
            amount: Stake amount
            duration: Contract duration
            duration_unit: "s" (seconds), "m" (minutes), "h" (hours)
            
        Returns:
            Buy response with contract details
        """
        # First get a price proposal
        proposal = await self._send({
            "proposal": 1,
            "amount": amount,
            "basis": "stake",
            "contract_type": contract_type,
            "currency": self.currency,
            "duration": duration,
            "duration_unit": duration_unit,
            "symbol": symbol
        })
        
        if "proposal" not in proposal:
            raise Exception("Failed to get price proposal")
        
        proposal_id = proposal["proposal"]["id"]
        payout = float(proposal["proposal"].get("payout", 0))
        
        logger.info(f"Proposal: {contract_type} {amount} {self.currency}, Payout: {payout}")
        
        # Buy the contract
        buy_response = await self._send({
            "buy": proposal_id,
            "price": amount
        })
        
        if "buy" in buy_response:
            return {
                "contract_id": buy_response["buy"]["contract_id"],
                "buy_price": float(buy_response["buy"]["buy_price"]),
                "payout": payout,
                "start_time": buy_response["buy"].get("start_time")
            }
        else:
            raise Exception("Failed to buy contract")
    
    def get_account_status(self) -> dict:
        """Get current account status."""
        return {
            "connected": self.is_connected,
            "authorized": self.is_authorized,
            "account_id": self.account_id,
            "balance": self.balance,
            "currency": self.currency,
            "active_contracts": len(self.active_contracts)
        }
    
    def get_candles(self, timeframe: str) -> List[dict]:
        """Get candles for a specific timeframe (completed candles only)."""
        if timeframe == "m1":
            return self.candles_m1.copy()
        elif timeframe == "m5":
            return self.candles_m5.copy()
        elif timeframe == "m15":
            return self.candles_m15.copy()
        return []
