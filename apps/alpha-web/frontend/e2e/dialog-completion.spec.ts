import { expect, test } from '@playwright/test'
import { acceptNextDialog, type AcceptedDialog } from './support/dialogCompletion'

test('dialog completion waits for the actual acceptance promise', async () => {
  let listener!: (dialog: AcceptedDialog) => void
  let accepted!: () => void
  const deferred = new Promise<void>(resolve => { accepted = resolve })
  const completion = acceptNextDialog({ once: (_event, callback) => { listener = callback } })
  let finished = false
  const observed = completion.then(() => { finished = true })
  listener({ accept: () => deferred })
  await Promise.resolve()
  expect(finished).toBe(false)
  accepted()
  await observed
  expect(finished).toBe(true)
})

test('dialog acceptance errors reach the caller unchanged', async () => {
  let listener!: (dialog: AcceptedDialog) => void
  const completion = acceptNextDialog({ once: (_event, callback) => { listener = callback } })
  const failure = new Error('acceptance failed')
  listener({ accept: () => Promise.reject(failure) })
  await expect(completion).rejects.toBe(failure)
})
