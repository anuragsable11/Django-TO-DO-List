/* The Stripes model. The head, body and arms are sculpted as smooth merged surfaces and painted per
   vertex (stripes, belly, muzzle, paws, inner ears, blush), then covered in shell fur. Eyes, nose,
   mouth, whiskers, badge, cape, clipboard and tail are separate meshes placed against the sculpt.
   buildTiger() returns the named parts the rig animates. Nothing here moves on its own. */
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { COLORS } from './textures.js';
import { sculpt, surfacePoint, strokePainter, projections, blobMask, smoothstep, mix, rgb } from './sculpt.js';
import { furMaterial, furredMesh } from './fur.js';

// Shoulder angles [around z, around x]. Arms hang down; +z swings the right arm out and up.
export const POSES = {
    rest:  { R: [0.3, -0.28],  L: [-0.3, -0.28] },
    wave:  { R: [2.25, -0.25], L: [-0.3, -0.28] },
    point: { R: [2.6, -0.5],   L: [-0.3, -0.28] },
    cheer: { R: [2.35, -0.3],  L: [-2.3, -0.32] },
};

// Eyelid angles (around the eye's x axis). Open tucks the lid up and back; closed rolls it over the front.
export const LID_OPEN = -1.25;
export const LID_CLOSED = 1.45;

const SPHERE = new THREE.SphereGeometry(1, 48, 32);
const SPHERE_LOW = new THREE.SphereGeometry(1, 16, 12);
const LID_CAP = new THREE.SphereGeometry(1, 40, 20, 0, Math.PI * 2, 0, Math.PI / 2);

const FUR = rgb(COLORS.fur);
const CREAM = rgb(COLORS.cream);
const INK = rgb(COLORS.ink);
const EAR = rgb(COLORS.earInner);
const BLUSH = rgb(COLORS.blush);

function mesh(geometry, material, { pos, scale, rot } = {}) {
    const m = new THREE.Mesh(geometry, material);
    if (pos) m.position.set(...pos);
    if (scale !== undefined) {
        if (Array.isArray(scale)) m.scale.set(...scale);
        else m.scale.setScalar(scale);
    }
    if (rot) m.rotation.set(...rot);
    m.castShadow = true;
    m.receiveShadow = true;
    return m;
}

// A smooth tube through points, with rounded ends
function tube(points, radius, material, segments = 40) {
    const curve = new THREE.CatmullRomCurve3(points.map((p) => (p.isVector3 ? p : new THREE.Vector3(...p))));
    const t = mesh(new THREE.TubeGeometry(curve, segments, radius, 10, false), material);
    for (const p of [points[0], points[points.length - 1]]) t.add(mesh(SPHERE_LOW, material, { pos: p.isVector3 ? p.toArray() : p, scale: radius }));
    return t;
}

function makeMaterials() {
    return {
        ink: new THREE.MeshStandardMaterial({ color: COLORS.ink, roughness: 0.5 }),
        whisker: new THREE.MeshStandardMaterial({ color: COLORS.whisker, roughness: 0.4 }),
        eyeWhite: new THREE.MeshPhysicalMaterial({ color: '#ffffff', roughness: 0.12, clearcoat: 1, clearcoatRoughness: 0.05 }),
        iris: new THREE.MeshPhysicalMaterial({ color: '#7a3f12', roughness: 0.3, clearcoat: 1, clearcoatRoughness: 0.05 }),
        pupil: new THREE.MeshPhysicalMaterial({ color: '#121419', roughness: 0.2, clearcoat: 1, clearcoatRoughness: 0.04 }),
        glint: new THREE.MeshBasicMaterial({ color: '#ffffff' }),
        nose: new THREE.MeshPhysicalMaterial({ color: COLORS.pink, roughness: 0.28, clearcoat: 0.9, clearcoatRoughness: 0.12 }),
        mouth: new THREE.MeshStandardMaterial({ color: COLORS.mouth, roughness: 0.65 }),
        tongue: new THREE.MeshPhysicalMaterial({ color: COLORS.tongue, roughness: 0.4, clearcoat: 0.6 }),
        tooth: new THREE.MeshStandardMaterial({ color: '#fffaf0', roughness: 0.35 }),
        cape: new THREE.MeshPhysicalMaterial({ color: COLORS.cape, roughness: 0.6, sheen: 1, sheenRoughness: 0.35, sheenColor: COLORS.capeSheen, side: THREE.DoubleSide }),
        badge: new THREE.MeshPhysicalMaterial({ color: COLORS.badge, roughness: 0.22, clearcoat: 1, clearcoatRoughness: 0.08 }),
        gold: new THREE.MeshStandardMaterial({ color: COLORS.gold, metalness: 1, roughness: 0.28 }),
        white: new THREE.MeshStandardMaterial({ color: '#ffffff', roughness: 0.35 }),
        wood: new THREE.MeshStandardMaterial({ color: COLORS.wood, roughness: 0.5 }),
        paper: new THREE.MeshStandardMaterial({ color: COLORS.paper, roughness: 0.9 }),
        metal: new THREE.MeshStandardMaterial({ color: '#d4d4d4', metalness: 1, roughness: 0.32 }),
        line: new THREE.MeshStandardMaterial({ color: COLORS.line, roughness: 0.9 }),
        tick: new THREE.MeshStandardMaterial({ color: COLORS.tick, roughness: 0.45, emissive: COLORS.tick, emissiveIntensity: 0.25 }),
        // plain fur for the tail segments: no vertex colours, same grain
        furSolid: furMaterial({ vertexColors: false, color: COLORS.fur }),
        inkFur: furMaterial({ vertexColors: false, color: COLORS.ink, sheenColor: '#777' }),
        lid: furMaterial({ vertexColors: false, color: COLORS.fur }),
    };
}

// The cape is a cloth sheet hanging from the back of the collar. update(t) ripples it.
function makeCape(material) {
    const geometry = new THREE.PlaneGeometry(1, 1, 14, 20);
    const position = geometry.attributes.position;
    const base = [];
    for (let i = 0; i < position.count; i++) {
        const e = position.getX(i) * 2;            // -1 .. 1 across
        const s = position.getY(i) + 0.5;          // 0 at the hem, 1 at the collar
        const width = THREE.MathUtils.lerp(0.92, 0.3, s);
        const x = e * width / 2;
        const y = THREE.MathUtils.lerp(0.2, 1.03, s);
        const pleats = Math.sin(e * Math.PI * 2.5 + 0.5) * 0.045 * Math.pow(1 - s, 0.7);
        const z = -0.27 - 0.24 * Math.pow(1 - s, 0.7) + 0.24 * e * e * (1 - s) - pleats;
        base.push([x, y, z, s, e]);
        position.setXYZ(i, x, y, z);
    }
    geometry.computeVertexNormals();
    const cape = mesh(geometry, material);

    function update(t) {
        for (let i = 0; i < position.count; i++) {
            const [x, y, z, s, e] = base[i];
            const free = Math.pow(1 - s, 1.4);      // the hem moves most, the collar not at all
            const wave = Math.sin(t * 2.2 + s * 3.2 + e * 1.6) * 0.035 + Math.sin(t * 1.3 + e * 2.4) * 0.02;
            position.setXYZ(i, x + Math.sin(t * 1.1 + s * 2) * 0.012 * free, y, z - wave * free);
        }
        position.needsUpdate = true;
        geometry.computeVertexNormals();
    }

    return { mesh: cape, update };
}

/* ---------- Head ---------- */

const HEAD_C = [0, 0.47, 0];   // head centre, in the head group's space (pivot at the neck)

const HEAD_BLOBS = [
    { p: [0, 0.47, 0], r: 0.5 },                                   // skull
    { p: [-0.4, 0.34, 0.12], r: 0.2, blend: 7 }, { p: [0.4, 0.34, 0.12], r: 0.2, blend: 7 },   // cheek ruff
    { p: [-0.11, 0.3, 0.4], r: 0.16, blend: 9 }, { p: [0.11, 0.3, 0.4], r: 0.16, blend: 9 },   // muzzle
    { p: [0, 0.2, 0.32], r: 0.11, blend: 9 },                                                    // chin
    { p: [-0.2, 0.66, 0.35], r: 0.12, blend: 9 }, { p: [0.2, 0.66, 0.35], r: 0.12, blend: 9 }, // brow ridge
    { p: [-0.33, 0.9, -0.02], r: 0.165, blend: 8 }, { p: [0.33, 0.9, -0.02], r: 0.165, blend: 8 }, // ears
    { p: [0, 1.03, 0.06], r: 0.085, blend: 12 }, { p: [-0.085, 0.99, 0.09], r: 0.062, blend: 12 }, { p: [0.09, 0.985, 0.05], r: 0.058, blend: 12 }, // tuft
    { p: [0, 0.06, 0], r: 0.19 },                                   // neck
];

// How far the merged surface actually sits from a blob's centre, measured outward from the head centre
function surfaceRadius(blobs, centre, blob) {
    const out = [blob.p[0] - centre[0], blob.p[1] - centre[1], blob.p[2] - centre[2]];
    return surfacePoint(blobs, blob.p, out).distanceTo(new THREE.Vector3(...blob.p));
}

function paintHead() {
    const radial = projections.radial(...HEAD_C);
    const D = (x, y, z) => [HEAD_C[0] + x, HEAD_C[1] + y, HEAD_C[2] + z]; // a point in the given direction
    // half-widths are in direction space: 0.05 is about 3 degrees, 0.025 units on this head
    const stripes = strokePainter(radial, [
        // forehead: thick at the hairline, tapering down toward the brows
        { pts: [D(0, 0.86, 0.5), D(0, 0.56, 0.84)], w: [0.05, 0.018] },
        { pts: [D(-0.18, 0.84, 0.5), D(-0.12, 0.58, 0.8)], w: [0.042, 0.016] },
        { pts: [D(0.18, 0.84, 0.5), D(0.12, 0.58, 0.8)], w: [0.042, 0.016] },
        { pts: [D(-0.36, 0.78, 0.46), D(-0.27, 0.6, 0.72)], w: [0.036, 0.015] },
        { pts: [D(0.36, 0.78, 0.46), D(0.27, 0.6, 0.72)], w: [0.036, 0.015] },
        // cheeks: from the sides, curving onto the front of the ruff toward the muzzle
        { pts: [D(-0.95, 0.25, -0.1), D(-0.75, 0.2, 0.55), D(-0.55, 0.14, 0.83)], w: [0.085, 0.02] },
        { pts: [D(0.95, 0.25, -0.1), D(0.75, 0.2, 0.55), D(0.55, 0.14, 0.83)], w: [0.085, 0.02] },
        { pts: [D(-0.97, 0.05, -0.12), D(-0.78, 0.02, 0.52), D(-0.6, -0.02, 0.8)], w: [0.09, 0.02] },
        { pts: [D(0.97, 0.05, -0.12), D(0.78, 0.02, 0.52), D(0.6, -0.02, 0.8)], w: [0.09, 0.02] },
        { pts: [D(-0.93, -0.15, -0.12), D(-0.76, -0.18, 0.5), D(-0.6, -0.2, 0.76)], w: [0.08, 0.02] },
        { pts: [D(0.93, -0.15, -0.12), D(0.76, -0.18, 0.5), D(0.6, -0.2, 0.76)], w: [0.08, 0.02] },
        // crown and the back of the head
        { pts: [D(0, 0.95, -0.15), D(0, 0.7, -0.7)], w: [0.07, 0.03] },
        { pts: [D(-0.22, 0.92, -0.2), D(-0.2, 0.7, -0.66)], w: [0.055, 0.025] },
        { pts: [D(0.22, 0.92, -0.2), D(0.2, 0.7, -0.66)], w: [0.055, 0.025] },
        { pts: [D(-0.5, 0.35, -0.75), D(-0.15, 0.2, -0.95)], w: [0.06, 0.025] },
        { pts: [D(0.5, 0.35, -0.75), D(0.15, 0.2, -0.95)], w: [0.06, 0.025] },
    ], 0.025);

    // masks sized to where the merged surface really is
    const jowls = HEAD_BLOBS.filter((b) => b.r === 0.16);
    const chin = HEAD_BLOBS.find((b) => b.r === 0.11);
    const ears = HEAD_BLOBS.filter((b) => b.r === 0.165);
    const jowlR = surfaceRadius(HEAD_BLOBS, HEAD_C, jowls[0]);
    const chinR = surfaceRadius(HEAD_BLOBS, HEAD_C, chin);
    const earR = surfaceRadius(HEAD_BLOBS, HEAD_C, ears[0]);
    const blushAt = [-1, 1].map((side) => surfacePoint(HEAD_BLOBS, HEAD_C, [side * 0.33, -0.08, 0.42]));

    return (p) => {
        let c = FUR;
        // muzzle and chin
        const cream = Math.max(
            ...jowls.map((b) => blobMask(p, ...b.p, jowlR * 0.9, jowlR * 1.35)),
            blobMask(p, ...chin.p, chinR * 0.85, chinR * 1.3));
        c = mix(c, CREAM, cream);
        // inner ears: a pink patch on the front face of each ear
        for (const ear of ears) {
            const front = [ear.p[0] * 0.97, ear.p[1] - 0.01, ear.p[2] + earR * 0.75];
            c = mix(c, EAR, blobMask(p, ...front, 0.07, 0.13));
        }
        c = mix(c, INK, stripes(p) * (1 - cream));
        // a soft blush on the cheeks
        const blush = Math.max(...blushAt.map((b) => blobMask(p, b.x, b.y, b.z, 0.04, 0.13)));
        return mix(c, BLUSH, blush * 0.32);
    };
}

/* ---------- Body ---------- */

const BODY_BLOBS = [
    { p: [0, 0.66, 0], r: 0.4 },                                    // torso
    { p: [0, 0.9, 0], r: 0.3, blend: 8 },                           // chest
    { p: [0, 0.58, 0.14], r: 0.34, blend: 7 },                      // belly
    { p: [-0.08, 0.42, 0], r: 0.3, blend: 8 }, { p: [0.08, 0.42, 0], r: 0.3, blend: 8 },        // hips
    { p: [0, 1.1, 0.02], r: 0.18, blend: 7 },                       // neck
    { p: [-0.35, 0.92, 0.08], r: 0.15, blend: 9 }, { p: [0.35, 0.92, 0.08], r: 0.15, blend: 9 }, // shoulders
    { p: [-0.17, 0.3, 0.02], r: 0.15, blend: 9 }, { p: [0.17, 0.3, 0.02], r: 0.15, blend: 9 },   // legs
    { p: [-0.17, 0.2, 0.03], r: 0.145, blend: 9 }, { p: [0.17, 0.2, 0.03], r: 0.145, blend: 9 },
    { p: [-0.17, 0.12, 0.1], r: 0.14, blend: 9 }, { p: [0.17, 0.12, 0.1], r: 0.14, blend: 9 },   // feet
    { p: [-0.17, 0.1, 0.2], r: 0.1, blend: 11 }, { p: [0.17, 0.1, 0.2], r: 0.1, blend: 11 },     // toes
];

function paintBody() {
    const around = projections.cylinder(0, 0, 0.38);
    const A = (angle, y) => [Math.sin(angle) * 0.4, y, Math.cos(angle) * 0.4];
    const strokes = [];
    for (const s of [-1, 1]) {
        // flank stripes sweeping down toward the belly
        strokes.push({ pts: [A(s * 2.5, 0.98), A(s * 1.6, 0.93), A(s * 1.0, 0.86)], w: [0.07, 0.02] });
        strokes.push({ pts: [A(s * 2.6, 0.82), A(s * 1.7, 0.77), A(s * 1.05, 0.7)], w: [0.075, 0.02] });
        strokes.push({ pts: [A(s * 2.6, 0.66), A(s * 1.7, 0.6), A(s * 1.1, 0.53)], w: [0.07, 0.02] });
        strokes.push({ pts: [A(s * 2.5, 0.5), A(s * 1.75, 0.45), A(s * 1.2, 0.4)], w: [0.06, 0.02] });
        // chevrons down the back (split at the seam behind)
        for (const y of [0.92, 0.74, 0.56]) strokes.push({ pts: [A(s * 3.1, y), A(s * 2.4, y - 0.08)], w: [0.05, 0.02] });
    }
    const stripes = strokePainter(around, strokes, 0.02);
    const creases = strokePainter(projections.world(), [-1, 1].flatMap((s) => [-1, 1].map((t) => ({
        pts: [[s * 0.17 + t * 0.045, 0.21, 0.19], [s * 0.17 + t * 0.045, 0.12, 0.27]], w: [0.015], soft: 0.012,
    }))));

    return (p) => {
        let c = FUR;
        const facing = p.z / (Math.hypot(p.x, p.z) || 1);
        const belly = smoothstep(0.62, 0.9, facing) * smoothstep(0.4, 0.52, p.y) * smoothstep(0.98, 0.86, p.y);
        c = mix(c, CREAM, belly);
        const feet = smoothstep(0.22, 0.15, p.y);
        c = mix(c, CREAM, feet);
        c = mix(c, INK, stripes(p) * (1 - belly) * (1 - feet));
        return mix(c, INK, creases(p) * feet);
    };
}

/* ---------- Arms ---------- */

const ARM_BLOBS = [
    { p: [0, 0, 0], r: 0.125, blend: 8 },          // shoulder ball, sits inside the body's shoulder
    { p: [0, -0.12, 0], r: 0.1, blend: 9 },
    { p: [0, -0.25, 0], r: 0.095, blend: 9 },
    { p: [0, -0.4, 0.01], r: 0.115, blend: 8 },    // paw
    { p: [0, -0.46, 0.06], r: 0.07, blend: 12 },   // fingers
];

function paintArm() {
    const creases = strokePainter(projections.world(), [-1, 1].map((s) => ({
        pts: [[s * 0.028, -0.38, 0.1], [s * 0.028, -0.45, 0.095]], w: [0.011], soft: 0.01,
    })));
    return (p) => {
        let c = FUR;
        const paw = smoothstep(-0.3, -0.36, p.y);
        c = mix(c, CREAM, paw);
        const angle = Math.atan2(p.x, p.z);
        let band = 0;
        for (const yb of [-0.14, -0.25]) band = Math.max(band, smoothstep(0.045, 0.025, Math.abs(p.y - yb - 0.012 * Math.sin(angle * 2 + 1))));
        c = mix(c, INK, band * (1 - paw));
        return mix(c, INK, creases(p) * paw);
    };
}

/* ---------- Assembly ---------- */

export function buildTiger({ quality = 'high' } = {}) {
    const high = quality === 'high';
    const fur = { shells: high ? 14 : 5 };
    const mat = makeMaterials();
    const parts = {};
    const tiger = new THREE.Group();    // whole character, feet on y = 0
    const body = new THREE.Group();     // everything that breathes
    tiger.add(body);
    parts.tiger = tiger;
    parts.body = body;

    // Body: torso, neck, legs and feet in one sculpt
    const bodyGeo = sculpt({ center: [0, 0.62, 0.02], size: 0.74, resolution: high ? 64 : 48, blobs: BODY_BLOBS, paint: paintBody(), scale: [1, 1, 0.9] });
    body.add(furredMesh(bodyGeo, { ...fur, length: 0.034, density: 300 }));

    // Cape, hanging from behind the neck
    parts.cape = makeCape(mat.cape);
    body.add(parts.cape.mesh);

    // Enamel badge with a gold rim and a white tick, on the chest
    const chest = surfacePoint(BODY_BLOBS, [0, 0.84, 0], [0, 0, 1]);
    const badge = new THREE.Group();
    badge.position.set(0, 0.84, chest.z + 0.012);
    badge.rotation.x = -0.2;
    badge.scale.setScalar(1.15);
    badge.add(mesh(new THREE.CylinderGeometry(0.1, 0.1, 0.032, 48), mat.badge, { rot: [Math.PI / 2, 0, 0] }));
    badge.add(mesh(new THREE.TorusGeometry(0.1, 0.012, 12, 64), mat.gold));
    badge.add(tube([[-0.046, 0.003, 0.018], [-0.013, -0.03, 0.018], [0.05, 0.042, 0.018]], 0.012, mat.white, 24));
    body.add(badge);

    // Tail: a chain of banded segments that curls up beside the right hip
    const tailRoot = new THREE.Group();
    tailRoot.position.set(0.3, 0.34, -0.04);
    const tailDir = new THREE.Vector3(1, -0.12, 0.06).normalize();
    const tailDown = new THREE.Vector3(0, -1, 0).addScaledVector(tailDir, -tailDir.y).normalize();
    tailRoot.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(tailDown, tailDir, tailDown.clone().cross(tailDir)));
    body.add(tailRoot);
    const tailColors = ['furSolid', 'furSolid', 'inkFur', 'furSolid', 'furSolid', 'inkFur', 'furSolid', 'inkFur', 'furSolid', 'inkFur'];
    parts.tail = [];
    let joint = tailRoot;
    tailColors.forEach((color, i) => {
        const next = new THREE.Group();
        next.position.y = i === 0 ? 0 : 0.078;
        next.userData.curl = i === 0 ? 0 : 0.22;
        next.rotation.z = next.userData.curl;
        const radius = 0.066 - i * 0.0016;
        const segment = furredMesh(new THREE.CapsuleGeometry(radius, 0.05, 12, 24), { shells: high ? 4 : 2, length: 0.02, density: 360, vertexColors: false, color: color === 'inkFur' ? COLORS.ink : COLORS.fur });
        segment.position.set(0, 0.04, 0);
        next.add(segment);
        joint.add(next);
        parts.tail.push(next);
        joint = next;
    });

    // Arms: sculpted, pivoting at the shoulder, hanging down and slightly forward
    const armGeo = sculpt({ center: [0, -0.2, 0.02], size: 0.36, resolution: high ? 40 : 32, blobs: ARM_BLOBS, paint: paintArm() });
    parts.arms = {};
    for (const [key, side] of [['L', -1], ['R', 1]]) {
        const shoulder = new THREE.Group();
        shoulder.position.set(side * 0.36, 0.9, 0.1);
        shoulder.add(furredMesh(armGeo, { ...fur, length: 0.025, density: 340 }));
        body.add(shoulder);
        parts.arms[key] = shoulder;
    }

    // Pointing finger (grows out in the point pose)
    parts.finger = mesh(new THREE.CapsuleGeometry(0.034, 0.07, 6, 12), mat.furSolid, { pos: [0, -0.49, 0.04] });
    parts.finger.material = furMaterial({ vertexColors: false, color: COLORS.cream });
    parts.finger.scale.setScalar(0.001);
    parts.arms.R.add(parts.finger);

    // Clipboard in the left paw
    const clipboard = new THREE.Group();
    clipboard.position.set(-0.02, -0.42, 0.12);
    clipboard.rotation.set(0.2, 0.15, 0.3);
    clipboard.add(mesh(new RoundedBoxGeometry(0.3, 0.38, 0.024, 4, 0.018), mat.wood, { pos: [-0.11, 0, 0] }));
    clipboard.add(mesh(new THREE.BoxGeometry(0.24, 0.3, 0.005), mat.paper, { pos: [-0.11, -0.02, 0.0145] }));
    clipboard.add(mesh(new RoundedBoxGeometry(0.11, 0.05, 0.034, 3, 0.01), mat.metal, { pos: [-0.11, 0.18, 0.012] }));
    parts.ticks = [];
    [0.07, -0.01, -0.09].forEach((y) => {
        clipboard.add(mesh(new THREE.BoxGeometry(0.032, 0.032, 0.006), mat.line, { pos: [-0.19, y, 0.018] }));
        clipboard.add(mesh(new THREE.BoxGeometry(0.11, 0.011, 0.004), mat.line, { pos: [-0.08, y, 0.018] }));
        const tick = tube([[-0.205, y + 0.002, 0.026], [-0.192, y - 0.012, 0.026], [-0.168, y + 0.02, 0.026]], 0.0065, mat.tick, 16);
        tick.visible = false;
        clipboard.add(tick);
        parts.ticks.push(tick);
    });
    parts.arms.L.add(clipboard);

    // Head: one sculpt with cheeks, muzzle, brow ridge, ears and tuft; pivots at the neck
    const head = new THREE.Group();
    head.position.set(0, 1.04, 0.02);
    body.add(head);
    parts.head = head;
    const headGeo = sculpt({ center: [0, 0.5, 0.02], size: 0.8, resolution: high ? 72 : 52, blobs: HEAD_BLOBS, paint: paintHead(), scale: [1.04, 1, 0.95] });
    head.add(furredMesh(headGeo, { ...fur, length: 0.03, density: 320 }));

    // Where the sculpted surface is along a direction from the head centre, pushed out by `lift`
    const onFace = (dir, lift = 0) => surfacePoint(HEAD_BLOBS, HEAD_C, dir).addScaledVector(new THREE.Vector3(...dir).normalize(), lift);

    // Nose, with a little shine
    const noseDir = [0, -0.07, 1];
    const nosePos = onFace(noseDir, 0.012);
    const nose = mesh(SPHERE, mat.nose, { pos: nosePos.toArray(), scale: [0.08, 0.056, 0.05], rot: [0.25, 0, 0] });
    head.add(nose);

    // Mouth: a "w" smile with a philtrum, plus an open mouth (cavity, tongue, two teeth) for talking
    parts.smile = new THREE.Group();
    parts.smile.add(tube([[-0.13, -0.2, 0.5], [-0.065, -0.235, 0.5], [0, -0.2, 0.5], [0.065, -0.235, 0.5], [0.13, -0.2, 0.5]].map((d) => onFace(d, 0.006)), 0.011, mat.ink));
    parts.smile.add(tube([onFace([0, -0.11, 0.5], 0.006), onFace([0, -0.19, 0.5], 0.006)], 0.011, mat.ink, 8));
    head.add(parts.smile);
    parts.mouth = new THREE.Group();
    parts.mouth.position.copy(onFace([0, -0.27, 0.5], -0.012));
    parts.mouth.add(mesh(SPHERE, mat.mouth, { scale: [0.085, 0.075, 0.045] }));
    parts.mouth.add(mesh(SPHERE, mat.tongue, { pos: [0, -0.034, 0.016], scale: [0.052, 0.03, 0.032] }));
    for (const side of [-1, 1]) parts.mouth.add(mesh(new RoundedBoxGeometry(0.024, 0.03, 0.014, 2, 0.006), mat.tooth, { pos: [side * 0.035, 0.044, 0.028] }));
    parts.mouth.scale.y = 0.001;
    parts.mouth.visible = false;
    head.add(parts.mouth);

    // Whisker dots and whiskers
    for (const side of [-1, 1]) {
        for (const d of [[0.075, -0.17, 0.5], [0.118, -0.2, 0.5], [0.068, -0.215, 0.5]]) {
            head.add(mesh(SPHERE_LOW, mat.ink, { pos: onFace([side * d[0], d[1], d[2]], 0.004).toArray(), scale: 0.011 }));
        }
        [[-0.16, 0.0, -0.1], [-0.19, -0.06, -0.2], [-0.22, -0.13, -0.3]].forEach(([y0, y1, y2], i) => {
            const root = onFace([side * 0.22, y0, 0.46], 0.0);
            head.add(tube([root, [root.x + side * 0.16, 0.47 + y1 * 1.2, root.z - 0.03], [root.x + side * 0.32, 0.47 + y2 * 1.1, root.z - 0.1]], 0.0045, mat.whisker, 20));
        });
    }

    // Eyes: glossy eyeballs with an amber iris, a pupil that looks around, and real eyelids
    parts.eyes = [];
    parts.pupils = [];
    parts.lids = [];
    parts.happyEyes = [];
    for (const side of [-1, 1]) {
        const dir = [side * 0.19, 0.09, 0.42];
        const eye = new THREE.Group();
        eye.position.copy(onFace(dir, -0.065));
        eye.rotation.set(-0.06, side * 0.3, 0);
        eye.scale.setScalar(1.1);
        eye.add(mesh(SPHERE, mat.eyeWhite, { scale: [0.125, 0.145, 0.075] }));
        const pupil = new THREE.Group();
        pupil.position.z = 0.05;
        pupil.add(mesh(SPHERE, mat.iris, { pos: [0, 0, -0.004], scale: [0.088, 0.098, 0.03] }));
        pupil.add(mesh(SPHERE, mat.pupil, { scale: [0.072, 0.082, 0.034] }));
        pupil.add(mesh(SPHERE_LOW, mat.glint, { pos: [-0.028, 0.034, 0.03], scale: 0.022 }));
        pupil.add(mesh(SPHERE_LOW, mat.glint, { pos: [0.022, -0.03, 0.03], scale: 0.011 }));
        eye.add(pupil);

        // The lid is a fur shell in a space shaped like the eyeball (a little deeper, so it closes
        // over the pupil and glints), so it hugs the eye at every angle. A dark rim reads as lashes.
        const lidSpace = new THREE.Group();
        lidSpace.scale.set(0.125 * 1.07, 0.145 * 1.07, 0.075 * 1.5);
        const lid = new THREE.Group();
        lid.add(mesh(LID_CAP, mat.lid));
        lid.add(mesh(new THREE.TorusGeometry(1, 0.06, 8, 48), mat.ink, { rot: [Math.PI / 2, 0, 0] }));
        lid.rotation.x = LID_OPEN;
        lidSpace.add(lid);
        eye.add(lidSpace);

        head.add(eye);
        parts.eyes.push(eye);
        parts.pupils.push(pupil);
        parts.lids.push(lid);

        const arc = mesh(new THREE.TorusGeometry(0.07, 0.017, 10, 32, Math.PI), mat.ink, { pos: onFace(dir, 0.02).toArray(), rot: [-0.06, side * 0.3, 0] });
        arc.visible = false;
        head.add(arc);
        parts.happyEyes.push(arc);
    }

    // Brows, resting on the brow ridge
    parts.brows = new THREE.Group();
    for (const side of [-1, 1]) {
        parts.brows.add(tube([onFace([side * 0.1, 0.3, 0.42], 0.012), onFace([side * 0.19, 0.33, 0.4], 0.012), onFace([side * 0.28, 0.3, 0.36], 0.012)], 0.017, mat.ink, 20));
    }
    head.add(parts.brows);

    return parts;
}
