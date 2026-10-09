/* Animation for the Stripes model: a transform rig (groups pivoting at shoulders, neck, tail joints)
   driven by springs, plus vertex animation for the cape. Not a skinned skeleton: no bones or skin weights. */
import { POSES, LID_OPEN, LID_CLOSED } from './tiger.js';

function spring(s, target, dt, stiffness = 150, damping = 15) {
    s.v += (stiffness * (target - s.x) - damping * s.v) * dt;
    s.x += s.v * dt;
}

function snap(s, target) {
    s.x = target;
    s.v = 0;
}

export function createRig(parts, stage, { reduceMotion, facing: initialFacing = 0.16 }) {
    let facing = initialFacing;
    const { tiger, body, head } = parts;
    const S = (x) => ({ x, v: 0 });

    const arms = { R: { z: S(POSES.rest.R[0]), x: S(POSES.rest.R[1]) }, L: { z: S(POSES.rest.L[0]), x: S(POSES.rest.L[1]) } };
    const yaw = S(0);
    const pitch = S(0);
    const mouth = S(0);
    const brow = S(0);
    const finger = S(0);
    const spin = S(0);
    const pupil = { x: S(0), y: S(0) };

    let pose = null;
    let poseAge = 0;
    let talking = false;
    let happy = false;
    let lookYaw = 0;
    let lookPitch = 0;
    let lookX = 0;
    let lookY = 0;
    let spinTarget = 0;
    let dragging = false;
    let hopAge = -1;
    let landAge = -1;
    let blinkAge = -1;
    let twitchAge = -1;
    let clock = 0;
    const pendingHops = [];

    function ease(s, target, dt, instant, stiffness, damping) {
        if (instant) snap(s, target);
        else spring(s, target, dt, stiffness, damping);
    }

    function updateArms(dt, instant) {
        const p = POSES[pose] || POSES.rest;
        for (const side of ['L', 'R']) {
            let tz = p[side][0];
            let tx = p[side][1];
            if (side === 'R' && pose === 'wave' && poseAge > 0.35 && poseAge < 2.6) tz += Math.sin((poseAge - 0.35) * 9) * 0.32;
            if (side === 'R' && pose === 'point' && poseAge > 0.35 && poseAge < 1.4) tx -= Math.sin((poseAge - 0.35) * 12) * 0.08;
            ease(arms[side].z, tz, dt, instant, 130, 13);
            ease(arms[side].x, tx, dt, instant, 130, 13);
            parts.arms[side].rotation.set(arms[side].x.x, 0, arms[side].z.x);
        }
    }

    // One simulation step. `settle` is false for intermediate sub-steps, which skip the cloth update.
    function update(dt, instant, settle = true) {
        clock += dt;
        poseAge += dt;
        const t = clock;
        const cheering = pose === 'cheer';

        updateArms(dt, instant);

        // pointing finger grows out in the point pose
        ease(finger, pose === 'point' ? 1 : 0, dt, instant, 200, 18);
        parts.finger.scale.setScalar(Math.max(finger.x, 0.001));

        // cheering ticks the clipboard
        parts.ticks.forEach((tick) => { tick.visible = cheering; });

        // mouth: flaps while talking, open when happy
        let mouthTarget = 0;
        if (talking) mouthTarget = Math.sin(t * 19) > 0 ? 0.9 : 0.2;
        else if (happy || cheering) mouthTarget = 0.85;
        ease(mouth, mouthTarget, dt, instant, 520, 30);
        const open = Math.max(mouth.x, 0);
        parts.mouth.visible = open > 0.05;
        parts.mouth.scale.set(0.6 + open * 0.4, Math.max(open, 0.001), 1);
        parts.smile.visible = open < 0.35;

        // brows lift when pleased
        ease(brow, happy || cheering || pose === 'wave' ? 0.04 : 0, dt, instant, 160, 16);
        parts.brows.position.y = brow.x;

        // blink: the eyelids roll down over the eyeballs and back; cheering swaps the eyes for happy arcs
        let closed = 0;
        if (blinkAge >= 0) {
            blinkAge += dt;
            closed = blinkAge < 0.18 ? Math.sin(Math.PI * blinkAge / 0.18) : 0;
            if (blinkAge >= 0.18) blinkAge = -1;
        }
        parts.lids.forEach((lid) => { lid.rotation.x = LID_OPEN + (LID_CLOSED - LID_OPEN) * closed; });
        parts.eyes.forEach((eye) => { eye.visible = !cheering; });
        parts.happyEyes.forEach((arc) => { arc.visible = cheering; });

        // a quick little head shake (the ears are part of the sculpt, so this stands in for a twitch)
        let shake = 0;
        if (twitchAge >= 0) {
            twitchAge += dt;
            shake = Math.sin(twitchAge * 26) * 0.06 * Math.max(0, 1 - twitchAge / 0.45);
            if (twitchAge >= 0.45) twitchAge = -1;
        }

        // head and pupils follow the look target (less while being spun around)
        const attention = dragging ? 0.3 : 1;
        ease(yaw, lookYaw * attention, dt, instant, 60, 11);
        ease(pitch, lookPitch * attention, dt, instant, 60, 11);
        head.rotation.set(pitch.x, yaw.x, (reduceMotion ? 0 : Math.sin(t * 0.9) * 0.03) + shake);
        ease(pupil.x, lookX, dt, instant, 300, 26);
        ease(pupil.y, lookY, dt, instant, 300, 26);
        parts.pupils.forEach((p) => p.position.set(pupil.x.x, pupil.y.x, 0.05));


        // idle life: breathing, tail, cape
        if (!reduceMotion) {
            body.scale.set(1 - Math.sin(t * 2) * 0.004, 1 + Math.sin(t * 2) * 0.012, 1);
            parts.tail.forEach((j, i) => {
                j.rotation.z = j.userData.curl + Math.sin(t * 2.3 - i * 0.55) * 0.12;
                j.rotation.x = Math.sin(t * 1.7 - i * 0.4) * 0.05;
            });
            if (settle) parts.cape.update(t);
        }

        // jumps: hops (clicks, cheers) and the drop-in landing
        let lift = 0;
        let squash = 0;
        let turn = 0;
        if (pendingHops.length && pendingHops[0] <= clock && hopAge < 0 && landAge < 0) {
            pendingHops.shift();
            hopAge = 0;
        }
        if (hopAge >= 0) {
            hopAge += dt;
            const u = Math.min(hopAge / 0.55, 1);
            lift = 0.42 * 4 * u * (1 - u);
            if (u < 0.15) squash = -0.1 * Math.sin(u / 0.15 * Math.PI);
            else if (u > 0.85) squash = -0.09 * Math.sin((u - 0.85) / 0.15 * Math.PI);
            else squash = 0.05 * Math.sin((u - 0.15) / 0.7 * Math.PI);
            if (u >= 1) hopAge = -1;
        }
        if (landAge >= 0) {
            landAge += dt;
            if (landAge < 0.5) {
                const u = landAge / 0.5;
                lift = 2.6 * (1 - u * u);
                turn = 0.9 * (1 - u);
            } else {
                const v = Math.min((landAge - 0.5) / 0.45, 1);
                squash = -0.15 * Math.sin(v * Math.PI) * (1 - v * 0.5);
                if (v >= 1) landAge = -1;
            }
        }

        // drag-to-rotate, springing back to face front when released
        ease(spin, dragging ? spinTarget : 0, dt, instant, dragging ? 400 : 40, dragging ? 40 : 9);
        if (!dragging) spinTarget = spin.x;

        tiger.position.y = lift;
        tiger.scale.set(1 / Math.sqrt(1 + squash), 1 + squash, 1 / Math.sqrt(1 + squash));
        tiger.rotation.y = facing + spin.x + turn + (reduceMotion ? 0 : Math.sin(t * 0.6) * 0.04);
        stage.setContact(lift, tiger.visible);
    }

    // Advance by real elapsed time in sub-steps of at most 1/60 s, so the springs stay stable and the
    // animation keeps real-time pace even when a slow device only manages a few frames per second.
    function advance(elapsed) {
        const total = Math.min(Math.max(elapsed, 0), 0.5);
        const steps = Math.min(Math.ceil(total / (1 / 60)) || 1, 30);
        const dt = total / steps;
        for (let i = 0; i < steps; i++) update(dt, false, i === steps - 1);
    }

    const clamp = (n) => Math.max(-1, Math.min(1, n));

    return {
        update,
        advance,
        pose(name) {
            const next = POSES[name] && name !== 'rest' ? name : null;
            if (next === 'cheer' && pose !== 'cheer') pendingHops.push(clock, clock + 0.6);
            if (next !== pose) poseAge = 0;
            pose = next;
        },
        talk(on) {
            talking = !!on;
        },
        happy(on) {
            happy = !!on;
        },
        hop() {
            if (!reduceMotion) pendingHops.push(clock);
        },
        land() {
            tiger.visible = true;
            if (!reduceMotion) landAge = 0;
        },
        blink() {
            if (!reduceMotion) blinkAge = 0;
        },
        twitch() {
            if (!reduceMotion) twitchAge = 0;
        },
        // Look toward a point on screen, given in client coordinates and the canvas box
        look(x, y, box) {
            const dx = x - (box.left + box.width / 2);
            const dy = y - (box.top + box.height * 0.36);
            lookYaw = clamp(dx / (box.width * 1.6)) * 0.6;
            lookPitch = clamp(dy / (box.height * 1.2)) * 0.32;
            lookX = clamp(dx / 320) * 0.032;
            lookY = clamp(-dy / 320) * 0.028;
        },
        // Drag rotation: radians, relative to where the drag started
        spin(radians) {
            dragging = true;
            spinTarget = Math.max(-2.4, Math.min(2.4, radians));
        },
        release() {
            dragging = false;
        },
        // which way the character faces at rest (radians around the vertical axis)
        face(radians) {
            facing = radians;
        },
        get dragging() {
            return dragging;
        },
        // what the rig is doing right now, for debugging
        state() {
            return {
                pose, talking, happy, dragging,
                visible: tiger.visible,
                spin: +spin.x.toFixed(3),
                turnY: +tiger.rotation.y.toFixed(3),
                headYaw: +yaw.x.toFixed(3),
                clock: +clock.toFixed(2),
                lift: +tiger.position.y.toFixed(3),
                scaleY: +tiger.scale.y.toFixed(3),
                landing: landAge >= 0,
                hopping: hopAge >= 0,
                queuedHops: pendingHops.length,
            };
        },
    };
}
