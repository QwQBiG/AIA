#![forbid(unsafe_code)]

use std::process::Stdio;

use ai_ex_domain::AppError;
use serde::de::DeserializeOwned;
use serde_json::Value;
use tokio::io::{AsyncBufRead, AsyncWrite, AsyncWriteExt, BufReader};
use tokio::process::{Child, Command};

use crate::{
    JSON_RPC_VERSION, JsonRpcRequest, JsonRpcResponse, MAX_JSON_RPC_LINE_BYTES, PluginHealth, PluginManifest, RpcId,
};

pub struct JsonRpcClient<R, W>
where
    R: AsyncBufRead + Unpin,
    W: AsyncWrite + Unpin,
{
    reader: R,
    writer: W,
    next_id: i64,
}

impl<R, W> JsonRpcClient<R, W>
where
    R: AsyncBufRead + Unpin,
    W: AsyncWrite + Unpin,
{
    pub fn new(reader: R, writer: W) -> Self
    {
        Self {
            reader,
            writer,
            next_id: 1,
        }
    }

    pub async fn request(&mut self, method: &str, params: Value) -> Result<Value, AppError>
    {
        let id = self.next_id;
        self.next_id = self
            .next_id
            .checked_add(1)
            .ok_or_else(|| AppError::protocol("plugin request id exhausted"))?;
        write_request(&mut self.writer, &JsonRpcRequest::new(id, method, params)).await?;
        let response = read_response(&mut self.reader).await?;
        if response.id != RpcId::Number(id)
        {
            return Err(AppError::protocol("plugin JSON-RPC response id mismatch"));
        }
        if let Some(error) = response.error
        {
            return Err(AppError::protocol(format!(
                "plugin request failed ({}): {}",
                error.code, error.message,
            )));
        }
        response
            .result
            .ok_or_else(|| AppError::protocol("plugin response has neither result nor error"))
    }

    pub async fn health(&mut self) -> Result<PluginHealth, AppError>
    {
        decode_result(self.request("health", Value::Object(Default::default())).await?)
    }

    pub async fn manifest(&mut self) -> Result<PluginManifest, AppError>
    {
        let manifest: PluginManifest =
            decode_result(self.request("manifest", Value::Object(Default::default())).await?)?;
        manifest.validate()?;
        Ok(manifest)
    }
}

pub struct StdioPlugin
{
    child: Child,
    client: JsonRpcClient<BufReader<tokio::process::ChildStdout>, tokio::process::ChildStdin>,
}

impl StdioPlugin
{
    pub fn spawn(program: impl AsRef<std::ffi::OsStr>, arguments: &[String]) -> Result<Self, AppError>
    {
        let mut command = Command::new(program);
        command
            .args(arguments)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit());
        let mut child = command
            .spawn()
            .map_err(|error| AppError::unavailable(format!("plugin process spawn failed: {error}")))?;
        let stdin = child
            .stdin
            .take()
            .ok_or_else(|| AppError::unavailable("plugin process stdin is unavailable"))?;
        let stdout = child
            .stdout
            .take()
            .ok_or_else(|| AppError::unavailable("plugin process stdout is unavailable"))?;
        Ok(Self {
            child,
            client: JsonRpcClient::new(BufReader::new(stdout), stdin),
        })
    }

    pub async fn request(&mut self, method: &str, params: Value) -> Result<Value, AppError>
    {
        self.client.request(method, params).await
    }

    pub async fn health(&mut self) -> Result<PluginHealth, AppError>
    {
        self.client.health().await
    }

    pub async fn manifest(&mut self) -> Result<PluginManifest, AppError>
    {
        self.client.manifest().await
    }

    pub async fn shutdown(mut self) -> Result<(), AppError>
    {
        self.child
            .kill()
            .await
            .map_err(|error| AppError::unavailable(format!("plugin process stop failed: {error}")))?;
        self.child
            .wait()
            .await
            .map_err(|error| AppError::unavailable(format!("plugin process wait failed: {error}")))?;
        Ok(())
    }

    pub fn try_wait(&mut self) -> Result<Option<std::process::ExitStatus>, AppError>
    {
        self.child
            .try_wait()
            .map_err(|error| AppError::unavailable(format!("plugin process status failed: {error}")))
    }
}

impl Drop for StdioPlugin
{
    fn drop(&mut self)
    {
        let _ignored = self.child.start_kill();
    }
}

pub async fn write_request<W>(writer: &mut W, request: &JsonRpcRequest) -> Result<(), AppError>
where
    W: AsyncWrite + Unpin,
{
    let payload = serde_json::to_vec(request)
        .map_err(|error| AppError::protocol(format!("plugin request encode failed: {error}")))?;
    if payload.len().saturating_add(1) > MAX_JSON_RPC_LINE_BYTES
    {
        return Err(AppError::protocol("plugin request exceeds size limit"));
    }
    writer
        .write_all(&payload)
        .await
        .map_err(|error| AppError::unavailable(format!("plugin stdin write failed: {error}")))?;
    writer
        .write_all(b"\n")
        .await
        .map_err(|error| AppError::unavailable(format!("plugin stdin write failed: {error}")))?;
    writer
        .flush()
        .await
        .map_err(|error| AppError::unavailable(format!("plugin stdin flush failed: {error}")))
}

pub async fn read_response<R>(reader: &mut R) -> Result<JsonRpcResponse, AppError>
where
    R: AsyncBufRead + Unpin,
{
    let line = crate::read_bounded_line(reader)
        .await?
        .ok_or_else(|| AppError::unavailable("plugin exited before response"))?;
    let text = std::str::from_utf8(&line)
        .map_err(|error| AppError::protocol(format!("plugin response is not UTF-8: {error}")))?;
    let response: JsonRpcResponse = serde_json::from_str(text.trim_end())
        .map_err(|error| AppError::protocol(format!("invalid plugin JSON-RPC response: {error}")))?;
    if response.jsonrpc != JSON_RPC_VERSION
    {
        return Err(AppError::protocol("plugin JSON-RPC version must be 2.0"));
    }
    Ok(response)
}

fn decode_result<T>(value: Value) -> Result<T, AppError>
where
    T: DeserializeOwned,
{
    serde_json::from_value(value)
        .map_err(|error| AppError::protocol(format!("invalid plugin result: {error}")))
}

#[cfg(test)]
mod tests
{
    use tokio::io::{AsyncWriteExt, BufReader, duplex, split};

    use super::*;

    #[tokio::test]
    async fn client_round_trips_request_and_validates_response()
    {
        let (client_io, server_io) = duplex(4_096);
        let (client_reader, client_writer) = split(client_io);
        let (server_reader, mut server_writer) = split(server_io);
        let server = tokio::spawn(async move {
            let mut reader = BufReader::new(server_reader);
            let request = crate::read_request(&mut reader)
                .await
                .expect("request reads")
                .expect("request exists");
            assert_eq!(request.method, "health");
            let response = JsonRpcResponse::success(
                request.id,
                serde_json::json!({"ready": true, "detail": "test"}),
            );
            let encoded = serde_json::to_vec(&response).expect("response encodes");
            server_writer.write_all(&encoded).await.expect("response writes");
            server_writer.write_all(b"\n").await.expect("response ends");
            server_writer.flush().await.expect("response flushes");
        });
        let mut client = JsonRpcClient::new(BufReader::new(client_reader), client_writer);
        let value = client
            .request("health", serde_json::json!({}))
            .await
            .expect("client request succeeds");
        assert_eq!(value["ready"], true);
        server.await.expect("server completes");
    }

    #[tokio::test]
    async fn response_reader_rejects_oversized_line()
    {
        let (mut writer, reader) = duplex(MAX_JSON_RPC_LINE_BYTES + 8);
        writer
            .write_all(vec![b'x'; MAX_JSON_RPC_LINE_BYTES + 1].as_slice())
            .await
            .expect("oversized response writes");
        drop(writer);
        let mut reader = BufReader::new(reader);
        assert!(read_response(&mut reader).await.is_err());
    }
}
