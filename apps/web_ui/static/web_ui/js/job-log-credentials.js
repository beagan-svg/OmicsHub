(() => {
  const panel = document.getElementById("job-log-credentials");
  if (!panel) return;

  const form = panel.querySelector("[data-job-log-credentials-form]");
  const pasteField = panel.querySelector("#jlc-paste");
  const submitBtn = panel.querySelector("[data-job-log-credentials-submit]");
  const clearBtn = panel.querySelector("[data-job-log-credentials-clear]");
  const statusPill = panel.querySelector("[data-job-log-credentials-status-pill]");
  const credentialsToggle = panel.querySelector("[data-job-log-credentials-toggle]");
  const credentialsIcon = panel.querySelector("[data-job-log-credentials-icon]");
  const identityBlock = panel.querySelector("[data-job-log-credentials-identity]");
  const accountField = panel.querySelector("[data-job-log-credentials-account]");
  const arnField = panel.querySelector("[data-job-log-credentials-arn]");
  const expiryField = panel.querySelector("[data-job-log-credentials-expiry]");

  const statusUrl = panel.dataset.statusUrl;
  const submitUrl = panel.dataset.submitUrl;
  const clearUrl = panel.dataset.clearUrl;
  const logsUrlTemplate = panel.dataset.logsUrlTemplate;
  const logsUrlFor = (demandId, stage) =>
    `${logsUrlTemplate.replace("DEMAND_ID", encodeURIComponent(demandId))}?stage=${encodeURIComponent(stage)}`;

  // Whether THIS session currently has AWS-validated credentials, per the server -- never
  // the credential values themselves, which never reach this script at all. Every log
  // fetch below still re-checks with the server; this only gates whether the eye icon is
  // clickable, and is not itself the security boundary.
  let valid = false;

  const csrfToken = () => form.querySelector("[name=csrfmiddlewaretoken]").value;

  // Pulled out of whatever was pasted -- an `export FOO="bar"` block (AWS SSO/CLI's own
  // output shape), bare `FOO=bar`, or just the three values on their own lines all match.
  // Nothing here is sent anywhere by itself; parseCredentials only produces the same
  // three values the view has always read from three separate fields.
  const parseCredentials = (text) => {
    const extract = (name) => {
      const match = text.match(new RegExp(`${name}\\s*=\\s*["']?([^"'\\s]+)`));
      return match ? match[1] : "";
    };
    return {
      accessKey: extract("AWS_ACCESS_KEY_ID"),
      secretKey: extract("AWS_SECRET_ACCESS_KEY"),
      sessionToken: extract("AWS_SESSION_TOKEN"),
    };
  };

  const post = (url, body) =>
    fetch(url, {
      method: "POST",
      headers: {"X-CSRFToken": csrfToken(), "X-Requested-With": "XMLHttpRequest"},
      body,
    }).then((response) => response.json().then((data) => ({ok: response.ok, data})));

  const setPill = (state, text, detail) => {
    statusPill.dataset.state = state;
    statusPill.textContent = text;
    // The specific AWS-provided reason (e.g. "AWS rejected these credentials.") lives in
    // a native tooltip rather than the pill's own text, so the pill stays one of a fixed
    // small set of words -- required/validating/valid/expired/failed -- and the detail
    // is still reachable on hover instead of being discarded outright.
    statusPill.title = detail || "";
  };

  // ExpiredToken(Exception) is the one AWS error code that means "this exact session is
  // past its lifetime," distinct from every other rejection reason (bad signature,
  // insufficient permissions, malformed value, etc.), which this app groups together as
  // a generic "failed" rather than trying to explain each one in the pill itself.
  const EXPIRED_CODES = new Set(["ExpiredToken", "ExpiredTokenException"]);

  const updateCredentialsToggle = () => {
    const open = document.getElementById("jlc-body")?.dataset.open === "true";
    credentialsToggle.setAttribute("aria-expanded", String(open));
    credentialsToggle.setAttribute(
      "aria-label",
      `${open ? "Collapse" : "Expand"} the AWS credentials panel`
    );
    credentialsIcon.classList.toggle("bi-eye", open);
    credentialsIcon.classList.toggle("bi-eye-slash", !open);
  };

  const setLogTogglesEnabled = (enabled) => {
    document.querySelectorAll("[data-job-log-toggle]").forEach((toggle) => {
      toggle.disabled = !enabled;
    });
  };

  const activeLogRequests = new Map();
  const retryAfterRefresh = new Set();
  const requestIsCurrent = (demandId, request) => {
    const panel = request.body.closest("[data-job-log-panel]");
    return (
      activeLogRequests.get(demandId) === request &&
      request.body.isConnected &&
      panel?.dataset.open === "true"
    );
  };
  const cancelLogRequest = (demandId) => {
    const request = activeLogRequests.get(demandId);
    if (!request) return;
    request.controller.abort();
    activeLogRequests.delete(demandId);
  };
  const cancelAllLogRequests = () => {
    activeLogRequests.forEach(({controller}, demandId) => {
      retryAfterRefresh.add(demandId);
      controller.abort();
    });
    activeLogRequests.clear();
  };

  const showRequired = () => {
    valid = false;
    identityBlock.hidden = true;
    clearBtn.hidden = true;
    submitBtn.hidden = false;
    form.hidden = false;
    setPill("unknown", "Credentials required");
    setLogTogglesEnabled(false);
  };

  const showValid = (account, arn) => {
    valid = true;
    accountField.textContent = account;
    arnField.textContent = arn;
    // Always this, for every credential set validated through GetCallerIdentity: AWS
    // never reports an expiration for a manually-supplied temporary session, and this
    // app does not guess one from the session token's structure. See showFailed below
    // for the one case that overrides it -- an explicit AWS rejection.
    expiryField.textContent = "Cannot be determined automatically.";
    identityBlock.hidden = false;
    form.hidden = true;
    submitBtn.hidden = true;
    clearBtn.hidden = false;
    setPill("done", "Credentials valid");
    setLogTogglesEnabled(true);
  };

  // Covers both an initial validation rejection and a later AWS rejection during a log
  // fetch (the server has already evicted the cached credentials either way) -- the
  // pill only ever distinguishes "expired" from a generic "failed"; the AWS-provided
  // detail (code + message) goes in the pill's tooltip instead of its visible text.
  const showFailed = (code, message) => {
    valid = false;
    identityBlock.hidden = true;
    clearBtn.hidden = false;
    submitBtn.hidden = false;
    form.hidden = false;
    const label = EXPIRED_CODES.has(code) ? "Credentials expired" : "Credentials failed";
    setPill("fail", label, message);
    setLogTogglesEnabled(false);
  };

  const loadStatus = async () => {
    try {
      const response = await fetch(statusUrl, {headers: {"X-Requested-With": "XMLHttpRequest"}});
      const data = await response.json();
      if (data.status === "valid") {
        showValid(data.account, data.arn);
      } else {
        showRequired();
      }
    } catch {
      showRequired();
    }
  };

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const {accessKey, secretKey, sessionToken} = parseCredentials(pasteField.value);
    if (!accessKey || !secretKey || !sessionToken) {
      showFailed(
        "MissingValue",
        "Couldn't find all three values (access key, secret key, session token) in that text."
      );
      return;
    }

    setPill("running", "Validating…");
    submitBtn.disabled = true;
    const body = new FormData();
    body.set("csrfmiddlewaretoken", csrfToken());
    body.set("access_key", accessKey);
    body.set("secret_key", secretKey);
    body.set("session_token", sessionToken);
    try {
      const {ok, data} = await post(submitUrl, body);
      if (ok && data.status === "valid") {
        showValid(data.account, data.arn);
        form.reset();
      } else {
        showFailed(data.code, data.message || "AWS rejected these credentials.");
      }
    } catch {
      showFailed("Unreachable", "Could not reach the server.");
    } finally {
      submitBtn.disabled = false;
    }
  });

  const doClear = async () => {
    cancelAllLogRequests();
    retryAfterRefresh.clear();
    try {
      await post(clearUrl, new FormData());
    } finally {
      form.reset();
      showRequired();
    }
  };

  clearBtn.addEventListener("click", doClear);

  pasteField.addEventListener("input", () => {
    clearBtn.hidden = pasteField.value.length === 0;
  });

  document.addEventListener("click", (event) => {
    if (!event.target.closest("[data-job-log-credentials-toggle]")) return;
    window.requestAnimationFrame(updateCredentialsToggle);
  });
  updateCredentialsToggle();

  // --- per-row log fetch -----------------------------------------------------------

  const formatLine = (event) => {
    const time = new Date(event.timestamp).toISOString().replace("T", " ").slice(0, 19);
    const line = document.createElement("div");
    line.className = "job-log-viewer__line";
    const ts = document.createElement("span");
    ts.className = "job-log-viewer__ts";
    ts.textContent = time;
    const msg = document.createElement("span");
    msg.className = "job-log-viewer__msg";
    msg.textContent = event.message;
    line.append(ts, msg);
    return line;
  };

  const renderLogs = (body, events) => {
    body.innerHTML = "";
    if (!events.length) {
      const empty = document.createElement("p");
      empty.className = "text-secondary mb-0";
      empty.textContent = "No log lines yet.";
      body.appendChild(empty);
      return;
    }
    const viewer = document.createElement("div");
    viewer.className = "job-log-viewer";
    events.forEach((event) => viewer.appendChild(formatLine(event)));
    body.appendChild(viewer);
  };

  const renderMessage = (body, text) => {
    body.innerHTML = "";
    const message = document.createElement("p");
    message.className = "text-secondary mb-0";
    message.textContent = text;
    body.appendChild(message);
  };

  const fetchLogsFor = async (demandId, stage, body, showLoading = true) => {
    cancelLogRequest(demandId);
    const controller = new AbortController();
    const request = {controller, body};
    activeLogRequests.set(demandId, request);
    if (showLoading) renderMessage(body, "Loading…");
    try {
      const response = await fetch(logsUrlFor(demandId, stage), {
        headers: {"X-Requested-With": "XMLHttpRequest"},
        signal: controller.signal,
      });
      const data = await response.json();
      if (!requestIsCurrent(demandId, request)) return;
      if (response.ok && data.status === "ok") {
        renderLogs(body, data.events);
        return;
      }
      if (data.status === "no_credentials") {
        renderMessage(body, "Provide AWS credentials above to view this job's container logs.");
        showRequired();
        return;
      }
      if (data.status === "not_visible") {
        renderMessage(body, "This job's logs are not available to view.");
        return;
      }
      // An AWS rejection here means the credentials themselves are no good any more
      // (the server has already evicted them) -- reflect that in the shared panel too,
      // not only in this one row.
      renderMessage(body, data.message || "Could not load logs for this job.");
      if (response.status === 401) {
        showFailed(data.code, data.message || "These credentials have expired.");
      }
    } catch (error) {
      if (error.name === "AbortError" || !requestIsCurrent(demandId, request)) return;
      renderMessage(body, "Could not reach the server.");
    } finally {
      if (activeLogRequests.get(demandId) === request) activeLogRequests.delete(demandId);
    }
  };

  // Delegated on `document`, not bound per-button with a "did I already bind this"
  // guard: an HTML attribute like data-job-log-bound survives an innerHTML round trip
  // (the Job Monitor and Failures pages' periodic table refresh does exactly that) even
  // though the addEventListener it was guarding does not -- a per-element guard reads as
  // "already handled" on a brand new node that in fact has no listener at all, so it
  // silently gets skipped forever after the first refresh. Delegation has no such state
  // to go stale: the DOM is re-queried at the moment of the click, not once at bind time.
  document.addEventListener("click", (event) => {
    const toggle = event.target.closest("[data-job-log-toggle]");
    if (!toggle || toggle.disabled) return;
    const demandId = toggle.dataset.demandId;
    const stage = toggle.dataset.stage;
    const targetPanel = document.getElementById(toggle.getAttribute("aria-controls"));
    if (!targetPanel) return;
    const body = targetPanel.querySelector("[data-job-log-body]");
    // disclosure.js already flips data-open/aria-expanded on the same click; this only
    // adds the fetch-and-render behavior, and only when the panel is opening.
    window.requestAnimationFrame(() => {
      if (targetPanel.dataset.open === "true" && body) {
        fetchLogsFor(demandId, stage, body);
      } else {
        cancelLogRequest(demandId);
      }
    });
  });
  document.addEventListener("joblog:before-refresh", cancelAllLogRequests);
  document.addEventListener("joblog:refreshed", () => {
    setLogTogglesEnabled(valid);
    retryAfterRefresh.forEach((demandId) => {
      const toggle = document.querySelector(`[data-job-log-toggle][data-demand-id="${demandId}"]`);
      const targetPanel = toggle && document.getElementById(toggle.getAttribute("aria-controls"));
      const body = targetPanel?.querySelector("[data-job-log-body]");
      if (valid && targetPanel?.dataset.open === "true" && body) {
        fetchLogsFor(demandId, toggle.dataset.stage, body, false);
      }
      retryAfterRefresh.delete(demandId);
    });
  });

  setLogTogglesEnabled(valid);
  loadStatus();
})();
