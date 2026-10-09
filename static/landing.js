(function () {
    var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    function wait(ms) {
        return new Promise(function (resolve) { setTimeout(resolve, ms); });
    }

    /* ---------- Stat counters ---------- */

    function countUp(el) {
        var target = parseInt(el.dataset.count, 10);
        if (reduceMotion || !target) return;

        var duration = 900;
        var start = null;
        el.textContent = '0';

        function step(ts) {
            if (!start) start = ts;
            var progress = Math.min((ts - start) / duration, 1);
            var eased = 1 - Math.pow(1 - progress, 3);
            el.textContent = Math.round(target * eased);
            if (progress < 1) requestAnimationFrame(step);
        }
        requestAnimationFrame(step);
    }

    /* ---------- Reveal on scroll ---------- */

    function reveal(el) {
        el.classList.add('is-visible');
        el.querySelectorAll('[data-count]').forEach(countUp);
    }

    var revealItems = document.querySelectorAll('.reveal');

    if ('IntersectionObserver' in window && !reduceMotion) {
        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    reveal(entry.target);
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.2 });

        revealItems.forEach(function (el) { observer.observe(el); });
    } else {
        revealItems.forEach(reveal);
    }

    /* ---------- "Adding tasks" demo ---------- */

    var list = document.getElementById('demo-list');
    var typing = document.getElementById('demo-typing');
    var addButton = document.getElementById('demo-add');
    var burst = document.getElementById('demo-burst');
    if (!list) return;

    var tasks = ['Review project brief', 'Book team meeting', 'Pay electricity bill'];

    function addRow(text) {
        var row = document.createElement('li');
        row.className = 'demo-row';
        row.innerHTML = '<span class="demo-num"></span><span class="demo-check"></span><span class="demo-text"></span>';
        row.querySelector('.demo-num').textContent = String(list.children.length + 1).padStart(2, '0');
        row.querySelector('.demo-text').textContent = text;
        list.appendChild(row);
        return row;
    }

    // Reduced motion: show the finished state, no loop.
    if (reduceMotion) {
        tasks.forEach(function (text) { addRow(text).classList.add('is-done'); });
        burst.classList.add('is-on');
        return;
    }

    async function typeText(text) {
        typing.textContent = '';
        for (var i = 0; i < text.length; i++) {
            typing.textContent += text[i];
            await wait(65 + Math.random() * 50);
        }
    }

    async function runDemo() {
        await wait(1200); // let the hero finish its entrance first

        while (true) {
            list.innerHTML = '';
            list.classList.remove('is-clearing');
            burst.classList.remove('is-on');

            // Type each task, press "+", pop it onto the list.
            for (var i = 0; i < tasks.length; i++) {
                await typeText(tasks[i]);
                await wait(250);
                addButton.classList.add('is-pressed');
                await wait(160);
                addButton.classList.remove('is-pressed');
                typing.textContent = '';
                addRow(tasks[i]);
                await wait(450);
            }

            // Tick them off one by one.
            await wait(500);
            var rows = list.querySelectorAll('.demo-row');
            for (var j = 0; j < rows.length; j++) {
                rows[j].classList.add('is-done');
                await wait(550);
            }

            burst.classList.add('is-on');
            await wait(2400);

            list.classList.add('is-clearing');
            burst.classList.remove('is-on');
            await wait(450);
        }
    }

    runDemo();
})();
