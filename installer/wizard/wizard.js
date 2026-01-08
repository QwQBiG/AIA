// Wizard state management
let state = {
  currentStep: 0,
  totalSteps: 4,
  steps: [],
  data: {}
};

// Step templates
const stepTemplates = {
  welcome: () => `
    <div class="step-container">
      <div class="welcome-icon">🎭</div>
      <h2 class="step-title">欢迎使用 AI VTuber Digital Human</h2>
      <p class="step-description">让我们一起完成初始配置，只需几分钟即可开始使用。</p>
      <ul class="feature-list">
        <li>支持多种大语言模型（Ollama、OpenAI、Anthropic）</li>
        <li>多平台直播支持（Twitch、YouTube、Bilibili）</li>
        <li>智能对话和记忆系统</li>
        <li>可定制的虚拟形象和语音</li>
      </ul>
    </div>
  `,

  llm: () => `
    <div class="step-container">
      <h2 class="step-title">LLM 配置</h2>
      <p class="step-description">选择您想使用的大语言模型提供者</p>
      
      <div class="provider-cards">
        <div class="provider-card ${state.data.llm?.provider === 'ollama' ? 'selected' : ''}" 
             onclick="selectLLMProvider('ollama')">
          <h3>Ollama</h3>
          <p>本地运行，免费使用，隐私保护</p>
          <span class="badge local">本地</span>
        </div>
        <div class="provider-card ${state.data.llm?.provider === 'koboldcpp' ? 'selected' : ''}" 
             onclick="selectLLMProvider('koboldcpp')">
          <h3>KoboldCPP</h3>
          <p>本地运行，支持多种模型格式</p>
          <span class="badge local">本地</span>
        </div>
        <div class="provider-card ${state.data.llm?.provider === 'openai' ? 'selected' : ''}" 
             onclick="selectLLMProvider('openai')">
          <h3>OpenAI</h3>
          <p>GPT-4 等强大模型，需要 API Key</p>
          <span class="badge cloud">云端</span>
        </div>
        <div class="provider-card ${state.data.llm?.provider === 'anthropic' ? 'selected' : ''}" 
             onclick="selectLLMProvider('anthropic')">
          <h3>Anthropic</h3>
          <p>Claude 系列模型，需要 API Key</p>
          <span class="badge cloud">云端</span>
        </div>
      </div>

      <div id="llm-config" class="config-section" style="display: ${state.data.llm?.provider ? 'block' : 'none'}">
        ${getLLMConfigFields()}
      </div>
    </div>
  `,

  tts: () => `
    <div class="step-container">
      <h2 class="step-title">TTS 配置</h2>
      <p class="step-description">选择语音合成服务</p>
      
      <div class="provider-cards">
        <div class="provider-card ${state.data.tts?.provider === 'vits' ? 'selected' : ''}" 
             onclick="selectTTSProvider('vits')">
          <h3>VITS</h3>
          <p>本地运行，免费使用</p>
          <span class="badge local">本地</span>
        </div>
        <div class="provider-card ${state.data.tts?.provider === 'gpt-sovits' ? 'selected' : ''}" 
             onclick="selectTTSProvider('gpt-sovits')">
          <h3>GPT-SoVITS</h3>
          <p>高质量语音克隆</p>
          <span class="badge local">本地</span>
        </div>
        <div class="provider-card ${state.data.tts?.provider === 'elevenlabs' ? 'selected' : ''}" 
             onclick="selectTTSProvider('elevenlabs')">
          <h3>ElevenLabs</h3>
          <p>高质量云端语音，需要 API Key</p>
          <span class="badge cloud">云端</span>
        </div>
        <div class="provider-card ${state.data.tts?.provider === 'azure' ? 'selected' : ''}" 
             onclick="selectTTSProvider('azure')">
          <h3>Azure TTS</h3>
          <p>微软云端语音服务</p>
          <span class="badge cloud">云端</span>
        </div>
      </div>

      <div id="tts-config" class="config-section" style="display: ${state.data.tts?.provider ? 'block' : 'none'}">
        ${getTTSConfigFields()}
      </div>
    </div>
  `,

  streaming: () => `
    <div class="step-container">
      <h2 class="step-title">直播平台配置</h2>
      <p class="step-description">配置您要连接的直播平台（可选）</p>
      
      <div class="form-group">
        <label>Twitch</label>
        <input type="text" id="twitch-channel" placeholder="频道名称" 
               value="${state.data.streaming?.twitch?.channel || ''}">
      </div>
      
      <div class="form-group">
        <label>YouTube Live Chat ID</label>
        <input type="text" id="youtube-chatid" placeholder="Live Chat ID" 
               value="${state.data.streaming?.youtube?.liveChatId || ''}">
      </div>
      
      <div class="form-group">
        <label>Bilibili 直播间 ID</label>
        <input type="text" id="bilibili-roomid" placeholder="直播间 ID" 
               value="${state.data.streaming?.bilibili?.roomId || ''}">
      </div>
      
      <p style="color: rgba(255,255,255,0.5); font-size: 12px; margin-top: 20px;">
        * 这些配置可以稍后在设置中修改
      </p>
    </div>
  `
};

function getLLMConfigFields() {
  const provider = state.data.llm?.provider;
  if (!provider) return '';

  switch (provider) {
    case 'ollama':
      return `
        <h4>Ollama 配置</h4>
        <div class="form-group">
          <label>端点地址</label>
          <input type="text" id="ollama-endpoint" placeholder="http://localhost:11434" 
                 value="${state.data.llm?.endpoint || 'http://localhost:11434'}">
        </div>
        <div class="form-group">
          <label>模型名称</label>
          <input type="text" id="ollama-model" placeholder="llama2" 
                 value="${state.data.llm?.model || 'llama2'}">
        </div>
      `;
    case 'koboldcpp':
      return `
        <h4>KoboldCPP 配置</h4>
        <div class="form-group">
          <label>端点地址</label>
          <input type="text" id="koboldcpp-endpoint" placeholder="http://localhost:5001" 
                 value="${state.data.llm?.endpoint || 'http://localhost:5001'}">
        </div>
      `;
    case 'openai':
      return `
        <h4>OpenAI 配置</h4>
        <div class="form-group">
          <label>API Key</label>
          <input type="password" id="openai-apikey" placeholder="sk-..." 
                 value="${state.data.llm?.apiKey || ''}">
        </div>
        <div class="form-group">
          <label>模型</label>
          <select id="openai-model">
            <option value="gpt-4" ${state.data.llm?.model === 'gpt-4' ? 'selected' : ''}>GPT-4</option>
            <option value="gpt-4-turbo" ${state.data.llm?.model === 'gpt-4-turbo' ? 'selected' : ''}>GPT-4 Turbo</option>
            <option value="gpt-3.5-turbo" ${state.data.llm?.model === 'gpt-3.5-turbo' ? 'selected' : ''}>GPT-3.5 Turbo</option>
          </select>
        </div>
      `;
    case 'anthropic':
      return `
        <h4>Anthropic 配置</h4>
        <div class="form-group">
          <label>API Key</label>
          <input type="password" id="anthropic-apikey" placeholder="sk-ant-..." 
                 value="${state.data.llm?.apiKey || ''}">
        </div>
        <div class="form-group">
          <label>模型</label>
          <select id="anthropic-model">
            <option value="claude-3-opus-20240229" ${state.data.llm?.model === 'claude-3-opus-20240229' ? 'selected' : ''}>Claude 3 Opus</option>
            <option value="claude-3-sonnet-20240229" ${state.data.llm?.model === 'claude-3-sonnet-20240229' ? 'selected' : ''}>Claude 3 Sonnet</option>
            <option value="claude-3-haiku-20240307" ${state.data.llm?.model === 'claude-3-haiku-20240307' ? 'selected' : ''}>Claude 3 Haiku</option>
          </select>
        </div>
      `;
    default:
      return '';
  }
}

function getTTSConfigFields() {
  const provider = state.data.tts?.provider;
  if (!provider) return '';

  switch (provider) {
    case 'vits':
    case 'gpt-sovits':
      return `
        <h4>${provider === 'vits' ? 'VITS' : 'GPT-SoVITS'} 配置</h4>
        <div class="form-group">
          <label>端点地址</label>
          <input type="text" id="tts-endpoint" placeholder="http://localhost:9880" 
                 value="${state.data.tts?.endpoint || 'http://localhost:9880'}">
        </div>
      `;
    case 'elevenlabs':
      return `
        <h4>ElevenLabs 配置</h4>
        <div class="form-group">
          <label>API Key</label>
          <input type="password" id="elevenlabs-apikey" placeholder="API Key" 
                 value="${state.data.tts?.apiKey || ''}">
        </div>
        <div class="form-group">
          <label>Voice ID</label>
          <input type="text" id="elevenlabs-voiceid" placeholder="Voice ID" 
                 value="${state.data.tts?.voiceId || ''}">
        </div>
      `;
    case 'azure':
      return `
        <h4>Azure TTS 配置</h4>
        <div class="form-group">
          <label>API Key</label>
          <input type="password" id="azure-apikey" placeholder="API Key" 
                 value="${state.data.tts?.apiKey || ''}">
        </div>
        <div class="form-group">
          <label>Region</label>
          <input type="text" id="azure-region" placeholder="eastus" 
                 value="${state.data.tts?.region || 'eastus'}">
        </div>
      `;
    default:
      return '';
  }
}

function selectLLMProvider(provider) {
  state.data.llm = { ...state.data.llm, provider };
  renderStep();
}

function selectTTSProvider(provider) {
  state.data.tts = { ...state.data.tts, provider };
  renderStep();
}

function collectStepData() {
  const stepId = state.steps[state.currentStep]?.id;
  
  switch (stepId) {
    case 'llm':
      const llmProvider = state.data.llm?.provider;
      if (llmProvider === 'ollama') {
        state.data.llm.endpoint = document.getElementById('ollama-endpoint')?.value;
        state.data.llm.model = document.getElementById('ollama-model')?.value;
      } else if (llmProvider === 'koboldcpp') {
        state.data.llm.endpoint = document.getElementById('koboldcpp-endpoint')?.value;
      } else if (llmProvider === 'openai') {
        state.data.llm.apiKey = document.getElementById('openai-apikey')?.value;
        state.data.llm.model = document.getElementById('openai-model')?.value;
      } else if (llmProvider === 'anthropic') {
        state.data.llm.apiKey = document.getElementById('anthropic-apikey')?.value;
        state.data.llm.model = document.getElementById('anthropic-model')?.value;
      }
      break;
      
    case 'tts':
      const ttsProvider = state.data.tts?.provider;
      if (ttsProvider === 'vits' || ttsProvider === 'gpt-sovits') {
        state.data.tts.endpoint = document.getElementById('tts-endpoint')?.value;
      } else if (ttsProvider === 'elevenlabs') {
        state.data.tts.apiKey = document.getElementById('elevenlabs-apikey')?.value;
        state.data.tts.voiceId = document.getElementById('elevenlabs-voiceid')?.value;
      } else if (ttsProvider === 'azure') {
        state.data.tts.apiKey = document.getElementById('azure-apikey')?.value;
        state.data.tts.region = document.getElementById('azure-region')?.value;
      }
      break;
      
    case 'streaming':
      state.data.streaming = {
        twitch: { channel: document.getElementById('twitch-channel')?.value },
        youtube: { liveChatId: document.getElementById('youtube-chatid')?.value },
        bilibili: { roomId: document.getElementById('bilibili-roomid')?.value }
      };
      break;
  }
}

function renderStep() {
  const content = document.getElementById('wizard-content');
  const stepId = state.steps[state.currentStep]?.id;
  
  if (stepTemplates[stepId]) {
    content.innerHTML = stepTemplates[stepId]();
  }
  
  updateProgress();
  updateButtons();
}

function updateProgress() {
  const progress = document.getElementById('progress');
  const percentage = ((state.currentStep + 1) / state.totalSteps) * 100;
  progress.style.width = `${percentage}%`;
  
  const indicator = document.getElementById('steps-indicator');
  indicator.innerHTML = state.steps.map((step, i) => `
    <div class="step-dot ${i === state.currentStep ? 'active' : ''} ${i < state.currentStep ? 'completed' : ''}"></div>
  `).join('');
}

function updateButtons() {
  const btnPrevious = document.getElementById('btn-previous');
  const btnNext = document.getElementById('btn-next');
  
  btnPrevious.disabled = state.currentStep === 0;
  
  if (state.currentStep === state.totalSteps - 1) {
    btnNext.textContent = '完成';
  } else {
    btnNext.textContent = '下一步';
  }
}

async function init() {
  // Get initial state from main process
  if (window.electronAPI) {
    state = await window.electronAPI.wizard?.getState() || state;
  }
  
  // Default steps if not provided
  if (!state.steps || state.steps.length === 0) {
    state.steps = [
      { id: 'welcome', title: '欢迎' },
      { id: 'llm', title: 'LLM 配置' },
      { id: 'tts', title: 'TTS 配置' },
      { id: 'streaming', title: '直播平台' }
    ];
    state.totalSteps = state.steps.length;
  }
  
  renderStep();
  
  // Button handlers
  document.getElementById('btn-previous').addEventListener('click', async () => {
    collectStepData();
    if (state.currentStep > 0) {
      state.currentStep--;
      renderStep();
    }
  });
  
  document.getElementById('btn-next').addEventListener('click', async () => {
    collectStepData();
    
    if (state.currentStep < state.totalSteps - 1) {
      state.currentStep++;
      renderStep();
    } else {
      // Finish wizard
      if (window.electronAPI) {
        await window.electronAPI.config?.save(state.data);
      }
      window.close();
    }
  });
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', init);
