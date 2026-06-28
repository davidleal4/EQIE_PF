# Synapse: Algorithmic Trading Architecture

**Synapse** is a heterogeneous, low-latency algorithmic trading framework designed for the execution of futures market strategies. The system leverages a dual-language architecture—utilizing the high-throughput safety of **Rust** for execution gateways and the rapid iteration capabilities of **Python** for machine learning, signal processing, and high-level strategy orchestration.

### The Architecture
The core innovation of Synapse is the **`EQIE_PHIDIAS2` Bridge**, a memory-efficient interface that enables zero-copy communication between Python’s data science stack and Rust’s high-frequency execution environment.

* **The Brain (Python):** Handles incoming market feeds, calculates statistical arbitrage vectors (Kalman filters, Z-score modeling), manages multi-strategy machine learning inference, and resolves state-machine logic.
* **The Muscle (Rust):** Acts as a low-latency "Gatekeeper," interfacing directly with the Rithmic liquidity API via asynchronous WebSockets. It enforces strict risk protocols, manages order lifecycle, and executes trades with sub-millisecond overhead.

---

### Core System Capabilities

#### 1. Real-Time Statistical Arbitrage
Synapse implements a dynamic **Kalman Filter** engine to track the cointegrated relationship between highly correlated assets (e.g., NQ vs. ES futures). By maintaining a real-time estimation of the "true" spread, the system identifies mean-reversion opportunities that are statistically robust against micro-noise.

#### 2. Adaptive Risk Engineering
The system incorporates institutional-grade protective logic:
* **Micro-Hedging (Overlay Tracking):** Automatically deploys correlated micro-contracts to neutralize delta during high-volatility spikes, effectively "hedging the hedge."
* **Circuit Breakers:** A multi-layered drawdown management system that enforces static loss limits (e.g., -490 USD) and EOD trailing floors, programmatically preventing further trading if volatility exceeds pre-defined risk boundaries.
* **Execution Chasing:** A state-machine-driven limit order manager that intelligently transitions to market orders if limit orders remain untouched during high-velocity moves.

#### 3. Heterogeneous Integration
* **PyO3/NumPy Bridge:** Uses zero-copy memory mapping for weekend backtesting. This allows the system to run millions of simulated ticks through the performance engine without the overhead of data serialization.
* **Asynchronous I/O:** Built on `tokio` and `tungstenite`, the Rithmic ingestion engine handles multiplexed data streams (Market Data, Order Status, Authentication) concurrently, ensuring that risk checks never block execution throughput.

---

### Quantitative Metrics
Synapse evaluates its own performance continuously, providing real-time telemetry on:
* **Precision (Win Rate):** Direct measure of trade profitability upon execution.
* **Recall:** Efficiency in capturing structural market movements.
* **F1-Score:** The harmonic mean of Precision and Recall, used as a primary metric for vetting strategy viability under varying market regimes.
* **Trade Sharpe:** Risk-adjusted return assessment of individual trade sequences.

---

### Tech Stack
* **Systems Programming:** Rust (Tokio, Crossbeam, Prost/Protobuf, Native-TLS).
* **Data Orchestration:** Python (Pandas, NumPy, PyO3, Pytz).
* **Infrastructure:** Custom TCP/WebSocket gateways, asynchronous memory-locked queues.
* **Backtesting:** Vectorized historical tick data simulation (Zero-copy).

