use pyo3::prelude::*;
use pyo3::exceptions::PyConnectionError;
use std::io::{Read, Write};
use std::net::TcpStream;
use std::collections::{BTreeMap, VecDeque};

#[pyclass]
pub struct QuantowerClient {
    stream: Option<TcpStream>,
    vwap_engine: VwapEngine,
    volume_profile: VolumeProfile,
    delta: f64, 
    delta_window: VecDeque<f64>,
    buffer: String, 
}

#[derive(Clone)]
struct VwapEngine {
    cumulative_pv: f64,
    cumulative_vol: f64,
}

impl VwapEngine {
    fn new() -> Self {
        Self { cumulative_pv: 0.0, cumulative_vol: 0.0 }
    }
    
    fn update(&mut self, price: f64, volume: f64) -> f64 {
        self.cumulative_pv += price * volume;
        self.cumulative_vol += volume;
        if self.cumulative_vol == 0.0 { price } else { self.cumulative_pv / self.cumulative_vol }
    }
}

#[derive(Clone)]
struct VolumeProfile {
    levels: BTreeMap<i64, f64>, 
    total_volume: f64,
    tick_size: f64,
}

impl VolumeProfile {
    fn new(tick_size: f64) -> Self {
        Self { levels: BTreeMap::new(), total_volume: 0.0, tick_size }
    }

    fn update(&mut self, price: f64, volume: f64) -> (f64, f64) {
        let price_tick = (price / self.tick_size).round() as i64;
        *self.levels.entry(price_tick).or_insert(0.0) += volume;
        self.total_volume += volume;

        if self.total_volume == 0.0 { return (price, price); }

        let mut poc_tick = price_tick;
        let mut max_vol = 0.0;
        for (&t, &v) in self.levels.iter() {
            if v > max_vol { max_vol = v; poc_tick = t; }
        }

        let target_vol = self.total_volume * 0.70;
        let mut current_vol = max_vol;
        let mut upper = poc_tick;
        let mut lower = poc_tick;

        while current_vol < target_vol {
            let next_upper = upper + 1;
            let next_lower = lower - 1;
            
            let vol_upper = self.levels.get(&next_upper).unwrap_or(&0.0);
            let vol_lower = self.levels.get(&next_lower).unwrap_or(&0.0);

            if *vol_upper == 0.0 && *vol_lower == 0.0 { break; }

            if vol_upper > vol_lower {
                current_vol += vol_upper;
                upper = next_upper;
            } else {
                current_vol += vol_lower;
                lower = next_lower;
            }
        }
        ((lower as f64) * self.tick_size, (upper as f64) * self.tick_size)
    }
}

#[pymethods]
impl QuantowerClient {
    #[new]
    fn new() -> Self {
        QuantowerClient {
            stream: None,
            vwap_engine: VwapEngine::new(),
            volume_profile: VolumeProfile::new(0.25),
            delta: 0.0, 
            delta_window: VecDeque::with_capacity(100),
            buffer: String::new(), 
        }
    }

    fn connect(&mut self, ip: &str, port: u16) -> PyResult<()> {
        let addr = format!("{}:{}", ip, port);
        let stream = TcpStream::connect(addr)?;
        
        stream.set_nodelay(true)?;
        stream.set_nonblocking(true)?;
        
        self.stream = Some(stream);
        Ok(())
    }

    // --- NEW: DYNAMIC SUBSCRIPTION STREAMING GATEWAY ---
    fn subscribe(&mut self, symbol: &str) -> PyResult<()> {
        if let Some(stream) = self.stream.as_mut() {
            let command = format!("SUBSCRIBE,{}\n", symbol);
            let bytes = command.as_bytes();
            
            // GUARANTEED TRANSMISSION: Block and retry if OS socket buffer is full
            loop {
                match stream.write(bytes) {
                    Ok(_) => break,
                    Err(ref e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                        std::thread::sleep(std::time::Duration::from_millis(1));
                    }
                    Err(_) => return Err(PyConnectionError::new_err("Failed to send subscription command.")),
                }
            }
        }
        Ok(())
    }

    fn read_next_tick(&mut self) -> PyResult<Option<(String, f64, f64, f64, f64, f64, f64, f64)>> {
        let mut latest_state = None;

        if let Some(stream) = self.stream.as_mut() {
            let mut temp_buf = [0u8; 8192];
            let mut reads_this_cycle = 0;

            loop {
                if reads_this_cycle >= 5 { break; }

                match stream.read(&mut temp_buf) {
                    Ok(0) => {
                        return Err(PyConnectionError::new_err("EOF: C# Watchdog severed the connection."));
                    }
                    Ok(n) => {
                        reads_this_cycle += 1;
                        let s = String::from_utf8_lossy(&temp_buf[..n]);
                        self.buffer.push_str(&s);

                        while let Some(newline_pos) = self.buffer.find('\n') {
                            let line: String = self.buffer.drain(..=newline_pos).collect();
                            let parts: Vec<&str> = line.trim().split(',').collect();

                            if parts.len() >= 4 {
                                let symbol = parts[0].to_string();
                                let price: f64 = parts[1].parse().unwrap_or(0.0);
                                let size: f64 = parts[2].parse().unwrap_or(0.0);
                                let side = parts[3]; 
                                
                                if side == "BUY" { self.delta += size; }
                                else if side == "SELL" { self.delta -= size; }
                                
                                if self.delta_window.len() == 100 {
                                    self.delta_window.pop_front();
                                }
                                self.delta_window.push_back(self.delta);

                                let mut z_score = 0.0;
                                if self.delta_window.len() > 1 {
                                    let sum: f64 = self.delta_window.iter().sum();
                                    let mean = sum / self.delta_window.len() as f64;
                                    let variance: f64 = self.delta_window.iter().map(|&value| {
                                        let diff = mean - value;
                                        diff * diff
                                    }).sum::<f64>() / self.delta_window.len() as f64;
                                    let std_dev = variance.sqrt();
                                    
                                    if std_dev > 0.0 {
                                        z_score = (self.delta - mean) / std_dev;
                                    }
                                }

                                let vwap = self.vwap_engine.update(price, size);
                                let (val, vah) = self.volume_profile.update(price, size);
                                
                                latest_state = Some((symbol, price, size, vwap, val, vah, self.delta, z_score));
                            }
                        }
                    }
                    Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                        break;
                    }
                    Err(e) => {
                        return Err(PyConnectionError::new_err(format!("Socket Error: {}", e)));
                    }
                }
            }
        }
        Ok(latest_state)
    }

    fn send_order(&mut self, signal: &str, symbol: &str, quantity: i32) -> PyResult<()> {
        if let Some(stream) = self.stream.as_mut() {
            let command = format!("EXECUTE,{},{},{},MARKET\n", signal, symbol, quantity);
            let bytes = command.as_bytes();
            
            loop {
                match stream.write(bytes) {
                    Ok(_) => break,
                    Err(ref e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                        std::thread::sleep(std::time::Duration::from_millis(1));
                    }
                    Err(_) => return Err(PyConnectionError::new_err("Failed to send order.")),
                }
            }
        }
        Ok(())
    }

    fn send_ping(&mut self) -> PyResult<()> {
        if let Some(stream) = self.stream.as_mut() {
            loop {
                match stream.write(b"PING\n") {
                    Ok(_) => break,
                    Err(ref e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                        std::thread::sleep(std::time::Duration::from_millis(1));
                    }
                    Err(_) => return Err(PyConnectionError::new_err("Failed to send heartbeat.")),
                }
            }
        }
        Ok(())
    }
}

#[pymodule]
fn eqie_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<QuantowerClient>()?;
    Ok(())
}