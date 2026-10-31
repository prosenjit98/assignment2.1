const form = document.getElementById('classify-form');
const textarea = document.getElementById('text');
const submitButton = document.getElementById('submit');
const placeholder = document.getElementById('placeholder');
const resultEl = document.getElementById('result');
const charCount = document.getElementById('char-count');

// Builds DOM nodes; text always goes through text nodes, never innerHTML.
function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === 'class') node.className = value;
    else node.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

function show(node) {
  placeholder.hidden = true;
  resultEl.hidden = false;
  resultEl.replaceChildren(node);
}

function field(label, ...value) {
  return el('div', { class: 'field' }, el('div', { class: 'label' }, label), el('div', {}, ...value));
}

function renderResult(r) {
  const pct = Math.round(r.confidence * 100);
  const meta = r.meta || {};
  const usage = meta.usage;

  const callouts = [];
  if (r.needs_clarification) {
    callouts.push(el('div', { class: 'callout callout-warn' },
      el('strong', {}, 'Needs clarification. '), 'Suggested follow-up: ',
      el('em', {}, r.clarifying_question)));
  }
  if (r.needs_human_review && !r.needs_clarification) {
    const reasons = r.warnings.length ? r.warnings.join(' ') : `Confidence is below 60%.`;
    callouts.push(el('div', { class: 'callout callout-review' },
      el('strong', {}, 'Flagged for human review. '), reasons));
  }

  const metaParts = [`source: ${meta.source}`];
  if (meta.model) metaParts.push(`model: ${meta.model}`);
  if (meta.latency_ms !== undefined) metaParts.push(`${meta.latency_ms} ms`);
  if (usage) {
    metaParts.push(`tokens in/out: ${usage.input_tokens}/${usage.output_tokens}`);
    if (usage.cached_input_tokens) metaParts.push(`cached: ${usage.cached_input_tokens}`);
  }

  show(el('div', {},
    el('div', { class: 'result-head' },
      el('div', {},
        el('div', { class: 'label' }, 'Category / subcategory'),
        el('div', { class: 'category' }, r.category, el('span', { class: 'sub' }, ` › ${r.subcategory}`))),
      el('div', { class: `priority p-${r.priority.toLowerCase()}` }, r.priority)),
    ...callouts,
    field('Routed to', r.routed_to),
    field('Summary', r.summary),
    field('Confidence',
      el('div', { class: 'meter' }, el('div', { class: 'meter-fill', style: `width:${pct}%` })),
      el('span', { class: 'meter-value' }, `${pct}%`)),
    r.secondary_categories.length
      ? field('Also involves', ...r.secondary_categories.map((c) => el('span', { class: 'chip' }, c)))
      : null,
    field('Rationale', r.rationale),
    el('div', { class: 'meta' }, metaParts.join(' · ')),
    el('details', { class: 'json', open: '' },
      el('summary', {}, 'JSON response'),
      el('pre', {}, JSON.stringify(r, null, 2)))));
}

function renderError(message) {
  show(el('div', { class: 'callout callout-error' }, el('strong', {}, 'Could not classify. '), message));
}

async function classify(text) {
  submitButton.disabled = true;
  submitButton.textContent = 'Classifying…';
  resultEl.classList.add('loading');
  try {
    const response = await fetch('/api/classify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    });
    const body = await response.json();
    if (response.ok) renderResult(body);
    else renderError(body.error || response.statusText);
  } catch (err) {
    renderError(err.message);
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = 'Classify';
    resultEl.classList.remove('loading');
  }
}

function updateCount() {
  charCount.textContent = textarea.value.length;
}

form.addEventListener('submit', (event) => {
  event.preventDefault();
  classify(textarea.value);
});

textarea.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) form.requestSubmit();
});
textarea.addEventListener('input', updateCount);

document.querySelectorAll('.example').forEach((button) => {
  button.addEventListener('click', () => {
    textarea.value = button.dataset.text;
    updateCount();
    classify(button.dataset.text);
  });
});

updateCount();
const initial = JSON.parse(document.getElementById('initial-result').textContent);
if (initial) {
  if (initial.status === 200) renderResult(initial.body);
  else renderError(initial.body.error);
}
