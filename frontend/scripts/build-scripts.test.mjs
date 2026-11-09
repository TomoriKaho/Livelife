import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const { scripts } = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8'));

for (const [name, vite] of [
  ['build', 'vite build'],
  ['build:preview', 'vite build --mode preview'],
  ['build:production', 'vite build --mode production'],
]) {
  test(`${name} forwards npm arguments to Vite and retains output checks`, () => {
    // npm appends -- arguments to the main script, not its post lifecycle hook.
    const commands = scripts[name].split('&&').map(command => command.trim());
    assert.equal(commands[0], 'vue-tsc -b');
    assert.equal(commands.at(-1), vite);
    assert.ok(scripts[`post${name}`].includes('node scripts/check-sketch-build.mjs'));
    if (name === 'build:production') {
      assert.ok(scripts[`post${name}`].includes('node scripts/check-internal-tools-build.mjs false'));
    }
  });
}
