<template>
  <main class="workspace">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">KH</div>
        <div>
          <strong>Knowledge Hub</strong>
          <span>Local Intelligence Workspace</span>
        </div>
      </div>

      <nav class="nav-list">
        <button
          v-for="item in navItems"
          :key="item.key"
          type="button"
          :class="{ active: activeView === item.key }"
          @click="activeView = item.key"
        >
          <span>{{ item.icon }}</span>
          {{ item.label }}
        </button>
      </nav>

      <section class="connection-card">
        <div class="status-line">
          <span :class="['pulse', { offline: !backendOnline }]"></span>
          {{ backendOnline ? '本地服务在线' : '本地服务离线' }}
        </div>
        <strong>127.0.0.1:8088</strong>
        <small>{{ backendOnline ? 'FastAPI / SQLite / Graph Pipeline' : '正在使用前端模拟数据' }}</small>
      </section>
    </aside>

    <section class="main-panel">
      <header class="topbar">
        <div>
          <p>{{ currentNav?.subtitle }}</p>
          <h1>{{ currentNav?.label }}</h1>
        </div>
        <div class="top-actions">
          <button type="button" @click="refreshCurrentView">局部刷新</button>
          <button class="primary-action" type="button" @click="openKnowledgeEditor()">新建知识</button>
        </div>
      </header>

      <section v-if="activeView === 'dashboard'" class="view-stack">
        <div class="metric-grid">
          <article
            v-for="metric in metrics"
            :key="metric.label"
            class="metric-card"
            role="button"
            tabindex="0"
            @click="jumpFromMetric(metric.label)"
            @keydown.enter="jumpFromMetric(metric.label)"
          >
            <span>{{ metric.label }}</span>
            <strong>{{ metric.value }}</strong>
            <small :class="metric.tone">{{ metric.delta }}</small>
          </article>
        </div>

        <div class="split-layout">
          <section class="panel">
            <div class="panel-head">
              <h2>系统运行态势</h2>
              <span class="tag active">AI Ready</span>
            </div>
            <div class="pipeline">
              <div v-for="step in pipeline" :key="step.name" class="pipeline-step">
                <span :class="['step-dot', step.status]"></span>
                <div>
                  <strong>{{ step.name }}</strong>
                  <small>{{ step.desc }}</small>
                </div>
              </div>
            </div>
          </section>

          <section class="panel">
            <div class="panel-head">
              <h2>最近上下文调用</h2>
              <span>Today</span>
            </div>
            <div class="activity-list">
              <article v-for="activity in activities" :key="activity.title">
                <strong>{{ activity.title }}</strong>
                <p>{{ activity.desc }}</p>
                <span>{{ activity.time }}</span>
              </article>
            </div>
          </section>
        </div>
      </section>

      <section v-if="activeView === 'knowledge'" class="knowledge-layout">
        <aside class="filter-panel">
          <h2>筛选</h2>
          <label>
            关键词
            <input v-model="knowledgeKeyword" placeholder="项目、技术、决策" />
          </label>
          <div class="filter-group">
            <span>来源</span>
            <button
              v-for="source in sources"
              :key="source"
              type="button"
              :class="{ active: sourceFilter === source }"
              @click="sourceFilter = source"
            >
              {{ source }}
            </button>
          </div>
          <div class="filter-group">
            <span>标签</span>
            <button
              v-for="tag in tags"
              :key="tag"
              type="button"
              :class="{ active: tagFilter === tag }"
              @click="tagFilter = tag"
            >
              {{ tag }}
            </button>
          </div>
        </aside>

        <div class="knowledge-list">
          <article
            v-for="item in filteredKnowledge"
            :key="item.id"
            :class="['knowledge-item', { selected: selectedKnowledge.id === item.id }]"
            @click="selectedKnowledge = item"
          >
            <div class="item-top">
              <strong>{{ item.title }}</strong>
              <span :class="['status-pill', item.statusType]">{{ item.status }}</span>
            </div>
            <p>{{ item.summary }}</p>
            <div class="tag-row">
              <span v-for="tag in item.tags" :key="tag">{{ tag }}</span>
            </div>
            <small>{{ item.source }} / {{ item.updatedAt }}</small>
          </article>
        </div>
      </section>

      <section v-if="activeView === 'import'" class="view-stack">
        <div class="import-grid">
          <article v-for="card in importCards" :key="card.title" class="import-card">
            <span>{{ card.icon }}</span>
            <h2>{{ card.title }}</h2>
            <p>{{ card.desc }}</p>
            <button type="button" @click="card.handler">{{ card.action }}</button>
          </article>
        </div>
        <input ref="fileInput" class="hidden-input" type="file" accept=".txt,.md,.markdown,.pdf,.docx,text/plain,text/markdown,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" @change="handleFileSelected" />
        <section class="panel">
          <div class="panel-head">
            <h2>导入策略</h2>
            <span>Chunk + Entity + Embedding</span>
          </div>
          <div class="flow-line">
            <span>抽取文本</span>
            <span>内容切块</span>
            <span>生成摘要</span>
            <span>实体关系</span>
            <span>向量索引</span>
          </div>
        </section>
      </section>

      <section v-if="activeView === 'jobs'" class="view-stack">
        <div class="queue-toolbar">
          <button
            v-for="status in jobFilters"
            :key="status"
            type="button"
            :class="{ active: jobFilter === status }"
            @click="jobFilter = status"
          >
            {{ status }}
          </button>
        </div>
        <section class="job-list">
          <article v-for="job in filteredJobs" :key="job.id" class="job-card">
            <div class="job-head">
              <div>
                <strong>{{ job.title }}</strong>
                <small>{{ job.source }} / 耗时 {{ job.duration }}</small>
              </div>
              <span :class="['status-pill', job.tone]">{{ job.status }}</span>
            </div>
            <div class="steps">
              <span
                v-for="step in job.steps"
                :key="step.name"
                :class="['process-step', step.state]"
              >
                {{ step.name }}
              </span>
            </div>
            <p v-if="job.error">{{ job.error }}</p>
          </article>
        </section>
      </section>

      <section v-if="activeView === 'graph'" class="graph-layout">
        <div class="graph-canvas">
          <svg viewBox="0 0 760 520" role="img" aria-label="知识图谱">
            <defs>
              <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
                <path d="M0,0 L0,6 L7,3 z" fill="#5f7c92" />
              </marker>
            </defs>
            <line
              v-for="edge in graphEdges"
              :key="edge.id"
              :x1="nodeById(edge.from).x"
              :y1="nodeById(edge.from).y"
              :x2="nodeById(edge.to).x"
              :y2="nodeById(edge.to).y"
              :class="['graph-edge', edge.status]"
              marker-end="url(#arrow)"
              @click="selectedEdge = edge"
            />
            <g
              v-for="node in graphNodes"
              :key="node.id"
              class="graph-node"
              :class="{ selected: selectedNode.id === node.id }"
              :transform="`translate(${node.x}, ${node.y})`"
              @click="selectedNode = node"
            >
              <circle r="32" :class="node.typeKey" />
              <text y="5">{{ node.label }}</text>
            </g>
          </svg>
        </div>
        <div class="legend-panel">
          <h2>图谱图例</h2>
          <span v-for="legend in legends" :key="legend.label">
            <i :class="legend.type"></i>{{ legend.label }}
          </span>
        </div>
      </section>

      <section v-if="activeView === 'context'" class="context-grid">
        <section class="panel prompt-panel">
          <h2>当前问题</h2>
          <textarea v-model="contextQuestion" rows="8"></textarea>
          <div class="param-grid">
            <label>Top K<input v-model.number="contextParams.topK" /></label>
            <label>图谱跳数<input v-model.number="contextParams.graphDepth" /></label>
            <label>Token 上限<input v-model.number="contextParams.tokenLimit" /></label>
          </div>
          <button class="primary-action" type="button" @click="runContextGeneration">生成上下文</button>
        </section>

        <section class="panel recall-panel">
          <div class="panel-head">
            <h2>调试结果</h2>
            <span>{{ retrievalDebug.mode || 'keyword' }}</span>
          </div>
          <div class="debug-tabs">
            <button type="button" :class="{ active: contextDebugTab === 'prompt' }" @click="contextDebugTab = 'prompt'">Prompt 预览</button>
            <button type="button" :class="{ active: contextDebugTab === 'recall' }" @click="contextDebugTab = 'recall'">召回链路</button>
          </div>

          <section v-if="contextDebugTab === 'prompt'" class="prompt-debug-view">
            <div class="debug-summary">
              <span>tokens {{ tokenEstimate }}</span>
              <span>Top K {{ retrievalDebug.topK || contextParams.topK }}</span>
              <span>limit {{ retrievalDebug.tokenLimit || contextParams.tokenLimit }}</span>
            </div>
            <pre>{{ contextPreview }}</pre>
          </section>

          <section v-else class="recall-debug-view">
            <div class="debug-summary">
              <span>raw {{ retrievalDebug.rawCount || 0 }}</span>
              <span>selected {{ retrievalDebug.selectedCount || 0 }}</span>
              <span>filtered {{ retrievalDebug.filteredCount || 0 }}</span>
            </div>

            <div v-if="retrievalDebug.errors?.length" class="debug-section">
              <h3>错误</h3>
              <article v-for="error in retrievalDebug.errors" :key="error" class="recall-item danger-item">{{ error }}</article>
            </div>

            <div class="debug-section">
              <h3>最终进入上下文</h3>
              <article v-for="item in retrievalDebug.selectedItems" :key="`selected-${item.itemId || item.title}`" class="recall-item selected-recall">
                <div class="recall-title">
                  <strong>{{ item.title }}</strong>
                  <span>{{ formatScore(item.score) }}</span>
                </div>
                <p>{{ item.reason || item.reference }}</p>
                <small>{{ item.reference }}</small>
                <ul v-if="item.chunks?.length" class="chunk-preview-list">
                  <li v-for="chunk in item.chunks" :key="`${item.title}-${chunk.chunkIndex}`">
                    #{{ chunk.chunkIndex ?? '-' }} · {{ formatScore(chunk.score) }} · {{ chunk.preview }}
                  </li>
                </ul>
              </article>
            </div>

            <div class="debug-section">
              <h3>原始召回</h3>
              <article v-for="hit in retrievalDebug.rawHits" :key="`raw-${hit.itemId || hit.title}-${hit.chunkIndex}`" class="recall-item">
                <div class="recall-title">
                  <strong>{{ hit.title }}</strong>
                  <span>{{ formatScore(hit.score) }}</span>
                </div>
                <p>{{ hit.reason }}</p>
                <small v-if="hit.distance !== null && hit.distance !== undefined">distance {{ hit.distance }}</small>
                <p class="debug-preview">{{ hit.preview }}</p>
              </article>
            </div>

            <div class="debug-section">
              <h3>过滤结果</h3>
              <article v-if="!retrievalDebug.filteredHits?.length" class="recall-item">暂无过滤项</article>
              <article v-for="hit in retrievalDebug.filteredHits" :key="`filtered-${hit.itemId || hit.title}-${hit.chunkIndex}-${hit.reason}`" class="recall-item muted-recall">
                <div class="recall-title">
                  <strong>{{ hit.title }}</strong>
                  <span>{{ formatScore(hit.score) }}</span>
                </div>
                <p>{{ hit.reason }}</p>
              </article>
            </div>
          </section>
        </section>
      </section>

      <section v-if="activeView === 'models'" class="settings-grid">
        <section class="panel form-panel">
          <h2>模型配置</h2>
          <div class="config-group">
            <h3>Chat 模型</h3>
            <label>Chat Base URL<input v-model="modelConfig.chatBaseUrl" placeholder="https://api.openai.com/v1" /></label>
            <label>Chat API Key<input v-model="modelConfig.chatApiKey" type="password" placeholder="可与 Embedding 不同" /></label>
            <label>Chat Model<input v-model="modelConfig.chatModel" /></label>
            <label>Chat Timeout<input v-model.number="modelConfig.chatTimeoutSeconds" /></label>
          </div>
          <div class="config-group">
            <h3>Embedding 模型</h3>
            <label>Embedding Base URL<input v-model="modelConfig.embeddingBaseUrl" placeholder="https://api.openai.com/v1" /></label>
            <label>Embedding API Key<input v-model="modelConfig.embeddingApiKey" type="password" placeholder="可与 Chat 不同" /></label>
            <label>Embedding Model<input v-model="modelConfig.embeddingModel" /></label>
            <label>Embedding Timeout<input v-model.number="modelConfig.embeddingTimeoutSeconds" /></label>
          </div>
          <label>
            上下文检索模式
            <select v-model="modelConfig.retrievalMode">
              <option value="keyword">关键词加权检索</option>
              <option value="vector">Embedding + Chroma 向量检索</option>
            </select>
          </label>
          <label>
            Chroma 模式
            <select v-model="modelConfig.chromaMode">
              <option value="local">本地持久化</option>
              <option value="http">HTTP 服务</option>
            </select>
          </label>
          <label v-if="modelConfig.chromaMode !== 'http'">Chroma 存储路径<input v-model="modelConfig.chromaPath" placeholder="默认 backend/data/chroma" /></label>
          <div v-else class="config-group compact-config">
            <h3>Chroma HTTP 服务</h3>
            <label>Host<input v-model="modelConfig.chromaHost" placeholder="localhost" /></label>
            <label>Port<input v-model.number="modelConfig.chromaPort" placeholder="8000" /></label>
            <label>SSL
              <select v-model="modelConfig.chromaSsl">
                <option :value="false">false</option>
                <option :value="true">true</option>
              </select>
            </label>
            <label>API Key<input v-model="modelConfig.chromaApiKey" type="password" placeholder="可选，Chroma Token" /></label>
          </div>
          <label>Chroma Collection<input v-model="modelConfig.chromaCollection" placeholder="personal_knowledge_chunks" /></label>
          <label>
            文档解析模式
            <select v-model="modelConfig.parserMode">
              <option value="local">本地 Python 解析</option>
              <option value="mineru">MinerU 服务解析</option>
            </select>
          </label>
          <label>MinerU 解析接口地址<input v-model="modelConfig.mineruBaseUrl" placeholder="https://xxx/openapi/v1/ocr/mineru-parser" /></label>
          <label>MinerU API Key<input v-model="modelConfig.mineruApiKey" type="password" placeholder="Bearer Token，可选" /></label>
          <label>MinerU Model<input v-model="modelConfig.mineruModel" placeholder="mineru-vl" /></label>
          <label>MinerU only_md
            <select v-model="modelConfig.mineruOnlyMd">
              <option :value="true">true</option>
              <option :value="false">false</option>
            </select>
          </label>
          <button type="button" @click="saveModelSettings">保存配置</button>
          <button class="primary-action" type="button" @click="testModelSettings">测试连接</button>
          <button type="button" @click="rebuildVectors">重建向量索引</button>
        </section>
        <section class="panel">
          <h2>能力状态</h2>
          <div class="capability-list">
            <span v-for="capability in capabilities" :key="capability">{{ capability }}</span>
          </div>
        </section>
      </section>

      <section v-if="activeView === 'settings'" class="settings-grid">
        <section class="panel form-panel">
          <h2>系统设置</h2>
          <label>数据目录<input value="data/personal_knowledge.db" /></label>
          <label>上传目录<input value="data/uploads" /></label>
          <label>默认主题<input value="深色科技" /></label>
        </section>
        <section class="panel">
          <h2>安全策略</h2>
          <p class="muted">默认本地优先。浏览器插件只在手动保存网页和手动注入上下文时触发，不自动采集浏览历史。</p>
        </section>
      </section>
    </section>

    <aside class="inspector">
      <section class="inspector-card">
        <p class="eyebrow">INSPECTOR</p>
        <h2>{{ inspectorTitle }}</h2>
        <p>{{ inspectorSummary }}</p>
        <div v-if="activeView === 'knowledge'" class="inspector-actions">
          <button type="button" @click="openKnowledgeEditor(selectedKnowledge)">编辑</button>
          <button type="button" @click="removeSelectedKnowledge">删除</button>
        </div>
      </section>

      <section class="inspector-card">
        <div class="panel-head">
          <h3>AI 建议</h3>
          <span class="tag active">Ready</span>
        </div>
        <ul class="suggestions">
          <li v-for="tip in tips" :key="tip">{{ tip }}</li>
        </ul>
      </section>

      <section class="inspector-card context-preview">
        <div class="panel-head">
          <h3>上下文预览</h3>
          <span>{{ tokenEstimate }} tokens</span>
        </div>
        <pre>{{ contextPreview }}</pre>
      </section>
    </aside>

    <dialog ref="knowledgeDialog" class="modal-dialog">
      <form method="dialog" @submit.prevent="saveKnowledgeForm">
        <div class="modal-head">
          <div>
            <p class="eyebrow">KNOWLEDGE ITEM</p>
            <h2>{{ knowledgeForm.id ? '编辑知识' : '新增知识' }}</h2>
          </div>
          <button type="button" @click="closeKnowledgeDialog">关闭</button>
        </div>
        <label>
          标题
          <input v-model="knowledgeForm.title" required maxlength="160" />
        </label>
        <label>
          摘要
          <textarea v-model="knowledgeForm.summary" rows="3" placeholder="不填则根据正文自动截取" />
        </label>
        <label>
          正文
          <textarea v-model="knowledgeForm.content" rows="9" required />
        </label>
        <div class="param-grid">
          <label>来源<input v-model="knowledgeForm.source" /></label>
          <label>来源 URL<input v-model="knowledgeForm.sourceUrl" /></label>
          <label>标签<input v-model="knowledgeForm.tagsText" placeholder="AI产品, MVP" /></label>
        </div>
        <menu>
          <button type="button" @click="closeKnowledgeDialog">取消</button>
          <button class="primary-action" type="submit">保存</button>
        </menu>
      </form>
    </dialog>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import {
  createKnowledgeItem,
  deleteKnowledgeItem,
  fetchDashboard,
  fetchGraph,
  fetchHealth,
  fetchJobs,
  fetchKnowledgeItems,
  fetchModelConfig,
  generateContext,
  importFile,
  importManual,
  importWebpage,
  rebuildVectorIndex,
  saveModelConfig,
  testChatModel,
  testEmbeddingModel,
  updateKnowledgeItem
} from './api';

const navItems = [
  { key: 'dashboard', label: '首页仪表盘', subtitle: '个人知识系统运行态势', icon: '⌁' },
  { key: 'knowledge', label: '知识库', subtitle: '管理、检索和维护知识条目', icon: '▣' },
  { key: 'import', label: '导入知识', subtitle: '文件、网页和手动笔记入口', icon: '↥' },
  { key: 'jobs', label: '加工队列', subtitle: '解析、抽取和向量化流水线', icon: '⚙' },
  { key: 'graph', label: '知识图谱', subtitle: '实体、关系和证据网络', icon: '◎' },
  { key: 'context', label: '上下文调试台', subtitle: '检索链路和 Prompt 控制台', icon: '▤' },
  { key: 'models', label: '模型配置', subtitle: 'OpenAI 兼容 API 设置', icon: '◇' },
  { key: 'settings', label: '系统设置', subtitle: '本地存储与安全策略', icon: '◌' }
];

const activeView = ref('dashboard');
const knowledgeKeyword = ref('');
const jobFilter = ref('全部');
const sourceFilter = ref('全部');
const tagFilter = ref('全部');
const backendOnline = ref(false);
const tokenEstimate = ref('2,186');
const fileInput = ref(null);
const knowledgeDialog = ref(null);
const knowledgeForm = ref(emptyKnowledgeForm());
const contextParams = ref({ topK: 8, graphDepth: 1, tokenLimit: 3200 });
const contextDebugTab = ref('recall');

const currentNav = computed(() => navItems.find((item) => item.key === activeView.value));

const fallbackMetrics = [
  { label: '知识条目', value: '248', delta: '+12 today', tone: 'good' },
  { label: '文件', value: '61', delta: 'PDF / Word / MD', tone: 'neutral' },
  { label: '网页收藏', value: '93', delta: '+8 this week', tone: 'good' },
  { label: '实体', value: '426', delta: '37 待确认', tone: 'warn' },
  { label: '关系', value: '812', delta: '91.4% 可信', tone: 'good' },
  { label: '失败任务', value: '3', delta: '可重试', tone: 'bad' }
];

const fallbackPipeline = [
  { name: '文本抽取', desc: 'Markdown / PDF / Word / Web', status: 'success' },
  { name: '内容切块', desc: '平均 620 tokens', status: 'success' },
  { name: '实体关系', desc: '37 条关系待确认', status: 'warning' },
  { name: '向量索引', desc: 'Embedding model ready', status: 'success' }
];

const fallbackActivities = [
  { title: '个人 AI 记忆层商业化分析', desc: '命中 6 条知识、12 个实体、18 条关系', time: '09:42' },
  { title: '机会雷达部署方案', desc: '引用 Docker、Spring Boot、私有部署相关知识', time: '昨天' },
  { title: '中年效率工具方向复盘', desc: '召回产品假设和用户痛点笔记', time: '周三' }
];

const fileSources = ['PDF', 'Word', 'Markdown', 'TXT'];
const sources = ['全部', '文件', '网页', 'PDF', 'Word', 'Markdown', 'TXT', '手动笔记'];
const tags = ['副业', 'AI产品', '技术架构', '运营', '家庭责任', '效率'];
const fallbackKnowledgeItems = [
  {
    id: 1,
    title: '个人 AI 记忆层 MVP 决策',
    summary: '第一版采用本地优先架构，浏览器插件作为入口，后端知识中枢负责知识库、图谱、模型调用和上下文生成。',
    tags: ['AI产品', 'MVP', '架构'],
    source: '手动笔记',
    updatedAt: '2026-06-26',
    status: '已索引',
    statusType: 'success'
  },
  {
    id: 2,
    title: '机会雷达产品化路径',
    summary: '通过 GitHub 高增长开源项目发现可复制机会，以加法/减法形成个人可运营产品。',
    tags: ['副业', '机会雷达'],
    source: 'Markdown',
    updatedAt: '2026-06-25',
    status: '已索引',
    statusType: 'success'
  },
  {
    id: 3,
    title: '知识图谱抽取策略',
    summary: '实体关系由 AI 初抽，进入待确认区，人工修正后进入正式图谱，所有关系保留来源证据。',
    tags: ['知识图谱', 'AI'],
    source: '网页',
    updatedAt: '2026-06-24',
    status: '待确认',
    statusType: 'warning'
  },
  {
    id: 4,
    title: 'Docker 私有部署记录',
    summary: '机会雷达采用本地编译产物上传服务器，服务器构建镜像并通过 Compose 启动。',
    tags: ['部署', 'Docker'],
    source: 'Word',
    updatedAt: '2026-06-23',
    status: '解析失败',
    statusType: 'danger'
  }
];

const metrics = ref(fallbackMetrics);
const pipeline = ref(fallbackPipeline);
const activities = ref(fallbackActivities);
const knowledgeItems = ref(fallbackKnowledgeItems);
const selectedKnowledge = ref(fallbackKnowledgeItems[0]);
const filteredKnowledge = computed(() => {
  const keyword = knowledgeKeyword.value.trim().toLowerCase();
  return knowledgeItems.value.filter((item) => {
    const matchedKeyword = !keyword || `${item.title}${item.summary}${item.tags.join('')}`.toLowerCase().includes(keyword);
    const matchedSource = sourceFilter.value === '全部'
      || item.source === sourceFilter.value
      || (sourceFilter.value === '文件' && fileSources.includes(item.source));
    const matchedTag = tagFilter.value === '全部' || item.tags.includes(tagFilter.value);
    return matchedKeyword && matchedSource && matchedTag;
  });
});

const importCards = [
  { icon: '✎', title: '手动笔记', desc: '记录长期偏好、项目背景、阶段性结论。', action: '新建笔记', handler: () => openKnowledgeEditor() },
  { icon: '⌘', title: '保存网页', desc: '粘贴 URL 或由浏览器插件保存当前页面。', action: '导入网页', handler: () => openWebImport() },
  { icon: '▥', title: '上传文件', desc: '支持 Markdown、TXT、PDF、Word。', action: '选择文件', handler: () => fileInput.value?.click() }
];

const jobFilters = ['全部', '处理中', '失败', '待确认', '成功'];
const fallbackJobs = [
  {
    id: 1,
    title: '个人 AI 记忆层 PRD.md',
    source: 'Markdown',
    status: '成功',
    tone: 'success',
    duration: '18s',
    steps: [
      { name: '抽取', state: 'done' },
      { name: '切块', state: 'done' },
      { name: '摘要', state: 'done' },
      { name: '实体', state: 'done' },
      { name: '向量', state: 'done' }
    ]
  },
  {
    id: 2,
    title: 'Docker部署记录.docx',
    source: 'Word',
    status: '失败',
    tone: 'danger',
    duration: '6s',
    error: 'Word 解析失败：文件疑似被占用，可重试。',
    steps: [
      { name: '抽取', state: 'failed' },
      { name: '切块', state: 'pending' },
      { name: '摘要', state: 'pending' },
      { name: '实体', state: 'pending' },
      { name: '向量', state: 'pending' }
    ]
  },
  {
    id: 3,
    title: '开源项目商业化文章',
    source: '网页',
    status: '待确认',
    tone: 'warning',
    duration: '31s',
    steps: [
      { name: '抽取', state: 'done' },
      { name: '切块', state: 'done' },
      { name: '摘要', state: 'done' },
      { name: '实体', state: 'warning' },
      { name: '向量', state: 'done' }
    ]
  }
];
const jobs = ref(fallbackJobs);
const filteredJobs = computed(() => jobFilter.value === '全部' ? jobs.value : jobs.value.filter((job) => job.status === jobFilter.value));

const fallbackGraphNodes = [
  { id: 'me', label: '我', typeKey: 'person', x: 380, y: 250 },
  { id: 'hub', label: '知识中枢', typeKey: 'project', x: 210, y: 150 },
  { id: 'radar', label: '机会雷达', typeKey: 'project', x: 570, y: 145 },
  { id: 'python', label: 'Python', typeKey: 'tech', x: 170, y: 340 },
  { id: 'graph', label: '知识图谱', typeKey: 'concept', x: 390, y: 85 },
  { id: 'mvp', label: 'MVP决策', typeKey: 'decision', x: 590, y: 335 },
  { id: 'risk', label: '维护成本', typeKey: 'risk', x: 385, y: 430 }
];
const fallbackGraphEdges = [
  { id: 'e1', from: 'me', to: 'hub', status: 'confirmed', label: '规划' },
  { id: 'e2', from: 'hub', to: 'python', status: 'confirmed', label: '使用' },
  { id: 'e3', from: 'hub', to: 'graph', status: 'pending', label: '包含' },
  { id: 'e4', from: 'me', to: 'radar', status: 'confirmed', label: '负责' },
  { id: 'e5', from: 'hub', to: 'mvp', status: 'confirmed', label: '形成' },
  { id: 'e6', from: 'hub', to: 'risk', status: 'pending', label: '面临' }
];
const graphNodes = ref(fallbackGraphNodes);
const graphEdges = ref(fallbackGraphEdges);
const selectedNode = ref(fallbackGraphNodes[1]);
const selectedEdge = ref(fallbackGraphEdges[0]);
const legends = [
  { label: '人物', type: 'person' },
  { label: '项目', type: 'project' },
  { label: '技术', type: 'tech' },
  { label: '概念', type: 'concept' },
  { label: '决策', type: 'decision' },
  { label: '风险', type: 'risk' }
];

function nodeById(id) {
  return graphNodes.value.find((node) => node.id === id) || graphNodes.value[0];
}

const contextQuestion = ref('基于我的背景和当前项目，帮我判断个人知识中枢下一步 MVP 应该优先做什么？');
const fallbackContextHits = [
  { title: '个人 AI 记忆层 MVP 决策', reason: '命中“本地优先、浏览器插件、知识中枢”', score: '0.91' },
  { title: '知识图谱抽取策略', reason: '提供实体关系待确认和证据链策略', score: '0.86' },
  { title: '机会雷达产品化路径', reason: '补充个人副业产品化偏好', score: '0.78' }
];
const fallbackRetrievalDebug = {
  mode: 'keyword',
  topK: 8,
  tokenLimit: 3200,
  rawCount: 3,
  selectedCount: 3,
  filteredCount: 0,
  rawHits: fallbackContextHits.map((hit) => ({ ...hit, preview: hit.reason })),
  selectedItems: fallbackContextHits.map((hit) => ({ ...hit, reference: '本地知识库', chunks: [] })),
  filteredHits: [],
  errors: []
};
const contextHits = ref(fallbackContextHits);
const retrievalDebug = ref(fallbackRetrievalDebug);
const capabilities = ['Chat 摘要', '标签生成', '实体抽取', '关系抽取', 'Embedding', '上下文压缩'];
const tips = ['优先维护“当前项目”和“决策”类知识。', '待确认关系过多时会降低上下文可信度。', '建议为浏览器插件增加保存选中文本能力。'];
const modelConfig = ref({
  baseUrl: 'https://api.openai.com/v1',
  apiKey: '',
  chatBaseUrl: 'https://api.openai.com/v1',
  chatApiKey: '',
  chatModel: 'gpt-4.1-mini',
  chatTimeoutSeconds: 45,
  embeddingBaseUrl: 'https://api.openai.com/v1',
  embeddingApiKey: '',
  embeddingModel: 'text-embedding-3-small',
  embeddingTimeoutSeconds: 45,
  timeoutSeconds: 45,
  retrievalMode: 'keyword',
  chromaMode: 'local',
  chromaPath: '',
  chromaHost: 'localhost',
  chromaPort: 8000,
  chromaSsl: false,
  chromaApiKey: '',
  chromaCollection: 'personal_knowledge_chunks',
  parserMode: 'local',
  mineruBaseUrl: '',
  mineruApiKey: '',
  mineruModel: 'mineru-vl',
  mineruOnlyMd: true
});

onMounted(async () => {
  await loadBackendData();
});

async function loadBackendData() {
  try {
    await fetchHealth();
    backendOnline.value = true;

    const [dashboard, remoteKnowledge, remoteJobs, remoteGraph, remoteModelConfig] = await Promise.all([
      fetchDashboard(),
      fetchKnowledgeItems(),
      fetchJobs(),
      fetchGraph(),
      fetchModelConfig()
    ]);

    metrics.value = dashboard.metrics || fallbackMetrics;
    pipeline.value = dashboard.pipeline || fallbackPipeline;
    activities.value = dashboard.activities || fallbackActivities;
    knowledgeItems.value = remoteKnowledge.length ? remoteKnowledge : fallbackKnowledgeItems;
    selectedKnowledge.value = knowledgeItems.value[0] || fallbackKnowledgeItems[0];
    jobs.value = remoteJobs.length ? remoteJobs : fallbackJobs;
    graphNodes.value = remoteGraph.nodes?.length ? remoteGraph.nodes : fallbackGraphNodes;
    graphEdges.value = remoteGraph.edges?.length ? remoteGraph.edges : fallbackGraphEdges;
    selectedNode.value = graphNodes.value[1] || graphNodes.value[0];
    selectedEdge.value = graphEdges.value[0];
    modelConfig.value = remoteModelConfig;
  } catch (error) {
    backendOnline.value = false;
  }
}

async function refreshCurrentView() {
  if (!backendOnline.value) {
    await loadBackendData();
    return;
  }

  if (activeView.value === 'dashboard') {
    await refreshDashboard();
  } else if (activeView.value === 'knowledge' || activeView.value === 'import') {
    await refreshKnowledge();
    await refreshDashboard();
  } else if (activeView.value === 'jobs') {
    await refreshJobs();
  } else if (activeView.value === 'graph') {
    await refreshGraph();
  } else if (activeView.value === 'models') {
    await refreshModelConfig();
  } else if (activeView.value === 'context') {
    await runContextGeneration();
  }
}

async function refreshDashboard() {
  const dashboard = await fetchDashboard();
  metrics.value = dashboard.metrics || metrics.value;
  pipeline.value = dashboard.pipeline || pipeline.value;
  activities.value = dashboard.activities || activities.value;
}

async function refreshKnowledge() {
  const remoteKnowledge = await fetchKnowledgeItems();
  knowledgeItems.value = remoteKnowledge.length ? remoteKnowledge : knowledgeItems.value;
  if (!knowledgeItems.value.some((item) => item.id === selectedKnowledge.value?.id)) {
    selectedKnowledge.value = knowledgeItems.value[0] || fallbackKnowledgeItems[0];
  }
}

async function refreshJobs() {
  const remoteJobs = await fetchJobs();
  jobs.value = remoteJobs.length ? remoteJobs : jobs.value;
}

async function refreshGraph() {
  const remoteGraph = await fetchGraph();
  graphNodes.value = remoteGraph.nodes?.length ? remoteGraph.nodes : graphNodes.value;
  graphEdges.value = remoteGraph.edges?.length ? remoteGraph.edges : graphEdges.value;
  selectedNode.value = graphNodes.value.find((node) => node.id === selectedNode.value?.id) || graphNodes.value[0];
  selectedEdge.value = graphEdges.value.find((edge) => edge.id === selectedEdge.value?.id) || graphEdges.value[0];
}

async function refreshModelConfig() {
  modelConfig.value = await fetchModelConfig();
}

async function jumpFromMetric(label) {
  if (label === '知识条目') {
    activeView.value = 'knowledge';
    sourceFilter.value = '全部';
    tagFilter.value = '全部';
    await refreshKnowledgeIfOnline();
  } else if (label === '文件') {
    activeView.value = 'knowledge';
    sourceFilter.value = '文件';
    tagFilter.value = '全部';
    await refreshKnowledgeIfOnline();
  } else if (label === '网页收藏') {
    activeView.value = 'knowledge';
    sourceFilter.value = '网页';
    tagFilter.value = '全部';
    await refreshKnowledgeIfOnline();
  } else if (label === '实体' || label === '关系') {
    activeView.value = 'graph';
    if (backendOnline.value) await refreshGraph();
  } else if (label === '失败任务') {
    activeView.value = 'jobs';
    jobFilter.value = '失败';
    if (backendOnline.value) await refreshJobs();
  }
}

async function refreshKnowledgeIfOnline() {
  if (backendOnline.value) {
    await refreshKnowledge();
  }
}

function openKnowledgeEditor(item = null) {
  knowledgeForm.value = item
    ? {
        id: item.id,
        title: item.title,
        summary: item.summary,
        content: item.content || item.summary,
        source: item.source,
        sourceUrl: item.sourceUrl || '',
        tagsText: item.tags.join(', ')
      }
    : emptyKnowledgeForm();
  knowledgeDialog.value?.showModal();
}

function openWebImport() {
  knowledgeForm.value = {
    ...emptyKnowledgeForm(),
    source: '网页',
    title: '网页知识',
    content: '请粘贴网页正文或选中文本。',
    tagsText: '网页'
  };
  knowledgeDialog.value?.showModal();
}

function closeKnowledgeDialog() {
  knowledgeDialog.value?.close();
}

async function saveKnowledgeForm() {
  const payload = formToPayload();
  if (!backendOnline.value) {
    const localItem = {
      id: Date.now(),
      ...payload,
      status: '本地模拟',
      statusType: 'warning',
      updatedAt: new Date().toISOString().slice(0, 10)
    };
    knowledgeItems.value = [localItem, ...knowledgeItems.value];
    selectedKnowledge.value = localItem;
    closeKnowledgeDialog();
    return;
  }

  const saved = knowledgeForm.value.id
    ? await updateKnowledgeItem(knowledgeForm.value.id, payload)
    : payload.source === '网页'
      ? await importWebpage(payload)
      : await importManual(payload);

  await loadBackendData();
  selectedKnowledge.value = saved;
  closeKnowledgeDialog();
}

async function removeSelectedKnowledge() {
  if (!selectedKnowledge.value?.id) return;
  if (!backendOnline.value) {
    knowledgeItems.value = knowledgeItems.value.filter((item) => item.id !== selectedKnowledge.value.id);
    selectedKnowledge.value = knowledgeItems.value[0] || fallbackKnowledgeItems[0];
    return;
  }
  await deleteKnowledgeItem(selectedKnowledge.value.id);
  await loadBackendData();
}

async function handleFileSelected(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  if (!backendOnline.value) {
    event.target.value = '';
    return;
  }
  const imported = await importFile(file);
  await loadBackendData();
  selectedKnowledge.value = imported;
  activeView.value = 'knowledge';
  event.target.value = '';
}

async function runContextGeneration() {
  if (!backendOnline.value) {
    contextHits.value = fallbackContextHits;
    retrievalDebug.value = fallbackRetrievalDebug;
    tokenEstimate.value = '2,186';
    return;
  }

  const result = await generateContext({
    question: contextQuestion.value,
    top_k: contextParams.value.topK,
    tokenLimit: contextParams.value.tokenLimit
  });
  contextHits.value = result.hits || fallbackContextHits;
  retrievalDebug.value = result.debug || fallbackRetrievalDebug;
  tokenEstimate.value = result.tokenEstimate || '0';
  generatedPrompt.value = result.prompt || '';
  contextDebugTab.value = 'recall';
}

async function saveModelSettings() {
  if (!backendOnline.value) return;
  modelConfig.value = await saveModelConfig(modelConfig.value);
}

async function testModelSettings() {
  if (!backendOnline.value) return;
  const chatResult = await testChatModel();
  tips.unshift(`Chat：${chatResult.message}`);
  if (modelConfig.value.retrievalMode === 'vector') {
    const embeddingResult = await testEmbeddingModel();
    tips.unshift(`Embedding：${embeddingResult.message}`);
  }
}

async function rebuildVectors() {
  if (!backendOnline.value) return;
  const result = await rebuildVectorIndex();
  if (result.ok) {
    tips.unshift(`向量索引已重建，写入 ${result.indexedChunks} 个 chunk。`);
  } else {
    tips.unshift(result.message || `向量索引重建失败，失败 ${result.failed?.length || 0} 条。`);
  }
}

const generatedPrompt = ref('');

function formatScore(score) {
  const value = Number(score || 0);
  return value.toFixed(2);
}

const inspectorTitle = computed(() => {
  if (activeView.value === 'knowledge') return selectedKnowledge.value.title;
  if (activeView.value === 'graph') return selectedNode.value.label;
  return currentNav.value?.label || '知识中枢';
});
const inspectorSummary = computed(() => {
  if (activeView.value === 'knowledge') return selectedKnowledge.value.summary;
  if (activeView.value === 'graph') return `类型：${selectedNode.value.typeKey}。关系证据：${selectedEdge.value.label} / ${selectedEdge.value.status === 'confirmed' ? '已确认' : '待确认'}。`;
  return '本地 AI 知识操作台正在汇总知识库、图谱、模型和上下文调用状态。';
});
const contextPreview = computed(() => {
  if (generatedPrompt.value) {
    return generatedPrompt.value;
  }
  return `# 个人上下文\n- ${selectedKnowledge.value.title}\n- ${selectedKnowledge.value.summary}\n\n# 相关图谱\n${selectedNode.value.label} 与 ${nodeById(selectedEdge.value.to)?.label || '知识节点'} 存在「${selectedEdge.value.label}」关系。\n\n# 回答要求\n请结合我的长期目标、项目约束和已确认知识，给出可执行建议。`;
});

function emptyKnowledgeForm() {
  return {
    id: null,
    title: '',
    summary: '',
    content: '',
    source: '手动笔记',
    sourceUrl: '',
    tagsText: ''
  };
}

function formToPayload() {
  return {
    title: knowledgeForm.value.title,
    summary: knowledgeForm.value.summary,
    content: knowledgeForm.value.content,
    source: knowledgeForm.value.source,
    sourceUrl: knowledgeForm.value.sourceUrl,
    tags: knowledgeForm.value.tagsText
      .split(/[，,\s]+/)
      .map((tag) => tag.trim())
      .filter(Boolean)
  };
}
</script>
