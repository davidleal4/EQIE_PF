import datetime

class MockBroker:
    def __init__(self, starting_balance: float = 50000.0):
        self.balance = starting_balance
        self.position = 0          # Positive for Long, Negative for Short
        self.entry_price = 0.0
        self.trade_log = []

    def process_signal(self, symbol: str, price: float, signal: str):
        """Executes mock trades based on incoming signals."""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]

        if signal == "BUY" and self.position <= 0:
            # If short, cover first. If flat, go long.
            if self.position < 0:
                self._close_position(symbol, price, timestamp)
            
            self.position = 1
            self.entry_price = price
            print(f"[{timestamp}] 🟢 EXECUTED MOCK BUY: {symbol} @ {price:.2f} | Balance: ${self.balance:.2f}")

        elif signal == "SELL" and self.position >= 0:
            # If long, sell to close. If flat, go short.
            if self.position > 0:
                self._close_position(symbol, price, timestamp)
            
            self.position = -1
            self.entry_price = price
            print(f"[{timestamp}] 🔴 EXECUTED MOCK SELL: {symbol} @ {price:.2f} | Balance: ${self.balance:.2f}")

    def _close_position(self, symbol: str, exit_price: float, timestamp: str):
        # Calculate PnL for Micro E-mini (MES is $5 per point)
        multiplier = 5.0
        if self.position > 0:
            pnl = (exit_price - self.entry_price) * multiplier
        else:
            pnl = (self.entry_price - exit_price) * multiplier

        self.balance += pnl
        self.trade_log.append({
            "time": timestamp,
            "symbol": symbol,
            "pnl": pnl,
            "balance": self.balance
        })
        
        result = "PROFIT" if pnl >= 0 else "LOSS"
        print(f"[{timestamp}] ⚪ CLOSED POSITION: {symbol} @ {exit_price:.2f} | {result}: ${pnl:.2f} | New Balance: ${self.balance:.2f}")
        self.position = 0
        self.entry_price = 0.0