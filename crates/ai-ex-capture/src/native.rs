use ai_ex_domain::AppError;
use ai_ex_duplex::{AudioFrame, AudioSourcePort};
use async_trait::async_trait;
use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use cpal::{Device, SampleFormat, Stream, StreamConfig};
use tokio::sync::mpsc;

#[derive(Debug, Clone)]
pub struct CaptureSettings
{
    pub device_name: Option<String>,
    pub queue_capacity: usize,
}

pub struct NativeAudioSource
{
    _stream: Stream,
    receiver: mpsc::Receiver<Result<AudioFrame, AppError>>,
}

impl NativeAudioSource
{
    pub fn open(settings: CaptureSettings) -> Result<Self, AppError>
    {
        if settings.queue_capacity == 0
        {
            return Err(AppError::configuration("capture queue capacity must be positive"));
        }
        let host = cpal::default_host();
        let device = select_device(&host, settings.device_name.as_deref())?;
        let supported = device
            .default_input_config()
            .map_err(|error| AppError::unavailable(format!("input format unavailable: {error}")))?;
        let sample_format = supported.sample_format();
        let config: StreamConfig = supported.into();
        let sample_rate = config.sample_rate.0;
        let channels = config.channels;
        let (sender, receiver) = mpsc::channel(settings.queue_capacity);
        let stream = match sample_format
        {
            SampleFormat::F32 => build_stream(
                &device,
                &config,
                sender,
                sample_rate,
                channels,
                |sample: f32| sample,
            ),
            SampleFormat::I16 => build_stream(
                &device,
                &config,
                sender,
                sample_rate,
                channels,
                |sample: i16| f32::from(sample) / 32_768.0,
            ),
            SampleFormat::U16 => build_stream(
                &device,
                &config,
                sender,
                sample_rate,
                channels,
                |sample: u16| (f32::from(sample) - 32_768.0) / 32_768.0,
            ),
            other => Err(AppError::unavailable(format!(
                "unsupported input sample format: {other:?}",
            ))),
        }?;
        stream
            .play()
            .map_err(|error| AppError::unavailable(format!("cannot start capture: {error}")))?;
        Ok(Self {
            _stream: stream,
            receiver,
        })
    }
}

#[async_trait]
impl AudioSourcePort for NativeAudioSource
{
    async fn next_frame(&mut self) -> Result<Option<AudioFrame>, AppError>
    {
        match self.receiver.recv().await
        {
            Some(Ok(frame)) => Ok(Some(frame)),
            Some(Err(error)) => Err(error),
            None => Ok(None),
        }
    }
}

fn select_device(host: &cpal::Host, requested: Option<&str>) -> Result<Device, AppError>
{
    if let Some(requested) = requested.filter(|name| !name.trim().is_empty())
    {
        let devices = host
            .input_devices()
            .map_err(|error| AppError::unavailable(format!("cannot list input devices: {error}")))?;
        for device in devices
        {
            let name = device.name().unwrap_or_default();
            if name.eq_ignore_ascii_case(requested)
            {
                return Ok(device);
            }
        }
        return Err(AppError::configuration(format!(
            "input device not found: {requested}",
        )));
    }
    host.default_input_device()
        .ok_or_else(|| AppError::unavailable("no default input device"))
}

fn build_stream<T, F>(
    device: &Device,
    config: &StreamConfig,
    sender: mpsc::Sender<Result<AudioFrame, AppError>>,
    sample_rate: u32,
    channels: u16,
    convert: F,
) -> Result<Stream, AppError>
where
    T: cpal::SizedSample + Copy,
    F: Fn(T) -> f32 + Send + Copy + 'static,
{
    let error_sender = sender.clone();
    device
        .build_input_stream(
            config,
            move |data: &[T], _info|
            {
                let samples = data.iter().copied().map(convert).collect();
                let frame = AudioFrame::new(samples, sample_rate, channels);
                let _ignored = sender.try_send(frame);
            },
            move |error|
            {
                let error = AppError::unavailable(format!("audio capture failed: {error}"));
                let _ignored = error_sender.try_send(Err(error));
            },
            None,
        )
        .map_err(|error| AppError::unavailable(format!("cannot build input stream: {error}")))
}
