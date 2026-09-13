(() => {
    const statusNode = document.querySelector("[data-run-status]");
    if (!statusNode) return;

    let delay = 1500;
    const poll = async () => {
        try {
            const response = await fetch(statusNode.dataset.statusUrl, {
                headers: { Accept: "application/json" },
                credentials: "same-origin",
            });
            if (!response.ok) return;
            const payload = await response.json();
            if (payload.terminal) {
                window.location.reload();
                return;
            }
            statusNode.textContent =
                `Optimization sedang ${payload.status.toLowerCase()}. ` +
                "Halaman akan diperbarui otomatis.";
        } catch (_error) {
            // Gangguan jaringan tidak mengubah lifecycle job di server.
        }
        delay = Math.min(Math.round(delay * 1.5), 10000);
        window.setTimeout(poll, delay);
    };

    window.setTimeout(poll, delay);
})();
