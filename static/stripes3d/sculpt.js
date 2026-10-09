/* Sculpting: smooth organic surfaces from blended blobs (metaballs polygonised with marching cubes),
   plus painters that colour the surface per vertex, so markings follow the shape with no seams. */
import * as THREE from 'three';
import { MarchingCubes } from 'three/addons/objects/MarchingCubes.js';

const ISO = 12;          // field level the surface sits on
const DEFAULT_BLEND = 6; // a blob's influence reaches sqrt((blend + ISO) / blend) times its radius

/* A blob of radius r contributes (blend + ISO) * r² / d² - blend at distance d (only while positive),
   so a lone blob's surface sits exactly at r. Overlapping blobs push the surface outward. */
export function fieldAt(blobs, x, y, z) {
    let sum = 0;
    for (const b of blobs) {
        const blend = b.blend || DEFAULT_BLEND;
        const dx = x - b.p[0];
        const dy = y - b.p[1];
        const dz = z - b.p[2];
        const v = (blend + ISO) * b.r * b.r / (1e-6 + dx * dx + dy * dy + dz * dz) - blend;
        if (v > 0) sum += b.carve ? -v : v;
    }
    return sum;
}

// Walk out from `origin` along `dir` until the surface is crossed; returns that surface point.
export function surfacePoint(blobs, origin, dir, maxDist = 2) {
    const d = new THREE.Vector3(...dir).normalize();
    const o = new THREE.Vector3(...origin);
    let inside = 0;
    let t = 0;
    const step = 0.01;
    while (t < maxDist) {
        const p = o.clone().addScaledVector(d, t);
        if (fieldAt(blobs, p.x, p.y, p.z) < ISO) break;
        inside = t;
        t += step;
    }
    // refine between the last inside point and the first outside one
    let lo = inside;
    let hi = Math.min(t, maxDist);
    for (let i = 0; i < 12; i++) {
        const mid = (lo + hi) / 2;
        const p = o.clone().addScaledVector(d, mid);
        if (fieldAt(blobs, p.x, p.y, p.z) >= ISO) lo = mid; else hi = mid;
    }
    return o.addScaledVector(d, (lo + hi) / 2);
}

/**
 * sculpt({ center, size, resolution, blobs, paint, scale, smoothing })
 *   center, size   the cube of space to sculpt in: center ± size on each axis
 *   blobs          [{ p: [x, y, z], r, blend?, carve? }]  bigger blend = crisper joins; carve subtracts
 *   paint(p, n)    returns [r, g, b] for a surface point (optional)
 *   scale          [x, y, z] applied around `center` after sculpting (optional)
 *   smoothing      passes of shrink-free (Taubin) smoothing to take the grid wobble out (default 2)
 * Returns an indexed BufferGeometry in the blobs' coordinate space. Normals come from the field
 * gradient, so they are smooth everywhere, independent of the triangles.
 */
export function sculpt({ center, size, resolution, blobs, paint, scale, smoothing = 2, maxTriangles = 160000 }) {
    const mc = new MarchingCubes(resolution, new THREE.MeshBasicMaterial(), false, false, maxTriangles);
    mc.isolation = ISO;
    mc.reset();
    for (const blob of blobs) {
        const blend = blob.blend || DEFAULT_BLEND;
        const fieldRadius = blob.r / (2 * size);                    // the field spans 0..1 across the cube
        const strength = (blend + ISO) * fieldRadius * fieldRadius;  // strength / r² - blend = ISO at the surface
        mc.addBall(
            (blob.p[0] - center[0]) / (2 * size) + 0.5,
            (blob.p[1] - center[1]) / (2 * size) + 0.5,
            (blob.p[2] - center[2]) / (2 * size) + 0.5,
            blob.carve ? -strength : strength,
            blend,
        );
    }
    mc.update();

    const count = mc.count;
    const sx = scale ? scale[0] : 1;
    const sy = scale ? scale[1] : 1;
    const sz = scale ? scale[2] : 1;
    const src = mc.geometry.getAttribute('position').array;
    const srcNormal = mc.geometry.getAttribute('normal').array;

    // Index the triangle soup: shared corners become one vertex, keeping the field-gradient normal
    const lookup = new Map();
    const index = new Uint32Array(count);
    const pos = [];
    const nor = [];
    for (let i = 0; i < count; i++) {
        const x = src[i * 3];
        const y = src[i * 3 + 1];
        const z = src[i * 3 + 2];
        const key = ((x * 2048) | 0) + ',' + ((y * 2048) | 0) + ',' + ((z * 2048) | 0);
        let v = lookup.get(key);
        if (v === undefined) {
            v = pos.length / 3;
            lookup.set(key, v);
            pos.push(center[0] + x * size * sx, center[1] + y * size * sy, center[2] + z * size * sz);
            // normals of a non-uniformly scaled surface scale by the inverse
            nor.push(srcNormal[i * 3] / sx, srcNormal[i * 3 + 1] / sy, srcNormal[i * 3 + 2] / sz);
        }
        index[i] = v;
    }
    mc.geometry.dispose();

    const position = new Float32Array(pos);
    const normal = new Float32Array(nor);
    for (let i = 0; i < normal.length; i += 3) {
        const l = Math.hypot(normal[i], normal[i + 1], normal[i + 2]) || 1;
        normal[i] /= l;
        normal[i + 1] /= l;
        normal[i + 2] /= l;
    }
    if (smoothing > 0) taubin(position, index, smoothing);

    const geometry = new THREE.BufferGeometry();
    geometry.setIndex(new THREE.BufferAttribute(index, 1));
    geometry.setAttribute('position', new THREE.BufferAttribute(position, 3));
    geometry.setAttribute('normal', new THREE.BufferAttribute(normal, 3));

    if (paint) {
        const pos = geometry.getAttribute('position');
        const nor = geometry.getAttribute('normal');
        const color = new Float32Array(pos.count * 3);
        const p = new THREE.Vector3();
        const n = new THREE.Vector3();
        for (let i = 0; i < pos.count; i++) {
            p.fromBufferAttribute(pos, i);
            n.fromBufferAttribute(nor, i);
            const c = paint(p, n);
            color[i * 3] = c[0];
            color[i * 3 + 1] = c[1];
            color[i * 3 + 2] = c[2];
        }
        geometry.setAttribute('color', new THREE.BufferAttribute(color, 3));
    }
    return geometry;
}

// Taubin smoothing: a shrinking pass followed by a slightly larger inflating one, so the surface
// loses its grid wobble without losing volume.
function taubin(position, index, passes) {
    const n = position.length / 3;
    const neighbours = Array.from({ length: n }, () => new Set());
    for (let i = 0; i < index.length; i += 3) {
        const a = index[i];
        const b = index[i + 1];
        const c = index[i + 2];
        neighbours[a].add(b).add(c);
        neighbours[b].add(a).add(c);
        neighbours[c].add(a).add(b);
    }
    const next = new Float32Array(position.length);
    const step = (lambda) => {
        for (let v = 0; v < n; v++) {
            let x = 0;
            let y = 0;
            let z = 0;
            for (const u of neighbours[v]) {
                x += position[u * 3];
                y += position[u * 3 + 1];
                z += position[u * 3 + 2];
            }
            const k = neighbours[v].size || 1;
            next[v * 3] = position[v * 3] + lambda * (x / k - position[v * 3]);
            next[v * 3 + 1] = position[v * 3 + 1] + lambda * (y / k - position[v * 3 + 1]);
            next[v * 3 + 2] = position[v * 3 + 2] + lambda * (z / k - position[v * 3 + 2]);
        }
        position.set(next);
    };
    for (let i = 0; i < passes; i++) {
        step(0.5);
        step(-0.53);
    }
}

/* ---------- Painting helpers (coverages are 0..1) ---------- */

export function smoothstep(e0, e1, x) {
    const t = Math.min(Math.max((x - e0) / (e1 - e0), 0), 1);
    return t * t * (3 - 2 * t);
}

export function rgb(hex) {
    const c = new THREE.Color(hex);
    return [c.r, c.g, c.b];
}

export function mix(a, b, t) {
    return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
}

// Soft blob mask around a point: 1 inside `inner`, fading to 0 at `outer`
export function blobMask(p, cx, cy, cz, inner, outer) {
    return smoothstep(outer, inner, Math.hypot(p.x - cx, p.y - cy, p.z - cz));
}

/**
 * Strokes painted onto the surface. A stroke is a polyline whose width tapers from w[0] to w[1],
 * with a soft edge. Distances are measured in a "painting space" given by `project(p)`, which maps
 * a 3D point to the space the stroke points are compared in (a direction from the head's centre,
 * or (angle × radius, height) around the body), so strokes wrap around the sculpt.
 */
export function strokePainter(project, strokes, soft = 0.02) {
    const prepared = strokes.map((s) => ({
        pts: s.pts.map((pt) => project(new THREE.Vector3(...pt))),
        w0: s.w[0],
        w1: s.w[1] === undefined ? s.w[0] : s.w[1],
        soft: s.soft === undefined ? soft : s.soft,
    }));
    const a = new THREE.Vector3();
    const b = new THREE.Vector3();
    return (p) => {
        const q = project(p);
        let coverage = 0;
        for (const s of prepared) {
            const last = s.pts.length - 1;
            for (let i = 0; i < last; i++) {
                a.copy(s.pts[i]);
                b.copy(s.pts[i + 1]).sub(a);
                const len2 = b.lengthSq() || 1e-9;
                let t = (q.x - a.x) * b.x + (q.y - a.y) * b.y + (q.z - a.z) * b.z;
                t = Math.min(Math.max(t / len2, 0), 1);
                const dist = Math.hypot(q.x - (a.x + b.x * t), q.y - (a.y + b.y * t), q.z - (a.z + b.z * t));
                const along = (i + t) / last;
                const w = s.w0 + (s.w1 - s.w0) * along;
                coverage = Math.max(coverage, smoothstep(w + s.soft, w - s.soft * 0.3, dist));
            }
        }
        return coverage;
    };
}

// Painting spaces
export const projections = {
    // unit direction from a centre; stroke points are anything along the wanted direction
    radial: (cx, cy, cz) => (p) => new THREE.Vector3(p.x - cx, p.y - cy, p.z - cz).normalize(),
    // around a vertical axis: x = angle (0 at the front, ± toward the back) × radius, y = height
    cylinder: (cx, cz, radius) => (p) => new THREE.Vector3(Math.atan2(p.x - cx, p.z - cz) * radius, p.y, 0),
    // plain 3D distance, widths in world units
    world: () => (p) => p.clone(),
};
