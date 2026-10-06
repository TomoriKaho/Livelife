import * as THREE from 'three';

// 模型上的笔触固定在局部坐标中；旋转、分层和相机移动不会重新随机上色。
export function pencilMaterial(options = {}) {
  const { scale = 1, ...properties } = options;
  const material = new THREE.MeshLambertMaterial(properties);
  if (!properties.vertexColors) material.color.lerp(new THREE.Color('#fff5db'), .04);
  material.userData.pencil = true;
  material.onBeforeCompile = shader => {
    shader.uniforms.pencilScale = { value: scale };
    shader.vertexShader = `varying vec3 pencilPoint; varying vec3 pencilNormal;\n${shader.vertexShader}`
      .replace('#include <begin_vertex>', '#include <begin_vertex>\npencilPoint = position; pencilNormal = normal;');
    shader.fragmentShader = `varying vec3 pencilPoint; varying vec3 pencilNormal; uniform float pencilScale;
      float pencilHash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
      float pencilNoise(vec2 p) {
        vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
        return mix(mix(pencilHash(i), pencilHash(i + vec2(1.0, 0.0)), f.x),
          mix(pencilHash(i + vec2(0.0, 1.0)), pencilHash(i + vec2(1.0, 1.0)), f.x), f.y);
      }
      ${shader.fragmentShader}`
      .replace('#include <color_fragment>', `#include <color_fragment>
        vec3 n = abs(normalize(pencilNormal));
        vec2 uv = n.y > max(n.x, n.z) ? pencilPoint.xz : (n.x > n.z ? pencilPoint.zy : pencilPoint.xy);
        uv *= pencilScale;
        // -30° 的宽笔触平涂，邻笔搭接产生深浅变化，轻微露纸也沿同一方向。
        float along = dot(uv, vec2(0.8660254, 0.5));
        float across = dot(uv, vec2(-0.5, 0.8660254));
        float broad = pencilNoise(vec2(along * 0.055, across * 0.6 + 0.12 * sin(along * 0.17))) * 2.0 - 1.0;
        float overlap = pencilNoise(vec2(along * 0.17 + 7.0, across * 1.1)) * 2.0 - 1.0;
        float soften = 1.0 - smoothstep(0.3, 1.8, fwidth(across));
        float tooth = sin(along * 23.0 + sin(across * 5.0)) * sin(across * 29.0);
        float grain = tooth * (1.0 - smoothstep(0.2, 1.2, max(fwidth(along * 23.0), fwidth(across * 29.0))));
        float gap = pow(max(0.0, sin(across * 2.7 + 0.08 * sin(along * 0.8))), 28.0)
          * smoothstep(0.42, 0.82, pencilNoise(vec2(along * 0.16, floor(across * 0.43)))) * soften;
        float paper = clamp(0.10 + (broad * 0.085 + overlap * 0.035) * soften + grain * 0.03 + gap * 0.32, 0.025, 0.46);
        diffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.96, 0.94, 0.86), paper);
      `)
      // 彩铅画保留色块本色，阴影只作为弱明暗层，避免亮黄被压成土黄。
      .replace('#include <opaque_fragment>', 'outgoingLight = mix(diffuseColor.rgb, outgoingLight, 0.45);\n#include <opaque_fragment>');
  };
  material.customProgramCacheKey = () => 'yanyuan-colored-pencil-v1';
  return material;
}

export function pencilEdge(mesh, { opacity = .52, threshold = 35 } = {}) {
  const source = new THREE.EdgesGeometry(mesh.geometry, threshold), p = source.attributes.position, vertices = [];
  const a = new THREE.Vector3(), b = new THREE.Vector3(), direction = new THREE.Vector3(), side = new THREE.Vector3();
  for (let i = 0; i < p.count; i += 2) {
    a.fromBufferAttribute(p, i); b.fromBufferAttribute(p, i + 1);
    const length = a.distanceTo(b), count = Math.max(1, Math.ceil(length / 2.5));
    direction.subVectors(b, a).normalize(); side.set(-direction.z, .25, direction.x).normalize();
    const point = t => a.clone().lerp(b, t).addScaledVector(side,
      Math.sin(t * Math.PI) * Math.sin(t * length * .7 + a.x * .13 + a.z * .11) * .045);
    for (let j = 0; j < count; j++) vertices.push(...point(j / count).toArray(), ...point((j + 1) / count).toArray());
  }
  source.dispose();
  const geometry = new THREE.BufferGeometry(); geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
  const line = new THREE.LineSegments(geometry, new THREE.LineBasicMaterial({ color: '#383d39', transparent: true, opacity, depthWrite: false }));
  line.userData.pencilEdge = true; mesh.add(line); return line;
}
