(function () {
  "use strict";

  var box = document.getElementById("f-body");
  var out = document.getElementById("preview-box");
  var state = document.getElementById("preview-state");
  if (!box || !out) return;

  function cookie(name) {
    var m = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
    return m ? decodeURIComponent(m[1]) : null;
  }

  var timer = null;
  var pending = false;

  function render() {
    var fd = new FormData();
    fd.append("body", box.value);
    fd.append("csrf_token", cookie("csrf_token") || "");
    if (state) state.textContent = "…";
    fetch("/items/preview", { method: "POST", body: fd })
      .then(function (r) {
        if (!r.ok) throw new Error(r.status);
        return r.text();
      })
      .then(function (html) {
        out.innerHTML = html;
        if (state) state.textContent = "✓";
      })
      .catch(function () {
        if (state) state.textContent = "önizleme hatası";
      });
  }

  box.addEventListener("input", function () {
    if (pending) return;
    pending = true;
    clearTimeout(timer);
    timer = setTimeout(function () {
      pending = false;
      render();
    }, 400);
  });

  if (box.value.trim()) render();
})();
