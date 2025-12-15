"""FastAPI server for the Deriv Trading Bot."""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Optional
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn
import os

from trading_bot import TradingBot
from trade_recorder import trade_recorder
from config import trading_config, server_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global bot instance
bot: Optional[TradingBot] = None
connected_clients: list[WebSocket] = []


class StartBotRequest(BaseModel):
    api_token: str


class TradeRequest(BaseModel):
    direction: str  # "CALL" or "PUT"


class SettingsUpdate(BaseModel):
    symbol: Optional[str] = None
    initial_stake: Optional[float] = None
    risk_percent: Optional[float] = None
    max_martingale_steps: Optional[int] = None
    trade_duration: Optional[int] = None
    max_daily_profit_target: Optional[float] = None
    max_session_loss: Optional[float] = None


async def broadcast_state(state: dict):
    """Broadcast state to all connected WebSocket clients."""
    if not connected_clients:
        return
    
    message = json.dumps({
        "type": "state_update",
        "data": state,
        "timestamp": datetime.now().isoformat()
    })
    
    disconnected = []
    for client in connected_clients:
        try:
            await client.send_text(message)
        except Exception:
            disconnected.append(client)
    
    for client in disconnected:
        connected_clients.remove(client)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    global bot
    # Reset bot state on startup to avoid stale state from previous runs
    bot = None
    logger.info("Starting Deriv Trading Bot API...")
    yield
    logger.info("Shutting down...")
    if bot and bot.is_running:
        await bot.stop()


app = FastAPI(
    title="Deriv Trading Bot API",
    description="API for the Mean Reversion Trading Bot",
    version="1.0.0",
    lifespan=lifespan
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "name": "Deriv Trading Bot",
        "version": "1.0.0"
    }


@app.get("/api/status")
async def get_status():
    """Get current bot status."""
    if not bot:
        return {
            "is_running": False,
            "is_trading_enabled": False,
            "message": "Bot not started"
        }
    
    return bot.get_state()


@app.post("/api/start")
async def start_bot(request: StartBotRequest):
    """Start the trading bot."""
    global bot
    
    if bot and bot.is_running:
        raise HTTPException(400, "Bot is already running")
    
    try:
        bot = TradingBot(
            api_token=request.api_token,
            on_state_update=broadcast_state
        )
        await bot.start()
        
        return {
            "success": True,
            "message": "Bot started successfully",
            "state": bot.get_state()
        }
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise HTTPException(500, str(e))


@app.post("/api/stop")
async def stop_bot():
    """Stop the trading bot."""
    global bot
    
    if not bot or not bot.is_running:
        raise HTTPException(400, "Bot is not running")
    
    await bot.stop()
    bot = None
    
    return {"success": True, "message": "Bot stopped"}


@app.post("/api/trading/enable")
async def enable_trading():
    """Enable automated trading."""
    if not bot or not bot.is_running:
        raise HTTPException(400, "Bot is not running")
    
    bot.enable_trading()
    return {"success": True, "is_trading_enabled": True}


@app.post("/api/trading/disable")
async def disable_trading():
    """Disable automated trading."""
    if not bot or not bot.is_running:
        raise HTTPException(400, "Bot is not running")
    
    bot.disable_trading()
    return {"success": True, "is_trading_enabled": False}


@app.post("/api/trade")
async def manual_trade(request: TradeRequest):
    """Execute a manual trade."""
    if not bot or not bot.is_running:
        raise HTTPException(400, "Bot is not running")
    
    if request.direction not in ["CALL", "PUT"]:
        raise HTTPException(400, "Direction must be CALL or PUT")
    
    try:
        result = await bot.manual_trade(request.direction)
        return {
            "success": True,
            "contract_id": result["contract_id"],
            "buy_price": result["buy_price"],
            "payout": result["payout"]
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/history")
async def get_trade_history(limit: int = 50):
    """Get trade history."""
    if not bot:
        return {"trades": []}
    
    return {"trades": bot.risk_manager.get_trade_history(limit)}


@app.delete("/api/history")
async def clear_trade_history():
    """Clear all trade history."""
    if not bot:
        raise HTTPException(status_code=400, detail="Bot not initialized")
    
    bot.risk_manager.clear_history()
    return {"success": True, "message": "Trade history cleared"}


@app.get("/api/statistics")
async def get_statistics():
    """Get trading statistics."""
    if not bot:
        return {"statistics": {}}
    
    return {"statistics": bot.risk_manager.get_statistics()}


@app.put("/api/settings")
async def update_settings(settings: SettingsUpdate):
    """Update trading settings."""
    if settings.symbol is not None:
        trading_config.symbol = settings.symbol
        logger.info(f"Symbol updated to: {settings.symbol}")
    if settings.initial_stake is not None:
        trading_config.initial_stake = settings.initial_stake
    if settings.risk_percent is not None:
        trading_config.risk_percent = settings.risk_percent
    if settings.max_martingale_steps is not None:
        trading_config.max_martingale_steps = settings.max_martingale_steps
    if settings.trade_duration is not None:
        trading_config.trade_duration = settings.trade_duration
        logger.info(f"Contract duration updated to: {settings.trade_duration}s")
    if settings.max_daily_profit_target is not None:
        trading_config.max_daily_profit_target = settings.max_daily_profit_target
    if settings.max_session_loss is not None:
        trading_config.max_session_loss = settings.max_session_loss
    
    # Update risk manager if bot is running
    if bot:
        bot.risk_manager.initial_stake = trading_config.initial_stake
        bot.risk_manager.risk_percent = trading_config.risk_percent
        bot.risk_manager.max_martingale_steps = trading_config.max_martingale_steps
        bot.risk_manager.max_daily_profit_target = trading_config.max_daily_profit_target
        bot.risk_manager.max_session_loss = trading_config.max_session_loss
        # Note: Symbol and duration changes require bot restart to take effect
    
    return {"success": True, "settings": settings.model_dump()}


@app.get("/api/records")
async def get_trade_records(limit: int = 50):
    """Get recorded trades with full indicator values for analysis."""
    return {
        "records": trade_recorder.get_recent_records(limit),
        "summary": trade_recorder.get_records_summary()
    }


@app.get("/api/records/summary")
async def get_records_summary():
    """Get summary statistics of all recorded trades."""
    return trade_recorder.get_records_summary()


@app.get("/api/records/download")
async def download_records():
    """Download the current month's trade records as CSV."""
    csv_path = trade_recorder.current_file
    if not os.path.exists(csv_path):
        raise HTTPException(status_code=404, detail="No trade records found")
    
    filename = os.path.basename(csv_path)
    return FileResponse(
        path=csv_path,
        filename=filename,
        media_type="text/csv"
    )


@app.get("/api/records/download/{year}/{month}")
async def download_records_by_month(year: int, month: int):
    """Download trade records for a specific month as CSV."""
    filename = f"trades_{year}_{month:02d}.csv"
    records_dir = os.path.dirname(trade_recorder.current_file)
    csv_path = os.path.join(records_dir, filename)
    
    if not os.path.exists(csv_path):
        raise HTTPException(status_code=404, detail=f"No records found for {year}-{month:02d}")
    
    return FileResponse(
        path=csv_path,
        filename=filename,
        media_type="text/csv"
    )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await websocket.accept()
    connected_clients.append(websocket)
    logger.info(f"WebSocket client connected. Total: {len(connected_clients)}")
    
    try:
        # Send initial state
        if bot:
            await websocket.send_text(json.dumps({
                "type": "state_update",
                "data": bot.get_state(),
                "timestamp": datetime.now().isoformat()
            }))
        
        # Keep connection alive and handle messages
        while True:
            try:
                message = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30
                )
                
                # Handle ping/pong
                data = json.loads(message)
                if data.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                    
            except asyncio.TimeoutError:
                # Send ping to keep alive
                try:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                except Exception:
                    break
                    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if websocket in connected_clients:
            connected_clients.remove(websocket)
        logger.info(f"WebSocket client disconnected. Total: {len(connected_clients)}")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=server_config.host,
        port=server_config.port,
        reload=server_config.debug
    )
