#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub(crate) enum BuiltinCharacter {
    #[default]
    Oc01,
    Original,
}

impl BuiltinCharacter {
    pub(crate) const ALL: [Self; 2] = [Self::Oc01, Self::Original];

    pub(crate) fn id(self) -> &'static str {
        match self {
            Self::Oc01 => "oc-01",
            Self::Original => "original",
        }
    }

    pub(crate) fn from_id(id: &str) -> Option<Self> {
        match id {
            "oc-01" => Some(Self::Oc01),
            "original" => Some(Self::Original),
            _ => None,
        }
    }

    pub(crate) fn label(self) -> &'static str {
        match self {
            Self::Oc01 => "01 · 一号人物",
            Self::Original => "02 · 初始伙伴",
        }
    }
}
