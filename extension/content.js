(function () {
  if (document.getElementById("otoscope-floating-btn")) return;

  const btn = document.createElement("button");
  btn.id = "otoscope-floating-btn";
  btn.innerText = "OtoScope ile Analiz Et";

  Object.assign(btn.style, {
    position: "fixed",
    bottom: "20px",
    right: "20px",
    backgroundColor: "#FFE800",
    color: "#0a0a0a",
    border: "none",
    padding: "15px 20px",
    fontFamily: "monospace",
    fontSize: "14px",
    fontWeight: "bold",
    cursor: "pointer",
    zIndex: "999999",
    borderRadius: "4px",
    boxShadow: "0 4px 12px rgba(0,0,0,0.5)",
    transition: "all 0.2s ease",
  });

  btn.addEventListener("mouseover", () => (btn.style.opacity = "0.9"));
  btn.addEventListener("mouseout", () => (btn.style.opacity = "1"));

  btn.addEventListener("click", async () => {
    const originalText = btn.innerText;
    btn.innerText = "Analiz ediliyor...";
    btn.disabled = true;
    btn.style.opacity = "0.7";

    try {
      let container = document.getElementById("classifiedDetail") || document.body;
      let clone = container.cloneNode(true);
      clone.querySelectorAll("script, style, noscript").forEach((t) => t.remove());
      const text = clone.innerText.replace(/\s+/g, " ").trim();

      // Route through background service worker to avoid mixed-content block.
      const response = await chrome.runtime.sendMessage({ type: "ANALYZE", text });

      if (!response.ok) throw new Error(response.error);

      btn.innerText = "✓ Tamamlandı";
      btn.style.backgroundColor = "#55ff55";

      setTimeout(() => {
        window.open(`http://localhost:5174?id=${response.id}`, "_blank");
        btn.innerText = originalText;
        btn.style.backgroundColor = "#FFE800";
        btn.disabled = false;
        btn.style.opacity = "1";
      }, 1500);
    } catch (err) {
      btn.innerText = "Hata! Tekrar Dene";
      btn.style.backgroundColor = "#ff5555";
      btn.style.color = "#fff";

      setTimeout(() => {
        btn.innerText = originalText;
        btn.style.backgroundColor = "#FFE800";
        btn.style.color = "#0a0a0a";
        btn.disabled = false;
        btn.style.opacity = "1";
      }, 3000);
    }
  });

  document.body.appendChild(btn);
})();
