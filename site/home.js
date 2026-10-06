// Home page: a short typed example in the terminal (static text when the visitor prefers less motion).
document.addEventListener("DOMContentLoaded", function () {
  "use strict";
  var demo = document.getElementById("demo");
  if (!demo) return;
  var lines = [
    ["rm notes.txt", "<span class='d'>1 item moved to the trash. undo brings it back.</span>"],
    ["undo", "Restored ~/notes.txt"],
    ["ping example.com", "<span class='d'>4 sent, 4 answered, 0% lost</span>"],
    ["pkg install chess", "Installed Chess <span class='d'>(it may use: your files)</span>"]
  ];
  var prompt = "<span class='p'>you@pyOS</span>:<span class='c'>~</span>$ ";
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
    demo.innerHTML = lines.map(function (l) { return prompt + l[0] + "\n" + l[1]; }).join("\n") + "\n" + prompt + "<span class='caret'></span>";
    return;
  }
  var li = 0, ci = 0, shown = "";
  (function tick() {
    if (li >= lines.length) { setTimeout(function () { li = 0; ci = 0; shown = ""; tick(); }, 5000); return; }
    var cmd = lines[li][0];
    if (ci <= cmd.length) {
      demo.innerHTML = shown + prompt + cmd.slice(0, ci) + "<span class='caret'></span>";
      ci++; setTimeout(tick, 40 + Math.random() * 40);
    } else {
      shown += prompt + cmd + "\n" + lines[li][1] + "\n";
      demo.innerHTML = shown + prompt + "<span class='caret'></span>";
      li++; ci = 0; setTimeout(tick, 900);
    }
  })();
});
