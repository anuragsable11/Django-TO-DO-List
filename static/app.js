/* Site-wide touches: time zone, theme switch, local date, keyboard shortcuts, date buttons,
   the inline "new list" form, undo toasts and the check-off animation. */
(function () {
    var root = document.documentElement;
    var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    /* ---------- Time zone: tell the server, so "today" and "overdue" follow the visitor's calendar ---------- */

    try {
        var zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
        if (zone && /^[A-Za-z0-9_+\-\/]{1,64}$/.test(zone) && document.cookie.indexOf('tz=' + zone) === -1) {
            document.cookie = 'tz=' + zone + '; path=/; max-age=31536000; SameSite=Lax';
        }
    } catch (e) {
        // very old browser: the server falls back to UTC
    }

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

    /* ---------- Keyboard: N writes a new task, / searches, Ctrl+Z undoes ---------- */

    function visible(el) {
        return el && el.offsetParent !== null;
    }

    document.addEventListener('keydown', function (e) {
        if (e.defaultPrevented || e.altKey) return;
        var typing = e.target.closest && e.target.closest('input, textarea, select, [contenteditable]');

        if ((e.ctrlKey || e.metaKey) && !e.shiftKey && (e.key === 'z' || e.key === 'Z')) {
            var undoButton = document.querySelector('[data-undo]');
            if (undoButton && !typing) {
                e.preventDefault();
                undoButton.click();
            }
            return;
        }

        if (e.ctrlKey || e.metaKey || typing) return;

        if (e.key === '/') {
            var search = Array.prototype.find.call(document.querySelectorAll('[data-search-input]'), visible);
            if (search) {
                e.preventDefault();
                search.focus();
                search.select();
            }
            return;
        }

        if (e.key !== 'n' && e.key !== 'N') return;

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

    /* ---------- Due date shortcuts in the task form: Today, Tomorrow, Next week, No date ---------- */

    function isoDate(date) {
        var month = String(date.getMonth() + 1).padStart(2, '0');
        var day = String(date.getDate()).padStart(2, '0');
        return date.getFullYear() + '-' + month + '-' + day;
    }

    document.addEventListener('click', function (e) {
        var button = e.target.closest('[data-date-shortcuts] [data-days]');
        if (!button) return;
        var input = document.getElementById(button.closest('[data-date-shortcuts]').dataset.dateShortcuts);
        var days = button.dataset.days;
        if (!input) return;
        if (days === '') {
            input.value = '';
        } else {
            var date = new Date();
            // next week = the coming Monday
            var add = days === 'next-week' ? ((8 - date.getDay()) % 7 || 7) : Number(days);
            date.setDate(date.getDate() + add);
            input.value = isoDate(date);
        }
        input.dispatchEvent(new Event('change', { bubbles: true }));
    });

    /* ---------- The rail's "+" opens a small inline form for a new list ---------- */

    var newListButton = document.querySelector('[data-new-list]');
    var newListForm = document.querySelector('[data-new-list-form]');
    if (newListButton && newListForm) {
        var closeNewList = function () {
            newListForm.hidden = true;
            newListButton.setAttribute('aria-expanded', 'false');
        };
        newListButton.setAttribute('aria-expanded', 'false');
        newListButton.addEventListener('click', function (e) {
            if (window.matchMedia('(max-width: 860px)').matches) return; // small screens use the full page
            e.preventDefault();
            var opening = newListForm.hidden;
            newListForm.hidden = !opening;
            newListButton.setAttribute('aria-expanded', String(opening));
            if (opening) newListForm.querySelector('input[name="name"]').focus();
        });
        newListForm.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') {
                closeNewList();
                newListButton.focus();
            }
        });
    }

    /* ---------- Phones: the views and lists scroll sideways; start with the current one in view ---------- */

    document.querySelectorAll('.rail-nav').forEach(function (nav) {
        var active = nav.querySelector('.is-active');
        if (!active || nav.scrollWidth <= nav.clientWidth) return;
        var navBox = nav.getBoundingClientRect();
        var box = active.getBoundingClientRect();
        nav.scrollLeft += box.left - navBox.left - (navBox.width - box.width) / 2;
    });

    /* ---------- Toasts: gone once faded, so Ctrl+Z only undoes while the message is showing ---------- */

    document.querySelectorAll('.toast').forEach(function (toast) {
        toast.addEventListener('animationend', function (e) {
            if (e.animationName === 'toast' || e.animationName === 'toast-long') toast.remove();
        });
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
