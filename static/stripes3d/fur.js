/* Fur: a physically based material with hair grain, plus "shell" fur - the surface drawn again in
   layers pushed out along the normals. Each layer keeps the hairs tall enough to reach it, thinning
   toward their tips, so the silhouette goes soft and fuzzy. Hairs are seeded from the un-extruded
   position, so every layer of a hair lines up. Roots are shaded darker, and the fur droops a little. */
import * as THREE from 'three';

const GLSL = {
    common: /* glsl */`
        varying vec3 vFurBase;
        uniform float uShell;
        uniform float uFurLength;
        uniform float uDensity;
        float furHash(vec3 c) { return fract(sin(dot(c, vec3(127.1, 311.7, 74.7))) * 43758.5453); }
    `,
    vertex: /* glsl */`
        vFurBase = (modelMatrix * vec4(position, 1.0)).xyz;
        #ifdef FUR_SHELL
            vec3 droop = transpose(mat3(modelMatrix)) * vec3(0.0, -1.0, 0.0);
            transformed += (objectNormal + droop * 0.5 * uShell) * uFurLength * uShell;
        #endif
    `,
    clip: /* glsl */`
        float furCoverage = 1.0;
        #ifdef FUR_SHELL
        {
            vec3 q = vFurBase * uDensity;
            vec3 cell = floor(q);
            float hair = 0.45 + 0.55 * furHash(cell);           // how tall this hair is (0..1 of fur length)
            float t = uShell / hair;                             // how far up the hair this shell cuts it
            vec3 f = abs(fract(q + vec3(furHash(cell + 7.0), furHash(cell + 3.0), 0.0) * 0.3) - 0.5);
            float rad = max(max(f.x, f.y), f.z);                 // distance to the hair's centre, as a cube
            float edge = 0.58 * (1.0 - 0.55 * t);                // solid at the root, thinning toward the tip
            furCoverage = (t > 1.0) ? 0.0 : clamp((edge - rad) / 0.1, 0.0, 1.0);
            // fuzz reads at the silhouette; face-on it only adds noise, so fade it there
            float facing = abs(dot(normalize(vNormal), normalize(vViewPosition)));
            furCoverage *= 1.0 - 0.85 * smoothstep(0.3, 0.9, facing);
            if (furCoverage <= 0.003) discard;
        }
        #endif
    `,
    color: /* glsl */`
        float grain = furHash(floor(vFurBase * 1400.0)) * 0.6 + furHash(floor(vFurBase * 420.0)) * 0.4;
        diffuseColor.rgb *= 0.95 + 0.1 * grain;
        diffuseColor.rgb *= mix(0.9, 1.02, uShell);
    `,
    alpha: /* glsl */`
        #ifdef FUR_SHELL
            gl_FragColor.a = furCoverage;
        #endif
    `,
};

/**
 * furMaterial({ shell, shells, length, density, color, vertexColors, sheenColor, roughness })
 * shell = 0 is the solid base surface; 1..shells are the fuzz layers.
 */
export function furMaterial({ shell = 0, shells = 1, length = 0.03, density = 300, color = 0xffffff, vertexColors = true, sheenColor = '#ffdcb4', roughness = 0.8 } = {}) {
    // The base surface gets the full velvet sheen; the fuzz layers use a lighter material, since
    // they are drawn many times over and mostly show at the silhouette.
    const material = shell > 0
        ? new THREE.MeshStandardMaterial({ color, vertexColors, roughness: 0.9, alphaToCoverage: true })
        : new THREE.MeshPhysicalMaterial({ color, vertexColors, roughness, sheen: 1, sheenRoughness: 0.45, sheenColor });
    const uniforms = {
        uShell: { value: shell / shells },
        uFurLength: { value: length },
        uDensity: { value: density },
    };
    material.onBeforeCompile = (shader) => {
        Object.assign(shader.uniforms, uniforms);
        if (shell > 0) shader.defines = Object.assign(shader.defines || {}, { FUR_SHELL: 1 });
        shader.vertexShader = shader.vertexShader
            .replace('#include <common>', '#include <common>\n' + GLSL.common)
            .replace('#include <begin_vertex>', '#include <begin_vertex>\n' + GLSL.vertex);
        shader.fragmentShader = shader.fragmentShader
            .replace('#include <common>', '#include <common>\n' + GLSL.common)
            .replace('#include <clipping_planes_fragment>', '#include <clipping_planes_fragment>\n' + GLSL.clip)
            .replace('#include <color_fragment>', '#include <color_fragment>\n' + GLSL.color)
            .replace('#include <dithering_fragment>', '#include <dithering_fragment>\n' + GLSL.alpha);
    };
    material.customProgramCacheKey = () => 'stripes-fur-' + (shell > 0 ? 'shell' : 'base') + (vertexColors ? '-vc' : '');
    return material;
}

/**
 * Furred mesh: a Group holding the solid base mesh (casts shadows) and its fuzz shells (don't).
 * `group.base` is the solid mesh.
 */
export function furredMesh(geometry, { shells = 14, length = 0.03, density = 300, vertexColors = true, color = 0xffffff } = {}) {
    const group = new THREE.Group();
    const base = new THREE.Mesh(geometry, furMaterial({ shell: 0, shells, length, density, vertexColors, color }));
    base.castShadow = true;
    base.receiveShadow = true;
    group.add(base);
    group.base = base;
    for (let i = 1; i <= shells; i++) {
        const shell = new THREE.Mesh(geometry, furMaterial({ shell: i, shells, length, density, vertexColors, color }));
        shell.receiveShadow = true;
        shell.renderOrder = i;
        shell.userData.furShell = { index: i, total: shells }; // lets the renderer thin the fur on slow devices
        group.add(shell);
    }
    return group;
}
