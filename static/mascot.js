/* Stripes the tiger: the landing-page task assistant.
   Not an AI - it picks lines from simple rules about the user's own task list. */
(function () {
    var root = document.getElementById('sidekick');
    var dataEl = document.getElementById('mascot-data');
    if (!root || !dataEl) return;

    var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var data = JSON.parse(dataEl.textContent) || {};
    var urls = root.dataset;

    var stage = root.querySelector('.sk-stage');
    var poke = root.querySelector('.sk-tiger');
    var tiger = root.querySelector('.tiger');
    var head = tiger.querySelector('.t-head');
    var eyes = tiger.querySelectorAll('.t-eye-white');
    var pupils = tiger.querySelectorAll('.t-pupil');
    var bubble = root.querySelector('.sk-bubble');
    var text = root.querySelector('.sk-text');
    var live = root.querySelector('.sk-live');
    var controls = root.querySelector('.sk-controls');
    var link = root.querySelector('.sk-link');
    var doneForm = root.querySelector('.sk-done');
    var count = root.querySelector('.sk-count');

    var AUTO_NEXT_MS = 7000;
    var JUST_DONE_KEY = 'stripes-just-done';

    /* ---------- What Stripes says ---------- */

    var REMINDERS = [
        "Don't forget:",
        'Still on your list:',
        'Quick reminder:',
        'Have you finished this one yet?'
    ];

    var TIPS = [
        'Tip: break big tasks into smaller steps. They are much easier to finish.',
        'Tip: start with the hardest task. Everything after it feels easier.',
        'Tip: a quick look at your list each morning keeps surprises away.',
        'Tip: deleted something by mistake? You can restore it from the trash.',
        'Tip: end a task with “friday” or “12 oct” and it gets that due date.',
        'Tip: type “every monday” after a task and it comes back each week.',
        'Tip: add #work to a task to file it in your Work list.',
        'Tip: checked something off too soon? Press Undo in the message, or Ctrl+Z.'
    ];

    var TICKLES = [
        'Hehe, that tickles!',
        "I'm awake, I promise!",
        'Still here, and ready to help.'
    ];

    function plural(n, word) {
        return n + ' ' + word + (n === 1 ? '' : 's');
    }

    function pick(list) {
        return list[Math.floor(Math.random() * list.length)];
    }

    function greeting() {
        var hour = new Date().getHours();
        if (hour < 12) return 'Good morning';
        if (hour < 17) return 'Good afternoon';
        return 'Good evening';
    }

    function guestLines() {
        return [
            { text: "Hi there! I'm Stripes, your task assistant. Click me anytime for a tip.", pose: 'wave' },
            { text: "Add your tasks and I'll keep reminding you what's still left to do.", pose: 'point' },
            { text: "And every time you finish one, I'll celebrate with you.", pose: 'cheer' },
            { text: 'Create a free account to get started. It only takes a minute.', pose: 'point', link: ['Create account', urls.urlRegister] },
            { text: "Already have an account? Log in and I'll show you what's waiting.", pose: 'wave', link: ['Log in', urls.urlLogin] },
            { text: pick(TIPS) }
        ];
    }

    function userLines() {
        var tasks = data.tasks || [];
        var lines = [
            { text: greeting() + ', ' + data.user + "! I'm Stripes, your task assistant. Click me anytime for a reminder.", pose: 'wave' }
        ];

        if (!data.open) {
            lines.push({ text: "Your list is empty. Add a task and I'll help you remember it.", pose: 'point', link: ['Add a task', urls.urlAdd] });
        } else {
            var summary = data.open === 1
                ? 'You have 1 open task.'
                : 'You have ' + data.open + ' open tasks.';
            var dueBits = [];
            if (data.due_today) dueBits.push(data.due_today + ' due today');
            if (data.overdue) dueBits.push(data.overdue + ' overdue');
            summary += dueBits.length
                ? ' ' + dueBits.join(' and ') + ". Let's start there."
                : (data.open === 1 ? ' You can do this!' : " Let's take them one at a time.");
            lines.push({
                text: summary,
                pose: 'point',
                link: data.overdue || data.due_today ? ['View today', urls.urlToday] : ['View tasks', urls.urlHome]
            });

            // One reminder per task: overdue first, then due today, then the soonest due
            var plain = 0;
            tasks.forEach(function (task) {
                var lead;
                if (task.when === 'overdue') lead = 'Overdue since ' + (task.due === 'Yesterday' ? 'yesterday' : task.due) + ':';
                else if (task.when === 'today') lead = 'Due today:';
                else if (task.due) lead = 'Due ' + (task.due === 'Tomorrow' ? 'tomorrow' : task.due) + ':';
                else lead = REMINDERS[plain++ % REMINDERS.length];
                var line = lead + ' “' + task.title + '”';
                if (task.notes) line += ' — ' + task.notes;
                lines.push({ text: line, pose: 'point', task: task });
            });

            if (data.open > tasks.length) {
                lines.push({
                    text: '…and ' + plural(data.open - tasks.length, 'more task') + ' after those. Want to see them all?',
                    pose: 'point',
                    link: ['View all tasks', urls.urlHome]
                });
            }
        }

        if (data.done) {
            var won = "Nice work! You've completed " + plural(data.done, 'task') + ' so far.';
            if (data.last_done) won += ' Latest: “' + data.last_done + '”.';
            lines.push({ text: won, pose: 'cheer', link: ['View completed', urls.urlComplete] });
        }

        if (data.trash) {
            lines.push({
                text: plural(data.trash, 'task') + (data.trash === 1 ? ' is' : ' are') + ' in the trash. Restore anything you still need.',
                pose: 'point',
                link: ['Open trash', urls.urlTrash]
            });
        }

        lines.push({ text: pick(TIPS) });
        return lines;
    }

    function buildLines() {
        return data.user ? userLines() : guestLines();
    }

    // Saved when "Mark as done" is pressed, so Stripes can celebrate after the reload
    function takeJustDone() {
        try {
            var title = sessionStorage.getItem(JUST_DONE_KEY);
            sessionStorage.removeItem(JUST_DONE_KEY);
            return title;
        } catch (e) {
            return null;
        }
    }

    var lines = buildLines();
    var justDone = takeJustDone();
    var stillOpen = (data.tasks || []).some(function (task) { return task.title === justDone; });
    if (justDone && !stillOpen) {
        lines.unshift({ text: 'Done! “' + justDone + '” is checked off. One less thing to remember.', pose: 'cheer' });
    }

    /* ---------- Talking ---------- */

    var index = 0;
    var typingTimer = null;
    var autoTimer = null;
    var paused = false;
    var onScreen = false;
    var leaving = false;
    var mouseSeen = false;

    function replay(el, className) {
        el.classList.remove(className);
        void el.getBoundingClientRect();
        el.classList.add(className);
    }

    /* ---------- The 3D tiger (stripes3d.js), when it loads, gets the same cues as the SVG ---------- */

    var rig3d = null;
    var currentPose = null;
    var talkingNow = false;

    function cue(method, arg) {
        if (rig3d) rig3d[method](arg);
    }

    root.addEventListener('stripes:ready', function (e) {
        rig3d = e.detail;
        rig3d.pose(currentPose);
        rig3d.talk(talkingNow);
        if (target) rig3d.look(target.x, target.y);
        if (started || reduceMotion) rig3d.land(); // already on screen: arrive now
    });

    function talking(on) {
        talkingNow = on;
        tiger.classList.toggle('is-talking', on);
        cue('talk', on);
    }

    function setPose(pose) {
        currentPose = pose || null;
        cue('pose', currentPose);
        tiger.classList.remove('pose-wave', 'pose-point', 'pose-cheer');
        stage.classList.toggle('is-cheer', pose === 'cheer');
        if (!pose) return;
        void tiger.getBoundingClientRect(); // so a repeated pose replays its animation
        tiger.classList.add('pose-' + pose);
    }

    function say(line, announce) {
        clearTimeout(typingTimer);
        clearTimeout(autoTimer);
        setPose(line.pose);
        if (!mouseSeen) lookAtBubble();

        link.hidden = !line.link;
        if (line.link) {
            link.textContent = line.link[0];
            link.href = line.link[1];
        }

        doneForm.hidden = !line.task;
        if (line.task) {
            doneForm.action = line.task.done_url;
            doneForm.dataset.title = line.task.title;
        }

        // Screen readers get the whole line at once, and only announced when the user asked for it
        live.setAttribute('aria-live', announce ? 'polite' : 'off');
        live.textContent = line.text;

        if (reduceMotion) {
            text.textContent = line.text;
            return;
        }

        var chars = Array.from(line.text);
        var shown = 0;
        talking(true);
        text.classList.add('is-typing');

        (function typeNext() {
            shown += 1;
            text.textContent = chars.slice(0, shown).join('');
            if (shown < chars.length) {
                typingTimer = setTimeout(typeNext, /[.!?…]/.test(chars[shown - 1]) ? 220 : 26);
            } else {
                talking(false);
                text.classList.remove('is-typing');
                scheduleNext();
            }
        })();
    }

    function show(i, announce) {
        if (leaving) return;
        if (i >= lines.length) {
            lines = buildLines(); // new lap: fresh tip, up-to-date greeting
            i = 0;
        }
        index = (i + lines.length) % lines.length;
        count.textContent = (index + 1) + ' / ' + lines.length;
        say(lines[index], announce);
    }

    function scheduleNext() {
        clearTimeout(autoTimer);
        if (reduceMotion) return;
        autoTimer = setTimeout(function () {
            if (paused || !onScreen || document.hidden) scheduleNext();
            else show(index + 1, false);
        }, AUTO_NEXT_MS);
    }

    // Hold still while someone is reading or using the controls
    root.addEventListener('pointerenter', function (e) {
        if (e.pointerType === 'mouse') paused = true;
    });
    root.addEventListener('pointerleave', function () { paused = false; });
    root.addEventListener('focusin', function () { paused = true; });
    root.addEventListener('focusout', function () { paused = false; });

    root.querySelector('.sk-prev').addEventListener('click', function () { show(index - 1, true); });
    root.querySelector('.sk-next').addEventListener('click', function () { show(index + 1, true); });

    /* ---------- Clicking Stripes ---------- */

    var pokes = [];

    poke.addEventListener('click', function () {
        if (!reduceMotion) replay(tiger, 'is-hop');
        cue('hop');

        var now = Date.now();
        pokes = pokes.filter(function (t) { return now - t < 2500; });
        pokes.push(now);

        if (pokes.length >= 4) {
            pokes = [];
            say({ text: pick(TICKLES) }, true);
            tiger.classList.add('is-happy');
            cue('happy', true);
            setTimeout(function () {
                tiger.classList.remove('is-happy');
                cue('happy', false);
            }, 1500);
        } else {
            show(index + 1, true);
        }
    });

    tiger.addEventListener('animationend', function (e) {
        if (e.animationName === 't-hop') tiger.classList.remove('is-hop');
        if (e.animationName === 't-land') tiger.classList.remove('is-landing');
        if (e.animationName === 't-twitch') tiger.classList.remove('is-twitch');
    });

    /* ---------- Mark a task done from the bubble ---------- */

    doneForm.addEventListener('submit', function (e) {
        try {
            sessionStorage.setItem(JUST_DONE_KEY, doneForm.dataset.title);
        } catch (err) {
            // storage blocked: the task still gets done, Stripes just won't celebrate after the reload
        }
        if (reduceMotion) return;

        // A quick victory dance, then submit for real
        e.preventDefault();
        doneForm.querySelector('button').disabled = true;
        say({ text: 'Great, marking it as done…', pose: 'cheer' }, false);
        leaving = true;
        setTimeout(function () { doneForm.submit(); }, 900);
    });

    /* ---------- Eyes, blinking, ears ---------- */

    var target = null;
    var frame = 0;

    function lookAt(x, y) {
        if (!onScreen) return;
        target = { x: x, y: y };
        if (!frame) frame = requestAnimationFrame(updateLook);
    }

    function lookAtBubble() {
        var box = bubble.getBoundingClientRect();
        lookAt(box.left + box.width / 2, box.top + box.height / 3);
    }

    function updateLook() {
        frame = 0;
        if (rig3d) rig3d.look(target.x, target.y);
        for (var i = 0; i < pupils.length; i++) {
            var box = eyes[i].getBoundingClientRect();
            var dx = target.x - (box.left + box.width / 2);
            var dy = target.y - (box.top + box.height / 2);
            var dist = Math.hypot(dx, dy) || 1;
            var reach = Math.min(dist / 150, 1); // look less far when the target is close to the face
            pupils[i].style.transform = 'translate(' + (dx / dist * 8 * reach).toFixed(1) + 'px, ' + (dy / dist * 9 * reach).toFixed(1) + 'px)';
        }

        if (!reduceMotion) {
            // lean the head a little toward whatever it's looking at
            var tigerBox = poke.getBoundingClientRect();
            var lean = (target.x - (tigerBox.left + tigerBox.width / 2)) / window.innerWidth;
            head.style.transform = 'rotate(' + (Math.max(-1, Math.min(1, lean * 2.5)) * 6).toFixed(2) + 'deg)';
        }
    }

    window.addEventListener('pointermove', function (e) {
        if (e.pointerType !== 'mouse') return;
        mouseSeen = true;
        lookAt(e.clientX, e.clientY);
    }, { passive: true });

    window.addEventListener('pointerdown', function (e) {
        lookAt(e.clientX, e.clientY);
    }, { passive: true });

    function blinkSoon() {
        setTimeout(function () {
            tiger.classList.add('is-blink');
            cue('blink');
            setTimeout(function () { tiger.classList.remove('is-blink'); }, 140);
            if (Math.random() < 0.3) {
                replay(tiger, 'is-twitch');
                cue('twitch');
            }
            blinkSoon();
        }, 2000 + Math.random() * 3500);
    }

    /* ---------- Entrance: lands when scrolled into view ---------- */

    var started = false;

    function start() {
        if (started) return;
        started = true;
        root.classList.remove('is-waiting');
        controls.hidden = false;
        text.setAttribute('aria-hidden', 'true');

        cue('land');
        if (reduceMotion) {
            show(0, false);
            return;
        }

        text.textContent = '';
        tiger.classList.add('is-landing');
        blinkSoon();
        setTimeout(function () { show(0, false); }, 650);
    }

    root.classList.add('is-waiting');

    // "Mark as done" comes back to /#sidekick: land just below the sticky header, not under it
    var nav = document.querySelector('.site-header');
    if (nav) {
        var padTop = parseFloat(getComputedStyle(root).paddingTop) || 0;
        root.style.scrollMarginTop = Math.max(nav.offsetHeight - padTop + 16, 0) + 'px';
    }

    if ('IntersectionObserver' in window) {
        new IntersectionObserver(function (entries) {
            // the first callback fires even when barely visible, so check the ratio
            onScreen = entries[0].intersectionRatio >= 0.4;
            if (onScreen) start();
        }, { threshold: 0.4 }).observe(stage);
    } else {
        onScreen = true;
        start();
    }
})();
