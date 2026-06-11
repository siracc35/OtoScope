document.addEventListener("DOMContentLoaded", () => {
  const sendBtn = document.getElementById("sendBtn");
  const loadingContainer = document.getElementById("loadingContainer");
  const statusEl = document.getElementById("status");
  const openAppBtn = document.getElementById("openAppBtn");

  sendBtn.addEventListener("click", async () => {
    sendBtn.classList.add("hidden");
    loadingContainer.classList.remove("hidden");
    statusEl.className = "";
    statusEl.innerText = "";
    openAppBtn.classList.add("hidden");

    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

      if (!tab.url.includes("sahibinden.com") && !tab.url.includes("arabam.com")) {
        throw new Error("Lütfen bir sahibinden.com veya arabam.com ilan sayfasına gidin.");
      }

      const [{ result: text }] = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: () => {
          let container = document.getElementById("classifiedDetail") || document.body;
          let clone = container.cloneNode(true);
          clone.querySelectorAll("script, style, noscript").forEach((t) => t.remove());
          return clone.innerText.replace(/\s+/g, " ").trim();
        },
      });

      if (!text) throw new Error("İlan metni bulunamadı.");

      // Route through background service worker to avoid mixed-content block.
      const response = await chrome.runtime.sendMessage({ type: "ANALYZE", text });

      if (!response.ok) throw new Error(response.error);

      loadingContainer.classList.add("hidden");
      statusEl.classList.add("success");
      statusEl.innerText = "✓ Analiz tamamlandı! OtoScope'u açın.";
      openAppBtn.dataset.id = response.id;
      openAppBtn.classList.remove("hidden");
    } catch (error) {
      loadingContainer.classList.add("hidden");
      sendBtn.classList.remove("hidden");
      statusEl.classList.add("error");
      statusEl.innerText = error.message;
    }
  });

  openAppBtn.addEventListener("click", async () => {
    const id = openAppBtn.dataset.id;
    const base = "https://otoscope-production.up.railway.app";
    const targetUrl = `${base}${id ? `?id=${id}` : ""}`;

    const [existing] = await chrome.tabs.query({ url: `${base}/*` });
    if (existing) {
      chrome.tabs.update(existing.id, { url: targetUrl, active: true });
      chrome.windows.update(existing.windowId, { focused: true });
    } else {
      chrome.tabs.create({ url: targetUrl });
    }
  });
});
