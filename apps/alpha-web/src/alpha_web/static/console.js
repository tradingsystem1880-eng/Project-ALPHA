// Stream a launched run into a <pre> via native EventSource (no framework, no build step).
// attachRunner wires a form: POST the args, then tail /jobs/<id>/stream until the terminal event.
function attachRunner(formId, preId, endpoint) {
  var form = document.getElementById(formId);
  var pre = document.getElementById(preId);
  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    pre.textContent = "";
    pre.classList.remove("console-error");
    var link = pre.nextElementSibling;
    if (link && link.classList.contains("console-done")) link.remove();
    fetch(endpoint, { method: "POST", body: new URLSearchParams(new FormData(form)) })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        var es = new EventSource("/jobs/" + j.job_id + "/stream");
        es.addEventListener("line", function (e) {
          pre.textContent += e.data + "\n";
          pre.scrollTop = pre.scrollHeight;
        });
        es.addEventListener("done", function (e) {
          es.close();
          if (e.data) {
            var a = document.createElement("a");
            a.href = "/runs/" + e.data;
            a.textContent = "→ open run " + e.data;
            a.className = "console-done";
            a.style.display = "block";
            pre.after(a);
          } else {
            pre.textContent += "\n✓ done";
          }
        });
        es.addEventListener("failed", function (e) {
          es.close();
          pre.textContent += "\n✗ " + (e.data || "failed");
          pre.classList.add("console-error");
        });
        es.onerror = function () { es.close(); };
      });
  });
}
