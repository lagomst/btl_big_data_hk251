document.getElementById('uploadForm').addEventListener('submit', async (e) => {
  e.preventDefault();

  const kb = document.getElementById('knowledge').value.trim();
  const fileInput = document.getElementById('file');
  const fileUrl = document.getElementById('file_url').value.trim();
  const useOCR = document.getElementById('use_ocr').checked;
  const statusDiv = document.getElementById('uploadStatus');

  if (!kb) {
    alert('Please enter a knowledge base name.');
    return;
  }

  const formData = new FormData();
  if (fileInput.files.length > 0) formData.append('file', fileInput.files[0]);
  if (fileUrl) formData.append('file_url', fileUrl);
  formData.append('use_ocr', useOCR);

  try {
    statusDiv.textContent = 'Uploading...';

    const res = await fetch(`/v1/rag/insert-file?knowledge=${encodeURIComponent(kb)}`, {
      method: 'POST',
      body: formData
    });

    const data = await res.json();
    if (data.status === 'success') {
      statusDiv.textContent = `✅ ${data.message}`;
    } else {
      statusDiv.textContent = `❌ ${data.message}`;
      console.error(data.data);
    }
  } catch (err) {
    statusDiv.textContent = '❌ Upload failed.';
    console.error(err);
  }
});
