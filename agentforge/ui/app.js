/**
 * AgentForge Web UI Dashboard Controller
 * Real-time event streaming, interactive pipeline visualizer, and proof inspection.
 */

document.addEventListener("DOMContentLoaded", () => {
  // DOM Elements
  const serverStatusBadge = document.getElementById("serverStatusBadge");
  const serverStatusText = document.getElementById("serverStatusText");
  const btnDemoMode = document.getElementById("btnDemoMode");

  const iterationBadge = document.getElementById("iterationBadge");
  const pipelineGlobalStatus = document.getElementById("pipelineGlobalStatus");

  const nodes = {
    identity: document.getElementById("nodeIdentity"),
    execution: document.getElementById("nodeExecution"),
    review: document.getElementById("nodeReview"),
    proof: document.getElementById("nodeProof"),
    gate: document.getElementById("nodeMergeGate"),
  };

  const badges = {
    identity: document.getElementById("badgeIdentity"),
    execution: document.getElementById("badgeExecution"),
    review: document.getElementById("badgeReview"),
    proof: document.getElementById("badgeProof"),
    gate: document.getElementById("badgeMergeGate"),
  };

  const connectors = [
    document.getElementById("connector-1"),
    document.getElementById("connector-2"),
    document.getElementById("connector-3"),
    document.getElementById("connector-4"),
  ];

  const taskForm = document.getElementById("taskForm");
  const promptInput = document.getElementById("promptInput");
  const repoPathInput = document.getElementById("repoPathInput");
  const maxIterationsInput = document.getElementById("maxIterationsInput");
  const btnLaunch = document.getElementById("btnLaunchPipeline");

  const confidenceValue = document.getElementById("confidenceValue");
  const gaugeCircle = document.getElementById("gaugeCircle");
  const proofStatusPill = document.getElementById("proofStatusPill");
  const statTestsPassed = document.getElementById("statTestsPassed");
  const statTestsFailed = document.getElementById("statTestsFailed");
  const statUnrelatedChanges = document.getElementById("statUnrelatedChanges");
  const criteriaProofList = document.getElementById("criteriaProofList");

  const reviewStatusPill = document.getElementById("reviewStatusPill");
  const reviewSummaryBox = document.getElementById("reviewSummaryBox");
  const issuesList = document.getElementById("issuesList");
  const diffViewer = document.getElementById("diffViewer");
  const diffStatsBadge = document.getElementById("diffStatsBadge");

  const terminalLogs = document.getElementById("terminalLogs");
  const btnClearAudit = document.getElementById("btnClearAudit");

  const mergeGateModal = document.getElementById("mergeGateModal");
  const modalTaskId = document.getElementById("modalTaskId");
  const modalConfidence = document.getElementById("modalConfidence");
  const modalEvidenceSummary = document.getElementById("modalEvidenceSummary");
  const btnCloseModal = document.getElementById("btnCloseModal");
  const btnRejectModal = document.getElementById("btnRejectModal");
  const btnApprovePR = document.getElementById("btnApprovePR");

  let currentTaskId = null;
  let activeEventSource = null;

  // Preset prompts
  document.querySelectorAll(".pill-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      promptInput.value = btn.getAttribute("data-prompt") || "";
      promptInput.focus();
    });
  });

  // Clear Audit Log
  btnClearAudit.addEventListener("click", () => {
    terminalLogs.innerHTML = "";
    addAuditLog("SYSTEM", "Audit terminal cleared.");
  });

  // Modal Close
  btnCloseModal.addEventListener("click", () => mergeGateModal.classList.add("hidden"));
  btnRejectModal.addEventListener("click", () => mergeGateModal.classList.add("hidden"));

  // Check Backend Health
  async function checkBackendHealth() {
    try {
      const res = await fetch("/api/tasks");
      if (res.ok) {
        serverStatusBadge.style.display = "flex";
        serverStatusText.textContent = "Backend Active";
      }
    } catch {
      serverStatusText.textContent = "Offline / Demo Mode";
      serverStatusBadge.style.borderColor = "var(--amber)";
      serverStatusBadge.querySelector(".status-dot").style.background = "var(--amber)";
    }
  }
  checkBackendHealth();

  // Audit Log Append
  function addAuditLog(actor, message) {
    const row = document.createElement("div");
    row.className = "log-entry";

    const time = new Date().toTimeString().split(" ")[0];
    const actorClass = `actor-${actor.toLowerCase().split(":")[0]}`;

    row.innerHTML = `
      <span class="log-time">${time}</span>
      <span class="log-actor ${actorClass}">${actor}</span>
      <span class="log-msg">${escapeHtml(message)}</span>
    `;

    terminalLogs.appendChild(row);
    terminalLogs.scrollTop = terminalLogs.scrollHeight;
  }

  function escapeHtml(str) {
    if (!str) return "";
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  // Update Visualizer State
  function setNodeState(nodeKey, state) {
    const node = nodes[nodeKey];
    const badge = badges[nodeKey];
    if (!node || !badge) return;

    node.classList.remove("active", "completed");
    badge.className = "node-status-badge";

    if (state === "active") {
      node.classList.add("active");
      badge.classList.add("badge-active");
      badge.textContent = "Working";
    } else if (state === "completed") {
      node.classList.add("completed");
      badge.classList.add("badge-success");
      badge.textContent = "Done";
    } else if (state === "rejected") {
      badge.classList.add("badge-danger");
      badge.textContent = "Needs Changes";
    } else {
      badge.classList.add("badge-idle");
      badge.textContent = "Idle";
    }
  }

  function setConnectors(upToIndex) {
    connectors.forEach((conn, i) => {
      if (i < upToIndex) {
        conn.classList.add("active");
      } else {
        conn.classList.remove("active");
      }
    });
  }

  function resetPipelineUI() {
    Object.keys(nodes).forEach((key) => setNodeState(key, "idle"));
    setConnectors(0);
    setConfidence(0);
    diffViewer.innerHTML = "<code>// No git diff generated yet.</code>";
    diffStatsBadge.textContent = "0 bytes";
    issuesList.innerHTML = "";
    criteriaProofList.innerHTML = `
      <div class="empty-state-card">
        <p>No criteria evaluated yet. Launch a pipeline to generate verifiable proofs.</p>
      </div>
    `;
    proofStatusPill.className = "status-pill pill-neutral";
    proofStatusPill.textContent = "Awaiting Verification";
    reviewStatusPill.className = "status-pill pill-neutral";
    reviewStatusPill.textContent = "Awaiting Review";
    statTestsPassed.textContent = "0";
    statTestsFailed.textContent = "0";
    statUnrelatedChanges.textContent = "None Detected";
  }

  // Set Confidence Gauge
  function setConfidence(score) {
    const circumference = 314; // 2 * pi * 50
    const val = Math.round(score * 100);
    confidenceValue.textContent = `${val}%`;

    const offset = circumference - (circumference * val) / 100;
    gaugeCircle.style.strokeDashoffset = offset;

    if (score >= 0.8) {
      gaugeCircle.style.stroke = "var(--emerald)";
    } else if (score >= 0.5) {
      gaugeCircle.style.stroke = "var(--amber)";
    } else {
      gaugeCircle.style.stroke = "var(--crimson)";
    }
  }

  // Render Diff with Colors
  function renderDiff(diffText) {
    if (!diffText || diffText.trim() === "") {
      diffViewer.innerHTML = "<code>// No changes detected in diff.</code>";
      diffStatsBadge.textContent = "0 bytes";
      return;
    }

    diffStatsBadge.textContent = `${diffText.length} chars`;
    const lines = diffText.split("\n");
    let html = "";

    lines.forEach((line) => {
      const esc = escapeHtml(line);
      if (line.startsWith("+++") || line.startsWith("---") || line.startsWith("@@")) {
        html += `<span class="diff-line-header">${esc}</span>`;
      } else if (line.startsWith("+")) {
        html += `<span class="diff-line-add">${esc}</span>`;
      } else if (line.startsWith("-")) {
        html += `<span class="diff-line-del">${esc}</span>`;
      } else {
        html += `<span>${esc}</span>\n`;
      }
    });

    diffViewer.innerHTML = `<code>${html}</code>`;
  }

  // Launch Pipeline Form Submit
  taskForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const prompt = promptInput.value.trim();
    if (!prompt) return;

    btnLaunch.disabled = true;
    btnLaunch.innerHTML = `<span class="status-dot"></span> Orchestrating...`;
    resetPipelineUI();

    try {
      const payload = {
        user_prompt: prompt,
        repo_url_or_path: repoPathInput.value.trim() || ".",
        max_iterations: parseInt(maxIterationsInput.value, 10) || 2,
      };

      const res = await fetch("/api/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) throw new Error("Failed to create task");

      const data = await res.json();
      currentTaskId = data.task_id;
      addAuditLog("SYSTEM", `Task '${currentTaskId}' queued on backend. Starting SSE event stream.`);

      connectSSE(currentTaskId);
    } catch (err) {
      addAuditLog("SYSTEM", `API Error: ${err.message}. Starting Demo Simulation.`);
      startDemoSimulation(prompt);
    } finally {
      btnLaunch.disabled = false;
      btnLaunch.innerHTML = `
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
        </svg> Launch Pipeline
      `;
    }
  });

  // Connect Server-Sent Events (SSE)
  function connectSSE(taskId) {
    if (activeEventSource) activeEventSource.close();

    activeEventSource = new EventSource(`/api/tasks/${taskId}/events`);

    activeEventSource.onmessage = (e) => {
      try {
        const payload = JSON.parse(e.data);
        handlePipelineEvent(payload.event, payload.data);
      } catch (err) {
        console.error("SSE parse error", err);
      }
    };

    activeEventSource.onerror = () => {
      // Refresh task state via polling fallback
      fetchTaskState(taskId);
    };
  }

  async function fetchTaskState(taskId) {
    try {
      const res = await fetch(`/api/tasks/${taskId}`);
      if (!res.ok) return;
      const state = await res.json();
      renderFullState(state);
    } catch (err) {
      console.error(err);
    }
  }

  function handlePipelineEvent(eventType, data) {
    if (!data) return;

    if (eventType === "pipeline_started") {
      pipelineGlobalStatus.textContent = "Pipeline Active: Specifying";
      setNodeState("identity", "active");
      addAuditLog("SYSTEM", `Pipeline started for task: ${data.task_id}`);
    } else if (eventType === "state_transition") {
      const st = data.status;
      iterationBadge.textContent = `Iteration ${data.iteration || 1} of 2`;

      if (st === "specifying") {
        setNodeState("identity", "active");
        pipelineGlobalStatus.textContent = "Identity Agent analyzing requirements...";
      } else if (st === "executing") {
        setNodeState("identity", "completed");
        setConnectors(1);
        setNodeState("execution", "active");
        pipelineGlobalStatus.textContent = "Execution Agent modifying workspace...";
      } else if (st === "reviewing") {
        setNodeState("execution", "completed");
        setConnectors(2);
        setNodeState("review", "active");
        pipelineGlobalStatus.textContent = "Review Agent inspecting security & AST...";
      } else if (st === "fixing") {
        setNodeState("review", "rejected");
        setNodeState("execution", "active");
        pipelineGlobalStatus.textContent = `Fixing cycle triggered (Iteration ${data.iteration})...`;
        addAuditLog("REVIEW", "Review requested changes. Retrying execution.");
      } else if (st === "verifying") {
        setNodeState("review", "completed");
        setConnectors(3);
        setNodeState("proof", "active");
        pipelineGlobalStatus.textContent = "Proof-of-Work Agent validating objective evidence...";
      }
    } else if (eventType === "identity_completed") {
      setNodeState("identity", "completed");
      addAuditLog("IDENTITY", `Created TaskSpecification '${data.title}' with ${data.criteria_count} criteria.`);
    } else if (eventType === "execution_completed") {
      setNodeState("execution", "completed");
      addAuditLog("EXECUTION", `Executed plan: modified ${data.modified_files.length} file(s), ${data.commits.length} commit(s).`);
      fetchTaskState(currentTaskId);
    } else if (eventType === "review_completed") {
      setNodeState("review", data.review_status === "approved" ? "completed" : "rejected");
      addAuditLog("REVIEW", `Review verdict: ${data.review_status.toUpperCase()} (${data.issues_count} issue(s)).`);
      fetchTaskState(currentTaskId);
    } else if (eventType === "proof_completed") {
      setNodeState("proof", "completed");
      setConfidence(data.confidence_score || 0);
      addAuditLog("PROOF", `Objective verification verdict: ${data.verification_status.toUpperCase()} (Confidence: ${Math.round(data.confidence_score * 100)}%).`);
      fetchTaskState(currentTaskId);
    } else if (eventType === "pipeline_completed") {
      pipelineGlobalStatus.textContent = data.verified ? "VERIFIED - Ready for Human Merge Gate" : "Pipeline Failed";
      if (data.verified) {
        setConnectors(4);
        setNodeState("gate", "active");
        showMergeGateModal(data.confidence_score);
      }
      if (activeEventSource) activeEventSource.close();
    }
  }

  function renderFullState(state) {
    if (!state) return;

    // Render diff
    if (state.diff) renderDiff(state.diff);

    // Render Review Reports
    if (state.review_reports && state.review_reports.length > 0) {
      const lastReview = state.review_reports[state.review_reports.length - 1];
      reviewStatusPill.className = `status-pill ${lastReview.status === "approved" ? "pill-success" : "pill-danger"}`;
      reviewStatusPill.textContent = lastReview.status === "approved" ? "APPROVED" : "NEEDS CHANGES";
      reviewSummaryBox.innerHTML = `<p>${escapeHtml(lastReview.summary)}</p>`;

      if (lastReview.issues && lastReview.issues.length > 0) {
        issuesList.innerHTML = lastReview.issues.map((issue) => `
          <div class="issue-item">
            <div class="issue-header">
              <span class="font-mono text-cyan">${escapeHtml(issue.file)}${issue.line ? `:${issue.line}` : ""}</span>
              <span class="issue-severity sev-${issue.severity.toLowerCase()}">${issue.severity}</span>
            </div>
            <p class="issue-problem">${escapeHtml(issue.problem)}</p>
          </div>
        `).join("");
      } else {
        issuesList.innerHTML = "";
      }
    }

    // Render Proof-of-Work Report
    if (state.verification_report) {
      const rep = state.verification_report;
      setConfidence(rep.confidence_score || 0);
      proofStatusPill.className = `status-pill ${rep.status === "verified" ? "pill-success" : "pill-danger"}`;
      proofStatusPill.textContent = rep.status.toUpperCase();

      statTestsPassed.textContent = rep.tests_passed || 0;
      statTestsFailed.textContent = rep.tests_failed || 0;
      statUnrelatedChanges.textContent = rep.unrelated_changes_detected ? `Warning: ${rep.unrelated_files.join(", ")}` : "None Detected";
      statUnrelatedChanges.className = `stat-value ${rep.unrelated_changes_detected ? "val-danger" : "val-success"}`;

      if (rep.requirements && rep.requirements.length > 0) {
        criteriaProofList.innerHTML = rep.requirements.map((req) => `
          <div class="criterion-card">
            <div class="criterion-card-header">
              <span class="criterion-id">${escapeHtml(req.criterion_id)}</span>
              <span class="status-pill ${req.status === "satisfied" ? "pill-success" : "pill-danger"}">${req.status.toUpperCase()}</span>
            </div>
            <p class="criterion-desc">${escapeHtml(req.description)}</p>
            ${req.evidence_items && req.evidence_items.length > 0 ? `
              <div class="evidence-items-box">
                ${req.evidence_items.map(e => `<div>✓ ${escapeHtml(e)}</div>`).join("")}
              </div>
            ` : ""}
          </div>
        `).join("");
      }
    }
  }

  function showMergeGateModal(conf) {
    modalTaskId.textContent = currentTaskId || "task_live_01";
    modalConfidence.textContent = `${Math.round((conf || 0.95) * 100)}%`;
    mergeGateModal.classList.remove("hidden");
  }

  // Approve PR Action
  btnApprovePR.addEventListener("click", async () => {
    btnApprovePR.disabled = true;
    btnApprovePR.textContent = "Merging...";

    try {
      if (currentTaskId) {
        const res = await fetch(`/api/tasks/${currentTaskId}/approve`, { method: "POST" });
        if (res.ok) {
          const data = await res.json();
          addAuditLog("GATE", `PR merged successfully: ${data.pull_request_url}`);
          setNodeState("gate", "completed");
        }
      } else {
        setNodeState("gate", "completed");
        addAuditLog("GATE", "Human approved merge into main branch.");
      }
      setTimeout(() => {
        mergeGateModal.classList.add("hidden");
        btnApprovePR.disabled = false;
        btnApprovePR.textContent = "Approve & Merge Pull Request";
      }, 1000);
    } catch {
      mergeGateModal.classList.add("hidden");
    }
  });

  // Demo Simulator Trigger
  btnDemoMode.addEventListener("click", () => {
    promptInput.value = "Add health() check endpoint in service.py and unit tests in tests/test_service.py";
    startDemoSimulation(promptInput.value);
  });

  // Demo Simulator Logic
  function startDemoSimulation(prompt) {
    currentTaskId = "demo_task_88";
    resetPipelineUI();
    addAuditLog("SYSTEM", "Starting live Demo Simulator mode...");

    // Step 1: Identity
    setNodeState("identity", "active");
    pipelineGlobalStatus.textContent = "Identity Agent specifying requirements...";
    addAuditLog("IDENTITY", "Exploring repository layout via list_files and search_code.");

    setTimeout(() => {
      setNodeState("identity", "completed");
      setConnectors(1);
      setNodeState("execution", "active");
      pipelineGlobalStatus.textContent = "Execution Agent modifying workspace...";
      addAuditLog("IDENTITY", "Generated TaskSpecification with 2 verifiable acceptance criteria.");
      addAuditLog("EXECUTION", "Dispatching controlled tools: write_file to service.py and tests/test_service.py.");

      renderDiff(`--- a/service.py
+++ b/service.py
@@ -1,3 +1,6 @@
 def ping():
     return 'pong'
+
+def health():
+    return {'status': 'ok'}
--- a/tests/test_service.py
+++ b/tests/test_service.py
@@ -1,5 +1,9 @@
-from service import ping
+from service import ping, health

 def test_ping():
     assert ping() == 'pong'
+
+def test_health():
+    assert health()['status'] == 'ok'`);

      // Step 2: Review
      setTimeout(() => {
        setNodeState("execution", "completed");
        setConnectors(2);
        setNodeState("review", "active");
        pipelineGlobalStatus.textContent = "Review Agent verifying AST syntax & secrets...";
        addAuditLog("EXECUTION", "Commit created: e4f9812 - 'feat: add health endpoint and tests'.");

        setTimeout(() => {
          setNodeState("review", "completed");
          setConnectors(3);
          setNodeState("proof", "active");
          reviewStatusPill.className = "status-pill pill-success";
          reviewStatusPill.textContent = "APPROVED";
          reviewSummaryBox.innerHTML = "<p>Code review passed: Clean AST, 0 secrets detected, strict boundaries respected.</p>";
          addAuditLog("REVIEW", "Review approved: 0 blocking defects detected.");

          // Step 3: Proof-of-Work
          setTimeout(() => {
            setNodeState("proof", "completed");
            setConnectors(4);
            setNodeState("gate", "active");
            setConfidence(0.95);
            proofStatusPill.className = "status-pill pill-success";
            proofStatusPill.textContent = "VERIFIED";
            statTestsPassed.textContent = "2";
            statTestsFailed.textContent = "0";
            statUnrelatedChanges.textContent = "None Detected";
            statUnrelatedChanges.className = "stat-value val-success";

            criteriaProofList.innerHTML = `
              <div class="criterion-card">
                <div class="criterion-card-header">
                  <span class="criterion-id">AC-1</span>
                  <span class="status-pill pill-success">SATISFIED</span>
                </div>
                <p class="criterion-desc">service.py defines and exports health function</p>
                <div class="evidence-items-box">
                  <div>✓ AST node verified: Symbol 'health' exists in 'service.py'</div>
                  <div>✓ Diff evidence in 'service.py': +def health():</div>
                </div>
              </div>
              <div class="criterion-card">
                <div class="criterion-card-header">
                  <span class="criterion-id">AC-2</span>
                  <span class="status-pill pill-success">SATISFIED</span>
                </div>
                <p class="criterion-desc">Automated tests for health function pass cleanly</p>
                <div class="evidence-items-box">
                  <div>✓ Automated test verification passed (2 test(s) succeeded)</div>
                </div>
              </div>
            `;

            pipelineGlobalStatus.textContent = "VERIFIED - Human Merge Gate Active";
            addAuditLog("PROOF", "Zero-Trust Proof Verified: 95% Confidence. Tests passed, AST confirmed.");

            setTimeout(() => {
              showMergeGateModal(0.95);
            }, 600);

          }, 1200);

        }, 1200);

      }, 1200);

    }, 1200);
  }
});
