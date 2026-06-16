use pyo3::prelude::*;
use parking_lot::Mutex;
use crossbeam_channel::{Sender, Receiver, unbounded};
use std::sync::Arc;

#[derive(Clone, Debug)]
pub struct TradeSignal {
    pub symbol: String,
    pub contracts: i32,
    pub is_closing: bool,
    pub action: String,
    pub price: f64,
    // Added risk parameters from the Python Evaluator
    pub stop_loss: f64,
    pub take_profit: f64,
}

#[pyclass]
#[derive(Clone)]
pub struct SharedEngine {
    pub book: Arc<Mutex<String>>, 
    pub tx: Sender<TradeSignal>,
    pub open_positions: Arc<Mutex<i32>>,
    pub emergency_flatten_flag: Arc<Mutex<bool>>,
}

// --- THIS IS THE PYTHON BRIDGE ---
// Any function in this block can be called directly from Python using shared_engine.function_name()
#[pymethods]
impl SharedEngine {
    pub fn send_signal(&self, symbol: String, contracts: i32, action: String, price: f64, stop_loss: f64, take_profit: f64) {
        let signal = TradeSignal {
            symbol,
            contracts,
            is_closing: false,
            action,
            price,
            stop_loss,
            take_profit,
        };
        
        // Push the struct into the crossbeam channel targeting the Gatekeeper
        if let Err(e) = self.tx.send(signal) {
            println!("⚠️ [PYTHON-RUST BRIDGE] Failed to send signal to Gatekeeper: {:?}", e);
        }
    }
}

pub fn create_engine_and_receiver() -> (SharedEngine, Receiver<TradeSignal>) {
    let (tx, rx) = unbounded();
    (
        SharedEngine {
            book: Arc::new(Mutex::new(String::new())),
            tx,
            open_positions: Arc::new(Mutex::new(0)),
            emergency_flatten_flag: Arc::new(Mutex::new(false)),
        },
        rx
    )
}