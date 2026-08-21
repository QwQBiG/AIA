use std::path::PathBuf;
use std::sync::{Arc, Mutex};

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
    start_service: bool,
    status: String,
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
            start_service: true,
            status: String::new(),
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

    fn save(&mut self, context: &egui::Context)
    {
        if self.persona_name.trim().is_empty()
            || self.endpoint.trim().is_empty()
            || self.model.trim().is_empty()
        {
            self.status = "请填写角色名、模型地址和模型名称。".to_owned();
            return;
        }
        if self.provider == ProviderChoice::DeepSeek
            && self.api_key.trim().is_empty()
            && std::env::var_os("DEEPSEEK_API_KEY").is_none()
        {
            self.status = "DeepSeek 需要 API Key；可以粘贴到这里，或先设置 DEEPSEEK_API_KEY 环境变量。密钥不会写入配置文件。".to_owned();
            return;
        }
        let Some(parent) = self.config_path.parent() else
        {
            self.status = "配置路径没有有效目录。".to_owned();
            return;
        };
        let token_path = parent.join("control.token");
        let token = format!("{}{}", Uuid::new_v4().simple(), Uuid::new_v4().simple());
        let config = self.config_text();
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
            Err(error) => self.status = format!("保存失败：{error}"),
        }
    }

    fn config_text(&self) -> String
    {
        let token_path = self
            .config_path
            .parent()
            .map(|path| path.join("control.token"))
            .unwrap_or_else(|| PathBuf::from("control.token"));
        let token_path = token_path.to_string_lossy().replace('\\', "/");
        let common = format!(
            "# AIex generated configuration\n[model]\nbackend = \"{}\"\n\n[persona]\nname = \"{}\"\nsystem_prompt = \"\"\ntone = \"warm, concise, and curious\"\ntaboos = []\nlive_mode = \"controlled\"\n\n[control]\nenabled = true\nbind = \"127.0.0.1:7878\"\ntoken_path = \"{token_path}\"\nmax_message_bytes = 65536\n\n[vts]\nenabled = false\n\n[memory]\nenabled = false\n",
            self.provider.backend(),
            self.persona_name.replace('"', "'"),
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

impl eframe::App for SetupApp
{
    fn ui(&mut self, ui: &mut egui::Ui, _frame: &mut eframe::Frame)
    {
        egui::CentralPanel::default().show(ui, |ui|
        {
            ui.heading("AIex 首次设置");
            ui.label("不需要命令行知识，按下面几步即可开始。密钥只在本次进程中使用，不会写入配置文件。");
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
            ui.horizontal(|ui|
            {
                ui.label("模型地址");
                ui.text_edit_singleline(&mut self.endpoint);
            });
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
            ui.checkbox(&mut self.start_service, "保存后自动启动服务（推荐）");
            ui.add_space(8.0);
            ui.label(format!("配置文件：{}", self.config_path.display()));
            ui.label("首次启动会自动生成本地控制令牌；开发者可以在 config/control.token 和日志文件中检查状态。");
            if !self.status.is_empty()
            {
                ui.colored_label(egui::Color32::LIGHT_RED, &self.status);
            }
            ui.add_space(12.0);
            if ui.button("保存并进入 AIex").clicked()
            {
                self.save(ui.ctx());
            }
        });
    }
}
