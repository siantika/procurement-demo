(() => {
    const storagePrefix = "procurement-dismissed-toast:";

    document.querySelectorAll("[data-toast]").forEach((toast) => {
        const storageKey = `${storagePrefix}${toast.dataset.toastId}`;
        try {
            if (window.sessionStorage.getItem(storageKey)) {
                toast.remove();
                return;
            }
        } catch (_error) {
            // Toast tetap dapat digunakan bila storage browser dibatasi.
        }

        const closeButton = toast.querySelector("[data-toast-close]");
        closeButton?.addEventListener("click", () => {
            try {
                window.sessionStorage.setItem(storageKey, "1");
            } catch (_error) {
                // Menutup toast tidak bergantung pada browser storage.
            }
            toast.remove();
        });
    });
})();
