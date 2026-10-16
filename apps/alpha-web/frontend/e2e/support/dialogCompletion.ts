export interface AcceptedDialog { accept(): Promise<void> }
export interface DialogSource {
  once(event: 'dialog', listener: (dialog: AcceptedDialog) => void): unknown
}

export function acceptNextDialog(page: DialogSource): Promise<void> {
  return new Promise((resolve, reject) => {
    page.once('dialog', dialog => {
      void Promise.resolve().then(() => dialog.accept()).then(resolve, reject)
    })
  })
}
