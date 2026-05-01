/* ──────────────────────────────────────────────────────────
   Wumpus World — Frontend Application
   ────────────────────────────────────────────────────────── */

// ─── API Helpers ─────────────────────────────────────────
async function postJSON(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {})
  });
  if (!res.ok) throw new Error('HTTP ' + res.status);
  return await res.json();
}

async function getJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error('HTTP ' + res.status);
  return await res.json();
}

// ─── DOM Helpers ─────────────────────────────────────────
const $ = (id) => document.getElementById(id);

// ─── State ───────────────────────────────────────────────
let autoRunInterval = null;
let isAutoRunning = false;

// ─── Render ──────────────────────────────────────────────
function render(state) {
  // Status badge
  const badge = $('statusBadge');
  const statusText = state.metrics.status;
  badge.textContent = statusText;
  badge.className = 'badge';
  if (statusText === 'Exploring') {
    badge.classList.add('exploring');
  } else if (statusText === 'Game Over' || statusText.includes('pit') || statusText.includes('wumpus')) {
    badge.classList.add('game-over');
  } else if (statusText.includes('complete')) {
    badge.classList.add('complete');
  }

  // Metrics
  $('agentPos').textContent = `(${state.agent.r}, ${state.agent.c})`;
  $('currentPercepts').textContent = state.percepts_list.length ? state.percepts_list.join(', ') : 'None';
  $('movesCount').textContent = state.metrics.moves;
  $('inferenceSteps').textContent = state.metrics.inference_steps;
  $('kbClauses').textContent = state.metrics.kb_clauses;
  $('currentQuery').textContent = state.decision.current_query || '—';

  // Buttons
  $('btnStep').disabled = !state.metrics.can_step;
  $('btnAutoRun').disabled = !state.metrics.can_step && !isAutoRunning;

  // Stop auto-run if game ended
  if (!state.metrics.can_step && isAutoRunning) {
    stopAutoRun();
  }

  // Render grid
  renderGrid(state);

  // Render decision log
  renderDecisionLog(state.decision.log);

  // Update stats
  updateStats();
}

function renderGrid(state) {
  const grid = $('grid');
  grid.style.gridTemplateColumns = `repeat(${state.cols}, 68px)`;

  // Adaptive sizing
  const w = window.innerWidth;
  let cellSize = 68;
  if (w <= 1200) cellSize = 56;
  if (w <= 960) cellSize = 50;
  grid.style.gridTemplateColumns = `repeat(${state.cols}, ${cellSize}px)`;

  grid.innerHTML = '';

  for (let r = 0; r < state.rows; r++) {
    for (let c = 0; c < state.cols; c++) {
      const cell = document.createElement('div');
      cell.className = 'cell';

      const isAgent = (state.agent.r === r && state.agent.c === c);
      const isVisited = state.visited[r][c];
      const isSafe = state.safe[r][c];
      const danger = state.danger[r][c]; // 0 none, 1 pit, 2 wumpus

      let label = '?';
      let cls = 'unknown';

      if (isAgent) {
        label = '🤖';
        cls = 'agent-cell';
      } else if (danger === 1) {
        label = '🕳️';
        cls = 'danger-cell';
      } else if (danger === 2) {
        label = '👹';
        cls = 'danger-cell';
      } else if (isVisited) {
        label = '✓';
        cls = 'visited';
      } else if (isSafe) {
        label = '✔';
        cls = 'safe-cell';
      }

      cell.classList.add(cls);

      // Cell label
      const labelEl = document.createElement('span');
      labelEl.className = 'cell-label';
      labelEl.textContent = label;
      cell.appendChild(labelEl);

      // Coordinate
      const coord = document.createElement('span');
      coord.className = 'cell-coord';
      coord.textContent = `${r},${c}`;
      cell.appendChild(coord);

      // Percept indicators
      if (isVisited && state.percept_map) {
        const p = state.percept_map[r][c];
        if (p.breeze || p.stench) {
          const percContainer = document.createElement('div');
          percContainer.className = 'cell-percepts';

          if (p.breeze) {
            const dot = document.createElement('span');
            dot.className = 'percept-dot percept-breeze';
            dot.textContent = '~';
            dot.title = 'Breeze';
            percContainer.appendChild(dot);
          }
          if (p.stench) {
            const dot = document.createElement('span');
            dot.className = 'percept-dot percept-stench';
            dot.textContent = '!';
            dot.title = 'Stench';
            percContainer.appendChild(dot);
          }

          cell.appendChild(percContainer);
        }
      }

      grid.appendChild(cell);
    }
  }
}

function renderDecisionLog(log) {
  const container = $('decisionLog');

  if (!log || log.length === 0) {
    container.innerHTML = '<div class="empty-state">Start a game to see agent decisions</div>';
    return;
  }

  container.innerHTML = '';
  for (const entry of log) {
    const el = document.createElement('div');
    el.className = 'decision-entry';
    if (entry.msg.includes('DEATH')) {
      el.classList.add('death');
    }

    const step = document.createElement('div');
    step.className = 'decision-step';
    step.textContent = entry.step;

    const msg = document.createElement('div');
    msg.className = 'decision-msg';
    msg.textContent = entry.msg;

    el.appendChild(step);
    el.appendChild(msg);
    container.appendChild(el);
  }

  // Auto-scroll to bottom
  container.scrollTop = container.scrollHeight;
}

async function updateStats() {
  try {
    const stats = await getJSON('/api/stats');
    $('winsCount').textContent = stats.wins;
    $('lossesCount').textContent = stats.losses;
    $('episodesCount').textContent = stats.total_episodes;
  } catch {
    // ignore
  }
}

async function refreshKB() {
  try {
    const data = await getJSON('/api/kb_clauses');
    const container = $('clauseViewer');
    if (!data.clauses || data.clauses.length === 0) {
      container.innerHTML = '<div class="empty-state">No clauses yet</div>';
      return;
    }
    container.innerHTML = '';
    data.clauses.forEach((clause, i) => {
      const line = document.createElement('div');
      line.className = 'clause-line';
      line.textContent = `${i + 1}. ${clause}`;
      container.appendChild(line);
    });
  } catch {
    // ignore
  }
}

async function refreshTrace() {
  try {
    const data = await getJSON('/api/resolution_trace');
    const container = $('traceViewer');
    if (!data.trace || data.trace.length === 0) {
      container.innerHTML = `<div class="empty-state">${data.query ? 'Query: ' + data.query : 'Run a step to see resolution trace'}</div>`;
      return;
    }
    container.innerHTML = '';
    const queryEl = document.createElement('div');
    queryEl.className = 'clause-line';
    queryEl.style.fontWeight = '700';
    queryEl.style.color = 'var(--blue-600)';
    queryEl.textContent = `Query: ${data.query}`;
    container.appendChild(queryEl);

    data.trace.forEach((step, i) => {
      const line = document.createElement('div');
      line.className = 'clause-line';
      line.textContent = `${i + 1}. ${step}`;
      container.appendChild(line);
    });
  } catch {
    // ignore
  }
}

// ─── Actions ─────────────────────────────────────────────
async function newGame() {
  const rows = parseInt($('inputRows').value || '4', 10);
  const cols = parseInt($('inputCols').value || '4', 10);
  const pits = parseInt($('inputPits').value || '3', 10);

  stopAutoRun();
  const state = await postJSON('/api/new', { rows, cols, pits });
  render(state);
  refreshKB();
}

async function resetGame() {
  stopAutoRun();
  const state = await postJSON('/api/reset', {});
  render(state);
  refreshKB();
}

async function step() {
  const state = await postJSON('/api/step', {});
  render(state);
  refreshKB();
  refreshTrace();
}

function toggleAutoRun() {
  if (isAutoRunning) {
    stopAutoRun();
  } else {
    startAutoRun();
  }
}

function startAutoRun() {
  isAutoRunning = true;
  const btn = $('btnAutoRun');
  btn.classList.add('running');
  btn.innerHTML = `
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
    Stop
  `;

  const speed = parseInt($('inputSpeed').value || '500', 10);
  autoRunInterval = setInterval(async () => {
    try {
      await step();
    } catch {
      stopAutoRun();
    }
  }, speed);
}

function stopAutoRun() {
  isAutoRunning = false;
  if (autoRunInterval) {
    clearInterval(autoRunInterval);
    autoRunInterval = null;
  }
  const btn = $('btnAutoRun');
  btn.classList.remove('running');
  btn.innerHTML = `
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/><line x1="19" y1="3" x2="19" y2="21"/></svg>
    Auto-Run
  `;
}

// ─── Event Listeners ─────────────────────────────────────
$('btnNew').addEventListener('click', () => {
  newGame().catch(err => console.error(err));
});

$('btnReset').addEventListener('click', () => {
  resetGame().catch(err => console.error(err));
});

$('btnStep').addEventListener('click', () => {
  step().catch(err => console.error(err));
});

$('btnAutoRun').addEventListener('click', () => {
  toggleAutoRun();
});

$('inputSpeed').addEventListener('input', (e) => {
  $('speedLabel').textContent = e.target.value + 'ms';
  // If auto-running, restart with new speed
  if (isAutoRunning) {
    stopAutoRun();
    startAutoRun();
  }
});

$('btnRefreshKB').addEventListener('click', () => {
  refreshKB();
});

// ─── Initial Load ────────────────────────────────────────
(async () => {
  try {
    const state = await postJSON('/api/state', {});
    render(state);
    refreshKB();
  } catch {
    // ignore on first load
  }
})();
