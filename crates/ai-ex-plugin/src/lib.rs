#![forbid(unsafe_code)]

use ai_ex_domain::AppError;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use tokio::io::{AsyncBufRead, AsyncBufReadExt, AsyncWrite, AsyncWriteExt};

pub const JSON_RPC_VERSION: &str = "2.0";

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct PluginManifest
{
    pub protocol_version: u16,
    pub id: String,
    pub version: String,
    pub capabilities: Vec<String>,
    pub config_schema: Value,
}

impl PluginManifest
{
    pub fn validate(&self) -> Result<(), AppError>
    {
        if self.protocol_version == 0
            || self.id.trim().is_empty()
            || self.version.trim().is_empty()
        {
            return Err(AppError::configuration("plugin manifest identity is invalid"));
        }
        if self.capabilities.iter().any(|item| item.trim().is_empty())
        {
            return Err(AppError::configuration("plugin capability must not be empty"));
        }
        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(untagged)]
pub enum RpcId
{
    Number(i64),
    String(String),
}

impl From<i64> for RpcId
{
    fn from(value: i64) -> Self
    {
        Self::Number(value)
    }
}

impl From<String> for RpcId
{
    fn from(value: String) -> Self
    {
        Self::String(value)
    }
}

impl From<&str> for RpcId
{
    fn from(value: &str) -> Self
    {
        Self::String(value.to_owned())
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct JsonRpcRequest
{
    pub jsonrpc: String,
    pub id: RpcId,
    pub method: String,
    #[serde(default)]
    pub params: Value,
}

impl JsonRpcRequest
{
    pub fn new(id: impl Into<RpcId>, method: impl Into<String>, params: Value) -> Self
    {
        Self {
            jsonrpc: JSON_RPC_VERSION.to_owned(),
            id: id.into(),
            method: method.into(),
            params,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct JsonRpcError
{
    pub code: i64,
    pub message: String,
    #[serde(default)]
    pub data: Option<Value>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct JsonRpcResponse
{
    pub jsonrpc: String,
    pub id: RpcId,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub result: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<JsonRpcError>,
}

impl JsonRpcResponse
{
    pub fn success(id: RpcId, result: Value) -> Self
    {
        Self {
            jsonrpc: JSON_RPC_VERSION.to_owned(),
            id,
            result: Some(result),
            error: None,
        }
    }

    pub fn failure(id: RpcId, code: i64, message: impl Into<String>) -> Self
    {
        Self {
            jsonrpc: JSON_RPC_VERSION.to_owned(),
            id,
            result: None,
            error: Some(JsonRpcError {
                code,
                message: message.into(),
                data: None,
            }),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct PluginHealth
{
    pub ready: bool,
    pub detail: String,
}

pub async fn read_request<R>(reader: &mut R) -> Result<Option<JsonRpcRequest>, AppError>
where
    R: AsyncBufRead + Unpin,
{
    let mut line = String::new();
    let size = reader
        .read_line(&mut line)
        .await
        .map_err(|error| AppError::unavailable(format!("plugin stdin read failed: {error}")))?;
    if size == 0
    {
        return Ok(None);
    }
    let request: JsonRpcRequest = serde_json::from_str(line.trim_end()).map_err(|error| {
        AppError::protocol(format!("invalid plugin JSON-RPC request: {error}"))
    })?;
    if request.jsonrpc != JSON_RPC_VERSION
    {
        return Err(AppError::protocol("plugin JSON-RPC version must be 2.0"));
    }
    Ok(Some(request))
}

pub async fn write_response<W>(writer: &mut W, response: &JsonRpcResponse) -> Result<(), AppError>
where
    W: AsyncWrite + Unpin,
{
    let payload = serde_json::to_vec(response)
        .map_err(|error| AppError::protocol(format!("plugin response encode failed: {error}")))?;
    writer
        .write_all(&payload)
        .await
        .map_err(|error| AppError::unavailable(format!("plugin stdout write failed: {error}")))?;
    writer
        .write_all(b"\n")
        .await
        .map_err(|error| AppError::unavailable(format!("plugin stdout write failed: {error}")))?;
    writer
        .flush()
        .await
        .map_err(|error| AppError::unavailable(format!("plugin stdout flush failed: {error}")))
}

#[cfg(test)]
mod tests
{
    use super::*;
    use tokio::io::BufReader;

    #[tokio::test]
    async fn stdio_request_response_round_trip()
    {
        let request = JsonRpcRequest::new(1_i64, "health", serde_json::json!({}));
        let encoded = serde_json::to_string(&request).expect("request encodes") + "\n";
        let mut reader = BufReader::new(encoded.as_bytes());
        let decoded = read_request(&mut reader)
            .await
            .expect("request reads")
            .expect("request exists");
        assert_eq!(decoded, request);

        let response = JsonRpcResponse::success(decoded.id, serde_json::json!({"ready": true}));
        let mut output = Vec::new();
        write_response(&mut output, &response)
            .await
            .expect("response writes");
        assert!(String::from_utf8(output).expect("response utf8").contains("ready"));
    }

    #[test]
    fn manifest_rejects_empty_capabilities()
    {
        let manifest = PluginManifest {
            protocol_version: 1,
            id: "vts".to_owned(),
            version: "1.0.0".to_owned(),
            capabilities: vec![String::new()],
            config_schema: Value::Null,
        };
        assert!(manifest.validate().is_err());
    }
}
