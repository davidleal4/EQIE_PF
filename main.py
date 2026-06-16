import time
import datetime
import sys
from collections import deque
import eqie_core

# ==========================================
# 1. DUAL-ASSET MARKET CONTEXT ENGINE
# ==========================================
class MarketContext:
    def __init__(self, symbols):
        self.data = {
            sym: {
                'session_high': -float('inf'),
                'session_low': float('inf'),
                'ny_open_price': 0.0,
                'vwap_history': deque(maxlen=20),
                'price_history': deque(maxlen=60)
            } for sym in symbols
        }

    def update_tick(self, symbol, price, vwap, current_time_obj):
        if symbol not in self.data: return
        ctx = self.data[symbol]
        
        if ctx['ny_open_price'] == 0.0 and current_time_obj.hour == 8 and current_time_obj.minute >= 30:
            ctx['ny_open_price'] = price
            
        if price > ctx['session_high']: ctx['session_high'] = price
        if price < ctx['session_low']: ctx['session_low'] = price
            
        ctx['price_history'].append(price)
        if vwap > 0: ctx['vwap_history'].append(vwap)

    def is_at_low_extreme(self, symbol, current_price, threshold_points=3.0):
        ctx = self.data.get(symbol)
        if not ctx or ctx['session_low'] == float('inf'): return False
        return (current_price - ctx['session_low']) <= threshold_points

    def is_at_high_extreme(self, symbol, current_price, threshold_points=3.0):
        ctx = self.data.get(symbol)
        if not ctx or ctx['session_high'] == -float('inf'): return False
        return (ctx['session_high'] - current_price) <= threshold_points

    def get_vwap_slope(self, symbol):
        ctx = self.data.get(symbol)
        if not ctx or len(ctx['vwap_history']) < 20: return 0.0
        return ctx['vwap_history'][-1] - ctx['vwap_history'][0]

    def get_dynamic_volatility_multiplier(self, symbol, base_range):
        ctx = self.data.get(symbol)
        if not ctx or len(ctx['price_history']) < 60: return 1.0
        
        recent_high = max(ctx['price_history'])
        recent_low = min(ctx['price_history'])
        price_range = recent_high - recent_low
        
        multiplier = price_range / base_range
        return max(0.66, min(multiplier, 1.50))

# ==========================================
# 2. THE APEX ENGINE (HEADLESS READY)
# ==========================================
def main():
    print("[System] Initializing V5 Apex Engine (Headless Dual-Asset Scale-Out)...")
    
    client = eqie_core.QuantowerClient()
    
    # 2. Establish TCP Connection to the Headless C# Bridge
    try:
        client.connect("192.168.64.3", 21000) # <--- CHANGED BACK TO YOUR VM IP
        print("[System] Socket connected. Network gateway established.")
    except Exception as e:
        print(f"[CRITICAL] Failed to connect: {e}")
        return

    # Asset Dictionaries & Initialization
    SYMBOLS = ["MESM6", "MNQM6"]
    market_context = MarketContext(SYMBOLS)
    
    # Broadcast dynamic subscription requests via the Rust method
    print("[System] Registering asset subscription matrix with headless router...")
    for sym in SYMBOLS:
        try:
            client.subscribe(sym)
            print(f"[System] Subscription verified and sent for: {sym}")
        except Exception as e:
            print(f"[System] Fatal Error during contract subscription for {sym}: {e}")
            sys.exit(1)
            
    # Asset Specific Parameters (Multiplier, Base Stop, Scale Out Target, Baseline Volatility Range)
    ASSET_PROFILES = {
        "MESM6": {"mult": 5.0, "base_stop": 3.00, "scale_out": 4.00, "detach": 4.00, "base_vol": 2.50},
        "MNQM6": {"mult": 2.0, "base_stop": 4.50, "scale_out": 6.00, "detach": 5.00, "base_vol": 5.00}
    }
    
    # Absolute State Variables (Topstep 50K Phase)
    STARTING_BALANCE = 50000.00
    STATIC_DRAWDOWN_FLOOR = 48000.00  # $2,000 Maximum Drawdown Buffer
    PROFIT_TARGET = 53000.00          # $3,000 Profit Target
    DAILY_LOSS_LIMIT = -400.00        # Expanded to breathe, but well below Topstep's $1,000 limit
    DAILY_PROFIT_CAP = 1000.00        # NEW: 40% Consistency Rule Guardian
    ROUND_TRIP_FEE = 1.50
    
    # Execution State
    net_balance = STARTING_BALANCE
    exec_state = "FLAT"
    active_symbol = None
    position_qty = 0
    has_scaled_out = False
    
    entry_price = 0.0
    stop_loss_price = 0.0
    highest_price_seen = 0.0
    lowest_price_seen = 0.0

    # System Tracking Variables
    net_equity = 0.0
    pending_timestamp = 0.0
    last_ping_time = time.time()
    last_exit_time = 0.0  
    prev_price_check = {s: 0.0 for s in SYMBOLS}
    cooldown_until = 0.0
    
    highest_z_seen = 0.0
    lowest_z_seen = 0.0
    
    # Time Filters (Double Window - CDT)
    S1_START = datetime.time(8, 30, 0)
    S1_END = datetime.time(10, 0, 0)
    S2_START = datetime.time(13, 0, 0)   # 1:00 PM CDT
    S2_END = datetime.time(15, 0, 0)     # 3:00 PM CDT

    print(f"[System] Handshake complete. Engine is live and hunting.")

    try:
        while True:
            current_time = time.time()
            now = datetime.datetime.now()
            current_clock = now.time()
            
            # --- 0. HEARTBEAT ---
            if current_time - last_ping_time > 1.0:
                client.send_ping()
                last_ping_time = current_time

            tick_data = client.read_next_tick()
            if not tick_data:
                time.sleep(0.001)
                continue
            
            symbol, price, size, vwap, val, vah, delta, z_score = tick_data
            if symbol not in SYMBOLS: continue
            
            current_time_str = now.strftime("%H:%M:%S")
            profile = ASSET_PROFILES[symbol]
            
            # Update Context Memory
            market_context.update_tick(symbol, price, vwap, now)
            vol_mod = market_context.get_dynamic_volatility_multiplier(symbol, profile["base_vol"])
            dyn_stop = round(max(2.00, min(profile["base_stop"] * vol_mod, 6.00)) * 4) / 4
            dyn_detach = round(max(3.00, min(profile["detach"] * vol_mod, 8.00)) * 4) / 4
            vwap_slope = market_context.get_vwap_slope(symbol)

            # --- 1. STATE MACHINE RESOLUTION ---
            if exec_state.startswith("PENDING") and active_symbol == symbol:
                time_in_pending = current_time - pending_timestamp
                if time_in_pending > 0.2: 
                    if exec_state == "PENDING_LONG": 
                        exec_state = "LONG"
                        highest_z_seen = z_score
                    elif exec_state == "PENDING_SHORT": 
                        exec_state = "SHORT"
                        lowest_z_seen = z_score
                    elif exec_state == "PENDING_EXIT":
                        exec_state = "FLAT"
                        active_symbol = None
                        last_exit_time = current_time
                if time_in_pending > 2.0:
                    exec_state = "FLAT" if exec_state != "PENDING_EXIT" else ("LONG" if position_qty > 0 else "SHORT")

            # --- 2. LIVE TRACKING (ACTIVE ASSET ONLY) ---
            if active_symbol == symbol:
                if exec_state == "LONG": 
                    net_equity = (price - entry_price) * profile["mult"] * position_qty
                elif exec_state == "SHORT": 
                    net_equity = (entry_price - price) * profile["mult"] * position_qty
                else: 
                    net_equity = 0.0

            current_account_value = net_balance + net_equity
            daily_pnl = current_account_value - STARTING_BALANCE

            # --- 3. GUARDIAN CONDITIONS ---
            if daily_pnl <= DAILY_LOSS_LIMIT:
                if position_qty > 0 and exec_state != "PENDING_EXIT":
                    client.send_order("SELL" if exec_state == "LONG" else "BUY", active_symbol, position_qty)
                print(f"\n[{current_time_str}] 🛑 [DAILY LIMIT] Session closed. PnL: ${daily_pnl:.2f}")
                sys.exit(0)

            # CONSISTENCY CAP: Secures profits to stay compliant with Topstep's 40% rule
            if daily_pnl >= DAILY_PROFIT_CAP:
                if position_qty > 0 and exec_state != "PENDING_EXIT":
                    client.send_order("SELL" if exec_state == "LONG" else "BUY", active_symbol, position_qty)
                print(f"\n[{current_time_str}] 📈 [CONSISTENCY CAP] Daily profit secured. Shutting down to preserve 40% metric.")
                sys.exit(0)

            if current_account_value <= STATIC_DRAWDOWN_FLOOR:
                if position_qty > 0 and exec_state != "PENDING_EXIT":
                    client.send_order("SELL" if exec_state == "LONG" else "BUY", active_symbol, position_qty)
                print(f"\n[{current_time_str}] 💀 [FATAL] DRAWDOWN LIMIT REACHED.")
                sys.exit(0) 

            if current_account_value >= PROFIT_TARGET:
                if position_qty > 0 and exec_state != "PENDING_EXIT":
                    client.send_order("SELL" if exec_state == "LONG" else "BUY", active_symbol, position_qty)
                print(f"\n[{current_time_str}] 🏆 [VICTORY] EVALUATION PASSED.")
                sys.exit(0)

            # --- 4. SESSION MANAGEMENT ---
            is_active_session = (S1_START <= current_clock <= S1_END) or (S2_START <= current_clock <= S2_END)
            
            # Flatten if window closes while holding a position
            if not is_active_session and position_qty > 0 and exec_state != "PENDING_EXIT" and active_symbol == symbol:
                client.send_order("SELL" if exec_state == "LONG" else "BUY", active_symbol, position_qty)
                exec_state = "PENDING_EXIT"
                pending_timestamp = current_time
                net_balance += (net_equity - (ROUND_TRIP_FEE * position_qty))
                position_qty = 0
                print(f"\n[{current_time_str}] 🛑 EOD FLATTEN | Session Closed.")
                continue 

            # --- 5. UI UPDATES ---
            status_prefix = "[LIVE]" if is_active_session else "[SLEEP]"
            if active_symbol == symbol or active_symbol is None:
                sys.stdout.write(f"\r{status_prefix} {symbol} | Pos: {position_qty} | PnL: ${daily_pnl:+.2f} | Z: {z_score:+.2f} | State: {exec_state}    ")
                sys.stdout.flush()

            # --- 6. OFFENSIVE TRADE MANAGEMENT & SCALE-OUT (ACTIVE ASSET ONLY) ---
            if active_symbol == symbol and exec_state in ["LONG", "SHORT"]:
                trigger_full_exit = False
                exit_reason = ""

                if exec_state == "LONG": 
                    highest_price_seen = max(highest_price_seen, price)
                    highest_z_seen = max(highest_z_seen, z_score)
                    
                    # SCALE OUT MECHANIC: Lock in 1 contract at target
                    if not has_scaled_out and position_qty == 2 and highest_price_seen >= entry_price + profile["scale_out"]:
                        client.send_order("SELL", symbol, 1)
                        position_qty = 1
                        has_scaled_out = True
                        stop_loss_price = entry_price + 1.00 # Breakeven + fee coverage
                        scale_profit = (profile["scale_out"] * profile["mult"]) - ROUND_TRIP_FEE
                        net_balance += scale_profit
                        print(f"\n[{current_time_str}] 💰 [SCALE OUT] 1 {symbol} Contract secured at +{profile['scale_out']} pts. Runner stop at {stop_loss_price:.2f}")

                    # Trailing Stop for Runner
                    if has_scaled_out and highest_price_seen >= entry_price + dyn_detach:
                        proposed_stop = min(max(stop_loss_price, vah), highest_price_seen - 2.50)
                        if proposed_stop > stop_loss_price: stop_loss_price = proposed_stop

                    # Exit Conditions
                    if price <= stop_loss_price:
                        trigger_full_exit = True
                        exit_reason = "Trailing_Stop_Or_Breakeven"
                    elif highest_price_seen >= entry_price + dyn_detach and highest_z_seen >= 3.0 and (highest_z_seen - z_score) >= 1.75:
                        trigger_full_exit = True
                        exit_reason = "Velocity_Exhaustion"

                elif exec_state == "SHORT":
                    lowest_price_seen = min(lowest_price_seen, price)
                    lowest_z_seen = min(lowest_z_seen, z_score)
                    
                    # SCALE OUT MECHANIC: Lock in 1 contract at target
                    if not has_scaled_out and position_qty == 2 and lowest_price_seen <= entry_price - profile["scale_out"]:
                        client.send_order("BUY", symbol, 1)
                        position_qty = 1
                        has_scaled_out = True
                        stop_loss_price = entry_price - 1.00 # Breakeven + fee coverage
                        scale_profit = (profile["scale_out"] * profile["mult"]) - ROUND_TRIP_FEE
                        net_balance += scale_profit
                        print(f"\n[{current_time_str}] 💰 [SCALE OUT] 1 {symbol} Contract secured at +{profile['scale_out']} pts. Runner stop at {stop_loss_price:.2f}")

                    # Trailing Stop for Runner
                    if has_scaled_out and lowest_price_seen <= entry_price - dyn_detach:
                        proposed_stop = max(min(stop_loss_price, val), lowest_price_seen + 2.50)
                        if proposed_stop < stop_loss_price: stop_loss_price = proposed_stop

                    # Exit Conditions
                    if price >= stop_loss_price:
                        trigger_full_exit = True
                        exit_reason = "Trailing_Stop_Or_Breakeven"
                    elif lowest_price_seen <= entry_price - dyn_detach and lowest_z_seen <= -3.0 and (z_score - lowest_z_seen) >= 1.75:
                        trigger_full_exit = True
                        exit_reason = "Velocity_Exhaustion"

                if trigger_full_exit:
                    client.send_order("SELL" if exec_state == "LONG" else "BUY", symbol, position_qty)
                    exec_state = "PENDING_EXIT"
                    pending_timestamp = current_time
                    net_pnl = net_equity - (ROUND_TRIP_FEE * position_qty)
                    net_balance += net_pnl
                    position_qty = 0
                    print(f"\n[{current_time_str}] ⚪ {symbol} CLOSED | {exit_reason} | Runner PnL: ${net_pnl:+.2f}")
                    cooldown_until = current_time + 300 # 5 minute cooldown after full cycle

            # --- 7. GLOBAL ENTRY LOGIC ---
            if exec_state == "FLAT" and active_symbol is None and is_active_session and current_time > cooldown_until:
                
                # LONG ENTRY
                if z_score >= 2.0 and price > vwap and vwap_slope > 0.0 and vah > 0.0 and price > vah and delta > 0:
                    if prev_price_check[symbol] == 0.0 or price > prev_price_check[symbol]:
                        if not market_context.is_at_high_extreme(symbol, price, 3.0):
                            client.send_order("BUY", symbol, 2)  
                            exec_state = "PENDING_LONG"
                            active_symbol = symbol
                            position_qty = 2
                            has_scaled_out = False
                            pending_timestamp = current_time
                            entry_price = price
                            highest_price_seen = price
                            stop_loss_price = price - dyn_stop
                            print(f"\n[{current_time_str}] 🟢 {symbol} LONG ENTRY (2x) | Price: {price:.2f} | Stop: {stop_loss_price:.2f}")
                    
                # SHORT ENTRY
                elif z_score <= -2.0 and price < vwap and vwap_slope < 0.0 and val > 0.0 and price < val and delta < 0:
                    if prev_price_check[symbol] == 0.0 or price < prev_price_check[symbol]:
                        if not market_context.is_at_low_extreme(symbol, price, 3.0):
                            client.send_order("SELL", symbol, 2) 
                            exec_state = "PENDING_SHORT"
                            active_symbol = symbol
                            position_qty = 2
                            has_scaled_out = False
                            pending_timestamp = current_time
                            entry_price = price
                            lowest_price_seen = price
                            stop_loss_price = price + dyn_stop
                            print(f"\n[{current_time_str}] 🔴 {symbol} SHORT ENTRY (2x) | Price: {price:.2f} | Stop: {stop_loss_price:.2f}")

            prev_price_check[symbol] = price

    except KeyboardInterrupt:
        print("\n[System] Manual shutdown received.")
    except Exception as e:
        print(f"\n[System] Fatal Error: {e}")
    finally:
        print("[System] Engine offline.")

if __name__ == "__main__":
    main()