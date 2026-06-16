// build.rs
use std::io::Result;

fn main() -> Result<()> {
    // This tells Cargo to compile the Rithmic schema files whenever you run maturin
    // We will create the proto folder in the next step.
    prost_build::compile_protos(&["proto/rithmic_base.proto"], &["proto/"])?;
    Ok(())
}