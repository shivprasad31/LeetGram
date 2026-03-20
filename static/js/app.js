document.addEventListener("DOMContentLoaded", () => {
  const root = document.documentElement;
  const body = document.body;
  const themeToggle = document.querySelector("[data-theme-toggle]");
  const storedTheme = localStorage.getItem("codearena-theme");
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;

  const normalizeTheme = (theme) => {
    if (theme === "dark" || theme === "light") {
      return theme;
    }
    return prefersDark ? "dark" : "light";
  };

  const applyTheme = (theme) => {
    const normalizedTheme = normalizeTheme(theme);
    root.dataset.theme = normalizedTheme;
    root.dataset.themePreference = normalizedTheme;
    root.style.colorScheme = normalizedTheme;
    if (body) {
      body.dataset.theme = normalizedTheme;
      body.dataset.themePreference = normalizedTheme;
    }
    localStorage.setItem("codearena-theme", normalizedTheme);
  };

  applyTheme(storedTheme || root.dataset.theme || body?.dataset.theme || "system");

  themeToggle?.addEventListener("click", () => {
    applyTheme(root.dataset.theme === "dark" ? "light" : "dark");
  });

  document.querySelectorAll("[data-counter]").forEach((counter) => {
    const target = Number(counter.dataset.counter || 0);
    let current = 0;
    const step = Math.max(1, Math.round(target / 30));
    const timer = setInterval(() => {
      current += step;
      if (current >= target) {
        current = target;
        clearInterval(timer);
      }
      counter.textContent = current.toLocaleString();
    }, 24);
  });

  document.querySelectorAll("[data-progress]").forEach((bar) => {
    requestAnimationFrame(() => {
      bar.style.width = `${bar.dataset.progress}%`;
    });
  });

  const socketPath = body.dataset.notificationsSocketPath;
  if (socketPath) {
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    try {
      const socket = new WebSocket(`${protocol}://${window.location.host}${socketPath}`);
      socket.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        const container = document.querySelector("[data-live-notifications]");
        if (container) {
          const item = document.createElement("div");
          item.className = "alert alert-light border shadow-sm mb-2";
          item.textContent = `${payload.title}: ${payload.message}`;
          container.prepend(item);
        }
      };
    } catch (error) {
      console.debug("Notification socket unavailable", error);
    }
  }
});
