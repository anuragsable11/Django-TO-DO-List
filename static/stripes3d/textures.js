/* Colours and the one painted texture Stripes still needs (the fur itself is painted per vertex). */
import * as THREE from 'three';

export const COLORS = {
    fur: '#ff8422',
    furSheen: '#ffd2a0',
    cream: '#fff3dc',
    ink: '#23252c',
    whisker: '#33343a',
    pink: '#ff7aa2',
    earInner: '#ffb9cc',
    blush: '#ff6f8f',
    cape: '#b4350f',
    capeSheen: '#ff9a6a',
    badge: '#15130f',
    gold: '#d9a54c',
    wood: '#b5793d',
    paper: '#fffaf0',
    line: '#c9c1b4',
    tick: '#e8590c',
    mouth: '#6b1121',
    tongue: '#ff6f91',
};

export function makeTextures(renderer) {
    // soft contact shadow under the feet
    const canvas = document.createElement('canvas');
    canvas.width = 256;
    canvas.height = 256;
    const g = canvas.getContext('2d');
    const gradient = g.createRadialGradient(128, 128, 0, 128, 128, 128);
    gradient.addColorStop(0, 'rgba(0, 0, 0, 0.55)');
    gradient.addColorStop(0.55, 'rgba(0, 0, 0, 0.22)');
    gradient.addColorStop(1, 'rgba(0, 0, 0, 0)');
    g.fillStyle = gradient;
    g.fillRect(0, 0, 256, 256);
    const contact = new THREE.CanvasTexture(canvas);
    contact.colorSpace = THREE.SRGBColorSpace;
    contact.anisotropy = renderer.capabilities.getMaxAnisotropy();
    return { contact };
}
