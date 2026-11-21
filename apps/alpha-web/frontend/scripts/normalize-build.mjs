import { execFileSync } from 'node:child_process'
import { readdir, readFile, writeFile } from 'node:fs/promises'

const buildDirectory = new URL('../../src/alpha_web/static/app/', import.meta.url)
const textAssetPattern = /\.(?:css|html|js)$/

async function normalizeDirectory(directory) {
  const entries = await readdir(directory, { withFileTypes: true })
  for (const entry of entries) {
    const path = new URL(entry.name, directory)
    if (entry.isDirectory()) {
      await normalizeDirectory(new URL(`${entry.name}/`, directory))
      continue
    }
    if (!textAssetPattern.test(entry.name)) continue

    const source = await readFile(path, 'utf8')
    const normalized = source.replace(/[ \t]+$/gm, '')
    if (normalized !== source) await writeFile(path, normalized, 'utf8')
  }
}

await normalizeDirectory(buildDirectory)

// Staleness signal: the commit and time this bundle was built. The backend returns it on /healthz
// next to the commit of the running code, and the status bar warns when they differ.
function currentCommit() {
  try {
    return execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim()
  } catch {
    return 'unknown'
  }
}

const buildInfo = { commit: currentCommit(), built_at: new Date().toISOString() }
await writeFile(new URL('build-info.json', buildDirectory), `${JSON.stringify(buildInfo)}\n`, 'utf8')
