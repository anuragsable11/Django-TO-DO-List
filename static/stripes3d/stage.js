/* Renderer, camera, lights and floor for Stripes. createStage() throws if WebGL is unavailable. */
import * as THREE from 'three';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const FRAME_HEIGHT = 3.3;   // world units visible top to bottom: the tiger plus room to jump
const FRAME_WIDTH = 2.7;    // never show less than this side to side (raised arms need it)
const LOOK_AT_Y = 1.3;

export function createStage(canvas) {
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'high-performance' });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, window.innerWidth < 640 ? 1.5 : 2));
    renderer.toneMapping = THREE.NeutralToneMapping;
    renderer.toneMappingExposure = 1.05;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    const scene = new THREE.Scene();
    const pmrem = new THREE.PMREMGenerator(renderer);
    scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    scene.environmentIntensity = 0.55;
    pmrem.dispose();

    const camera = new THREE.PerspectiveCamera(24, 1, 0.1, 50);

    scene.add(new THREE.HemisphereLight('#fff6ea', '#3b2a22', 0.85));
    // key light from the upper right gives the shape; it casts no shadow, so nothing streaks sideways
    const key = new THREE.DirectionalLight('#fff1df', 2.2);
    key.position.set(2.6, 4.2, 3.6);
    scene.add(key);
    // a soft light from almost straight above casts the shadows: under the head, the arms, and the feet
    const top = new THREE.DirectionalLight('#fff4e6', 0.9);
    top.position.set(0.5, 6, 1.6);
    top.castShadow = true;
    top.shadow.mapSize.set(1024, 1024);
    top.shadow.camera.left = -1.3;
    top.shadow.camera.right = 1.3;
    top.shadow.camera.top = 1.5;
    top.shadow.camera.bottom = -1.5;
    top.shadow.camera.near = 2;
    top.shadow.camera.far = 10;
    top.shadow.bias = -0.0004;
    top.shadow.normalBias = 0.02;
    scene.add(top);
    // warm rim lights from behind lift the silhouette off the dark stage
    const rimLeft = new THREE.DirectionalLight('#ff8a3d', 3.2);
    rimLeft.position.set(-2.4, 2.6, -3.2);
    scene.add(rimLeft);
    const rimRight = new THREE.DirectionalLight('#ffb27a', 1.8);
    rimRight.position.set(2.6, 2.2, -3);
    scene.add(rimRight);

    // Floor: a real cast shadow plus a soft contact shadow that shrinks when the tiger jumps.
    // The floor is a small disc so the shadow stays on the stage and never reaches the page around it.
    const floor = new THREE.Mesh(new THREE.CircleGeometry(1.2, 48), new THREE.ShadowMaterial({ opacity: 0.26 }));
    floor.rotation.x = -Math.PI / 2;
    floor.receiveShadow = true;
    scene.add(floor);
    const contact = new THREE.Mesh(new THREE.PlaneGeometry(1.5, 1.1), new THREE.MeshBasicMaterial({ transparent: true, depthWrite: false, opacity: 0 }));
    contact.rotation.x = -Math.PI / 2;
    contact.position.y = 0.002;
    scene.add(contact);

    // Frame the character for whatever shape the canvas has: pull back on narrow canvases
    function frame(width, height) {
        const aspect = width / height;
        const halfFov = THREE.MathUtils.degToRad(camera.fov / 2);
        let distance = (FRAME_HEIGHT / 2) / Math.tan(halfFov);
        const visibleWidth = FRAME_HEIGHT * aspect;
        if (visibleWidth < FRAME_WIDTH) distance *= FRAME_WIDTH / visibleWidth;
        camera.aspect = aspect;
        camera.position.set(0, LOOK_AT_Y + 0.45, distance);
        camera.lookAt(0, LOOK_AT_Y, 0);
        camera.updateProjectionMatrix();
    }

    function resize() {
        const width = canvas.clientWidth;
        const height = canvas.clientHeight;
        if (!width || !height) return false;
        renderer.setSize(width, height, false);
        frame(width, height);
        return true;
    }

    return {
        renderer,
        scene,
        camera,
        resize,
        render() {
            renderer.render(scene, camera);
        },
        setContactTexture(texture) {
            contact.material.map = texture;
            contact.material.needsUpdate = true;
        },
        // contact shadow follows the jump: smaller and fainter the higher the tiger is
        setContact(lift, visible) {
            const shrink = 1 - Math.min(lift, 1.4) * 0.35;
            contact.scale.set(shrink, shrink, 1);
            contact.material.opacity = visible ? Math.max(shrink, 0.25) : 0;
        },
        dispose() {
            renderer.dispose();
        },
    };
}
