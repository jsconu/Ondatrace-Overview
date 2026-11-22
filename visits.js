// Visit counts for ondatrace.com, without cookies or local storage.
// Sends the page path, the site that sent the visitor (the app keeps only its name) and any utm_ tags
// to app.ondatrace.com, which turns them into anonymous daily counts. See /privacy/.
// Also passes utm_ tags from this page on to the signup links, so the app can tell which campaign led to a signup.
(function () {
  var params = new URLSearchParams(location.search);
  var utm = {};
  ["utm_source", "utm_medium", "utm_campaign"].forEach(function (key) {
    var value = params.get(key);
    if (value) utm[key] = value.slice(0, 100);
  });

  var body = JSON.stringify({
    p: location.pathname,
    r: document.referrer || null,
    us: utm.utm_source || null,
    um: utm.utm_medium || null,
    uc: utm.utm_campaign || null
  });
  var url = "https://app.ondatrace.com/site-visit";
  try {
    if (navigator.sendBeacon) {
      navigator.sendBeacon(url, new Blob([body], { type: "text/plain" }));
    } else {
      fetch(url, { method: "POST", body: body, mode: "no-cors", keepalive: true });
    }
  } catch (e) { /* counting must never break the page */ }

  if (Object.keys(utm).length) {
    document.querySelectorAll('a[href^="https://app.ondatrace.com/signup"], a[href="try/"]').forEach(function (link) {
      var target = new URL(link.href);
      Object.keys(utm).forEach(function (key) { target.searchParams.set(key, utm[key]); });
      link.href = target.toString();
    });
  }
})();
