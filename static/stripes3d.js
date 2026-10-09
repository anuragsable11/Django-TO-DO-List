/* Stripes in 3D.
   Mounts a WebGL tiger (three.js, see static/stripes3d/) over every element marked data-stripes-3d.
   The SVG tiger inside the element stays as the loading state and the fallback: it is only hidden
   once the 3D one has rendered, and comes back if the WebGL context is lost.
     data-stripes-3d="sidekick"  driven by mascot.js through the rig sent in a "stripes:ready" event
     data-stripes-3d="wave"      runs on its own: drops in, waves, blinks and watches the pointer
   Dragging the character (mouse or touch) turns it around; it springs back when let go. */
import { makeTextures } from './stripes3d/textures.js';
import { buildTiger } from './stripes3d/tiger.js';
import { createStage } from './stripes3d/stage.js';
import { createRig } from './stripes3d/rig.js';

const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const DRAG_THRESHOLD = 6;      // px of movement before a press counts as a drag, not a click

function mount(host) {
    const mode = host.getAttribute('data-stripes-3d'); // not dataset: "-3d" doesn't camel-case
    const canvas = document.createElement('canvas');
    canvas.className = 'stripes-3d';
    canvas.setAttribute('aria-hidden', 'true');
    host.appendChild(canvas);

    let stage;
    let textures;
    try {
        stage = createStage(canvas);
        textures = makeTextures(stage.renderer);
    } catch (e) {
        canvas.remove(); // no WebGL: the SVG stays
        return;
    }
    stage.setContactTexture(textures.contact);

    // Sculpting the character takes a few hundred milliseconds, so it waits for an idle moment:
    // the SVG tiger stands in until then, and nothing else on the page is held up.
    const idle = window.requestIdleCallback ? (cb) => window.requestIdleCallback(cb, { timeout: 600 }) : (cb) => setTimeout(cb, 80);
    idle(() => {
        const quality = window.innerWidth < 640 || (navigator.hardwareConcurrency || 8) <= 4 ? 'low' : 'high';
        const t0 = performance.now();
        const parts = buildTiger({ quality });
        host.dataset.stripesBuildMs = Math.round(performance.now() - t0); // sculpting time, for debugging
        parts.tiger.visible = false;
        stage.scene.add(parts.tiger);
        run(host, canvas, stage, mode, parts, createRig(parts, stage, { reduceMotion }));
    });
}

// Everything after the model exists: render loop, interaction, and the public rig
function run(host, canvas, stage, mode, parts, rig) {
    /* ---------- Render loop: only while on screen, only when something can change ---------- */
    let running = false;
    let last = 0;
    let shown = false;

    // Adaptive quality, so motion stays smooth on any device. Every 1.5 s of animation, if the
    // typical frame took longer than ~22 ms, step down once (never back up, to avoid flicker):
    //   1: every second fur layer  2: every fourth fur layer  3: render at 1x pixel density
    // The fur keeps its length and look at each step; it just gets a little thinner.
    let furStep = 1;
    let level = 0;
    let watchFrom = 0;
    let samples = [];
    function setFurStep(step) {
        furStep = step;
        parts.tiger.traverse((o) => {
            const f = o.userData.furShell;
            if (f) o.visible = f.index % step === 0 || f.index === f.total;
        });
    }
    function adapt(now, ms) {
        if (!watchFrom) watchFrom = now + 1000;  // let shaders compile first
        if (now < watchFrom) return;
        samples.push(ms);
        if (now - watchFrom < 1500 || samples.length < 3) return;
        samples.sort((a, b) => a - b);
        const typical = samples[Math.floor(samples.length / 2)];
        samples = [];
        watchFrom = now;
        if (typical <= 22 || level >= 3) return;
        level += 1;
        if (level <= 2) setFurStep(2 ** level);
        else if (stage.renderer.getPixelRatio() > 1) {
            stage.renderer.setPixelRatio(1);
            stage.resize();
        }
    }

    // Only one loop may ever run: each start gets a new id, and older pending frames see it and stop
    let loopId = 0;

    function frame(id, now) {
        if (!running || id !== loopId) return;
        const ms = now - last;
        if (ms > 0) {
            adapt(now, ms);
            rig.advance(ms / 1000);
        }
        last = now;
        stage.render();
        requestAnimationFrame((t) => frame(id, t));
    }

    function startLoop() {
        if (running || reduceMotion) return;
        running = true;
        const id = ++loopId;
        last = performance.now();
        requestAnimationFrame((t) => frame(id, t));
    }

    // reduced motion: no loop, just a fresh still whenever something changes
    function still() {
        rig.update(0, true);
        stage.render();
    }

    function show() {
        if (shown) return;
        shown = true;
        host.classList.add('has-3d');
    }

    new ResizeObserver(() => {
        if (stage.resize() && !running) still();
    }).observe(canvas);

    new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting) startLoop();
        else running = false;
    }).observe(canvas);

    // Lost context (GPU reset, too many contexts): bring the SVG back; restored: carry on
    canvas.addEventListener('webglcontextlost', (e) => {
        e.preventDefault();
        running = false;
        host.classList.remove('has-3d');
        shown = false;
    });
    canvas.addEventListener('webglcontextrestored', () => {
        show();
        startLoop();
        if (reduceMotion) still();
    });

    /* ---------- Drag to rotate (mouse, pen and touch); a short tap is still a click ---------- */
    let press = null;
    host.style.touchAction = 'pan-y';

    host.addEventListener('pointerdown', (e) => {
        if (e.button !== 0 && e.pointerType === 'mouse') return;
        press = { id: e.pointerId, x: e.clientX, dragged: false };
    });

    host.addEventListener('pointermove', (e) => {
        if (!press || e.pointerId !== press.id) return;
        const dx = e.clientX - press.x;
        if (!press.dragged && Math.abs(dx) < DRAG_THRESHOLD) return;
        if (!press.dragged) {
            press.dragged = true;
            host.classList.add('is-dragging');
            try { host.setPointerCapture(e.pointerId); } catch (err) { /* already released */ }
        }
        rig.spin(dx * 0.012);
        if (reduceMotion) still();
    });

    function endPress(e) {
        if (!press || e.pointerId !== press.id) return;
        if (press.dragged) {
            host.classList.remove('is-dragging');
            rig.release();
            if (reduceMotion) still();
            // swallow the click that follows a drag
            host.addEventListener('click', (c) => { c.stopPropagation(); c.preventDefault(); }, { capture: true, once: true });
            setTimeout(() => { if (!running) still(); }, 0);
        }
        press = null;
    }
    host.addEventListener('pointerup', endPress);
    host.addEventListener('pointercancel', endPress);

    /* ---------- Public rig: what mascot.js (or the standalone script below) drives ---------- */
    const api = {
        pose(name) { rig.pose(name); if (reduceMotion) still(); },
        talk(on) { rig.talk(on); if (reduceMotion) still(); },
        happy(on) { rig.happy(on); if (reduceMotion) still(); },
        hop() { rig.hop(); },
        land() {
            rig.land();
            show();
            if (reduceMotion) still();
        },
        blink() { rig.blink(); },
        twitch() { rig.twitch(); },
        look(x, y) {
            rig.look(x, y, canvas.getBoundingClientRect());
            if (reduceMotion) still();
        },
        face(radians) { rig.face(radians); if (reduceMotion) still(); },
        // rendering cost and fur level, for debugging
        stats() {
            const info = stage.renderer.info.render;
            return { triangles: info.triangles, drawCalls: info.calls, level, furStep, pixelRatio: stage.renderer.getPixelRatio() };
        },
        state: rig.state,
    };
    host.stripes3d = api; // handy for debugging in the console

    stage.resize();

    if (mode === 'sidekick') {
        host.dispatchEvent(new CustomEvent('stripes:ready', { bubbles: true, detail: api }));
        return;
    }

    // Standalone: drop in, wave hello, then idle, blink and watch the pointer
    api.land();
    setTimeout(() => api.pose('wave'), 900);
    setTimeout(() => api.pose(null), 3800);
    window.addEventListener('pointermove', (e) => {
        if (e.pointerType === 'mouse' && !rig.dragging) api.look(e.clientX, e.clientY);
    }, { passive: true });
    (function blinkSoon() {
        setTimeout(() => {
            api.blink();
            if (Math.random() < 0.25) api.twitch();
            blinkSoon();
        }, 2200 + Math.random() * 3200);
    })();
}

document.querySelectorAll('[data-stripes-3d]').forEach(mount);
