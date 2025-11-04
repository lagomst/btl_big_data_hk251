const filesTableBody = document.querySelector('#filesTable tbody');
const uploadForm = document.getElementById('uploadForm');
const uploadStatus = document.getElementById('uploadStatus');
const searchBtn = document.getElementById('searchBtn');
const queryInput = document.getElementById('query');
const chatWindow = document.getElementById('chat-window');
const chatForm = document.getElementById('chat-form');
const userInput = document.getElementById('user-input');

if (chatForm && userInput) {
  chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const question = userInput.value.trim();
    if (!question) return;

    addMessage('user', question);
    userInput.value = '';

      try {
        const params = new URLSearchParams({
          knowledge: kb,
          str_query: question
        });

        // Show spinner in input area
        let spinner = document.getElementById('chat-spinner');
        if (!spinner) {
          spinner = document.createElement('span');
          spinner.id = 'chat-spinner';
          spinner.className = 'spinner';
          const inputWrap = document.querySelector('.chat-input-wrap');
          if (inputWrap) inputWrap.appendChild(spinner);
        }

        // ensure spinner visible
        spinner.style.display = 'inline-block';

        const res = await fetch(`/v1/rag/query-stream?${params}`);
        const json = await res.json();

        // hide spinner
        spinner.style.display = 'none';

        if (json.status === 'success') {
          const d = json.data;
          const responseText = d.content || '(no content)';
          const timeText = d.time ? `🕒 Took ${d.time.toFixed(2)}s` : '';
          addMessage('bot', `${responseText}\n\n${timeText}`);
          appendAnswer(responseText, timeText);
        } else {
          addMessage('bot', `❌ Error: ${json.message}`);
        }
      } catch (err) {
        console.error(err);
        // hide spinner if present
        const spinner = document.getElementById('chat-spinner');
        if (spinner) spinner.style.display = 'none';
        addMessage('bot', `⚠️ Failed to reach server`);
      }
  });
} else {
  // If chat form or input is not present, log a small warning so it's easy to debug
  console.debug('Chat form or input not found on this page; chat features are disabled.');
}

function addMessage(sender, text) {
  // Safe guard: chatWindow may be absent on pages that don't include the chat UI
  if (!chatWindow) {
    // Fallback: print to console so messages aren't lost during debugging
    console.log(`[${sender}] ${text}`);
    return;
  }

  const div = document.createElement('div');
  div.className = `message ${sender}`;
  div.innerText = text;
  chatWindow.appendChild(div);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function truncateWords(text, limit = 32) {
  if (!text) return '';

  const words = text.split(/\s+/);
  let result = '';
  let length = 0;

  for (const word of words) {
    // +1 for the space (except the first word)
    const extra = result.length ? 1 : 0;
    if (length + word.length + extra > limit) break;

    result += (result ? ' ' : '') + word;
    length += word.length + extra;
  }

  return result.trim();
}

function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str).replace(/[&<>"']/g, (m) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  }[m]));
}

async function fetchFiles(query = '') {
  const url = `/v1/rag/search-files?knowledge=${encodeURIComponent(kb)}${query ? `&prefix=${encodeURIComponent(query)}` : ''}`;
  const res = await fetch(url);
  const data = await res.json();
  filesTableBody.innerHTML = '';
  if (data.status === 'success') {
    let docs = data.data;
    if (!Array.isArray(docs)) {
      // Maybe it’s an object with a 'docs' field
      if (docs.docs && Array.isArray(docs.docs)) {
        docs = docs.docs;
      } else {
        // Maybe it's a dict of filename -> doc
        docs = Object.values(docs);
      }
    }

    if (docs.length === 0) {
      filesTableBody.innerHTML = `<tr><td colspan="6">No documents found</td></tr>`;
      return;
    }

    docs.forEach(doc => {
      const row = document.createElement('tr');
      row.innerHTML = `
      <td>${doc.file_path}</td>
      <td>${truncateWords(doc.content_summary) + "..." || '(no preview)'}</td>
      <td>${doc.status}</td>
      <td>${doc.updated_at}</td>
      <td>${doc.chunks_count ?? '-'}</td>
      <td><button onclick="deleteFile('${doc.file_path}')" rendered="doc.status == success">Delete</button></td>
    `;
      filesTableBody.appendChild(row);
    });
  } else {
    filesTableBody.innerHTML = `<tr><td colspan="6">Error while fetching files!/td></tr>`;
  }

}

// Append an answer to the end-of-page answers list
function appendAnswer(text, meta = '') {
  let answers = document.getElementById('answer-list');
  if (!answers) {
    // create an answers container at bottom if not present
    const section = document.createElement('section');
    section.className = 'answer-section container';
    section.innerHTML = `\n      <h2>Answers</h2>\n      <div id="answer-list" class="answer-list"></div>\n    `;
    document.body.appendChild(section);
    answers = document.getElementById('answer-list');
  }

  const card = document.createElement('div');
  card.className = 'answer-card';
  const metaHtml = meta ? `<div class="answer-meta">${meta}</div>` : '';
  card.innerHTML = `${metaHtml}<div class="answer-content">${escapeHtml(text)}</div>`;
  answers.appendChild(card);
  // Scroll answers area to bottom
  answers.scrollTop = answers.scrollHeight;
}

async function deleteFile(filePath) {
  if (!confirm(`Delete file: ${filePath}?`)) return;
  const res = await fetch(`/v1/rag/delete-file?knowledge=${encodeURIComponent(kb)}&raw_filename=${encodeURIComponent(filePath)}`, {
    method: 'DELETE'
  });
  const data = await res.json();
  alert(data.message);
  fetchFiles(queryInput.value);
}

uploadForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const file = document.getElementById('file').files[0];
  const useOCR = document.getElementById('use_ocr').checked;

  if (!file) {
    alert('Please select a file.');
    return;
  }

  const formData = new FormData();
  formData.append('file', file);
  formData.append('use_ocr', useOCR);

  uploadStatus.textContent = 'Uploading...';
  const res = await fetch(`/v1/rag/insert-file?knowledge=${encodeURIComponent(kb)}`, {
    method: 'POST',
    body: formData
  });
  const data = await res.json();

  uploadStatus.textContent = data.message;
  fetchFiles(); // refresh after upload
});

searchBtn.addEventListener('click', () => fetchFiles(queryInput.value));

// Load on start
fetchFiles();

// Chat widget toggle (collapse/expand)
(function setupChatToggle() {
  const chatToggle = document.getElementById('chat-toggle');
  const chatWidget = document.getElementById('chat-widget');
  if (!chatToggle || !chatWidget) return;

  // Set initial state attributes
  chatToggle.setAttribute('aria-expanded', String(!chatWidget.classList.contains('collapsed')));

  chatToggle.addEventListener('click', (e) => {
    e.preventDefault();
    const nowCollapsed = chatWidget.classList.toggle('collapsed');
    chatToggle.innerText = nowCollapsed ? '+' : '✕';
    chatToggle.setAttribute('aria-expanded', String(!nowCollapsed));
  });

  // Also allow clicking the header to toggle
  const header = chatWidget.querySelector('.chat-header');
  if (header) {
    header.addEventListener('dblclick', () => {
      const nowCollapsed = chatWidget.classList.toggle('collapsed');
      chatToggle.innerText = nowCollapsed ? '+' : '✕';
      chatToggle.setAttribute('aria-expanded', String(!nowCollapsed));
    });
  }
})();
