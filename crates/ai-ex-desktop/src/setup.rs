use std::io::{Read, Write};
use std::net::{TcpStream, ToSocketAddrs};
use std::path::PathBuf;
use std::sync::{mpsc::{self, Receiver}, Arc, Mutex};
use std::thread;
use std::time::Duration;

use ai_ex_domain::AppError;
use eframe::egui;
use uuid::Uuid;

#[derive(Debug, Clone)]
pub struct SetupResult
{
    pub config_path: PathBuf,
    pub api_key: Option<String>,
    pub start_service: bool,
}

pub fn run(default_path: PathBuf) -> Result<SetupResult, AppError>
{
    let result = Arc::new(Mutex::new(None));
    let shared = Arc::clone(&result);
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([760.0, 620.0])
            .with_min_inner_size([640.0, 520.0]),
        ..Default::default()
    };
    eframe::run_native(
        "AIex 首次设置",
        options,
        Box::new(move |context| {
            Ok(Box::new(SetupApp::new(context, default_path, shared)))
        }),
    )
    .map_err(|error| AppError::unavailable(error.to_string()))?;
    result
        .lock()
        .map_err(|_| AppError::unavailable("setup result lock poisoned"))?
        .clone()
        .ok_or_else(|| AppError::configuration("setup canceled; run AIex again to retry"))
}

struct SetupApp
{
    config_path: PathBuf,
    provider: ProviderChoice,
    model: String,
    endpoint: String,
    api_key: String,
    persona_name: String,
    bilibili_enabled: bool,
    bilibili_room_id: String,
    bilibili_cookie_env: String,
    start_service: bool,
    status: String,
    status_error: bool,
    checking: bool,
    probe_receiver: Option<Receiver<Result<String, String>>>,
    result: Arc<Mutex<Option<SetupResult>>>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum ProviderChoice
{
    DeepSeek,
    KoboldCpp,
    Ollama,
}

impl ProviderChoice
{
    fn label(self) -> &'static str
    {
        match self
        {
            Self::DeepSeek => "DeepSeek 云端模型",
            Self::KoboldCpp => "KoboldCpp 本地模型",
            Self::Ollama => "Ollama 本地模型",
        }
    }

    fn backend(self) -> &'static str
    {
        match self
        {
            Self::DeepSeek => "deepseek",
            Self::KoboldCpp => "koboldcpp",
            Self::Ollama => "ollama",
        }
    }

    fn description(self) -> &'static str
    {
        match self
        {
            Self::DeepSeek => "云端 API，适合直接开始测试；需要 DEEPSEEK_API_KEY。",
            Self::KoboldCpp => "本地兼容 API，默认 127.0.0.1:5001；需要先启动 KoboldCpp。",
            Self::Ollama => "本地模型服务，默认 127.0.0.1:11434；需要先安装并运行 Ollama。",
        }
    }

    fn model_hint(self) -> &'static str
    {
        match self
        {
            Self::DeepSeek => "模型名按账户可用清单填写，例如 deepseek-v4-flash。",
            Self::KoboldCpp => "填写 KoboldCpp 当前加载的模型标识；服务会使用已加载模型。",
            Self::Ollama => "填写本机已安装的模型名，例如 llama3.2:latest。",
        }
    }
}

impl SetupApp
{
    fn new(
        _context: &eframe::CreationContext<'_>,
        config_path: PathBuf,
        result: Arc<Mutex<Option<SetupResult>>>,
    ) -> Self
    {
        Self {
            config_path,
            provider: ProviderChoice::DeepSeek,
            model: "deepseek-v4-flash".to_owned(),
            endpoint: "https://api.deepseek.com".to_owned(),
            api_key: String::new(),
            persona_name: "AIex".to_owned(),
            bilibili_enabled: false,
            bilibili_room_id: String::new(),
            bilibili_cookie_env: "BILIBILI_COOKIE".to_owned(),
            start_service: true,
            status: String::new(),
            status_error: false,
            checking: false,
            probe_receiver: None,
            result,
        }
    }

    fn provider_changed(&mut self)
    {
        match self.provider
        {
            ProviderChoice::DeepSeek =>
            {
                self.endpoint = "https://api.deepseek.com".to_owned();
                self.model = "deepseek-v4-flash".to_owned();
            }
            ProviderChoice::KoboldCpp =>
            {
                self.endpoint = "http://127.0.0.1:5001".to_owned();
                self.model = "koboldcpp".to_owned();
            }
            ProviderChoice::Ollama =>
            {
                self.endpoint = "http://127.0.0.1:11434".to_owned();
                self.model = "llama3.2:latest".to_owned();
            }
        }
    }

    fn set_status(&mut self, message: impl Into<String>, error: bool)
    {
        self.status = message.into();
        self.status_error = error;
    }

    fn poll_probe(&mut self)
    {
        let Some(receiver) = self.probe_receiver.take() else
        {
            return;
        };
        match receiver.try_recv()
        {
            Ok(Ok(message)) =>
            {
                self.checking = false;
                self.set_status(message, false);
            }
            Ok(Err(error)) =>
            {
                self.checking = false;
                self.set_status(format!("连接检查失败：{error}"), true);
            }
            Err(mpsc::TryRecvError::Empty) => self.probe_receiver = Some(receiver),
            Err(mpsc::TryRecvError::Disconnected) =>
            {
                self.checking = false;
                self.set_status("连接检查线程已停止，请重试。", true);
            }
        }
    }

    fn check_connection(&mut self)
    {
        if self.endpoint.trim().is_empty()
        {
            self.set_status("请先填写模型地址。", true);
            return;
        }
        if self.provider == ProviderChoice::DeepSeek
            && self.api_key.trim().is_empty()
            && std::env::var_os("DEEPSEEK_API_KEY").is_none()
        {
            self.set_status("DeepSeek 连接检查需要 API Key；密钥不会写入配置文件。", true);
            return;
        }
        let endpoint = self.endpoint.trim().to_owned();
        let provider = self.provider;
        let (sender, receiver) = mpsc::channel();
        self.checking = true;
        self.set_status("正在检查地址和网络端口……", false);
        self.probe_receiver = Some(receiver);
        thread::spawn(move ||
        {
            let result = probe_endpoint(provider, &endpoint).map_err(|error| error.to_string());
            let _ignored = sender.send(result);
        });
    }
    fn save(&mut self, context: &egui::Context)
    {
        if self.persona_name.trim().is_empty()
            || self.endpoint.trim().is_empty()
            || self.model.trim().is_empty()
        {
            self.set_status("请填写角色名、模型地址和模型名称。", true);
            return;
        }
        if self.provider == ProviderChoice::DeepSeek
            && self.api_key.trim().is_empty()
            && std::env::var_os("DEEPSEEK_API_KEY").is_none()
        {
            self.set_status("DeepSeek 需要 API Key；可以粘贴到这里，或先设置 DEEPSEEK_API_KEY 环境变量。密钥不会写入配置文件。", true);
            return;
        }
        let bilibili_room_id = if self.bilibili_enabled
        {
            match self.bilibili_room_id.trim().parse::<u64>()
            {
                Ok(room_id) if room_id > 0 => room_id,
                _ =>
                {
                    self.set_status("启用 Bilibili 时必须填写大于 0 的房间号。", true);
                    return;
                }
            }
        }
        else
        {
            0
        };

        let Some(parent) = self.config_path.parent() else
        {
            self.set_status("配置路径没有有效目录。", true);
            return;
        };
        let token_path = parent.join("control.token");
        let token = format!("{}{}", Uuid::new_v4().simple(), Uuid::new_v4().simple());
        let config = self.config_text(bilibili_room_id);
        let result = std::fs::create_dir_all(parent)
            .and_then(|_| std::fs::write(&self.config_path, config))
            .and_then(|_| std::fs::write(&token_path, format!("{token}\n")));
        match result
        {
            Ok(()) =>
            {
                let api_key = if self.api_key.trim().is_empty()
                {
                    None
                }
                else
                {
                    Some(self.api_key.trim().to_owned())
                };
                if let Ok(mut target) = self.result.lock()
                {
                    *target = Some(SetupResult {
                        config_path: self.config_path.clone(),
                        api_key,
                        start_service: self.start_service,
                    });
                }
                context.send_viewport_cmd(egui::ViewportCommand::Close);
            }
            Err(error) => self.set_status(format!("保存失败：{error}"), true),
        }
    }

    fn config_text(&self, bilibili_room_id: u64) -> String
    {
        let token_path = self
            .config_path
            .parent()
            .map(|path| path.join("control.token"))
            .unwrap_or_else(|| PathBuf::from("control.token"));
        let token_path = token_path.to_string_lossy().replace('\\', "/");
        let common = format!(
            "# AIex generated configuration\n[model]\nbackend = \"{}\"\n\n[persona]\nprofile_id = \"default\"\nrevision = 1\nname = \"{}\"\nsystem_prompt = \"\"\ntone = \"warm, concise, and curious\"\ntaboos = []\nlive_mode = \"controlled\"\n\n[control]\nenabled = true\nbind = \"127.0.0.1:7878\"\ntoken_path = \"{token_path}\"\nmax_message_bytes = 65536\n\n[vts]\nenabled = false\n\n[memory]\nenabled = false\n\n[bilibili]\nenabled = {}\nroom_id = {}\nendpoint = \"wss://broadcastlv.chat.bilibili.com:443/sub\"\ncookie_env = \"{}\"\nreconnect_delay_ms = 2000\nauto_react = false\nresponse_mode = \"suggest\"\nreaction_cooldown_ms = 5000\n",
            self.provider.backend(),
            self.persona_name.replace('"', "'"),
            self.bilibili_enabled,
            bilibili_room_id,
            self.bilibili_cookie_env.trim().replace(char::from(34), "'"),
        );
        match self.provider
        {
            ProviderChoice::DeepSeek => format!(
                "{common}\n[deepseek]\nbase_url = \"{}\"\nmodel = \"{}\"\napi_key_env = \"DEEPSEEK_API_KEY\"\ntimeout_seconds = 120\nthinking = false\nreasoning_effort = \"high\"\n",
                self.endpoint,
                self.model,
            ),
            ProviderChoice::KoboldCpp => format!(
                "{common}\n[koboldcpp]\nbase_url = \"{}\"\nmodel = \"{}\"\ntimeout_seconds = 120\nmax_context_length = 2048\nmax_length = 256\ntemperature = 0.7\n",
                self.endpoint,
                self.model,
            ),
            ProviderChoice::Ollama => format!(
                "{common}\n[ollama]\nbase_url = \"{}\"\nmodel = \"{}\"\ntimeout_seconds = 120\n",
                self.endpoint,
                self.model,
            ),
        }
    }
}

fn probe_endpoint(provider: ProviderChoice, endpoint: &str) -> Result<String, AppError>
{
    let endpoint = endpoint.trim();
    let (scheme, remainder) = endpoint
        .split_once("://")
        .ok_or_else(|| AppError::configuration("模型地址必须以 http:// 或 https:// 开头"))?;
    if scheme != "http" && scheme != "https"
    {
        return Err(AppError::configuration("模型地址只支持 HTTP 或 HTTPS"));
    }
    let authority = remainder
        .split(['/', '?', '#'])
        .next()
        .filter(|value| !value.trim().is_empty())
        .ok_or_else(|| AppError::configuration("模型地址缺少主机名"))?;
    let (host, port) = endpoint_host_port(scheme, authority)?;
    let address = format!("{host}:{port}");
    let socket = address
        .to_socket_addrs()
        .map_err(|error| AppError::unavailable(format!("无法解析模型地址 {address}: {error}")))?
        .next()
        .ok_or_else(|| AppError::unavailable(format!("模型地址没有可用网络地址：{address}")))?;
    let mut stream = TcpStream::connect_timeout(&socket, Duration::from_secs(5))
        .map_err(|error| AppError::unavailable(format!("无法连接 {address}: {error}")))?;
    stream
        .set_read_timeout(Some(Duration::from_secs(5)))
        .map_err(|error| AppError::unavailable(format!("设置连接超时失败：{error}")))?;
    if scheme == "https"
    {
        return Ok(format!("{}：网络端口可达；HTTPS/API 密钥将在服务启动时继续验证。", provider.label()));
    }
    let request = format!("GET / HTTP/1.1\r\nHost: {authority}\r\nConnection: close\r\n\r\n");
    stream
        .write_all(request.as_bytes())
        .map_err(|error| AppError::unavailable(format!("发送连通性请求失败：{error}")))?;
    let mut buffer = [0_u8; 256];
    let count = stream
        .read(&mut buffer)
        .map_err(|error| AppError::unavailable(format!("读取模型服务响应失败：{error}")))?;
    let response = String::from_utf8_lossy(&buffer[..count]);
    let status = response
        .lines()
        .next()
        .and_then(|line| line.split_whitespace().nth(1))
        .and_then(|value| value.parse::<u16>().ok())
        .ok_or_else(|| AppError::protocol("模型服务返回的 HTTP 响应无法识别"))?;
    if status >= 500
    {
        return Err(AppError::unavailable(format!("模型服务返回 HTTP {status}")));
    }
    Ok(format!("{}：服务已响应 HTTP {status}。", provider.label()))
}

fn endpoint_host_port(scheme: &str, authority: &str) -> Result<(String, u16), AppError>
{
    if authority.starts_with('[')
    {
        let end = authority
            .find(']')
            .ok_or_else(|| AppError::configuration("IPv6 模型地址缺少右方括号"))?;
        let host = authority[1..end].to_owned();
        let port = authority
            .get(end + 1..)
            .and_then(|value| value.strip_prefix(':'))
            .map(parse_port)
            .transpose()?
            .unwrap_or_else(|| default_port(scheme));
        return Ok((format!("[{host}]"), port));
    }
    if let Some((host, port)) = authority.rsplit_once(':')
    {
        if !host.is_empty()
        {
            return Ok((host.to_owned(), parse_port(port)?));
        }
    }
    Ok((authority.to_owned(), default_port(scheme)))
}

fn parse_port(value: &str) -> Result<u16, AppError>
{
    let port = value
        .parse::<u16>()
        .map_err(|_| AppError::configuration("模型地址端口必须是 1 到 65535"))?;
    if port == 0
    {
        return Err(AppError::configuration("模型地址端口不能为 0"));
    }
    Ok(port)
}

fn default_port(scheme: &str) -> u16
{
    if scheme == "https" { 443 } else { 80 }
}
impl eframe::App for SetupApp
{
    fn ui(&mut self, ui: &mut egui::Ui, _frame: &mut eframe::Frame)
    {
        self.poll_probe();
        egui::CentralPanel::default().show(ui, |ui|
        {
            ui.heading("AIex 首次设置");
            ui.label("不需要命令行知识，按下面几步即可开始。密钥只在本次进程中使用，不会写入配置文件。");
            ui.horizontal_wrapped(|ui|
            {
                ui.strong("1 选择模型");
                ui.label("→");
                ui.strong("2 检查连接");
                ui.label("→");
                ui.strong("3 保存并开始对话");
            });
            ui.add_space(12.0);
            ui.horizontal(|ui|
            {
                ui.label("模型来源");
                let before = self.provider;
                egui::ComboBox::from_id_salt("provider")
                    .selected_text(self.provider.label())
                    .show_ui(ui, |ui|
                    {
                        ui.selectable_value(&mut self.provider, ProviderChoice::DeepSeek, ProviderChoice::DeepSeek.label());
                        ui.selectable_value(&mut self.provider, ProviderChoice::KoboldCpp, ProviderChoice::KoboldCpp.label());
                        ui.selectable_value(&mut self.provider, ProviderChoice::Ollama, ProviderChoice::Ollama.label());
                    });
                if before != self.provider
                {
                    self.provider_changed();
                }
            });
            ui.group(|ui|
            {
                ui.strong(format!("当前 Provider：{}", self.provider.label()));
                ui.label(self.provider.description());
                ui.small(self.provider.model_hint());
            });
            let check_clicked = ui.horizontal(|ui|
            {
                ui.label("模型地址");
                ui.text_edit_singleline(&mut self.endpoint);
                ui.add_enabled(!self.checking, egui::Button::new("检查连接")).clicked()
            }).inner;
            if check_clicked
            {
                self.check_connection();
            }
            if self.checking
            {
                ui.weak("正在检查；不会保存 API Key。");
            }
            ui.horizontal(|ui|
            {
                ui.label("模型名称");
                ui.text_edit_singleline(&mut self.model);
            });
            ui.horizontal(|ui|
            {
                ui.label("角色名称");
                ui.text_edit_singleline(&mut self.persona_name);
            });
            if self.provider == ProviderChoice::DeepSeek
            {
                ui.horizontal(|ui|
                {
                    ui.label("DeepSeek API Key");
                    ui.add(egui::TextEdit::singleline(&mut self.api_key).password(true));
                });
            }
            ui.checkbox(&mut self.bilibili_enabled, "接收 Bilibili 直播事件（可稍后开启）");
            if self.bilibili_enabled
            {
                ui.horizontal(|ui|
                {
                    ui.label("直播间号");
                    ui.text_edit_singleline(&mut self.bilibili_room_id);
                });
                ui.horizontal(|ui|
                {
                    ui.label("Cookie 环境变量名");
                    ui.text_edit_singleline(&mut self.bilibili_cookie_env);
                });
                ui.label("只填写环境变量名，不要把 Cookie 粘贴到配置或聊天窗口。");
            }
            ui.checkbox(&mut self.start_service, "保存后自动启动服务（推荐）");
            ui.add_space(8.0);
            ui.label(format!("配置文件：{}", self.config_path.display()));
            ui.label("首次启动会自动生成本地控制令牌；开发者可以在 config/control.token 和日志文件中检查状态。");
            if !self.status.is_empty()
            {
                let color = if self.status_error { egui::Color32::LIGHT_RED } else { egui::Color32::LIGHT_GREEN };
                ui.colored_label(color, &self.status);
            }
            ui.add_space(12.0);
            if ui.button("保存并进入 AIex").clicked()
            {
                self.save(ui.ctx());
            }
        });
    }
}
#[cfg(test)]
mod tests
{
    use std::net::TcpListener;

    use super::*;

    #[test]
    fn endpoint_parser_uses_provider_defaults()
    {
        assert_eq!(endpoint_host_port("http", "127.0.0.1").expect("default HTTP port"), ("127.0.0.1".to_owned(), 80));
        assert_eq!(endpoint_host_port("https", "api.deepseek.com").expect("default HTTPS port"), ("api.deepseek.com".to_owned(), 443));
        assert_eq!(endpoint_host_port("http", "127.0.0.1:5001").expect("explicit port"), ("127.0.0.1".to_owned(), 5001));
    }

    #[test]
    fn provider_help_explains_local_and_cloud_requirements()
    {
        assert!(ProviderChoice::DeepSeek.description().contains("DEEPSEEK_API_KEY"));
        assert!(ProviderChoice::KoboldCpp.description().contains("5001"));
        assert!(ProviderChoice::Ollama.description().contains("Ollama"));
        assert!(ProviderChoice::Ollama.model_hint().contains("已安装"));
    }
    #[test]
    fn probe_endpoint_reports_local_http_response()
    {
        let listener = TcpListener::bind("127.0.0.1:0").expect("listener binds");
        let address = listener.local_addr().expect("listener address");
        let server = thread::spawn(move ||
        {
            let (mut stream, _) = listener.accept().expect("request accepts");
            let mut request = [0_u8; 128];
            let _ignored = stream.read(&mut request);
            stream
                .write_all(b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n")
                .expect("response writes");
        });
        let message = probe_endpoint(
            ProviderChoice::KoboldCpp,
            &format!("http://{}", address),
        )
        .expect("local service responds");
        assert!(message.contains("HTTP 200"));
        server.join().expect("server joins");
    }

    #[test]
    fn probe_endpoint_rejects_missing_scheme()
    {
        assert!(probe_endpoint(ProviderChoice::Ollama, "127.0.0.1:11434").is_err());
    }
}
