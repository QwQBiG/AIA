use ai_ex_domain::AppError;
use ai_ex_duplex::Utterance;

const HEADER_SIZE: usize = 44;

pub fn encode_pcm16_wav(utterance: &Utterance) -> Result<Vec<u8>, AppError>
{
    validate(utterance)?;
    let data_size = utterance
        .samples
        .len()
        .checked_mul(2)
        .and_then(|size| u32::try_from(size).ok())
        .ok_or_else(|| AppError::protocol("utterance is too large for a WAV file"))?;
    let riff_size = data_size
        .checked_add(36)
        .ok_or_else(|| AppError::protocol("WAV RIFF size overflow"))?;
    let block_align = utterance
        .channels
        .checked_mul(2)
        .ok_or_else(|| AppError::protocol("WAV channel count overflow"))?;
    let byte_rate = utterance
        .sample_rate
        .checked_mul(u32::from(block_align))
        .ok_or_else(|| AppError::protocol("WAV byte rate overflow"))?;
    let capacity = HEADER_SIZE
        .checked_add(data_size as usize)
        .ok_or_else(|| AppError::protocol("WAV allocation size overflow"))?;
    let mut output = Vec::with_capacity(capacity);

    output.extend_from_slice(b"RIFF");
    output.extend_from_slice(&riff_size.to_le_bytes());
    output.extend_from_slice(b"WAVEfmt ");
    output.extend_from_slice(&16_u32.to_le_bytes());
    output.extend_from_slice(&1_u16.to_le_bytes());
    output.extend_from_slice(&utterance.channels.to_le_bytes());
    output.extend_from_slice(&utterance.sample_rate.to_le_bytes());
    output.extend_from_slice(&byte_rate.to_le_bytes());
    output.extend_from_slice(&block_align.to_le_bytes());
    output.extend_from_slice(&16_u16.to_le_bytes());
    output.extend_from_slice(b"data");
    output.extend_from_slice(&data_size.to_le_bytes());
    for sample in &utterance.samples
    {
        let scaled = if *sample < 0.0
        {
            sample.clamp(-1.0, 1.0) * 32_768.0
        }
        else
        {
            sample.clamp(-1.0, 1.0) * 32_767.0
        };
        output.extend_from_slice(&(scaled.round() as i16).to_le_bytes());
    }
    Ok(output)
}

fn validate(utterance: &Utterance) -> Result<(), AppError>
{
    if utterance.samples.is_empty()
    {
        return Err(AppError::protocol("cannot encode an empty utterance"));
    }
    if utterance.sample_rate == 0 || utterance.channels == 0
    {
        return Err(AppError::protocol("utterance audio format is invalid"));
    }
    if !utterance.samples.iter().all(|sample| sample.is_finite())
    {
        return Err(AppError::protocol("utterance contains non-finite samples"));
    }
    Ok(())
}

#[cfg(test)]
mod tests
{
    use super::*;

    #[test]
    fn encodes_standard_pcm16_header_and_samples()
    {
        let wav = encode_pcm16_wav(&Utterance {
            samples: vec![-1.0, 0.0, 1.0],
            sample_rate: 16_000,
            channels: 1,
        })
        .expect("encode WAV");

        assert_eq!(&wav[0..4], b"RIFF");
        assert_eq!(&wav[8..12], b"WAVE");
        assert_eq!(&wav[36..40], b"data");
        assert_eq!(u32::from_le_bytes(wav[40..44].try_into().unwrap()), 6);
        assert_eq!(wav.len(), HEADER_SIZE + 6);
        assert_eq!(i16::from_le_bytes(wav[44..46].try_into().unwrap()), i16::MIN);
        assert_eq!(i16::from_le_bytes(wav[48..50].try_into().unwrap()), i16::MAX);
    }

    #[test]
    fn rejects_empty_utterance()
    {
        let result = encode_pcm16_wav(&Utterance {
            samples: Vec::new(),
            sample_rate: 16_000,
            channels: 1,
        });

        assert!(result.is_err());
    }
}
