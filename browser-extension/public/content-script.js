const INPUT_SELECTOR = [
  'textarea',
  '[contenteditable="true"]',
  '[role="textbox"]',
  'div[contenteditable="true"]'
].join(',');

function getVisibleInput() {
  const inputs = Array.from(document.querySelectorAll(INPUT_SELECTOR));
  return inputs
    .filter((input) => {
      const rect = input.getBoundingClientRect();
      return rect.width > 80 && rect.height > 20 && rect.bottom > 0 && rect.right > 0;
    })
    .sort((a, b) => b.getBoundingClientRect().bottom - a.getBoundingClientRect().bottom)[0];
}

function insertIntoElement(element, text) {
  element.focus();

  if (element.tagName === 'TEXTAREA' || element.tagName === 'INPUT') {
    const start = element.selectionStart ?? element.value.length;
    const end = element.selectionEnd ?? element.value.length;
    const before = element.value.slice(0, start);
    const after = element.value.slice(end);
    element.value = `${before}${text}${after}`;
    element.selectionStart = element.selectionEnd = start + text.length;
    element.dispatchEvent(new Event('input', { bubbles: true }));
    element.dispatchEvent(new Event('change', { bubbles: true }));
    return true;
  }

  const selection = window.getSelection();
  if (selection && selection.rangeCount > 0 && element.contains(selection.anchorNode)) {
    const range = selection.getRangeAt(0);
    range.deleteContents();
    range.insertNode(document.createTextNode(text));
    range.collapse(false);
    selection.removeAllRanges();
    selection.addRange(range);
  } else {
    element.textContent = `${element.textContent || ''}${text}`;
  }

  element.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: text }));
  element.dispatchEvent(new Event('change', { bubbles: true }));
  return true;
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === 'PAM_GET_PAGE') {
    const selection = window.getSelection()?.toString()?.trim() || '';
    const content = selection || document.body?.innerText?.slice(0, 12000) || '';
    sendResponse({
      ok: true,
      title: document.title || location.hostname,
      url: location.href,
      content
    });
    return true;
  }

  if (message?.type !== 'PAM_INSERT_CONTEXT') {
    return false;
  }

  const input = getVisibleInput();
  if (!input) {
    sendResponse({ ok: false, reason: '未找到可插入的输入框，请先点击 AI 页面输入框后重试。' });
    return true;
  }

  const ok = insertIntoElement(input, message.payload || '');
  sendResponse({ ok });
  return true;
});
