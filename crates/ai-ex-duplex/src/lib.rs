#![forbid(unsafe_code)]

mod controller;
mod ports;
mod types;
mod vad;

#[cfg(test)]
mod controller_tests;
#[cfg(test)]
mod vad_tests;

pub use controller::{DuplexController, DuplexDirective};
pub use ports::{AudioSourcePort, TranscriberPort};
pub use types::{AudioFrame, Utterance, VadConfig, VadEvent};
pub use vad::EnergyVad;
