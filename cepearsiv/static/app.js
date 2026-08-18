(function () {
  "use strict";

  function cookie(name) {
    var m = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
    return m ? decodeURIComponent(m[1]) : null;
  }

  var themes = ["auto", "light", "dark"];
  function nextTheme(current) {
    return themes[(themes.indexOf(current) + 1) % themes.length] || "auto";
  }

  var toggle = document.getElementById("theme-toggle");
  if (toggle) {
    toggle.addEventListener("click", function () {
      var current = document.documentElement.dataset.theme || "auto";
      var next = nextTheme(current);
      var csrf = cookie("csrf_token");
      var fd = new FormData();
      fd.append("theme", next);
      fd.append("csrf_token", csrf || "");
      fetch("/settings/theme", { method: "POST", body: fd })
        .then(function () {
          document.documentElement.dataset.theme = next;
        })
        .catch(function () {});
    });
  }

  function liveTheme() {
    var theme = document.documentElement.dataset.theme;
    if (theme !== "auto") return;
    var dark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", dark ? "#161A1E" : "#F6F1E7");
  }
  liveTheme();
  if (window.matchMedia) {
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", liveTheme);
  }

  document.addEventListener("keydown", function (e) {
    var tag = (e.target && e.target.tagName) || "";
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || e.metaKey || e.ctrlKey || e.altKey) {
      return;
    }
    if (e.key === "/") {
      var search = document.getElementById("topsearch");
      if (search) {
        e.preventDefault();
        search.focus();
        search.select();
      }
    } else if (e.key === "n" || e.key === "N") {
      e.preventDefault();
      window.location.href = "/items/new";
    } else if (e.key === "j" || e.key === "J") {
      var links = Array.prototype.slice.call(document.querySelectorAll("#card-grid a.card-link"));
      var idx = links.indexOf(document.activeElement);
      var next = links[(idx + 1) % links.length];
      if (next) next.focus();
    } else if (e.key === "k" || e.key === "K") {
      var klinks = Array.prototype.slice.call(document.querySelectorAll("#card-grid a.card-link"));
      var kidx = klinks.indexOf(document.activeElement);
      var knext = klinks[(kidx - 1 + klinks.length) % klinks.length];
      if (knext) knext.focus();
    }
  });

  document.addEventListener("click", function (e) {
    var el = e.target.closest ? e.target.closest("[data-copy]") : null;
    if (!el) return;
    var text = el.getAttribute("data-copy") || el.textContent.trim();
    function done() {
      var original = el.textContent;
      el.textContent = "Kopyalandı ✓";
      setTimeout(function () { el.textContent = original; }, 1600);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done).catch(function () {});
    } else {
      var ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand("copy"); } catch (e2) {}
      document.body.removeChild(ta);
      done();
    }
  });

  window.showToast = function (message, kind) {
    var wrap = document.getElementById("toast-wrap");
    if (!wrap) return;
    var t = document.createElement("div");
    t.className = "toast" + (kind === "ok" || kind === "err" ? " " + kind : "");
    t.textContent = message;
    wrap.appendChild(t);
    setTimeout(function () {
      t.style.opacity = "0";
      t.style.transition = "opacity .3s ease";
      setTimeout(function () { if (t.parentNode) t.parentNode.removeChild(t); }, 320);
    }, 3200);
  };

  if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost" || location.hostname === "127.0.0.1")) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("/static/sw.js").catch(function () {});
    });
  }
})();
