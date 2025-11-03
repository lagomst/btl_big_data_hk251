// Helper to create a KB card element
function makeKbCard(kb) {
  // kb may be string or object
  const id = typeof kb === 'string' ? kb : (kb.id || kb.name || JSON.stringify(kb));
  const name = typeof kb === 'string' ? kb : (kb.name || id);
  const description = (typeof kb === 'object' && kb.description) ? kb.description : '';
  const docCount = (typeof kb === 'object' && kb.document_count != null) ? kb.document_count : '-';

  const li = document.createElement('li');
  li.className = 'kb-item';
  li.dataset.kbId = id;

  li.innerHTML = `
    <div class="kb-name">${escapeHtml(name)}</div>
    <div class="kb-description">${escapeHtml(description)}</div>
    <div class="kb-stats">
      <span>Documents: ${escapeHtml(String(docCount))}</span>
      <span class="kb-actions" style="margin-left:8px;"></span>
    </div>
    <button class="select-button">Select</button>
  `;

  // select click
  li.querySelector('.select-button').addEventListener('click', () => {
    selectKnowledgeBase(id, li);
  });

  // add a small delete button
  const actions = li.querySelector('.kb-actions');
  const delBtn = document.createElement('button');
  delBtn.textContent = 'Delete';
  delBtn.style.marginLeft = '0.5rem';
  delBtn.onclick = (e) => {
    e.stopPropagation();
    if (!confirm('Delete knowledge base ' + id + '?')) return;
    deleteKnowledgeBase(id).then(ok => {
      if (ok) li.remove();
    });
  };
  actions.appendChild(delBtn);

  return li;
}

function escapeHtml(str) {
  return str.replace(/[&<>"']/g, (m) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]));
}

async function loadKnowledgeBases() {
  const list = document.querySelector('.kb-list');
  list.innerHTML = '<li>Loading...</li>';
  try {
    const res = await fetch('/v1/rag/knowledge');
    const json = await res.json();
    const data = json.data || json; // fallback if shape differs
    list.innerHTML = '';
    if (!data || data.length === 0) {
      list.innerHTML = '<li>No knowledge bases found.</li>';
      return;
    }
    data.forEach(kb => {
      list.appendChild(makeKbCard(kb));
    });
  } catch (err) {
    list.innerHTML = '<li>Error loading knowledge bases</li>';
    console.error(err);
  }
}

async function selectKnowledgeBase(kbName, cardElement = null) {
  window.location.href = `/knowledge-base/${encodeURIComponent(kbName)}`;
  // optimistic UI
  // document.querySelectorAll('.kb-item.selected').forEach(el => el.classList.remove('selected'));
  // if (cardElement) cardElement.classList.add('selected');
  
  // try {
  //   const params = new URLSearchParams({ knowledge: kbName });
  //   const res = await fetch(`/v1/rag/knowledge/model?${params}`, {
  //     method: 'GET',
  //     headers: { 'Content-Type': 'application/json' }
  //   });
  //   const json = await res.json();
  //   if (json.status != 'success') {
  //     alert('Select failed: ' + (json.message || JSON.stringify(json)));
  //   }
    
  // } catch (err) {
  //   console.error('Select error', err);
  //   alert('Error selecting knowledge base');
  // }
}

async function createKnowledgeBase(name) {
  try {
    const res = await fetch(`/v1/rag/knowledge/${encodeURIComponent(name)}`, { method: 'POST' });
    // console.log(res)
    const json = await res.json();
    if (json.status === 'success') {
      await loadKnowledgeBases(); // reload list
      return true;
    } else {
      alert('Create failed: ' + (json.message || JSON.stringify(json)));
      return false;
    }
  } catch (err) {
    console.error(err);
    alert('Create error');
    return false;
  }
}

async function deleteKnowledgeBase(name) {
  try {
    const res = await fetch(`/v1/rag/knowledge/${encodeURIComponent(name)}`, { method: 'DELETE' });
    const json = await res.json();
    if (json.status === 'success') {
      return true;
    } else {
      alert('Delete failed: ' + (json.message || JSON.stringify(json)));
      return false;
    }
  } catch (err) {
    console.error(err);
    alert('Delete error');
    return false;
  }
}

// On page ready
document.addEventListener('DOMContentLoaded', () => {
  loadKnowledgeBases();

  // optional: wire a create form if present
  const createForm = document.getElementById('kb-create-form');
  if (createForm) {
    createForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const name = document.getElementById('kb-create-name').value.trim();
      if (!name) return alert('Enter a name');
      const ok = await createKnowledgeBase(name);
      if (ok) document.getElementById('kb-create-name').value = '';
    });
  }
});