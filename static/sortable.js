/* Drag to reorder tasks (any list marked data-sortable).
   - Mouse, pen and touch: press the handle and drag. The other rows slide out of the way.
   - Keyboard: focus the handle and press the up / down arrow keys.
   The new order is saved in the background; if saving fails the page reloads to show the real order. */
(function () {
    var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var status = document.querySelector('[data-sort-status]');
    var EDGE = 72;        // px from the top / bottom of the window where dragging scrolls the page
    var THRESHOLD = 4;    // px of movement before a press on the handle becomes a drag

    function announce(text) {
        if (status) status.textContent = text;
    }

    function csrfToken() {
        var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
        return input ? input.value : '';
    }

    function setup(list) {
        var url = list.dataset.reorderUrl;
        var drag = null;
        var saveTimer = null;
        var scrollFrame = 0;

        function rows() {
            return Array.prototype.filter.call(list.children, function (el) { return el.classList.contains('task'); });
        }

        function renumber() {
            rows().forEach(function (row, i) {
                var num = row.querySelector('.task-num');
                if (num) num.textContent = String(i + 1).padStart(2, '0');
            });
        }

        function save() {
            clearTimeout(saveTimer);
            saveTimer = setTimeout(function () {
                fetch(url, {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
                    body: JSON.stringify({ ids: rows().map(function (row) { return Number(row.dataset.id); }) })
                }).then(function (response) {
                    if (!response.ok) throw new Error(response.status);
                }).catch(function () {
                    announce("Couldn't save the new order. Reloading.");
                    setTimeout(function () { window.location.reload(); }, 1200);
                });
            }, 300);
        }

        // FLIP: after rows move in the DOM, animate each one from where it was to where it is now
        function moveWithAnimation(mutate) {
            var before = new Map();
            rows().forEach(function (row) { before.set(row, row.offsetTop); });
            mutate();
            if (reduceMotion) return;
            rows().forEach(function (row) {
                if (drag && row === drag.row) return;
                var dy = before.get(row) - row.offsetTop;
                if (!dy) return;
                row.style.transition = 'none';
                row.style.transform = 'translateY(' + dy + 'px)';
                void row.offsetHeight; // apply the starting point before animating away from it
                row.style.transition = 'transform 0.22s cubic-bezier(0.2, 0.7, 0.2, 1)';
                row.style.transform = '';
                setTimeout(function () { if (!drag || drag.row !== row) row.style.transition = ''; }, 240);
            });
        }

        /* ---------- Pointer dragging ---------- */

        function follow() {
            var rowHeight = drag.row.offsetHeight;
            var listTop = list.getBoundingClientRect().top + list.clientTop;
            // where the row's top edge should be, in the list's own coordinates, kept inside the list
            var top = Math.min(Math.max(drag.y - listTop - drag.grab, 0), list.clientHeight - rowHeight);
            var middle = top + rowHeight / 2;

            var target = null;
            var others = rows().filter(function (row) { return row !== drag.row; });
            for (var i = 0; i < others.length; i++) {
                if (middle < others[i].offsetTop + others[i].offsetHeight / 2) {
                    target = others[i];
                    break;
                }
            }
            if (target !== drag.row.nextElementSibling && target !== drag.row) {
                moveWithAnimation(function () { list.insertBefore(drag.row, target); });
            }
            drag.row.style.transform = 'translateY(' + (top - drag.row.offsetTop) + 'px)';
        }

        function autoScroll() {
            cancelAnimationFrame(scrollFrame);
            if (!drag || !drag.moved) return;
            var speed = 0;
            if (drag.y < EDGE) speed = -Math.ceil((EDGE - drag.y) / 6);
            else if (drag.y > window.innerHeight - EDGE) speed = Math.ceil((drag.y - (window.innerHeight - EDGE)) / 6);
            if (!speed) return;
            window.scrollBy(0, speed);
            follow();
            scrollFrame = requestAnimationFrame(autoScroll);
        }

        list.addEventListener('pointerdown', function (e) {
            var grip = e.target.closest('[data-grip]');
            if (!grip || drag || (e.pointerType === 'mouse' && e.button !== 0)) return;
            var row = grip.closest('.task');
            e.preventDefault(); // no text selection, no focus jump
            grip.setPointerCapture(e.pointerId);
            drag = {
                row: row,
                grip: grip,
                pointer: e.pointerId,
                startY: e.clientY,
                y: e.clientY,
                grab: e.clientY - row.getBoundingClientRect().top,
                index: rows().indexOf(row),
                moved: false
            };
        });

        list.addEventListener('pointermove', function (e) {
            if (!drag || e.pointerId !== drag.pointer) return;
            drag.y = e.clientY;
            if (!drag.moved) {
                if (Math.abs(e.clientY - drag.startY) < THRESHOLD) return;
                drag.moved = true;
                list.classList.add('is-sorting');
                drag.row.classList.add('is-dragging');
                drag.row.style.transition = 'none';
            }
            follow();
            autoScroll();
        });

        function finish(e) {
            if (!drag || e.pointerId !== drag.pointer) return;
            var done = drag;
            drag = null;
            cancelAnimationFrame(scrollFrame);
            if (!done.moved) {
                done.grip.focus();
                return;
            }
            list.classList.remove('is-sorting');
            var row = done.row;
            row.style.transition = reduceMotion ? 'none' : 'transform 0.2s cubic-bezier(0.2, 0.7, 0.2, 1)';
            row.style.transform = '';
            setTimeout(function () {
                row.classList.remove('is-dragging');
                row.style.transition = '';
            }, 200);
            renumber();
            var index = rows().indexOf(row);
            if (index !== done.index) {
                save();
                announce('Moved to position ' + (index + 1) + ' of ' + rows().length + '.');
            }
        }

        list.addEventListener('pointerup', finish);
        list.addEventListener('pointercancel', finish);

        /* ---------- Keyboard: arrow keys on a focused handle ---------- */

        list.addEventListener('keydown', function (e) {
            var grip = e.target.closest('[data-grip]');
            if (!grip || drag) return;
            var row = grip.closest('.task');
            var all = rows();
            var index = all.indexOf(row);
            var to = index;
            if (e.key === 'ArrowUp') to = index - 1;
            else if (e.key === 'ArrowDown') to = index + 1;
            else if (e.key === 'Home') to = 0;
            else if (e.key === 'End') to = all.length - 1;
            else return;
            e.preventDefault();
            if (to < 0 || to >= all.length || to === index) return;
            moveWithAnimation(function () {
                list.insertBefore(row, to > index ? all[to].nextElementSibling : all[to]);
            });
            grip.focus();
            renumber();
            save();
            announce('Moved to position ' + (to + 1) + ' of ' + all.length + '.');
        });
    }

    document.querySelectorAll('[data-sortable]').forEach(setup);
})();
