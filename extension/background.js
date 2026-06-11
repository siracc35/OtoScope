chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type !== "ANALYZE") return;

  fetch("https://otoscope-production.up.railway.app/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: message.text }),
  })
    .then((r) => {
      if (!r.ok) throw new Error(`API Hatası: ${r.status}`);
      return r.json();
    })
    .then((data) => sendResponse({ ok: true, data, id: data.id }))
    .catch((err) => sendResponse({ ok: false, error: err.message }));

  return true; // async response
});
