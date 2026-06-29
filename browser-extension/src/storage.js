const DB_NAME = 'personal-ai-memory';
const DB_VERSION = 1;
const STORE_MEMORIES = 'memories';
const STORE_SETTINGS = 'settings';

let dbPromise;

function openDb() {
  if (dbPromise) {
    return dbPromise;
  }

  dbPromise = new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE_MEMORIES)) {
        const store = db.createObjectStore(STORE_MEMORIES, { keyPath: 'id' });
        store.createIndex('scope', 'scope');
        store.createIndex('type', 'type');
        store.createIndex('updatedAt', 'updatedAt');
      }
      if (!db.objectStoreNames.contains(STORE_SETTINGS)) {
        db.createObjectStore(STORE_SETTINGS, { keyPath: 'key' });
      }
    };

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });

  return dbPromise;
}

async function transaction(storeName, mode, action) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, mode);
    const store = tx.objectStore(storeName);
    const result = action(store);

    tx.oncomplete = () => resolve(result);
    tx.onerror = () => reject(tx.error);
    tx.onabort = () => reject(tx.error);
  });
}

function requestToPromise(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export async function listMemories() {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_MEMORIES, 'readonly');
    const request = tx.objectStore(STORE_MEMORIES).getAll();
    request.onsuccess = () => resolve(request.result.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt)));
    request.onerror = () => reject(request.error);
  });
}

export async function saveMemory(memory) {
  const now = new Date().toISOString();
  const record = {
    id: memory.id || crypto.randomUUID(),
    title: memory.title.trim(),
    content: memory.content.trim(),
    scope: memory.scope || '工作',
    type: memory.type || '工作画像',
    tags: normalizeTags(memory.tags),
    confidence: memory.confidence || '已确认',
    createdAt: memory.createdAt || now,
    updatedAt: now
  };

  await transaction(STORE_MEMORIES, 'readwrite', (store) => store.put(record));
  return record;
}

export async function deleteMemory(id) {
  await transaction(STORE_MEMORIES, 'readwrite', (store) => store.delete(id));
}

export async function getSetting(key, defaultValue = null) {
  const db = await openDb();
  const result = await requestToPromise(db.transaction(STORE_SETTINGS, 'readonly').objectStore(STORE_SETTINGS).get(key));
  return result?.value ?? defaultValue;
}

export async function setSetting(key, value) {
  await transaction(STORE_SETTINGS, 'readwrite', (store) => store.put({ key, value }));
}

export function normalizeTags(tags) {
  if (Array.isArray(tags)) {
    return tags.map((tag) => String(tag).trim()).filter(Boolean);
  }
  return String(tags || '')
    .split(/[，,\s]+/)
    .map((tag) => tag.trim())
    .filter(Boolean);
}

export const seedMemories = [
  {
    title: '我的角色画像',
    type: '工作画像',
    scope: '工作',
    tags: ['画像', '输出偏好'],
    content: '我是有 15 年以上后端开发、技术架构和技术管理经验的技术负责人，熟悉企业 ERP、互联网金融、政务信息化和央企工作环境，偏好务实、可落地、可迭代的方案。'
  },
  {
    title: '副业探索目标',
    type: '当前项目',
    scope: '工作',
    tags: ['副业', '产品'],
    content: '我的一年目标是通过技术背景和 AI 应用经验，做出一个可自运营、能覆盖工资收入的产品。当前倾向从已有需求和成熟技术中做加法或减法，而不是凭空制造需求。'
  },
  {
    title: 'AI 回复偏好',
    type: '输出偏好',
    scope: '工作',
    tags: ['AI', '沟通'],
    content: '回答需要像 partner 一样共同推演，先讲判断，再给可执行路径。不要空泛鼓励，要指出风险、取舍和下一步动作。'
  }
];
