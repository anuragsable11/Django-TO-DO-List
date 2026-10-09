/* Site-wide touches: theme switch, local date, keyboard shortcut, check-off animation. */
(function () {
    var root = document.documentElement;
    var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    /* ---------- Light / dark ---------- */

    function savedTheme() {
        try {
            return localStorage.getItem('theme');
        } catch (e) {
            return null;
        }
    }

    function applyTheme(theme, save) {
        root.dataset.theme = theme;
        document.querySelectorAll('[data-theme-toggle]').forEach(function (button) {
            button.setAttribute('aria-label', theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode');
        });
        if (save) {
            try {
                localStorage.setItem('theme', theme);
            } catch (e) {
                // storage blocked: the choice just won't be remembered
            }
        }
    }

    applyTheme(root.dataset.theme === 'dark' ? 'dark' : 'light', false);

    document.addEventListener('click', function (e) {
        if (e.target.closest('[data-theme-toggle]')) {
            applyTheme(root.dataset.theme === 'dark' ? 'light' : 'dark', true);
        }
    });

    // Follow the system setting until someone picks a theme themselves
    var systemDark = window.matchMedia('(prefers-color-scheme: dark)');
    if (systemDark.addEventListener) {
        systemDark.addEventListener('change', function (e) {
            if (!savedTheme()) applyTheme(e.matches ? 'dark' : 'light', false);
        });
    }

    /* ---------- Today's date, in the visitor's own time zone (the server runs on UTC) ---------- */

    var DATE_PARTS = {
        day: { day: '2-digit' },
        month: { month: 'short' },
        weekday: { weekday: 'long' }
    };

    document.querySelectorAll('[data-today]').forEach(function (el) {
        var parts = DATE_PARTS[el.dataset.today];
        if (parts) el.textContent = new Intl.DateTimeFormat('en', parts).format(new Date());
    });

    /* ---------- Keyboard: N or / to write a new task ---------- */

    document.addEventListener('keydown', function (e) {
        if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey) return;
        if (e.key !== 'n' && e.key !== 'N' && e.key !== '/') return;
        if (e.target.closest && e.target.closest('input, textarea, select, [contenteditable]')) return;

        var quickAdd = document.getElementById('quick-add-title');
        if (quickAdd) {
            e.preventDefault();
            quickAdd.focus();
            return;
        }
        var newTask = document.querySelector('[data-shortcut="new-task"]');
        if (newTask) {
            e.preventDefault();
            window.location.href = newTask.href;
        }
    });

    /* ---------- Checking a task off: draw the tick and strike the title, then submit ---------- */

    document.addEventListener('submit', function (e) {
        var form = e.target;
        if (!form.matches('[data-complete]') || reduceMotion) return;
        var row = form.closest('.task');
        if (!row) return;

        e.preventDefault();
        if (row.classList.contains('is-completing')) return; // already on its way
        row.classList.add('is-completing');
        setTimeout(function () { form.submit(); }, 420);
    });
})();
