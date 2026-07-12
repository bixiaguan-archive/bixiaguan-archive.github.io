(function() {
  'use strict';

  var STORAGE_KEY = 'bixiaguan.proofreading-marks.v1';
  var currentEpisode = null;
  var selectedTarget = null;
  var activeType = null;
  var turnstileWidgetId = null;
  var turnstileToken = '';
  var config = window.CROWD_REPORT_CONFIG || {};
  var labels = {
    asr_error: 'ASR 错误',
    annotation: '添加附注',
    fact_error: '事实勘误',
    uncertain: '待核实'
  };

  var css = `
    .proofreading-toolbar { display:flex; align-items:center; gap:8px; margin-top:12px; flex-wrap:wrap; }
    .proofreading-btn { border:1px solid #d8cfc5; background:#fff; color:#6c5448; border-radius:4px; padding:5px 9px; font:inherit; font-size:.76rem; cursor:pointer; }
    .proofreading-btn:hover { border-color:#a83a3a; color:#a83a3a; background:#fff8f4; }
    .proofreading-btn.primary { background:#6c5448; color:#fff; border-color:#6c5448; }
    .proofreading-btn.primary:hover { background:#513d34; color:#fff; }
    .proofreading-count { color:#888; font-size:.76rem; }
    .proofreading-panel { display:none; margin:0 18px 14px; border:1px solid #e8e2da; border-radius:6px; background:#fdfcfa; }
    .proofreading-panel.open { display:block; }
    .proofreading-panel-head { display:flex; justify-content:space-between; gap:8px; align-items:center; padding:10px 12px; border-bottom:1px solid #e8e2da; font-size:.82rem; }
    .proofreading-panel-actions { display:flex; gap:6px; flex-wrap:wrap; }
    .proofreading-list { max-height:250px; overflow:auto; }
    .proofreading-empty { padding:14px 12px; color:#888; font-size:.8rem; line-height:1.7; }
    .proofreading-item { display:grid; grid-template-columns:auto minmax(0,1fr) auto; gap:8px; align-items:start; padding:10px 12px; border-bottom:1px solid #f0ece6; font-size:.8rem; }
    .proofreading-item:last-child { border-bottom:0; }
    .proofreading-kind { color:#fff; background:#8a6b5b; border-radius:3px; padding:1px 5px; font-size:.67rem; white-space:nowrap; }
    .proofreading-kind.annotation { background:#0f8b8d; }
    .proofreading-kind.fact_error { background:#c44; }
    .proofreading-kind.uncertain { background:#9b8753; }
    .proofreading-original { color:#444; line-height:1.55; overflow-wrap:anywhere; }
    .proofreading-meta { color:#888; font-size:.72rem; margin-top:2px; }
    .proofreading-icon-btn { border:0; background:none; color:#9b6a5a; font:inherit; font-size:.72rem; padding:1px; cursor:pointer; white-space:nowrap; }
    .proofreading-icon-btn:hover { color:#a83a3a; text-decoration:underline; }
    .proofreading-menu { display:none; position:absolute; z-index:1200; min-width:145px; padding:4px; border:1px solid #ded5cb; border-radius:6px; background:#fff; box-shadow:0 5px 18px rgba(0,0,0,.16); }
    .proofreading-menu.open { display:block; }
    .proofreading-menu button { display:block; width:100%; border:0; background:none; text-align:left; padding:7px 9px; border-radius:3px; color:#444; font:inherit; font-size:.8rem; cursor:pointer; }
    .proofreading-menu button:hover { background:#fff3e8; color:#a83a3a; }
    .proofreading-menu .report { border-top:1px solid #eee5dc; margin-top:3px; padding-top:8px; color:#6c5448; }
    .proofreading-modal { display:none; position:fixed; z-index:1300; inset:0; background:rgba(44,44,44,.34); padding:16px; align-items:center; justify-content:center; }
    .proofreading-modal.open { display:flex; }
    .proofreading-dialog { width:min(520px, 100%); max-height:90vh; overflow:auto; background:#fff; border-radius:8px; box-shadow:0 8px 30px rgba(0,0,0,.22); }
    .proofreading-dialog-head { display:flex; align-items:center; justify-content:space-between; gap:12px; padding:14px 16px; border-bottom:1px solid #e8e2da; background:#fdfcfa; }
    .proofreading-dialog-title { font-size:.98rem; font-weight:600; }
    .proofreading-close { border:0; background:none; color:#777; padding:0 3px; font-size:1.4rem; line-height:1; cursor:pointer; }
    .proofreading-dialog-body { padding:14px 16px 16px; }
    .proofreading-quote { padding:9px 10px; background:#faf8f5; border-left:3px solid #c9b7a7; color:#555; font-size:.85rem; line-height:1.65; overflow-wrap:anywhere; }
    .proofreading-location { margin-top:5px; color:#888; font: .73rem 'Courier New', monospace; }
    .proofreading-field { display:block; margin-top:13px; color:#555; font-size:.82rem; }
    .proofreading-field input, .proofreading-field textarea { width:100%; margin-top:5px; padding:8px 9px; border:1px solid #d8cfc5; border-radius:4px; color:#333; font:inherit; font-size:.86rem; }
    .proofreading-field textarea { min-height:76px; resize:vertical; }
    .proofreading-help { color:#888; font-size:.74rem; line-height:1.6; margin-top:5px; }
    .proofreading-form-status { min-height:1.3em; margin-top:10px; color:#a83a3a; font-size:.78rem; }
    .proofreading-form-actions { display:flex; justify-content:flex-end; gap:8px; margin-top:14px; }
    .proofreading-form-actions button { border:1px solid #d8cfc5; border-radius:4px; padding:7px 11px; background:#fff; color:#555; font:inherit; font-size:.82rem; cursor:pointer; }
    .proofreading-form-actions .submit { background:#6c5448; border-color:#6c5448; color:#fff; }
    .proofreading-form-actions .submit:hover { background:#513d34; }
    .proofreading-turnstile { margin-top:13px; }
    @media (max-width:640px) { .proofreading-panel { margin:0 12px 12px; } .proofreading-toolbar { gap:6px; } .proofreading-btn { padding:5px 7px; } }
  `;

  function addUi() {
    var style = document.createElement('style');
    style.textContent = css;
    document.head.appendChild(style);
    var menu = document.createElement('div');
    menu.id = 'proofreading-menu';
    menu.className = 'proofreading-menu';
    menu.innerHTML = '<button data-type="asr_error">ASR 错误</button>' +
      '<button data-type="annotation">添加附注</button>' +
      '<button data-type="fact_error">事实勘误</button>' +
      '<button data-type="uncertain">待核实</button>';
    document.body.appendChild(menu);

    var modal = document.createElement('div');
    modal.id = 'proofreading-modal';
    modal.className = 'proofreading-modal';
    modal.innerHTML = '<div class="proofreading-dialog" role="dialog" aria-modal="true" aria-labelledby="proofreading-dialog-title">' +
      '<div class="proofreading-dialog-head"><span id="proofreading-dialog-title" class="proofreading-dialog-title"></span><button class="proofreading-close" aria-label="关闭">&times;</button></div>' +
      '<form id="proofreading-form" class="proofreading-dialog-body">' +
        '<div id="proofreading-quote" class="proofreading-quote"></div><div id="proofreading-location" class="proofreading-location"></div>' +
        '<label id="proofreading-main-label" class="proofreading-field"><span></span><input id="proofreading-main-input" maxlength="300"></label>' +
        '<label id="proofreading-comment-label" class="proofreading-field"><span>说明（可选）</span><textarea id="proofreading-comment" maxlength="1000"></textarea></label>' +
        '<div id="proofreading-turnstile" class="proofreading-turnstile"></div><div id="proofreading-form-status" class="proofreading-form-status" role="status"></div>' +
        '<div class="proofreading-form-actions"><button type="button" data-close>取消</button><button type="submit" class="submit"></button></div>' +
      '</form></div>';
    document.body.appendChild(modal);

    menu.addEventListener('mousedown', function(event) { event.preventDefault(); });
    menu.addEventListener('click', function(event) {
      var type = event.target.getAttribute('data-type');
      if (type) openModal(type);
    });
    modal.querySelector('.proofreading-close').addEventListener('click', closeModal);
    modal.querySelector('[data-close]').addEventListener('click', closeModal);
    modal.addEventListener('click', function(event) { if (event.target === modal) closeModal(); });
    modal.querySelector('form').addEventListener('submit', submitModal);
  }

  function readMarks() {
    try {
      var marks = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
      return Array.isArray(marks) ? marks : [];
    } catch (_) { return []; }
  }

  function writeMarks(marks) { localStorage.setItem(STORAGE_KEY, JSON.stringify(marks)); }
  function marksForEpisode(ep) { return readMarks().filter(function(mark) { return mark.episode === ep; }); }
  function sourceForEpisode(ep) {
    var data = (window.INDEX || []).find(function(item) { return item.ep === ep; });
    return data ? data.segments.map(function(segment) { return segment.text || ''; }).join('') : '';
  }
  function episodeData(ep) { return (window.INDEX || []).find(function(item) { return item.ep === ep; }); }

  function closestElement(node, selector) {
    var element = node && node.nodeType === Node.ELEMENT_NODE ? node : node && node.parentElement;
    return element ? element.closest(selector) : null;
  }

  function textWithoutBadges(root) {
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    var text = '';
    var node;
    while ((node = walker.nextNode())) {
      if (!closestElement(node, '.note-badge')) text += node.nodeValue;
    }
    return text;
  }

  function transcriptTextFromFragment(fragment) {
    var holder = document.createElement('div');
    holder.appendChild(fragment);
    var total = '';
    holder.querySelectorAll('.txt').forEach(function(textEl) { total += textWithoutBadges(textEl); });
    return total;
  }

  function sourceOffsetBefore(body, node, offset) {
    var prefix = document.createRange();
    prefix.selectNodeContents(body);
    prefix.setEnd(node, offset);
    return transcriptTextFromFragment(prefix.cloneContents()).length;
  }

  function targetFromSelection() {
    var selection = window.getSelection();
    if (!selection || selection.rangeCount !== 1 || selection.isCollapsed) return null;
    var range = selection.getRangeAt(0);
    var startText = closestElement(range.startContainer, '.txt');
    var endText = closestElement(range.endContainer, '.txt');
    var body = startText && startText.closest('.transcript-body');
    if (!body || !endText || endText.closest('.transcript-body') !== body || !currentEpisode) return null;
    var start = sourceOffsetBefore(body, range.startContainer, range.startOffset);
    var end = sourceOffsetBefore(body, range.endContainer, range.endOffset);
    if (end <= start) return null;
    var source = sourceForEpisode(currentEpisode);
    var original = source.slice(start, end);
    if (!original.trim()) return null;
    var segments = Array.prototype.slice.call(body.querySelectorAll('.transcript-seg'));
    var startSeg = segments.indexOf(startText.closest('.transcript-seg'));
    var endSeg = segments.indexOf(endText.closest('.transcript-seg'));
    var data = episodeData(currentEpisode);
    if (!data || startSeg < 0 || endSeg < 0) return null;
    return {
      episode: currentEpisode,
      original: original,
      anchor: {
        exact: original,
        prefix: source.slice(Math.max(0, start - 32), start),
        suffix: source.slice(end, Math.min(source.length, end + 32)),
        start: start,
        end: end,
        startSegment: startSeg,
        endSegment: endSeg,
        startTime: data.segments[startSeg].start,
        endTime: data.segments[endSeg].end
      },
      timecode: fmtTime(data.segments[startSeg].start),
      sourceUrl: window.location.href
    };
  }

  function maybeShowMenu() {
    window.setTimeout(function() {
      var target = targetFromSelection();
      if (!target) return;
      selectedTarget = target;
      var range = window.getSelection().getRangeAt(0);
      var rect = range.getBoundingClientRect();
      var menu = document.getElementById('proofreading-menu');
      menu.classList.add('open');
      var left = Math.min(Math.max(8, rect.left + window.scrollX), window.scrollX + window.innerWidth - 160);
      menu.style.left = left + 'px';
      menu.style.top = (rect.bottom + window.scrollY + 6) + 'px';
    }, 0);
  }

  function closeMenu() { document.getElementById('proofreading-menu').classList.remove('open'); }

  function mainFieldCopy(type) {
    if (type === 'asr_error') return { label: '正确写法（可留空）', placeholder: '例如：顾颉刚', help: '保留空白表示先标记，稍后回听或查证。' };
    if (type === 'annotation') return { label: '附注主题或说明方向（可留空）', placeholder: '例如：补充人物背景与代表著作', help: '附注由编辑统一核实和撰写。' };
    if (type === 'fact_error') return { label: '建议更正或待查事实（可留空）', placeholder: '例如：应为玄孙，不是曾孙', help: '事实勘误不直接改动主播原话。' };
    if (type === 'uncertain') return { label: '待查写法或听感（可留空）', placeholder: '例如：疑似为“攒尖式”', help: '用于听不清、断句或专有名词存疑的地方。' };
    return { label: '建议的正确写法（可留空）', placeholder: '如果不确定，可以只提交原文位置', help: '提交后由编辑回听和核实，不会直接改动文本。' };
  }

  function openModal(type) {
    if (!selectedTarget) return;
    closeMenu();
    activeType = type;
    var modal = document.getElementById('proofreading-modal');
    var copy = mainFieldCopy(type);
    modal.querySelector('#proofreading-dialog-title').textContent = labels[type];
    modal.querySelector('#proofreading-quote').textContent = selectedTarget.original;
    modal.querySelector('#proofreading-location').textContent = 'EP' + String(selectedTarget.episode).padStart(3, '0') + ' · ' + selectedTarget.timecode;
    modal.querySelector('#proofreading-main-label span').textContent = copy.label;
    var input = modal.querySelector('#proofreading-main-input');
    input.placeholder = copy.placeholder;
    input.value = '';
    modal.querySelector('#proofreading-comment').value = '';
    modal.querySelector('#proofreading-comment-label span').textContent = '说明（可选）';
    modal.querySelector('#proofreading-form-status').textContent = '';
    modal.querySelector('.submit').textContent = '保存标记';
    modal.querySelector('#proofreading-turnstile').innerHTML = '<div class="proofreading-help">' + copy.help + '</div>';
    modal.classList.add('open');
    input.focus();
  }

  function closeModal() {
    document.getElementById('proofreading-modal').classList.remove('open');
    activeType = null;
  }

  function setupTurnstile() {
    if (!config.turnstileSiteKey) return;
    turnstileToken = '';
    var slot = document.getElementById('proofreading-turnstile');
    slot.innerHTML = '<div id="proofreading-turnstile-widget"></div>';
    var render = function() {
      if (!window.turnstile) return;
      if (turnstileWidgetId !== null && window.turnstile.remove) window.turnstile.remove(turnstileWidgetId);
      turnstileWidgetId = window.turnstile.render('#proofreading-turnstile-widget', {
        sitekey: config.turnstileSiteKey,
        callback: function(token) { turnstileToken = token; },
        'expired-callback': function() { turnstileToken = ''; }
      });
    };
    if (window.turnstile) { render(); return; }
    var script = document.querySelector('script[data-proofreading-turnstile]');
    if (script) { script.addEventListener('load', render, { once: true }); return; }
    script = document.createElement('script');
    script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
    script.async = true;
    script.defer = true;
    script.dataset.proofreadingTurnstile = 'true';
    script.addEventListener('load', render, { once: true });
    document.head.appendChild(script);
  }

  async function submitModal(event) {
    event.preventDefault();
    if (!selectedTarget || !activeType) return;
    var modal = document.getElementById('proofreading-modal');
    var status = modal.querySelector('#proofreading-form-status');
    var suggestion = modal.querySelector('#proofreading-main-input').value.trim();
    var comment = modal.querySelector('#proofreading-comment').value.trim();
    var mark = {
      id: crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random(),
      createdAt: new Date().toISOString(),
      kind: activeType,
      episode: selectedTarget.episode,
      timecode: selectedTarget.timecode,
      original: selectedTarget.original,
      suggestion: suggestion,
      comment: comment,
      anchor: selectedTarget.anchor,
      sourceUrl: selectedTarget.sourceUrl
    };
    var marks = readMarks();
    marks.push(mark);
    writeMarks(marks);
    closeModal();
    renderProofreadingUi();
  }

  function renderProofreadingUi() {
    var view = document.querySelector('.transcript-view');
    if (!view || !currentEpisode) return;
    var toolbar = view.querySelector('.proofreading-toolbar');
    var panel = view.querySelector('.proofreading-panel');
    if (!toolbar || !panel) return;
    var allMarks = readMarks();
    var episodeMarks = marksForEpisode(currentEpisode);
    toolbar.querySelector('.proofreading-count').textContent = '本机草稿 ' + episodeMarks.length + ' 条 · 全部 ' + allMarks.length + ' 条';
    var list = panel.querySelector('.proofreading-list');
    if (!episodeMarks.length) {
      list.innerHTML = '<div class="proofreading-empty">选择转录文字即可标记。草稿仅保存在当前浏览器，导出后可交给 LLM 或人工整理。</div>';
      return;
    }
    list.innerHTML = episodeMarks.map(function(mark) {
      var kind = labels[mark.kind] || mark.kind;
      return '<div class="proofreading-item">' +
        '<span class="proofreading-kind ' + escapeHtml(mark.kind) + '">' + escapeHtml(kind) + '</span>' +
        '<div><div class="proofreading-original">' + escapeHtml(mark.original) + '</div><div class="proofreading-meta">' + escapeHtml(mark.timecode) + (mark.suggestion ? ' → ' + escapeHtml(mark.suggestion) : '') + '</div></div>' +
        '<span><button class="proofreading-icon-btn" data-jump="' + escapeHtml(mark.id) + '">定位</button> <button class="proofreading-icon-btn" data-delete="' + escapeHtml(mark.id) + '">删除</button></span>' +
      '</div>';
    }).join('');
  }

  function createToolbar() {
    var view = document.querySelector('.transcript-view');
    if (!view || view.querySelector('.proofreading-toolbar')) return;
    var header = view.querySelector('.transcript-header');
    var toolbar = document.createElement('div');
    toolbar.className = 'proofreading-toolbar';
    toolbar.innerHTML = '<button class="proofreading-btn primary" data-action="toggle">校对标记</button><button class="proofreading-btn" data-action="export-json">导出 JSON</button><button class="proofreading-btn" data-action="export-md">导出 Markdown</button><span class="proofreading-count"></span>';
    header.appendChild(toolbar);
    var panel = document.createElement('section');
    panel.className = 'proofreading-panel';
    panel.innerHTML = '<div class="proofreading-panel-head"><span>本期校对草稿</span><div class="proofreading-panel-actions"><button class="proofreading-icon-btn" data-action="clear-episode">清空本期</button></div></div><div class="proofreading-list"></div>';
    header.insertAdjacentElement('afterend', panel);
    toolbar.addEventListener('click', handleToolbarAction);
    panel.addEventListener('click', handlePanelAction);
    document.querySelector('.transcript-body').querySelectorAll('.transcript-seg').forEach(function(seg, index) { seg.dataset.segmentIndex = index; });
    renderProofreadingUi();
  }

  function handleToolbarAction(event) {
    var action = event.target.getAttribute('data-action');
    if (!action) return;
    if (action === 'toggle') document.querySelector('.proofreading-panel').classList.toggle('open');
    if (action === 'export-json') downloadExport('json');
    if (action === 'export-md') downloadExport('md');
  }

  function handlePanelAction(event) {
    var id = event.target.getAttribute('data-delete');
    if (id) {
      writeMarks(readMarks().filter(function(mark) { return mark.id !== id; }));
      renderProofreadingUi();
      return;
    }
    id = event.target.getAttribute('data-jump');
    if (id) {
      var mark = readMarks().find(function(item) { return item.id === id; });
      var segment = mark && document.querySelector('.transcript-seg[data-segment-index="' + mark.anchor.startSegment + '"]');
      if (segment) segment.scrollIntoView({ behavior: 'smooth', block: 'center' });
      return;
    }
    if (event.target.getAttribute('data-action') === 'clear-episode') {
      if (window.confirm('清空本期所有本机校对标记？')) {
        writeMarks(readMarks().filter(function(mark) { return mark.episode !== currentEpisode; }));
        renderProofreadingUi();
      }
    }
  }

  function exportPayload() {
    return { schemaVersion: 1, exportedAt: new Date().toISOString(), marks: readMarks() };
  }

  function exportMarkdown(payload) {
    var byEpisode = {};
    payload.marks.forEach(function(mark) { (byEpisode[mark.episode] || (byEpisode[mark.episode] = [])).push(mark); });
    var output = '# 壁下观校对标记\n\n导出时间：' + payload.exportedAt + '\n\n';
    Object.keys(byEpisode).sort(function(a, b) { return Number(a) - Number(b); }).forEach(function(ep) {
      output += '## EP' + String(ep).padStart(3, '0') + '\n\n';
      byEpisode[ep].forEach(function(mark) {
        output += '- [' + (labels[mark.kind] || mark.kind) + '] ' + mark.timecode + '：' + mark.original + '\n';
        if (mark.suggestion) output += '  - 建议：' + mark.suggestion + '\n';
        if (mark.comment) output += '  - 说明：' + mark.comment + '\n';
        output += '  - 定位：' + mark.anchor.start + '-' + mark.anchor.end + '\n';
      });
      output += '\n';
    });
    return output;
  }

  function downloadExport(format) {
    var payload = exportPayload();
    var isJson = format === 'json';
    var content = isJson ? JSON.stringify(payload, null, 2) : exportMarkdown(payload);
    var blob = new Blob([content], { type: isJson ? 'application/json;charset=utf-8' : 'text/markdown;charset=utf-8' });
    var link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'bixiaguan-proofreading-marks-' + new Date().toISOString().slice(0, 10) + '.' + (isJson ? 'json' : 'md');
    link.click();
    window.setTimeout(function() { URL.revokeObjectURL(link.href); }, 0);
  }

  function enhanceTranscript(epNum) {
    currentEpisode = epNum;
    createToolbar();
  }

  function init() {
    addUi();
    var originalShowFullTranscript = window.showFullTranscript;
    window.showFullTranscript = function(epNum) {
      originalShowFullTranscript(epNum);
      enhanceTranscript(epNum);
    };
    document.addEventListener('mouseup', maybeShowMenu);
    document.addEventListener('touchend', maybeShowMenu);
    document.addEventListener('keydown', function(event) {
      if (event.key === 'Escape') { closeMenu(); closeModal(); }
      if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') maybeShowMenu();
    });
    document.addEventListener('click', function(event) {
      var menu = document.getElementById('proofreading-menu');
      if (!menu.contains(event.target)) closeMenu();
    });
  }

  init();
})();
