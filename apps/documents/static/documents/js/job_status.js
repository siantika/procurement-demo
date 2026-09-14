(() => {
    const root = document.querySelector("[data-document-job]");
    if (!root || root.dataset.terminal === "true") return;

    let delay = 1500;
    const poll = async () => {
        try {
            const response = await fetch(root.dataset.statusUrl, {
                headers: {Accept: "application/json"},
                credentials: "same-origin",
            });
            if (!response.ok) return;
            const data = await response.json();
            const badge = root.querySelector("[data-job-status]");
            if (badge) badge.textContent = data.status_label;
            if (data.terminal) {
                window.location.reload();
                return;
            }
        } catch (_error) {
            // A temporary network error is handled by the next poll.
        }
        delay = Math.min(Math.round(delay * 1.5), 10000);
        window.setTimeout(poll, delay);
    };
    window.setTimeout(poll, delay);
})();
