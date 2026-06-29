const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8088/api';

async function request(path, options = {}) {
  const headers = options.body instanceof FormData
    ? (options.headers || {})
    : {
        'Content-Type': 'application/json',
        ...(options.headers || {})
      };
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (!response.ok) {
    throw new Error(`API ${path} failed: ${response.status}`);
  }

  return response.json();
}

export function fetchHealth() {
  return request('/health');
}

export function fetchDashboard() {
  return request('/dashboard');
}

export function fetchKnowledgeItems(keyword = '') {
  const query = keyword ? `?keyword=${encodeURIComponent(keyword)}` : '';
  return request(`/knowledge-items${query}`);
}

export function createKnowledgeItem(payload) {
  return request('/knowledge-items', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export function updateKnowledgeItem(id, payload) {
  return request(`/knowledge-items/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload)
  });
}

export function deleteKnowledgeItem(id) {
  return request(`/knowledge-items/${id}`, {
    method: 'DELETE'
  });
}

export function importManual(payload) {
  return request('/import/manual', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export function importWebpage(payload) {
  return request('/import/webpage', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export function importFile(file) {
  const formData = new FormData();
  formData.append('file', file);
  return request('/import/file', {
    method: 'POST',
    body: formData
  });
}

export function fetchJobs() {
  return request('/jobs');
}

export function fetchGraph() {
  return request('/graph');
}

export function generateContext(payload) {
  return request('/context/generate', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export function fetchModelConfig() {
  return request('/model-config');
}

export function saveModelConfig(payload) {
  return request('/model-config', {
    method: 'POST',
    body: JSON.stringify({
      base_url: payload.chatBaseUrl || payload.baseUrl || '',
      apiKey: payload.chatApiKey || payload.apiKey || '',
      chatBaseUrl: payload.chatBaseUrl || '',
      chatApiKey: payload.chatApiKey || '',
      chat_model: payload.chatModel,
      embeddingBaseUrl: payload.embeddingBaseUrl || '',
      embeddingApiKey: payload.embeddingApiKey || '',
      embedding_model: payload.embeddingModel,
      timeout_seconds: Number(payload.chatTimeoutSeconds || payload.timeoutSeconds || 45),
      chatTimeoutSeconds: Number(payload.chatTimeoutSeconds || payload.timeoutSeconds || 45),
      embeddingTimeoutSeconds: Number(payload.embeddingTimeoutSeconds || payload.timeoutSeconds || 45),
      enabled: Boolean(payload.enabled),
      parserMode: payload.parserMode || 'local',
      mineruBaseUrl: payload.mineruBaseUrl || '',
      mineruApiKey: payload.mineruApiKey || '',
      retrievalMode: payload.retrievalMode || 'keyword',
      chromaPath: payload.chromaPath || '',
      chromaCollection: payload.chromaCollection || 'personal_knowledge_chunks'
    })
  });
}

export function testChatModel() {
  return request('/model-config/test-chat', { method: 'POST' });
}

export function testEmbeddingModel() {
  return request('/model-config/test-embedding', { method: 'POST' });
}

export function rebuildVectorIndex() {
  return request('/vector/rebuild', { method: 'POST' });
}
