<template>
  <main class="app-shell">
    <header class="topbar">
      <div>
        <p class="eyebrow">Local-first Memory</p>
        <h1>个人 AI 记忆层</h1>
      </div>
      <button class="icon-button" type="button" title="新增记忆" @click="startCreate">＋</button>
    </header>

    <section v-if="!initialized" class="setup-panel">
      <h2>先建立第一批可信上下文</h2>
      <p>这些记忆只保存在当前浏览器 IndexedDB 中。第一版不上传、不自动发送，所有注入动作都由你确认。</p>
      <button class="primary-button" type="button" @click="initializeSeeds">导入建议初始记忆</button>
    </section>

    <section class="composer">
      <label for="backend">知识中枢服务</label>
      <input id="backend" v-model="backendBaseUrl" placeholder="http://127.0.0.1:8088" />
      <div class="toolbar">
        <button type="button" @click="saveBackendConfig">保存地址</button>
        <button type="button" @click="checkBackend">测试连接</button>
        <button class="primary-button" type="button" @click="saveCurrentPage">保存当前网页</button>
      </div>
      <p v-if="backendMessage" class="message">{{ backendMessage }}</p>
    </section>

    <section class="composer">
      <label for="task">当前要问 AI 的问题</label>
      <textarea
        id="task"
        v-model="taskText"
        rows="5"
        placeholder="例如：帮我基于个人背景，分析个人 AI 记忆层这个产品的 MVP 版本和商业化路径。"
      />

      <div class="toolbar">
        <select v-model="scopeFilter" title="记忆范围">
          <option>全部</option>
          <option>工作</option>
          <option>学习</option>
          <option>私人</option>
        </select>
        <button type="button" @click="generateRemoteContext">推荐上下文</button>
        <button type="button" @click="copyPrompt">复制</button>
        <button class="primary-button" type="button" @click="insertPrompt">插入当前 AI 页面</button>
      </div>

      <p v-if="message" class="message">{{ message }}</p>
    </section>

    <section class="memory-section">
      <div class="section-head">
        <div>
          <h2>候选记忆</h2>
          <p>{{ selectedCount }} 条已选择，{{ rankedMemories.length }} 条可用</p>
        </div>
        <input v-model="keyword" type="search" placeholder="搜索记忆" />
      </div>

      <div v-if="rankedMemories.length === 0" class="empty-state">
        暂无记忆。先新增一条你的角色、项目或输出偏好。
      </div>

      <article
        v-for="memory in rankedMemories"
        :key="memory.id"
        class="memory-card"
        :class="{ selected: selectedIds.has(memory.id) }"
      >
        <label class="memory-select">
          <input type="checkbox" :checked="selectedIds.has(memory.id)" @change="toggleMemory(memory.id)" />
          <span>
            <strong>{{ memory.title }}</strong>
            <small>{{ memory.scope }} / {{ memory.type }} / {{ memory.confidence }}</small>
          </span>
        </label>
        <p>{{ memory.content }}</p>
        <div class="tags">
          <span v-for="tag in memory.tags" :key="tag">{{ tag }}</span>
        </div>
        <div class="card-actions">
          <button type="button" @click="editMemory(memory)">编辑</button>
          <button type="button" @click="removeMemory(memory.id)">删除</button>
        </div>
      </article>
    </section>

    <section class="preview">
      <div class="section-head">
        <h2>即将注入的上下文</h2>
        <span>{{ promptPreview.length }} 字</span>
      </div>
      <pre>{{ promptPreview }}</pre>
    </section>

    <dialog ref="editorDialog" class="editor-dialog">
      <form method="dialog" @submit.prevent="saveCurrentMemory">
        <h2>{{ editingMemory.id ? '编辑记忆' : '新增记忆' }}</h2>
        <label>
          标题
          <input v-model="editingMemory.title" required maxlength="80" />
        </label>
        <div class="field-grid">
          <label>
            范围
            <select v-model="editingMemory.scope">
              <option>工作</option>
              <option>学习</option>
              <option>私人</option>
            </select>
          </label>
          <label>
            类型
            <select v-model="editingMemory.type">
              <option>工作画像</option>
              <option>当前项目</option>
              <option>输出偏好</option>
              <option>确认事实</option>
              <option>学习资料</option>
            </select>
          </label>
        </div>
        <label>
          内容
          <textarea v-model="editingMemory.content" required rows="7" />
        </label>
        <label>
          标签
          <input v-model="editingMemory.tagsText" placeholder="副业, AI, 产品" />
        </label>
        <menu>
          <button type="button" @click="closeEditor">取消</button>
          <button class="primary-button" type="submit">保存</button>
        </menu>
      </form>
    </dialog>
  </main>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue';
import { composePrompt, rankMemories } from './contextEngine';
import { deleteMemory, getSetting, listMemories, normalizeTags, saveMemory, seedMemories, setSetting } from './storage';
import {
  callKnowledgeHub,
  getActivePageSnapshot,
  getBackendBaseUrl,
  insertPromptToActiveTab,
  setBackendBaseUrl
} from './extensionApi';

const memories = ref([]);
const selectedIds = ref(new Set());
const initialized = ref(true);
const taskText = ref('');
const keyword = ref('');
const scopeFilter = ref('全部');
const message = ref('');
const backendMessage = ref('');
const backendBaseUrl = ref('http://127.0.0.1:8088');
const remotePrompt = ref('');
const editorDialog = ref(null);
const editingMemory = reactive(emptyMemory());

const rankedMemories = computed(() => {
  const query = `${taskText.value} ${keyword.value}`;
  return rankMemories(memories.value, query, { scope: scopeFilter.value });
});

const selectedMemories = computed(() =>
  rankedMemories.value
    .filter((memory) => selectedIds.value.has(memory.id))
    .map((memory) => ({ ...memory, selected: true }))
);

const selectedCount = computed(() => selectedIds.value.size);
const promptPreview = computed(() => remotePrompt.value || composePrompt(selectedMemories.value, taskText.value));

onMounted(async () => {
  backendBaseUrl.value = await getBackendBaseUrl();
  initialized.value = await getSetting('initialized', false);
  await refreshMemories();
  await checkBackend();
});

async function refreshMemories() {
  memories.value = await listMemories();
}

async function initializeSeeds() {
  for (const memory of seedMemories) {
    await saveMemory(memory);
  }
  await setSetting('initialized', true);
  initialized.value = true;
  await refreshMemories();
  selectTopMemories();
  showMessage('已导入建议初始记忆，可继续编辑成你的真实表达。');
}

function selectTopMemories() {
  const topIds = rankedMemories.value.slice(0, 6).map((memory) => memory.id);
  selectedIds.value = new Set(topIds);
}

async function generateRemoteContext() {
  remotePrompt.value = '';
  try {
    const result = await callKnowledgeHub('/extension/context', {
      method: 'POST',
      body: JSON.stringify({
        question: taskText.value || '请结合我的个人知识库，帮助我完成当前问题。',
        top_k: 8
      })
    });
    remotePrompt.value = result.prompt || '';
    showMessage(`已从知识中枢召回 ${result.hits?.length || 0} 条上下文。`);
  } catch (error) {
    selectTopMemories();
    showMessage('知识中枢不可用，已使用插件本地记忆推荐。');
  }
}

function toggleMemory(id) {
  remotePrompt.value = '';
  const next = new Set(selectedIds.value);
  if (next.has(id)) {
    next.delete(id);
  } else {
    next.add(id);
  }
  selectedIds.value = next;
}

async function copyPrompt() {
  await navigator.clipboard.writeText(promptPreview.value);
  showMessage('已复制上下文提示词。');
}

async function insertPrompt() {
  const result = await insertPromptToActiveTab(promptPreview.value);
  if (result.ok) {
    showMessage(result.copied ? result.reason || '已复制到剪贴板。' : '已插入当前 AI 页面输入框，请确认后发送。');
  } else {
    showMessage(result.reason || '插入失败，请复制后手动粘贴。');
  }
}

async function saveBackendConfig() {
  await setBackendBaseUrl(backendBaseUrl.value.trim() || 'http://127.0.0.1:8088');
  await checkBackend();
}

async function checkBackend() {
  try {
    const health = await callKnowledgeHub('/health');
    backendMessage.value = `${health.service || 'Knowledge Hub'} 在线`;
  } catch (error) {
    backendMessage.value = '知识中枢离线，当前使用插件本地记忆';
  }
}

async function saveCurrentPage() {
  try {
    const page = await getActivePageSnapshot();
    if (!page.ok) {
      backendMessage.value = page.reason || '读取当前网页失败';
      return;
    }
    await callKnowledgeHub('/extension/save-page', {
      method: 'POST',
      body: JSON.stringify({
        title: page.title,
        url: page.url,
        content: page.content,
        summary: '',
        tags: ['网页', '插件']
      })
    });
    backendMessage.value = '当前网页已保存到知识中枢';
  } catch (error) {
    backendMessage.value = '保存失败，请确认后端已启动且地址正确';
  }
}

function startCreate() {
  Object.assign(editingMemory, emptyMemory());
  editorDialog.value?.showModal();
}

function editMemory(memory) {
  Object.assign(editingMemory, {
    ...memory,
    tagsText: (memory.tags || []).join(', ')
  });
  editorDialog.value?.showModal();
}

async function saveCurrentMemory() {
  await saveMemory({
    ...editingMemory,
    tags: normalizeTags(editingMemory.tagsText)
  });
  closeEditor();
  await refreshMemories();
  showMessage('记忆已保存。');
}

async function removeMemory(id) {
  await deleteMemory(id);
  const next = new Set(selectedIds.value);
  next.delete(id);
  selectedIds.value = next;
  await refreshMemories();
  showMessage('记忆已删除。');
}

function closeEditor() {
  editorDialog.value?.close();
}

function emptyMemory() {
  return {
    id: '',
    title: '',
    content: '',
    scope: '工作',
    type: '当前项目',
    confidence: '已确认',
    tagsText: ''
  };
}

function showMessage(text) {
  message.value = text;
  window.clearTimeout(showMessage.timer);
  showMessage.timer = window.setTimeout(() => {
    message.value = '';
  }, 2800);
}
</script>
