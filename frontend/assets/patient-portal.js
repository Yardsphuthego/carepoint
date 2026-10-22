// Accept workspace navigation only from the currently open patient form.
if (!window.carepointWorkspaceListener) {
  window.carepointWorkspaceListener = true;
  window.addEventListener('message', (event) => {
    const frame = document.querySelector('.account-modal-frame');
    if (!frame || event.source !== frame.contentWindow) return;
    const origin = new URL(frame.src).origin;
    if (event.origin !== origin || event.data?.type !== 'carepoint:workspace') return;
    if (!['/appointments/', '/admin/', '/clinician/appointments/'].includes(event.data.path)) return;
    window.location.assign(new URL(event.data.path, origin).href);
  });
}
