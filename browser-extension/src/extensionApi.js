export function isExtensionRuntime() {
  return typeof chrome !== 'undefined' && Boolean(chrome.runtime?.id);
}

export async function insertPromptToActiveTab(prompt) {
  if (!isExtensionRuntime()) {
    await navigator.clipboard.writeText(prompt);
    return { ok: true, copied: true };
  }

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) {
    return { ok: false, reason: '未找到当前活动标签页。' };
  }

  try {
    const response = await chrome.tabs.sendMessage(tab.id, {
      type: 'PAM_INSERT_CONTEXT',
      payload: prompt
    });
    return response?.ok ? { ok: true } : { ok: false, reason: response?.reason || '插入失败。' };
  } catch (error) {
    await navigator.clipboard.writeText(prompt);
    return {
      ok: true,
      copied: true,
      reason: '当前页面没有可用内容脚本，已复制到剪贴板。'
    };
  }
}

export async function getActivePageSnapshot() {
  if (!isExtensionRuntime()) {
    return {
      ok: true,
      title: document.title || '当前网页',
      url: location.href,
      content: document.body?.innerText?.slice(0, 12000) || ''
    };
  }

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) {
    return { ok: false, reason: '未找到当前活动标签页。' };
  }

  try {
    return await chrome.tabs.sendMessage(tab.id, { type: 'PAM_GET_PAGE' });
  } catch (error) {
    return {
      ok: false,
      reason: '当前页面暂不支持读取，请确认页面已在插件授权范围内。'
    };
  }
}

export async function getBackendBaseUrl() {
  if (!isExtensionRuntime()) {
    return localStorage.getItem('pam_backend_base_url') || 'http://127.0.0.1:8088';
  }
  const result = await chrome.storage.local.get(['pam_backend_base_url']);
  return result.pam_backend_base_url || 'http://127.0.0.1:8088';
}

export async function setBackendBaseUrl(url) {
  if (!isExtensionRuntime()) {
    localStorage.setItem('pam_backend_base_url', url);
    return;
  }
  await chrome.storage.local.set({ pam_backend_base_url: url });
}

export async function callKnowledgeHub(path, options = {}) {
  const baseUrl = await getBackendBaseUrl();
  const response = await fetch(`${baseUrl.replace(/\/$/, '')}/api${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {})
    },
    ...options
  });
  if (!response.ok) {
    throw new Error(`Knowledge Hub ${path} failed: ${response.status}`);
  }
  return response.json();
}
