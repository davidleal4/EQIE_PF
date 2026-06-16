import time
import random
from datetime import datetime
import pytz

TARGET_SYMBOL = "MESM6"
MAX_DAILY_TRADES = 3
CONTRACT_SIZE = 2
DAILY_LOSS_LIMIT = -120.0
DAILY_PROFIT_TARGET = 300.0
TIMEZONE = pytz.timezone("America/Chicago")

class TradingSession:
    def __init__(self):
        self.trades_taken_today = 0
        self.daily_pnl = 0.0
        self.session_active = True

    def reset_session(self):
        self.trades_taken_today = 0
        self.daily_pnl = 0.0
        self.session_active = True

session = TradingSession()

def is_within_trading_window() -> bool:
    now_cdt = datetime.now(TIMEZONE).time()
    
    primary_start = datetime.strptime("08:30", "%H:%M").time()
    primary_end = datetime.strptime("10:30", "%H:%M").time()
    
    secondary_start = datetime.strptime("13:00", "%H:%M").time()
    secondary_end = datetime.strptime("15:00", "%H:%M").time()
    
    in_primary = primary_start <= now_cdt <= primary_end
    in_secondary = secondary_start <= now_cdt <= secondary_end
    
    return in_primary or in_secondary

def evaluate_market_data(market_data: dict) -> dict | None:
    if not session.session_active:
        return None
        
    if session.trades_taken_today >= MAX_DAILY_TRADES:
        print("🛑 [EVALUATOR] Max daily trades reached. Powering down.")
        session.session_active = False
        return None
        
    if session.daily_pnl <= DAILY_LOSS_LIMIT:
        print(f"💀 [EVALUATOR] Daily loss limit breached (${session.daily_pnl}). Powering down.")
        session.session_active = False
        return None
        
    if session.daily_pnl >= DAILY_PROFIT_TARGET:
        print(f"🏆 [EVALUATOR] Daily profit target hit (${session.daily_pnl}). Powering down.")
        session.session_active = False
        return None

    # OVERRIDE FOR WEEKEND TESTING: 
    # Force the window to return True so we don't get blocked by the timezone check right now.
    # When trading live, remove this line:
    in_trading_window = True # is_within_trading_window()

    if not in_trading_window:
        return None

    current_bid = market_data.get("bid", 0.0)
    current_ask = market_data.get("ask", 0.0)
    spread = current_ask - current_bid
    
    if 0.0 < spread <= 0.50:
        action = "BUY" if random.choice([True, False]) else "SELL"
        execution_price = current_ask if action == "BUY" else current_bid
        
        sl_points = 6.0
        tp_points = 15.0
        
        if action == "BUY":
            stop_loss = execution_price - sl_points
            take_profit = execution_price + tp_points
        else:
            stop_loss = execution_price + sl_points
            take_profit = execution_price - tp_points
        
        signal = {
            "symbol": TARGET_SYMBOL,
            "action": action,
            "size": CONTRACT_SIZE,
            "price": execution_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "timestamp": time.time()
        }
        
        session.trades_taken_today += 1
        return signal

    return None

# Added shared_engine parameter
def run_evaluator_loop(shared_engine):
    print(f"🚀 [EVALUATOR] Starting Python Fast-Path.")
    print(f"🔒 [EVALUATOR] Locked to target symbol: {TARGET_SYMBOL}")
    print(f"🛡️ [EVALUATOR] Rules Engine Active: Max {MAX_DAILY_TRADES} Trades, {CONTRACT_SIZE} Contracts.")
    
    try:
        while True:
            mock_data = {
                "bid": 5300.00,
                "ask": 5300.25,
                "timestamp": time.time()
            }
            
            signal = evaluate_market_data(mock_data)
            
            if signal:
                print(f"⚡ [EVALUATOR] Signal Generated: {signal['action']} {signal['size']}x {signal['symbol']} @ {signal['price']}")
                
                # --- THIS IS THE BRIDGE ACTIVATION ---
                # Call the #[pymethods] Rust function and pass the variables
                shared_engine.send_signal(
                    signal['symbol'],
                    signal['size'],
                    signal['action'],
                    signal['price'],
                    signal['stop_loss'],
                    signal['take_profit']
                )
                
                mock_outcome = random.choice([-60.0, 150.0])
                session.daily_pnl += mock_outcome
                print(f"    -> Mock PnL Update: Session PnL is now ${session.daily_pnl}")
            
            time.sleep(2.0) # Slowed down to 2 seconds for readable terminal output
            
    except KeyboardInterrupt:
        print("\n🛑 [EVALUATOR] Shutting down Python Fast-Path.")