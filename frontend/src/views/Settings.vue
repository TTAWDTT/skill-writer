<template>
  <div class="max-w-4xl mx-auto">
    <!-- Header -->
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-dark-300 mb-2">Settings</h1>
      <p class="text-dark-50">Configure your LLM provider and API settings</p>
    </div>

    <!-- Current Status -->
    <div class="bg-warm-50 rounded-2xl border border-warm-300 p-6 mb-6">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-4">
          <div
            class="w-12 h-12 rounded-xl flex items-center justify-center"
            :class="currentConfig.has_api_key || currentConfig.has_github_token ? 'bg-green-100' : 'bg-red-100'"
          >
            <svg
              v-if="currentConfig.has_api_key || currentConfig.has_github_token"
              class="w-6 h-6 text-green-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
            </svg>
            <svg v-else class="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <div>
            <h3 class="font-semibold text-dark-300">{{ currentConfig.provider_name || 'Not Configured' }}</h3>
            <p class="text-sm text-dark-50">
              <span v-if="currentConfig.has_api_key || currentConfig.has_github_token">
                Model: {{ currentConfig.model }}
              </span>
              <span v-else class="text-red-500">API key not configured</span>
            </p>
          </div>
        </div>
        <div v-if="currentConfig.github_user" class="flex items-center gap-2 text-sm text-dark-50">
          <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
          </svg>
          {{ currentConfig.github_user }}
        </div>
      </div>
    </div>

    <!-- Provider Selection -->
    <div class="bg-warm-50 rounded-2xl border border-warm-300 p-6 mb-6">
      <h2 class="text-lg font-semibold text-dark-300 mb-4">Select Provider</h2>

      <div class="grid grid-cols-2 md:grid-cols-3 gap-3">
        <button
          v-for="preset in presets"
          :key="preset.id"
          @click="selectPreset(preset)"
          class="p-4 rounded-xl border-2 transition-all text-left"
          :class="[
            selectedPreset?.id === preset.id
              ? 'border-anthropic-orange bg-anthropic-orange-light/10'
              : 'border-warm-300 hover:border-warm-400 bg-white'
          ]"
        >
          <div class="flex items-center gap-3 mb-2">
            <div class="w-8 h-8 rounded-lg bg-warm-200 flex items-center justify-center">
              <span class="text-sm font-bold text-dark-100">{{ preset.name.charAt(0) }}</span>
            </div>
            <span class="font-medium text-dark-300">{{ preset.name }}</span>
          </div>
          <p class="text-xs text-dark-50 truncate">{{ preset.base_url }}</p>
          <div v-if="preset.requires_oauth" class="mt-2">
            <span class="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">OAuth</span>
          </div>
          <div v-if="preset.no_api_key" class="mt-2">
            <span class="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">No API Key</span>
          </div>
        </button>
      </div>
    </div>

    <!-- Configuration Form -->
    <div v-if="selectedPreset" class="bg-warm-50 rounded-2xl border border-warm-300 p-6 mb-6">
      <h2 class="text-lg font-semibold text-dark-300 mb-4">Configure {{ selectedPreset.name }}</h2>

      <!-- GitHub OAuth -->
      <div v-if="selectedPreset.requires_oauth" class="mb-6">
        <div v-if="currentConfig.github_user" class="flex items-center justify-between p-4 bg-green-50 rounded-xl border border-green-200">
          <div class="flex items-center gap-3">
            <svg class="w-6 h-6 text-green-600" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
            </svg>
            <div>
              <p class="font-medium text-green-800">Connected as {{ currentConfig.github_user }}</p>
              <p class="text-sm text-green-600">GitHub Copilot ready to use</p>
            </div>
          </div>
          <button
            @click="logoutGitHub"
            class="px-4 py-2 text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors"
          >
            Disconnect
          </button>
        </div>

        <!-- Device Flow UI -->
        <div v-else class="text-center py-6">
          <!-- Not started -->
          <div v-if="!deviceFlow.started">
            <svg class="w-16 h-16 mx-auto mb-4 text-dark-50" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
            </svg>
            <p class="text-dark-100 mb-4">Login with GitHub to use Copilot models</p>
            <button
              @click="startDeviceFlow"
              :disabled="githubLoading"
              class="px-6 py-3 bg-dark-300 text-white rounded-xl font-medium hover:bg-dark-200 transition-colors flex items-center gap-2 mx-auto"
            >
              <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
              </svg>
              {{ githubLoading ? 'Loading...' : 'Login with GitHub' }}
            </button>
            <p class="text-xs text-dark-50 mt-4">
              Requires GitHub Copilot subscription
            </p>
          </div>

          <!-- Device code display -->
          <div v-else-if="deviceFlow.userCode" class="space-y-4">
            <div class="bg-warm-100 rounded-xl p-6 border border-warm-300">
              <p class="text-sm text-dark-50 mb-2">Enter this code on GitHub:</p>
              <div class="text-3xl font-mono font-bold text-dark-300 tracking-widest mb-4">
                {{ deviceFlow.userCode }}
              </div>
              <a
                :href="deviceFlow.verificationUri"
                target="_blank"
                class="inline-flex items-center gap-2 px-4 py-2 bg-dark-300 text-white rounded-lg hover:bg-dark-200 transition-colors"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
                Open GitHub
              </a>
            </div>

            <div class="flex items-center justify-center gap-2 text-dark-50">
              <svg class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <span>{{ deviceFlow.statusMessage || 'Waiting for authorization...' }}</span>
            </div>

            <button
              @click="cancelDeviceFlow"
              class="text-sm text-dark-50 hover:text-red-500 transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>

      <!-- API Key Input -->
      <div v-if="!selectedPreset.requires_oauth && !selectedPreset.no_api_key" class="mb-4">
        <label class="block text-sm font-medium text-dark-100 mb-2">API Key</label>
        <input
          v-model="formData.api_key"
          type="password"
          placeholder="Enter your API key"
          class="w-full px-4 py-3 bg-white border border-warm-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-anthropic-orange focus:border-transparent"
        />
      </div>

      <!-- Base URL (Advanced) -->
      <div class="mb-4">
        <label class="block text-sm font-medium text-dark-100 mb-2">
          Base URL
          <span class="text-dark-50 font-normal">(Advanced)</span>
        </label>
        <input
          v-model="formData.base_url"
          type="text"
          :placeholder="selectedPreset.base_url"
          class="w-full px-4 py-3 bg-white border border-warm-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-anthropic-orange focus:border-transparent"
        />
      </div>

      <!-- Model Selection -->
      <div class="mb-4">
        <label class="block text-sm font-medium text-dark-100 mb-2">Model</label>
        <select
          v-model="formData.model"
          class="w-full px-4 py-3 bg-white border border-warm-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-anthropic-orange focus:border-transparent"
        >
          <option v-for="model in selectedPreset.models" :key="model" :value="model">
            {{ model }}
          </option>
        </select>
      </div>

      <!-- Temperature -->
      <div class="mb-6">
        <label class="block text-sm font-medium text-dark-100 mb-2">
          Temperature: {{ formData.temperature }}
        </label>
        <input
          v-model.number="formData.temperature"
          type="range"
          min="0"
          max="1"
          step="0.1"
          class="w-full accent-anthropic-orange"
        />
        <div class="flex justify-between text-xs text-dark-50 mt-1">
          <span>Precise (0)</span>
          <span>Creative (1)</span>
        </div>
      </div>

      <!-- Action Buttons -->
      <div class="flex gap-3">
        <button
          @click="testConnection"
          :disabled="testing"
          class="flex-1 px-4 py-3 bg-warm-200 text-dark-100 rounded-xl font-medium hover:bg-warm-300 transition-colors flex items-center justify-center gap-2"
        >
          <svg v-if="testing" class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          {{ testing ? 'Testing...' : 'Test Connection' }}
        </button>
        <button
          @click="saveConfig"
          :disabled="saving"
          class="flex-1 px-4 py-3 bg-anthropic-orange text-white rounded-xl font-medium hover:bg-anthropic-orange-dark transition-colors flex items-center justify-center gap-2"
        >
          <svg v-if="saving" class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          {{ saving ? 'Saving...' : 'Save Configuration' }}
        </button>
      </div>

      <!-- Test Result -->
      <div
        v-if="testResult"
        class="mt-4 p-4 rounded-xl"
        :class="testResult.success ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'"
      >
        <div class="flex items-start gap-3">
          <svg
            v-if="testResult.success"
            class="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
          </svg>
          <svg
            v-else
            class="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
          <div>
            <p :class="testResult.success ? 'text-green-800' : 'text-red-800'" class="font-medium">
              {{ testResult.message }}
            </p>
            <p v-if="testResult.response" class="text-sm text-green-600 mt-1">
              Response: {{ testResult.response }}
            </p>
          </div>
        </div>
      </div>
    </div>

    <!-- Help Section -->
    <div class="bg-warm-100 rounded-2xl p-6">
      <h3 class="font-semibold text-dark-300 mb-3">Need Help?</h3>
      <ul class="space-y-2 text-sm text-dark-50">
        <li class="flex items-start gap-2">
          <span class="text-anthropic-orange">•</span>
          <span><strong>DeepSeek:</strong> Get API key from <a href="https://platform.deepseek.com/" target="_blank" class="text-anthropic-orange hover:underline">platform.deepseek.com</a></span>
        </li>
        <li class="flex items-start gap-2">
          <span class="text-anthropic-orange">•</span>
          <span><strong>OpenAI:</strong> Get API key from <a href="https://platform.openai.com/api-keys" target="_blank" class="text-anthropic-orange hover:underline">platform.openai.com</a></span>
        </li>
        <li class="flex items-start gap-2">
          <span class="text-anthropic-orange">•</span>
          <span><strong>Google AI Studio:</strong> Get API key from <a href="https://aistudio.google.com/apikey" target="_blank" class="text-anthropic-orange hover:underline">aistudio.google.com</a></span>
        </li>
        <li class="flex items-start gap-2">
          <span class="text-anthropic-orange">•</span>
          <span><strong>GitHub Copilot:</strong> Requires active GitHub Copilot subscription</span>
        </li>
        <li class="flex items-start gap-2">
          <span class="text-anthropic-orange">•</span>
          <span><strong>Ollama:</strong> Run locally with <code class="bg-warm-200 px-1 rounded">ollama serve</code></span>
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { api } from '../api'

// State
const presets = ref([])
const currentConfig = ref({})
const selectedPreset = ref(null)
const formData = reactive({
  api_key: '',
  base_url: '',
  model: '',
  temperature: 0.3,
})

const loading = ref(true)
const saving = ref(false)
const testing = ref(false)
const testResult = ref(null)
const githubLoading = ref(false)

// Device Flow state
const deviceFlow = reactive({
  started: false,
  deviceCode: null,
  userCode: null,
  verificationUri: null,
  expiresIn: 0,
  interval: 5,
  statusMessage: '',
  pollTimer: null,
})

// Fetch initial data
const fetchConfig = async () => {
  try {
    const [configRes, presetsRes] = await Promise.all([
      api.get('/config/llm'),
      api.get('/config/llm/presets'),
    ])
    currentConfig.value = configRes.data
    presets.value = presetsRes.data.presets

    // Auto-select current provider
    const currentPreset = presets.value.find(p => p.name === currentConfig.value.provider_name)
    if (currentPreset) {
      selectPreset(currentPreset)
    }
  } catch (e) {
    console.error('Failed to fetch config:', e)
  } finally {
    loading.value = false
  }
}

const selectPreset = (preset) => {
  selectedPreset.value = preset
  formData.base_url = preset.base_url
  formData.model = preset.default_model
  formData.api_key = ''
  testResult.value = null
}

const testConnection = async () => {
  testing.value = true
  testResult.value = null

  try {
    const response = await api.post('/config/llm/test', {
      provider: selectedPreset.value.id,
      api_key: formData.api_key || undefined,
      base_url: formData.base_url || undefined,
      model: formData.model || undefined,
      github_token: currentConfig.value.has_github_token ? 'use_saved' : undefined,
    })
    testResult.value = response.data
  } catch (e) {
    testResult.value = {
      success: false,
      message: e.response?.data?.detail || e.message,
    }
  } finally {
    testing.value = false
  }
}

const saveConfig = async () => {
  saving.value = true

  try {
    await api.post('/config/llm', {
      provider: selectedPreset.value.id,
      api_key: formData.api_key || undefined,
      base_url: formData.base_url || undefined,
      model: formData.model || undefined,
      temperature: formData.temperature,
    })

    // Refresh current config
    const configRes = await api.get('/config/llm')
    currentConfig.value = configRes.data

    testResult.value = {
      success: true,
      message: 'Configuration saved successfully!',
    }
  } catch (e) {
    testResult.value = {
      success: false,
      message: e.response?.data?.detail || 'Failed to save configuration',
    }
  } finally {
    saving.value = false
  }
}

// Device Flow methods
const startDeviceFlow = async () => {
  githubLoading.value = true
  deviceFlow.started = false
  deviceFlow.statusMessage = ''

  try {
    const response = await api.post('/config/github/device-code')
    const data = response.data

    deviceFlow.started = true
    deviceFlow.deviceCode = data.device_code
    deviceFlow.userCode = data.user_code
    deviceFlow.verificationUri = data.verification_uri
    deviceFlow.expiresIn = data.expires_in
    deviceFlow.interval = data.interval || 5

    // Start polling for authorization
    startPolling()
  } catch (e) {
    testResult.value = {
      success: false,
      message: e.response?.data?.detail || 'Failed to start GitHub login',
    }
  } finally {
    githubLoading.value = false
  }
}

const startPolling = () => {
  // Clear any existing timer
  if (deviceFlow.pollTimer) {
    clearInterval(deviceFlow.pollTimer)
  }

  deviceFlow.statusMessage = 'Waiting for authorization...'

  deviceFlow.pollTimer = setInterval(async () => {
    try {
      const response = await api.post(`/config/github/device-poll?device_code=${deviceFlow.deviceCode}`)
      const data = response.data

      switch (data.status) {
        case 'success':
          // Authorization successful
          clearInterval(deviceFlow.pollTimer)
          deviceFlow.pollTimer = null
          deviceFlow.started = false
          deviceFlow.userCode = null

          // Refresh config
          const configRes = await api.get('/config/llm')
          currentConfig.value = configRes.data

          testResult.value = {
            success: true,
            message: `GitHub connected as ${data.user}!`,
          }
          break

        case 'pending':
          deviceFlow.statusMessage = 'Waiting for authorization...'
          break

        case 'slow_down':
          // Increase interval
          deviceFlow.interval = Math.min(deviceFlow.interval + 5, 30)
          deviceFlow.statusMessage = 'Slowing down polling...'
          break

        case 'expired':
          clearInterval(deviceFlow.pollTimer)
          deviceFlow.pollTimer = null
          deviceFlow.started = false
          testResult.value = {
            success: false,
            message: 'Device code expired. Please try again.',
          }
          break

        case 'denied':
          clearInterval(deviceFlow.pollTimer)
          deviceFlow.pollTimer = null
          deviceFlow.started = false
          testResult.value = {
            success: false,
            message: 'Authorization was denied.',
          }
          break

        default:
          deviceFlow.statusMessage = data.message || 'Checking...'
      }
    } catch (e) {
      console.error('Polling error:', e)
      deviceFlow.statusMessage = 'Error checking status...'
    }
  }, deviceFlow.interval * 1000)
}

const cancelDeviceFlow = () => {
  if (deviceFlow.pollTimer) {
    clearInterval(deviceFlow.pollTimer)
    deviceFlow.pollTimer = null
  }
  deviceFlow.started = false
  deviceFlow.userCode = null
  deviceFlow.deviceCode = null
  deviceFlow.statusMessage = ''
}

const logoutGitHub = async () => {
  try {
    await api.post('/config/github/logout')
    currentConfig.value.github_user = null
    currentConfig.value.has_github_token = false
  } catch (e) {
    console.error('Failed to logout:', e)
  }
}

onMounted(() => {
  fetchConfig()
})

onUnmounted(() => {
  // Clean up polling timer
  if (deviceFlow.pollTimer) {
    clearInterval(deviceFlow.pollTimer)
    deviceFlow.pollTimer = null
  }
})
</script>
