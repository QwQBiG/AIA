#![forbid(unsafe_code)]

use std::collections::BTreeMap;

use ai_ex_domain::{AppError, ComponentHealth};
use serde::{Deserialize, Serialize};

use crate::{PluginHealth, PluginManifest};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct PluginStatus
{
    pub manifest: PluginManifest,
    pub health: PluginHealth,
}

pub struct PluginRegistry
{
    entries: BTreeMap<String, PluginStatus>,
}

impl PluginRegistry
{
    pub fn new() -> Self
    {
        Self {
            entries: BTreeMap::new(),
        }
    }

    pub fn register(&mut self, manifest: PluginManifest) -> Result<(), AppError>
    {
        manifest.validate()?;
        if self.entries.contains_key(&manifest.id)
        {
            return Err(AppError::configuration(format!(
                "plugin id already registered: {}",
                manifest.id,
            )));
        }
        let id = manifest.id.clone();
        self.entries.insert(
            id,
            PluginStatus {
                manifest,
                health: PluginHealth {
                    ready: false,
                    detail: "health has not been reported".to_owned(),
                },
            },
        );
        Ok(())
    }

    pub fn update_health(
        &mut self,
        id: &str,
        health: PluginHealth,
    ) -> Result<(), AppError>
    {
        let status = self
            .entries
            .get_mut(id)
            .ok_or_else(|| AppError::configuration(format!("plugin id is not registered: {id}")))?;
        status.health = health;
        Ok(())
    }

    pub fn get(&self, id: &str) -> Option<&PluginStatus>
    {
        self.entries.get(id)
    }

    pub fn len(&self) -> usize
    {
        self.entries.len()
    }

    pub fn is_empty(&self) -> bool
    {
        self.entries.is_empty()
    }

    pub fn statuses(&self) -> impl Iterator<Item = &PluginStatus>
    {
        self.entries.values()
    }

    pub fn health(&self) -> ComponentHealth
    {
        let ready = self.entries.values().all(|status| status.health.ready);
        ComponentHealth {
            component: "plugin-registry".to_owned(),
            ready,
            detail: format!("{} plugin(s) registered", self.entries.len()),
        }
    }

    pub fn component_health(&self) -> Vec<ComponentHealth>
    {
        self.entries
            .values()
            .map(|status| ComponentHealth {
                component: format!("plugin:{}", status.manifest.id),
                ready: status.health.ready,
                detail: format!(
                    "{} v{}: {}",
                    status.manifest.id,
                    status.manifest.version,
                    status.health.detail,
                ),
            })
            .collect()
    }
}

impl Default for PluginRegistry
{
    fn default() -> Self
    {
        Self::new()
    }
}

#[cfg(test)]
mod tests
{
    use serde_json::Value;

    use super::*;

    fn manifest(id: &str) -> PluginManifest
    {
        PluginManifest {
            protocol_version: 1,
            id: id.to_owned(),
            version: "1.0.0".to_owned(),
            capabilities: vec!["vision.observe".to_owned()],
            config_schema: Value::Null,
        }
    }

    #[test]
    fn registers_updates_and_projects_plugin_health()
    {
        let mut registry = PluginRegistry::new();
        registry.register(manifest("vision.demo")).expect("registers");
        assert_eq!(registry.len(), 1);
        assert!(!registry.health().ready);
        registry
            .update_health(
                "vision.demo",
                PluginHealth {
                    ready: true,
                    detail: "dry-run ready".to_owned(),
                },
            )
            .expect("health updates");
        assert!(registry.health().ready);
        assert_eq!(registry.component_health()[0].component, "plugin:vision.demo");
    }

    #[test]
    fn rejects_duplicate_and_unknown_plugins()
    {
        let mut registry = PluginRegistry::new();
        registry.register(manifest("game.demo")).expect("registers");
        assert!(registry.register(manifest("game.demo")).is_err());
        assert!(registry
            .update_health(
                "missing",
                PluginHealth {
                    ready: true,
                    detail: String::new(),
                },
            )
            .is_err());
    }
}
