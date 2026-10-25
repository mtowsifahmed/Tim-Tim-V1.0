/* Small additions loaded after the main app: speak important messages out loud with the computer's own voice
   (free, local, no quota), so limit/offline notices are heard as well as read. */
(function () {
  const TT = window.TT; if (!TT) return;
  let last = '';
  TT.speakLocal = text => {
    try {
      if (!window.speechSynthesis || !TT.voice || !TT.voice.speakReplies || !text || text === last) return;
      last = text; setTimeout(() => { last = ''; }, 8000);
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(String(text).slice(0, 220)); u.rate = 1; window.speechSynthesis.speak(u);
    } catch (_) {}
  };
})();
