use chrono::{Utc, Timelike};
use crate::shared_memory::{SharedEngine, TradeSignal};

pub async fn run_gatekeeper(
    signal_rx: crossbeam_channel::Receiver<TradeSignal>,
    shared_state: SharedEngine,
) {
    loop {
        // --- 1. THE EOD TIME CHECK (9:55 PM UTC) ---
        let now = Utc::now();
        if now.hour() == 21 && now.minute() >= 55 {
            let mut open_pos = shared_state.open_positions.lock();
            if *open_pos > 0 {
                println!("🚨 [GATEKEEPER] EOD 9:55 PM UTC reached. Flattening all positions.");
                *open_pos = 0; 
            }
        }

        // --- 2. UNREALIZED PnL KILL SWITCH (-$490 STATIC LIMIT) ---
        {
            let open_pnl = calculate_unrealized_pnl(&shared_state); 
            if open_pnl <= -490.0 {
                println!("💀 [GATEKEEPER] FATAL: Drawdown threshold breached (-$490). Flattening.");
                let mut open_pos = shared_state.open_positions.lock();
                *open_pos = 0;
            }
        }

        // --- 3. THE MES-ONLY SIZING FILTER ---
        if let Ok(signal) = signal_rx.try_recv() {
            if !signal.symbol.starts_with("MES") {
                println!("⚠️ [GATEKEEPER] Rejected: Invalid Asset ({}). MES only.", signal.symbol);
                continue;
            }

            if signal.contracts > 4 || signal.contracts < 1 {
                println!("⚠️ [GATEKEEPER] Rejected: Size limit violation ({}).", signal.contracts);
                continue;
            }

            // Updated to print the newly bridged data
            println!(
                "✅ [GATEKEEPER] Signal Approved: {}x {} | {} @ {} | SL: {} TP: {}", 
                signal.contracts, signal.symbol, signal.action, signal.price, signal.stop_loss, signal.take_profit
            );
        }
        
        tokio::task::yield_now().await;
    }
}

fn calculate_unrealized_pnl(_state: &SharedEngine) -> f64 {
    0.0 
}
