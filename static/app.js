(() => {
  const STORAGE_KEY = "classroom-ai.sessions.v1";
  const $ = (selector) => document.querySelector(selector);
  const historyList = $("#history-list");
  const messageList = $("#message-list");
  const promptInput = $("#prompt");
  const sendButton = $("#send-button");
  const modal = $("#project-modal");
  let sessions = loadSessions();
  let activeId = null;
  let toastTimer;
  let isSending = false;

  function loadSessions() {
    try {
      const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
      return Array.isArray(value) ? value.filter((item) => item && item.id && Array.isArray(item.messages)) : [];
    } catch {
      return [];
    }
  }

  function saveSessions() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
    } catch {
      showToast("Could not save chat history in this browser.", true);
    }
  }

  function activeSession() {
    return sessions.find((item) => item.id === activeId) || null;
  }

  function createSession(type, title, className = "") {
    const session = {
      id: crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`,
      type,
      title,
      className,
      createdAt: Date.now(),
      messages: [],
    };
    sessions.unshift(session);
    activeId = session.id;
    saveSessions();
    render();
    promptInput.focus();
    return session;
  }

  function showToast(message, isError = false) {
    const toast = $("#toast");
    toast.textContent = message;
    toast.classList.toggle("error", isError);
    toast.classList.add("visible");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove("visible"), 3600);
  }

  function renderHistory() {
    historyList.replaceChildren();
    $("#empty-history").hidden = sessions.length > 0;
    sessions.forEach((session) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `history-item${session.id === activeId ? " selected" : ""}`;
      button.title = session.title;

      const icon = document.createElement("span");
      icon.className = "history-icon";
      icon.innerHTML = session.type === "project"
        ? '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>'
        : '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 11.5a7.5 7.5 0 0 1-7.5 7.5H5l1.8-3.1A7.5 7.5 0 1 1 20 11.5z"/></svg>';

      const name = document.createElement("span");
      name.className = "history-name";
      name.textContent = session.title;
      button.append(icon, name);
      if (session.type === "project") {
        const classLabel = document.createElement("span");
        classLabel.className = "history-class";
        classLabel.textContent = session.className;
        button.append(classLabel);
      }
      button.addEventListener("click", () => {
        activeId = session.id;
        render();
        closeSidebar();
      });
      historyList.append(button);
    });
  }

  function renderAssistantContent(container, content, isProject) {
    if (isProject) {
      try {
        const data = JSON.parse(content);
        if (Array.isArray(data.questions)) {
          data.questions.forEach((question, index) => {
            const card = document.createElement("article");
            card.className = "question-card";
            const title = document.createElement("div");
            title.className = "question-title";
            title.textContent = `${index + 1}. ${question.question || "Question"}`;
            card.append(title);

            if (question.options && typeof question.options === "object") {
              ["A", "B", "C", "D"].forEach((letter) => {
                if (question.options[letter] === undefined) return;
                const option = document.createElement("div");
                option.className = "question-option";
                const marker = document.createElement("b");
                marker.textContent = `${letter}.`;
                const value = document.createElement("span");
                value.textContent = String(question.options[letter]);
                option.append(marker, value);
                card.append(option);
              });
            }

            if (question.correct_answer) {
              const answer = document.createElement("div");
              answer.className = "answer-key";
              answer.textContent = `Answer: ${question.correct_answer}`;
              card.append(answer);
            }
            container.append(card);
          });
          return;
        }
      } catch {
        // Display the model output as plain text when it is not valid JSON.
      }
    }
    const text = document.createElement("div");
    text.textContent = content;
    container.append(text);
  }

  function renderMessages(session) {
    messageList.replaceChildren();
    if (!session) return;

    session.messages.forEach((message) => {
      const row = document.createElement("article");
      row.className = `message ${message.role}`;
      if (message.role === "assistant") {
        const avatar = document.createElement("div");
        avatar.className = "message-avatar";
        avatar.textContent = "C";
        const body = document.createElement("div");
        body.className = "message-body";
        const meta = document.createElement("span");
        meta.className = "message-meta";
        meta.textContent = session.type === "project" ? "Question generator" : "Classroom AI";
        body.append(meta);
        renderAssistantContent(body, message.content, session.type === "project");
        row.append(avatar, body);
      } else {
        const body = document.createElement("div");
        body.className = "message-body";
        body.textContent = message.content;
        row.append(body);
      }
      messageList.append(row);
    });
  }

  function render() {
    const session = activeSession();
    renderHistory();
    renderMessages(session);
    $("#welcome").hidden = Boolean(session && session.messages.length);
    $("#project-context").hidden = !session || session.type !== "project";
    $("#project-context").replaceChildren();
    if (session && session.type === "project") {
      const chip = document.createElement("span");
      chip.className = "context-chip";
      chip.textContent = `${session.title} · ${session.className}`;
      $("#project-context").append(chip);
      $("#prompt").placeholder = "Describe the questions you want to generate...";
      $("#composer-hint").textContent = "Questions are based on indexed learning materials.";
    } else {
      $("#prompt").placeholder = "Message Classroom AI";
      $("#composer-hint").textContent = "AI can make mistakes. Check important information.";
    }
    sendButton.disabled = !promptInput.value.trim() || isSending;
    $("#thinking").hidden = !isSending;
    $("#conversation").scrollTop = $("#conversation").scrollHeight;
  }

  function startNewChat() {
    createSession("chat", "New chat");
    closeSidebar();
  }

  function openSidebar() {
    $("#sidebar").classList.add("open");
  }

  function closeSidebar() {
    $("#sidebar").classList.remove("open");
  }

  function openProjectModal() {
    modal.hidden = false;
    $("#project-name").focus();
  }

  function closeProjectModal() {
    modal.hidden = true;
  }

  async function sendMessage(value = promptInput.value) {
    const text = value.trim();
    if (!text || isSending) return;
    let session = activeSession();
    if (!session) session = createSession("chat", "New chat");

    const previousMessages = session.messages.map(({ role, content }) => ({ role, content }));
    session.messages.push({ role: "user", content: text });
    if (session.title === "New chat") session.title = text.slice(0, 38) + (text.length > 38 ? "…" : "");
    saveSessions();
    promptInput.value = "";
    promptInput.style.height = "auto";
    isSending = true;
    render();

    try {
      const response = await fetch(session.type === "project" ? "/api/generate" : "/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(session.type === "project"
          ? { className: session.className, prompt: text }
          : {
            prompt: text,
            history: previousMessages.map(({ role, content }) => ({ role, content })),
          }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "The request could not be completed.");
      session.messages.push({ role: "assistant", content: String(data.reply) });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Something went wrong.";
      showToast(message, true);
      session.messages.push({
        role: "assistant",
        content: `I couldn't complete that request. ${message}`,
      });
    } finally {
      isSending = false;
      saveSessions();
      render();
      promptInput.focus();
    }
  }

  $("#new-chat").addEventListener("click", startNewChat);
  $("#new-project").addEventListener("click", openProjectModal);
  $("#open-sidebar").addEventListener("click", openSidebar);
  $("#close-sidebar").addEventListener("click", closeSidebar);
  $("#close-modal").addEventListener("click", closeProjectModal);
  modal.addEventListener("click", (event) => {
    if (event.target === modal) closeProjectModal();
  });
  $("#project-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const name = $("#project-name").value.trim();
    const className = $("#class-select").value;
    if (!name) return;
    closeProjectModal();
    createSession("project", name, className);
  });
  $("#clear-history").addEventListener("click", () => {
    if (!sessions.length) return;
    if (!window.confirm("Clear all conversations saved in this browser?")) return;
    sessions = [];
    activeId = null;
    saveSessions();
    render();
  });
  $("#composer").addEventListener("submit", (event) => {
    event.preventDefault();
    sendMessage();
  });
  promptInput.addEventListener("input", () => {
    promptInput.style.height = "auto";
    promptInput.style.height = `${Math.min(promptInput.scrollHeight, 180)}px`;
    sendButton.disabled = !promptInput.value.trim() || isSending;
  });
  promptInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  });
  document.querySelectorAll(".suggestion-card").forEach((button) => {
    button.addEventListener("click", () => {
      if (!activeSession()) startNewChat();
      sendMessage(button.dataset.prompt);
    });
  });
  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      startNewChat();
    }
    if (event.key === "Escape") {
      closeProjectModal();
      closeSidebar();
    }
  });

  if (sessions.length) activeId = sessions[0].id;
  render();
})();
