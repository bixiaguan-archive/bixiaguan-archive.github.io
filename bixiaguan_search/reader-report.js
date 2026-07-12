(function() {
  'use strict';

  var isLocal = location.hostname === 'localhost' || location.hostname === '127.0.0.1' || location.hostname === '::1';
  if (isLocal) return;

  var config = window.CROWD_REPORT_CONFIG || {};
  var currentEpisode = null;
  var selectedTarget = null;
  var turnstileWidgetId = null;
  var turnstileToken = '';

  var css = `
    .reader-report-menu { display:none; position:absolute; z-index:1200; padding:4px; border:1px solid #ded5cb; border-radius:6px; background:#fff; box-shadow:0 5px 18px rgba(0,0,0,.16); }
    .reader-report-menu.open { display:block; }
    .reader-report-menu button { border:0; background:none; padding:7px 10px; border-radius:3px; color:#6c5448; font:inherit; font-size:.8rem; cursor:pointer; }
    .reader-report-menu button:hover { background:#fff3e8; color:#a83a3a; }
    .reader-report-modal { display:none; position:fixed; z-index:1300; inset:0; background:rgba(44,44,44,.34); padding:16px; align-items:center; justify-content:center; }
    .reader-report-modal.open { display:flex; }
    .reader-report-dialog { width:min(520px, 100%); max-height:90vh; overflow:auto; background:#fff; border-radius:8px; box-shadow:0 8px 30px rgba(0,0,0,.22); }
    .reader-report-head { display:flex; align-items:center; justify-content:space-between; gap:12px; padding:14px 16px; border-bottom:1px solid #e8e2da; background:#fdfcfa; }
    .reader-report-head strong { font-size:.98rem; }
    .reader-report-close { border:0; background:none; color:#777; padding:0 3px; font-size:1.4rem; line-height:1; cursor:pointer; }
    .reader-report-body { padding:14px 16px 16px; }
    .reader-report-quote { padding:9px 10px; background:#faf8f5; border-left:3px solid #c9b7a7; color:#555; font-size:.85rem; line-height:1.65; overflow-wrap:anywhere; }
    .reader-report-location { margin-top:5px; color:#888; font:.73rem 'Courier New', monospace; }
    .reader-report-field { display:block; margin-top:13px; color:#555; font-size:.82rem; }
    .reader-report-field input, .reader-report-field textarea { width:100%; margin-top:5px; padding:8px 9px; border:1px solid #d8cfc5; border-radius:4px; color:#333; font:inherit; font-size:.86rem; }
    .reader-report-field textarea { min-height:76px; resize:vertical; }
    .reader-report-help { color:#888; font-size:.74rem; line-height:1.6; margin-top:5px; }
    .reader-report-status { min-height:1.3em; margin-top:10px; color:#a83a3a; font-size:.78rem; }
    .reader-report-actions { display:flex; justify-content:flex-end; gap:8px; margin-top:14px; }
    .reader-report-actions button { border:1px solid #d8cfc5; border-radius:4px; padding:7px 11px; background:#fff; color:#555; font:inherit; font-size:.82rem; cursor:pointer; }
    .reader-report-actions .submit { background:#6c5448; border-color:#6c5448; color:#fff; }
    .reader-report-actions .submit:hover { background:#513d34; }
    .reader-report-turnstile { margin-top:13px; }
  `;

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
    var text = '';
    holder.querySelectorAll('.txt').forEach(function(textEl) { text += textWithoutBadges(textEl); });
    return text;
  }

  function sourceOffsetBefore(body, node, offset) {
    var prefix = document.createRange();
    prefix.selectNodeContents(body);
    prefix.setEnd(node, offset);
    return transcriptTextFromFragment(prefix.cloneContents()).length;
  }

  function episodeData(ep) {
    return (window.INDEX || []).find(function(item) { return item.ep === ep; });
  }

  function targetFromSelection() {
    var selection = window.getSelection();
    if (!selection || selection.rangeCount !== 1 || selection.isCollapsed || !currentEpisode) return null;
    var range = selection.getRangeAt(0);
    var startText = closestElement(range.startContainer, '.txt');
    var endText = closestElement(range.endContainer, '.txt');
    var body = startText && startText.closest('.transcript-body');
    if (!body || !endText || endText.closest('.transcript-body') !== body) return null;
    var start = sourceOffsetBefore(body, range.startContainer, range.startOffset);
    var end = sourceOffsetBefore(body, range.endContainer, range.endOffset);
    var data = episodeData(currentEpisode);
    if (!data || end <= start) return null;
    var source = data.segments.map(function(segment) { return segment.text || ''; }).join('');
    var original = source.slice(start, end);
    if (!original.trim()) return null;
    var segments = Array.prototype.slice.call(body.querySelectorAll('.transcript-seg'));
    var startSeg = segments.indexOf(startText.closest('.transcript-seg'));
    var endSeg = segments.indexOf(endText.closest('.transcript-seg'));
    if (startSeg < 0 || endSeg < 0) return null;
    return {
      episode: currentEpisode,
      original: original,
      timecode: fmtTime(data.segments[startSeg].start),
      sourceUrl: window.location.href,
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
      }
    };
  }

  function closeMenu() { document.getElementById('reader-report-menu').classList.remove('open'); }

  function maybeShowMenu() {
    window.setTimeout(function() {
      var target = targetFromSelection();
      if (!target) return;
      selectedTarget = target;
      var rect = window.getSelection().getRangeAt(0).getBoundingClientRect();
      var menu = document.getElementById('reader-report-menu');
      menu.classList.add('open');
      menu.style.left = Math.min(Math.max(8, rect.left + window.scrollX), window.scrollX + window.innerWidth - 155) + 'px';
      menu.style.top = (rect.bottom + window.scrollY + 6) + 'px';
    }, 0);
  }

  function closeModal() { document.getElementById('reader-report-modal').classList.remove('open'); }

  function setupTurnstile() {
    if (!config.turnstileSiteKey) return;
    turnstileToken = '';
    var slot = document.getElementById('reader-report-turnstile');
    slot.innerHTML = '<div id="reader-report-turnstile-widget"></div>';
    var render = function() {
      if (!window.turnstile) return;
      if (turnstileWidgetId !== null && window.turnstile.remove) window.turnstile.remove(turnstileWidgetId);
      turnstileWidgetId = window.turnstile.render('#reader-report-turnstile-widget', {
        sitekey: config.turnstileSiteKey,
        callback: function(token) { turnstileToken = token; },
        'expired-callback': function() { turnstileToken = ''; }
      });
    };
    if (window.turnstile) { render(); return; }
    var script = document.querySelector('script[data-reader-turnstile]');
    if (script) { script.addEventListener('load', render, { once: true }); return; }
    script = document.createElement('script');
    script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
    script.async = true;
    script.defer = true;
    script.dataset.readerTurnstile = 'true';
    script.addEventListener('load', render, { once: true });
    document.head.appendChild(script);
  }

  function openModal() {
    if (!selectedTarget) return;
    closeMenu();
    var modal = document.getElementById('reader-report-modal');
    modal.querySelector('.reader-report-quote').textContent = selectedTarget.original;
    modal.querySelector('.reader-report-location').textContent = 'EP' + String(selectedTarget.episode).padStart(3, '0') + ' · ' + selectedTarget.timecode;
    modal.querySelector('input').value = '';
    modal.querySelector('textarea').value = '';
    modal.querySelector('.reader-report-status').textContent = '';
    modal.classList.add('open');
    setupTurnstile();
    modal.querySelector('input').focus();
  }

  async function submitReport(event) {
    event.preventDefault();
    var modal = document.getElementById('reader-report-modal');
    var status = modal.querySelector('.reader-report-status');
    if (!config.endpoint) { status.textContent = '报错服务暂未开放，请稍后再试。'; return; }
    var submit = modal.querySelector('.submit');
    submit.disabled = true;
    submit.textContent = '提交中…';
    status.textContent = '';
    try {
      var response = await fetch(config.endpoint, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          episode: selectedTarget.episode,
          timecode: selectedTarget.timecode,
          original: selectedTarget.original,
          suggestion: modal.querySelector('input').value.trim(),
          comment: modal.querySelector('textarea').value.trim(),
          anchor: selectedTarget.anchor,
          sourceUrl: selectedTarget.sourceUrl,
          turnstileToken: turnstileToken
        })
      });
      var data = await response.json().catch(function() { return {}; });
      if (!response.ok) throw new Error(data.error || '提交失败，请稍后再试。');
      closeModal();
      alert('已收到。感谢你帮助校对转录文本。');
    } catch (error) {
      status.textContent = error.message || '提交失败，请稍后再试。';
    } finally {
      submit.disabled = false;
      submit.textContent = '提交报错';
    }
  }

  function addUi() {
    var style = document.createElement('style');
    style.textContent = css;
    document.head.appendChild(style);
    var menu = document.createElement('div');
    menu.id = 'reader-report-menu';
    menu.className = 'reader-report-menu';
    menu.innerHTML = '<button>报告转录错误</button>';
    document.body.appendChild(menu);
    menu.addEventListener('mousedown', function(event) { event.preventDefault(); });
    menu.addEventListener('click', openModal);

    var modal = document.createElement('div');
    modal.id = 'reader-report-modal';
    modal.className = 'reader-report-modal';
    modal.innerHTML = '<div class="reader-report-dialog" role="dialog" aria-modal="true" aria-label="报告转录错误">' +
      '<div class="reader-report-head"><strong>报告转录错误</strong><button class="reader-report-close" aria-label="关闭">&times;</button></div>' +
      '<form class="reader-report-body"><div class="reader-report-quote"></div><div class="reader-report-location"></div>' +
      '<label class="reader-report-field">建议的正确写法（可留空）<input maxlength="300" placeholder="如果不确定，可以只提交原文位置"></label>' +
      '<label class="reader-report-field">补充说明（可选）<textarea maxlength="1000"></textarea></label>' +
      '<div id="reader-report-turnstile" class="reader-report-turnstile"><div class="reader-report-help">提交后由编辑回听和核实，不会直接改动文本。</div></div>' +
      '<div class="reader-report-status" role="status"></div><div class="reader-report-actions"><button type="button" data-close>取消</button><button type="submit" class="submit">提交报错</button></div></form></div>';
    document.body.appendChild(modal);
    modal.querySelector('.reader-report-close').addEventListener('click', closeModal);
    modal.querySelector('[data-close]').addEventListener('click', closeModal);
    modal.addEventListener('click', function(event) { if (event.target === modal) closeModal(); });
    modal.querySelector('form').addEventListener('submit', submitReport);
  }

  function init() {
    addUi();
    var originalShowFullTranscript = window.showFullTranscript;
    window.showFullTranscript = function(epNum) {
      originalShowFullTranscript(epNum);
      currentEpisode = epNum;
    };
    document.addEventListener('mouseup', maybeShowMenu);
    document.addEventListener('touchend', maybeShowMenu);
    document.addEventListener('keydown', function(event) { if (event.key === 'Escape') { closeMenu(); closeModal(); } });
    document.addEventListener('click', function(event) {
      var menu = document.getElementById('reader-report-menu');
      if (!menu.contains(event.target)) closeMenu();
    });
  }

  init();
})();
