use serde::{Deserialize, Deserializer, Serializer};

// Internally tagged control responses buffer integers as u64, not u128.
// Ordinary epoch milliseconds retain their existing JSON number representation.
#[derive(Deserialize)]
#[serde(untagged)]
enum Milliseconds {
    Number(u64),
    Decimal(String),
}

impl Milliseconds {
    fn value<E: serde::de::Error>(self) -> Result<u128, E> {
        match self {
            Self::Number(value) => Ok(u128::from(value)),
            Self::Decimal(value) => value.parse().map_err(E::custom),
        }
    }
}

pub fn serialize<S: Serializer>(value: &u128, serializer: S) -> Result<S::Ok, S::Error> {
    match u64::try_from(*value) {
        Ok(value) => serializer.serialize_u64(value),
        Err(_) => serializer.serialize_str(&value.to_string()),
    }
}

pub fn deserialize<'de, D: Deserializer<'de>>(deserializer: D) -> Result<u128, D::Error> {
    Milliseconds::deserialize(deserializer)?.value()
}

pub mod optional {
    use super::*;
    use serde::Serialize;

    pub fn serialize<S: Serializer>(
        value: &Option<u128>,
        serializer: S,
    ) -> Result<S::Ok, S::Error> {
        match value {
            Some(value) => match u64::try_from(*value) {
                Ok(value) => Some(value).serialize(serializer),
                Err(_) => Some(value.to_string()).serialize(serializer),
            },
            None => serializer.serialize_none(),
        }
    }

    pub fn deserialize<'de, D: Deserializer<'de>>(
        deserializer: D,
    ) -> Result<Option<u128>, D::Error> {
        Option::<Milliseconds>::deserialize(deserializer)?
            .map(Milliseconds::value)
            .transpose()
    }
}
