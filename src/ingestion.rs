use tokio::time::{timeout, Duration};
use tokio_tungstenite::{
    connect_async_tls_with_config, 
    Connector, 
    tungstenite::protocol::Message
};
use futures_util::{StreamExt, SinkExt};
use prost::Message as ProstMessage; 
use std::env;
use native_tls::TlsConnector;
use crate::shared_memory::SharedEngine;

pub mod rithmic_api {
    include!(concat!(env!("OUT_DIR"), "/rithmic.rs"));
}

pub async fn run_rithmic_ingestion(engine: std::sync::Arc<SharedEngine>, system_name: String) {
    let wss_url = env::var("RITHMIC_WSS_URL").unwrap_or_else(|_| "wss://rituz00100.rithmic.com:443".to_string());
    println!("🌐 [INGESTION] Connecting to Rithmic Cloud: {}", wss_url);

    let native_tls_builder = TlsConnector::builder()
        .danger_accept_invalid_certs(true)
        .danger_accept_invalid_hostnames(true)
        .build()
        .expect("Failed to build NativeTls connector");
        
    let connector = Connector::NativeTls(native_tls_builder);

    let ws_stream = match connect_async_tls_with_config(&wss_url, None, false, Some(connector)).await {
        Ok((stream, _)) => {
            println!("✅ [INGESTION] TLS Handshake Successful.");
            stream
        }
        Err(e) => {
            println!("💀 [INGESTION] FATAL: Could not connect: {}", e);
            return;
        }
    };

    let (mut write, mut read) = ws_stream.split();

    // 1. BUILD THE PROTOBUF LOGIN HANDSHAKE
    println!("🔐 [INGESTION] Constructing Cloud Login Payload...");
    let login_request = rithmic_api::RequestLogin {
        template_id: 10, 
        template_version: None,
        user_msg: vec![],
        user: Some(env::var("RITHMIC_USER").unwrap_or_default()),
        password: Some(env::var("RITHMIC_PASS").unwrap_or_default()),
        
        // Spoofing the Web GUI to bypass prop firm restrictions
        app_name: Some("R-Trader Web".to_string()), 
        app_version: Some("1.0.0.0".to_string()),
        
        // Dynamically injecting "Phidias Paper Trading"
        system_name: Some(system_name), 
        infra_type: Some(1), 
    };

    // 2. ENCODE AND TRANSMIT
    let mut buf = Vec::new();
    login_request.encode(&mut buf).unwrap();
    
    if let Err(e) = write.send(Message::Binary(buf)).await {
        println!("💀 [INGESTION] Failed to send login payload: {}", e);
        return;
    }
    println!("📡 [INGESTION] Login payload transmitted to Chicago. Awaiting response...");

    let timeout_duration = Duration::from_secs(5);

    // 3. THE EVENT LOOP
    loop {
        match timeout(timeout_duration, read.next()).await {
            Ok(Some(Ok(Message::Binary(binary_payload)))) => {
                if let Ok(response) = rithmic_api::ResponseLogin::decode(&binary_payload[..]) {
                    if response.rp_code.contains(&"0".to_string()) {
                        println!("✅ [INGESTION] Cloud Login Accepted! Session Authenticated.");
                    } else {
                        println!("❌ [INGESTION] Cloud Login Rejected: {:?}", response.rp_code);
                    }
                } else {
                    println!("📦 [INGESTION] Received {} bytes of Market Data", binary_payload.len());
                }
            }
            Ok(Some(Ok(Message::Ping(_)))) => { /* Heartbeat */ }
            Ok(Some(Ok(Message::Close(frame)))) => {
                println!("💀 [INGESTION] WebSocket closed by server: {:?}", frame);
                trigger_emergency_disconnect(&engine);
                break;
            }
            Ok(Some(Err(e))) => {
                println!("💀 [INGESTION] WebSocket read error: {:?}", e);
                trigger_emergency_disconnect(&engine);
                break;
            }
            Ok(None) => {
                println!("💀 [INGESTION] Connection closed by Rithmic.");
                trigger_emergency_disconnect(&engine);
                break;
            }
            Err(_) => {
                println!("💀 [INGESTION] Heartbeat timeout.");
                trigger_emergency_disconnect(&engine);
                break;
            }
            _ => {}
        }
    }
}

fn trigger_emergency_disconnect(shared_state: &SharedEngine) {
    let mut flag = shared_state.emergency_flatten_flag.lock();
    *flag = true; 
}