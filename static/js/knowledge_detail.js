const filesTableBody = document.querySelector('#filesTable tbody');
const uploadForm = document.getElementById('uploadForm');
const uploadStatus = document.getElementById('uploadStatus');
const searchBtn = document.getElementById('searchBtn');
const queryInput = document.getElementById('query');

async function fetchFiles(query = '') {
  const url = `/v1/rag/search-files?knowledge=${encodeURIComponent(kb)}${query ? `&prefix=${encodeURIComponent(query)}` : ''}`;
  const res = await fetch(url);
  const data = await res.json();

  filesTableBody.innerHTML = '';
  if (data.status === 'success' && data.data.length > 0) {
    data.data.forEach(doc => {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td>${doc.file_path}</td>
        <td>${doc.content_summary || '(no preview)'}</td>
        <td>${doc.status}</td>
        <td>${doc.updated_at}</td>
        <td>${doc.chunks_count ?? '-'}</td>
        <td><button onclick="deleteFile('${doc.file_path}')">Delete</button></td>
      `;
      filesTableBody.appendChild(row);
    });
  } else {
    filesTableBody.innerHTML = `<tr><td colspan="6">No documents found</td></tr>`;
  }
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
