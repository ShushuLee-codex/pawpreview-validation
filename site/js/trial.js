(function () {
  const API_BASE = "https://pawpreview-validation.onrender.com";
  const form = document.getElementById("trial-form");
  if (!form) return;

  const waitEl = document.getElementById("form-wait");
  const errEl = document.getElementById("form-errors");
  const successEl = document.getElementById("form-success");
  const submitBtn = document.getElementById("submit-btn");

  function showErrors(messages) {
    errEl.innerHTML = messages.map((m) => "<div>" + escapeHtml(m) + "</div>").join("");
    errEl.hidden = messages.length === 0;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function setWaiting(on, label) {
    waitEl.hidden = !on;
    if (label) {
      const strong = waitEl.querySelector("strong");
      if (strong) strong.textContent = label;
    }
    submitBtn.disabled = on;
    form.setAttribute("aria-busy", on ? "true" : "false");
  }

  async function fetchWithTimeout(url, options, timeoutMs) {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), timeoutMs);
    try {
      return await fetch(url, { ...options, signal: ctrl.signal });
    } finally {
      clearTimeout(t);
    }
  }

  async function wakeService() {
    setWaiting(true, "Waking the trial form…");
    const delays = [0, 4000, 8000];
    let lastErr = "Could not reach the trial form.";
    for (let i = 0; i < delays.length; i++) {
      if (delays[i]) await new Promise((r) => setTimeout(r, delays[i]));
      try {
        const res = await fetchWithTimeout(API_BASE + "/health", { cache: "no-store" }, 90000);
        if (res.ok) return true;
        lastErr = "The trial form is not ready yet (status " + res.status + ").";
      } catch (err) {
        lastErr = "Still waiting for the trial form to wake up.";
      }
      setWaiting(true, "Still waking the trial form…");
    }
    throw new Error(lastErr + " Please try again in a moment.");
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    showErrors([]);
    if (!form.reportValidity()) return;

    const payload = {
      store_url: form.store_url.value,
      email: form.email.value,
      category: form.category.value,
      monthly_orders: form.monthly_orders.value,
      pay_range: form.pay_range.value,
      wanted_feature: form.wanted_feature.value,
      company_website: form.company_website.value
    };

    try {
      await wakeService();
      setWaiting(true, "Submitting your request…");
      const res = await fetchWithTimeout(
        API_BASE + "/apply",
        {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify(payload)
        },
        90000
      );
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.ok) {
        const msgs = data.errors && data.errors.length ? data.errors : [data.error || "Submission failed. Please try again."];
        throw new ErrorList(msgs);
      }
      form.hidden = true;
      successEl.hidden = false;
      waitEl.hidden = true;
      successEl.scrollIntoView({ behavior: "smooth", block: "center" });
    } catch (err) {
      const msgs = err instanceof ErrorList ? err.messages : [err.message || "Something went wrong. Please try again."];
      showErrors(msgs);
      setWaiting(false);
    }
  });

  function ErrorList(messages) {
    this.messages = messages;
    this.message = messages.join(" ");
  }
})();
