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
