const TYPE_WEIGHT = {
  '当前项目': 1.35,
  '工作画像': 1.15,
  '输出偏好': 1.1,
  '确认事实': 1,
  '学习资料': 0.9
};

export function rankMemories(memories, query, options = {}) {
  const words = tokenize(query);
  const scope = options.scope || '全部';

  return memories
    .filter((memory) => scope === '全部' || memory.scope === scope)
    .map((memory) => ({
      ...memory,
      score: scoreMemory(memory, words)
    }))
    .sort((a, b) => b.score - a.score || b.updatedAt.localeCompare(a.updatedAt));
}

export function composePrompt(memories, userInput) {
  const selected = memories.filter((memory) => memory.selected);
  const memoryText = selected
    .map((memory, index) => `${index + 1}. [${memory.scope}/${memory.type}] ${memory.title}\n${memory.content}`)
    .join('\n\n');

  const task = userInput.trim() || '请结合以上个人上下文，帮助我完成当前问题。';

  if (!memoryText) {
    return task;
  }

  return `请先读取我的个人上下文，再回答最后的问题。只使用与问题相关的上下文；如果上下文不足，请明确说明需要补充什么。\n\n# 我的个人上下文\n${memoryText}\n\n# 当前问题\n${task}`;
}

function scoreMemory(memory, words) {
  const haystack = `${memory.title} ${memory.content} ${(memory.tags || []).join(' ')} ${memory.type} ${memory.scope}`.toLowerCase();
  const keywordScore = words.reduce((score, word) => score + (haystack.includes(word) ? 3 : 0), 0);
  const tagScore = (memory.tags || []).reduce((score, tag) => score + (words.includes(tag.toLowerCase()) ? 4 : 0), 0);
  const recencyScore = Math.max(0, 2 - daysSince(memory.updatedAt) / 30);
  const typeScore = TYPE_WEIGHT[memory.type] || 1;

  return (keywordScore + tagScore + recencyScore + 1) * typeScore;
}

function tokenize(input) {
  return String(input || '')
    .toLowerCase()
    .split(/[\s,，。！？、；：\n\r\t]+/)
    .map((word) => word.trim())
    .filter(Boolean);
}

function daysSince(dateText) {
  const time = new Date(dateText).getTime();
  if (!Number.isFinite(time)) {
    return 30;
  }
  return (Date.now() - time) / 86400000;
}
