# EQIE_PF
**Equity Quantitative Inference Engine (Portfolio Edition)**

A high-performance predictive architecture and localized multi-agent intelligence system optimized for automated execution in highly constrained risk environments.

## Overview
EQIE_PF is the second major iteration of the Equity Quantitative Inference Engine. Designed specifically to navigate the strict risk-management and End-of-Day (EOD) drawdown parameters required by quantitative evaluation programs (specifically optimized for a $50K Topstep Combine), the engine transitions from standard isolated scripting to an autonomous, continuous machine learning environment.

The primary focus of this architecture is executing low-latency market analysis on E-mini S&P 500 (ES) and Micro E-mini (MES) futures, identifying structural setups (such as algorithmic representations of break-and-retest or triple-line dynamics) while strictly managing system-level resource constraints.

## System Architecture
To achieve near-zero latency while processing high-dimensional data, EQIE_PF utilizes a hybrid language approach and a custom network gateway:

*   **Execution Layer (Rust):** Core logic, deterministic mechanics, and risk-management boundaries are written in Rust. This eliminates latency, parses real-time Level 2 Order Book (DOM) data, and ensures memory safety during high-frequency execution.
*   **Modeling Layer (Python):** Predictive modeling, Bayesian variance calculations, and statistical pipelines are handled in Python.
*   **Memory Bridge (PyO3 & Maturin):** The system relies on a PyO3 bridge to facilitate seamless, low-overhead memory transfers between the Python and Rust environments, ensuring transparent and immediate execution without the overhead of local REST APIs.
*   **Network Router (C# Headless Bridge):** A lightweight C# plugin hooks directly into Quantower, bypassing the GUI to stream top-of-book and Depth of Market (DOM) updates through a localhost TCP socket directly into the Rust core.

## Advanced Institutional Logic
This engine moves beyond standard retail indicators by calculating order flow and variance dynamically:

*   **Deep Order Flow Imbalance (OFI):** Instead of relying on lagging trade delta, the Rust core ingests the top 5 levels of the Bid and Ask limit order book to calculate standardized OFI, identifying liquidity pulls and institutional stacking before trades execute.
*   **Bayesian Regime Detection:** The system utilizes approximated Bayesian Online Changepoint Detection (BOCPD) by tracking the ratio of short-term to long-term price variance. When volatility spikes, the engine autonomously shifts into a "High-Vol" regime, dynamically widening required standard deviation and OFI execution thresholds.
*   **Anchored VWAP (AVWAP) & Standard Deviations:** VWAP is calculated and anchored continuously, wrapped in dynamically computed 1st and 2nd standard deviation bands to map precise structural reversal points.

## Asymmetric Scale-Out & Risk Framework
EQIE_PF does not attempt to predict every tick; it relies on mathematical asymmetry and strict loss mitigation tailored to prop-firm metrics:

*   **Consistency Rule Guardian:** A hardcoded daily profit cap ($1,000) forces the engine to automatically flatten positions and shut down once targets are reached, guaranteeing compliance with 40% consistency rules for payout qualification.
*   **EOD Drawdown Protection:** The architecture operates on a 2-contract scale-out basis. The first contract locks in rapid micro-profits to finance the trade, leaving a trailing "runner" contract to capture macro-momentum without triggering daily loss limits (-$400 hard stop) or threatening the $2,000 maximum trailing drawdown buffer.

## Localized Intelligence & Privacy
To maintain complete data sovereignty and prevent the leakage of proprietary logic, EQIE_PF operates entirely on local hardware. The system integrates localized AI workflows using Ollama, allowing for privacy-first, on-device intelligence processing without relying on external API calls that introduce latency or compromise structural integrity.

## Disclaimer
*Note: To protect proprietary execution strategies, specific model weights, signal logic, and internal network configurations have been removed or replaced with `.env.example` configuration templates in this public repository. This repository serves strictly as an architectural demonstration of the engine's data structures, risk management framework, and memory bridges.*
