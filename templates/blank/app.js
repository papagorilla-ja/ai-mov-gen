/**
 * ==========================================================================
 * HyperFrames Video Studio - Application Controller (GSAP Orchestrator)
 *
 * 表示モードは2種類:
 *   - レンダリングモード（既定）… #stage だけを原寸で表示する。hyperframes が
 *     window.__timelines からタイムラインを取り出してフレームを描画する。
 *   - プレビューモード … index.html?preview=1 で開いたときだけ。
 *     ダッシュボードUI（サイドバー・再生コントロール）を表示する。
 * ==========================================================================
 */

  // クエリで明示されたときだけプレビュー扱いにする。
  // 旧実装は UA に "Headless" を含むかで判定していたが、判定を外すと
  // ダッシュボードUIが映像に写り込むため、既定を安全側（レンダリング）にしている。
  const isPreviewMode = new URLSearchParams(window.location.search).has("preview");

  if (isPreviewMode) {
    document.body.classList.add("preview-mode");
    // FontAwesome はダッシュボードのアイコンにしか使わないため、ここでだけ読み込む
    // （レンダリングを外部ネットワークに依存させない）
    const faLink = document.createElement("link");
    faLink.rel = "stylesheet";
    faLink.href = "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css";
    document.head.appendChild(faLink);
  }

  // --- 1. GSAP Timeline Core Creation ---
  const stage = document.getElementById("stage");
  const totalDuration = parseFloat(stage.getAttribute("data-duration")) || 190;
  const compositionId = stage.getAttribute("data-composition-id") || "composition";

  // Create paused GSAP timeline
  const tl = gsap.timeline({ paused: true });

  // hyperframes はルート要素の data-composition-id をキーにタイムラインを探す。
  // キーが一致しないとアニメーションが一切適用されず、中身が空の動画になる。
  window.__timelines = window.__timelines || {};
  window.__timelines[compositionId] = tl;
  // 旧バージョン互換のフォールバック（__timelines を配列で上書きしないこと）
  window.__timeline = tl;

  // --- 2. 背景モチーフの動き ---
  //
  // 背景の 2 層（.stage-bg-motif / .stage-bg-glow）を、動画の尺いっぱいかけて
  // ごくゆっくり動かす。静止した背景だと、本文が出入りするだけの平板な絵になる。
  //
  // CSS アニメーションは使わない。hyperframes はタイムラインを任意の時刻へ
  // シークしてから 1 枚ずつ捕獲するため、実時間で進む CSS アニメーションは
  // フレームごとに位相がばらつき、背景だけが不規則に震える動画になってしまう。
  // GSAP のタイムラインに載せれば「時刻 → 見た目」が一意に決まる。
  // （Chart.js を animation: false にしているのと同じ理由。）
  //
  // 速さは「言われないと気づかない」程度に留める。背景が目立つと本文と
  // 注意を奪い合い、読み取りの邪魔になる。目安は 1 周 30 秒以上。
  //
  // 無限リピート（repeat: -1）は使わない。タイムラインの尺が Infinity になり、
  // hyperframes が総尺を測れなくなるため。往復させたいものは回数を計算して渡す。

  // 動きの速さ。いずれも「1 周期に何秒かけるか」で持つ。
  // 尺で割った移動量にせず周期で持つのは、15 分の動画でも 1 分の動画でも
  // 「見た目の速さ」を同じにするため。
  const GRID_TILE_PX = 60;      // CSS の background-size と揃える
  const GRID_CYCLE_SEC = 40;    // 方眼が 1 タイル進む秒数
  const WAVE_STRIPE_PX = 58;    // CSS の repeating-linear-gradient と揃える
  const WAVE_CYCLE_SEC = 30;    // 縞が 1 本ぶん進む秒数
  const DOT_HALF_SEC = 7;       // 点の明滅の半周期
  const MESH_HALF_SEC = 45;     // 色玉が片道を巡る秒数
  const NOISE_HALF_SEC = 50;    // 光が片道ぶん広がる秒数

  /** 模様を一定の速さで流す。1 周期の距離と秒数から総移動量を決める。 */
  function addDrift(target, dx, dy, cycleSec, total) {
    const k = total / cycleSec;
    tl.fromTo(target,
      { backgroundPosition: "0px 0px" },
      {
        backgroundPosition: `${(dx * k).toFixed(1)}px ${(dy * k).toFixed(1)}px`,
        duration: total, ease: "none",
      }, 0);
  }

  /**
   * 動画の尺いっぱいを往復で埋める。
   *
   * 半周期を「尺を割り切れる値」へ丸めているのは、端数が出ると tween が
   * 動画の尺をはみ出し、タイムラインの総尺が動画より長くなってしまうため。
   */
  function addOscillation(target, from, to, halfSec, total) {
    const runs = Math.max(1, Math.round(total / halfSec));
    tl.fromTo(target, from, {
      ...to, duration: total / runs, ease: "sine.inOut", repeat: runs - 1, yoyo: true,
    }, 0);
  }

  const MOTIF_MOTIONS = {
    // 方眼を斜めに流す。
    grid: (motif, glow, total) =>
      addDrift(motif, GRID_TILE_PX, GRID_TILE_PX, GRID_CYCLE_SEC, total),

    // 色玉を巡回させる。玉は 1 枚の背景画像なので、層ごと回して動かす。
    // 層は inset:-80px と blur(40px) で画面より大きいため、この程度の
    // 回転・拡大では縁が入り込まない。角度を増やすときは縁が出ないか要確認。
    mesh: (motif, glow, total) =>
      addOscillation(motif, { rotation: -3, scale: 1.06 }, { rotation: 3, scale: 1.12 },
                     MESH_HALF_SEC, total),

    // 点の明滅。位置を動かすとタイルの継ぎ目が目に付くので、濃さだけ変える。
    dots: (motif, glow, total) =>
      addOscillation(motif, { opacity: 0.7 }, { opacity: 1 }, DOT_HALF_SEC, total),

    // 斜めの帯を流す。
    waves: (motif, glow, total) =>
      addDrift(motif, WAVE_STRIPE_PX, -WAVE_STRIPE_PX, WAVE_CYCLE_SEC, total),

    // 粒そのものは動かさない。1px 単位の粒がずれるとフレームごとにちらつき、
    // 見づらいうえに動画の圧縮効率も落ちる。代わりに光の層だけ広げる。
    noise: (motif, glow, total) =>
      addOscillation(glow, { scale: 1, opacity: 0.8 }, { scale: 1.12, opacity: 1 },
                     NOISE_HALF_SEC, total),

    // 無地は何もしない。「内容に集中させたい」ときの選択肢なので動かさない。
    plain: null,
  };

  function registerMotifMotion() {
    const motif = document.querySelector(".stage-bg-motif");
    const glow = document.querySelector(".stage-bg-glow");
    if (!motif || !glow) return;

    // モチーフの種類は #stage の motif-* クラスが持つ（design_tokens.py が付ける）。
    const name = Array.from(stage.classList)
      .find((c) => c.startsWith("motif-"))
      ?.slice("motif-".length);
    // 尺が取れないときは動かさない（0 秒の tween は GSAP が即座に完了扱いにする）
    if (!(totalDuration > 0)) return;

    const motion = name ? MOTIF_MOTIONS[name] : undefined;
    if (motion === undefined) {
      console.warn(`[motif] 未知の背景モチーフ "${name}" です。背景は静止のままにします`);
      return;
    }
    if (motion) motion(motif, glow, totalDuration);
  }

  registerMotifMotion();

  // --- 3. シーン切替トランジション ---
  //
  // シーン同士は時間軸上で重ならない（composition.py が尺を順に積むだけ）ため、
  // 「持ち時間の中で退場を終え、次のシーンが登場する」方式で表現する。
  // 切替の瞬間に見えるのはステージの背景モチーフで、黒画面にはならない。
  //
  // 既定は "none"（従来どおり瞬時に切り替わる）。data-transition が未設定の
  // 古いコンポジションでも挙動が一切変わらないようにしている。

  // from / to / out は同じプロパティ集合で書くこと。片方にしか無いプロパティを
  // 混ぜると、GSAP が未設定の初期値から補間を始めて予期しない動きになる。
  const SLIDE_TRANSITIONS = {
    fade: {
      duration: 0.45,
      from: { opacity: 0 },
      to: { opacity: 1 },
      out: { opacity: 0 },
    },
    slide: {
      duration: 0.5,
      from: { opacity: 0, xPercent: 5 },
      to: { opacity: 1, xPercent: 0 },
      out: { opacity: 0, xPercent: -5 },
    },
    zoom: {
      duration: 0.5,
      from: { opacity: 0, scale: 1.06 },
      to: { opacity: 1, scale: 1 },
      out: { opacity: 0, scale: 0.97 },
    },
    wipe: {
      duration: 0.55,
      from: { opacity: 0, clipPath: "inset(100% 0% 0% 0%)" },
      to: { opacity: 1, clipPath: "inset(0% 0% 0% 0%)" },
      out: { opacity: 0, clipPath: "inset(0% 0% 100% 0%)" },
    },
  };

  const transitionName = stage.getAttribute("data-transition") || "none";
  const transition = SLIDE_TRANSITIONS[transitionName] || null;

  /**
   * スライド1枚ぶんの表示・非表示をタイムラインに登録する。
   * transition が null のときは従来どおり set による瞬時切替。
   */
  function registerSlideVisibility(el, start, duration) {
    gsap.set(el, { display: "none", opacity: 0, pointerEvents: "none" });

    if (!transition) {
      tl.set(el, { display: "flex", opacity: 1, pointerEvents: "auto" }, start);
      tl.set(el, { display: "none", opacity: 0, pointerEvents: "none" }, start + duration);
      return;
    }

    // 登場：表示状態にしてから from の値でアニメーションさせる
    const inDuration = Math.min(transition.duration, duration / 2);
    tl.set(el, { display: "flex", pointerEvents: "auto" }, start);
    tl.fromTo(
      el,
      transition.from,
      { ...transition.to, duration: inDuration, ease: "power2.out" },
      start
    );

    // 退場：持ち時間の内側で必ず完了させる（次のシーンと重ねない）
    const outDuration = Math.min(0.35, duration / 3);
    tl.to(el, { ...transition.out, duration: outDuration, ease: "power2.in" }, start + duration - outDuration);
    tl.set(el, { display: "none", opacity: 0, pointerEvents: "none" }, start + duration);
  }

  // --- 4. アニメーションの登録 ---
  //
  // 以前はクラス名（info-card / bullet-item / dialog-line …）で分岐していたが、
  // レイアウトを 1 つ増やすたびにこのファイルへ if を足す必要があった。
  // いまはレイアウト側が data-anim で「動きの語彙」を宣言し、ここは辞書を引くだけ。
  // レイアウトを追加してもこのファイルは触らない。
  //
  // 語彙を増やすときは layouts/<id>/template.html 側の宣言とここの 2 箇所だけ。
  //
  // 語彙は 3 系統ある。**足す前に既存と重複していないか必ず確かめること。**
  //   1. transform 系 … rise / slide-* / pop / expand-circle / flip
  //        伸びる表現は grow-bar（下→上・scaleY）と scale-x（左→右・scaleX）の対。
  //   2. clip-path 系 … draw-right(左→右) / draw-down(上→下) / draw-up(下→上)
  //        transform を使わないので、角丸・グラデーション・線幅を歪めずに現れる。
  //        帯・棒・線はこちらを使う。scaleX で伸ばすとグラデーションごと潰れる。
  //        逆向きの draw-left は使う場所がまだ無いので置いていない。
  //   3. 文字そのものを動かす … count-up
  //        CSS プロパティの補間では表せないため、extra に関数を持たせている。
  const ANIMS = {
    none:            { from: {},                                            to: {} },
    fade:            { from: {},                                            to: { duration: 0.7 } },
    rise:            { from: { y: 30 },                                     to: { y: 0, duration: 0.8 } },
    "slide-right":   { from: { x: -40 },                                    to: { x: 0, duration: 0.7 } },
    "slide-left":    { from: { x: 40 },                                     to: { x: 0, duration: 0.7 } },
    pop:             { from: { scale: 0.9 },                                to: { scale: 1, duration: 0.65, ease: "back.out(1.5)" } },
    "scale-x":       { from: { scaleX: 0 },                                 to: { scaleX: 1, duration: 0.7, transformOrigin: "left center" } },
    // clip-path での「伸びる」表現。パスの長さを測らずに済み、
    // 要素が CSS で回転していても、その向きに沿って伸びる。
    "draw-right":    { from: { clipPath: "inset(0 100% 0 0)" },             to: { clipPath: "inset(0 0% 0 0)", duration: 0.6 } },
    "draw-down":     { from: { clipPath: "inset(0 0 100% 0)" },             to: { clipPath: "inset(0 0 0% 0)", duration: 0.6 } },
    "draw-up":       { from: { clipPath: "inset(100% 0 0 0)" },             to: { clipPath: "inset(0% 0 0 0)", duration: 0.6 } },
    "expand-circle": { from: { scale: 0.6 },                                to: { scale: 1, duration: 0.8, ease: "power3.out" } },
    "grow-bar":      { from: { scaleY: 0 },                                 to: { scaleY: 1, duration: 0.7, transformOrigin: "center bottom" } },
    "blur-in":       { from: { filter: "blur(14px)", scale: 1.04 },         to: { filter: "blur(0px)", scale: 1, duration: 0.9 } },
    flip:            { from: { rotationY: -70 },                            to: { rotationY: 0, duration: 0.7 } },
    // 数値が主役のときだけ使う。軽く持ち上げつつ、数字を 0 から目標値まで動かす。
    "count-up":      { from: { y: 18 },                                     to: { y: 0, duration: 0.5 }, extra: countUp },
  };
  const DEFAULT_ANIM = "rise";
  // 退場は透明度だけにしている。位置や拡大を触ると、CSS 側で
  // transform を持つ要素（図解のノードや回転した矢印）と取り合いになり、
  // 最後の 0.4 秒だけ図が崩れる、という分かりにくい壊れ方をするため。
  const EXIT_DURATION = 0.4;

  // ---- count-up の実装 ----
  //
  // 「42.5%」「1,200 件」「約 3.2 倍」のように、数値の前後に文字が付く前提で書く。
  // 最初に見つかった数値だけを 0 から目標値へ動かし、それ以外の文字は触らない。
  //
  // シーク方式の書き出しでも破綻しない。hyperframes はタイムラインを任意の時刻へ
  // シークしてから 1 枚捕獲するが、GSAP はシーク先の時刻で tween を描画し直すため、
  // onUpdate で書き戻す方式なら「時刻 → 表示」が一意に決まる。
  // （Chart.js を animation: false にしたのは、あちらが rAF 駆動で
  //   シークに追従しないため。GSAP の tween であればこの問題は起きない。）
  const NUMBER_RE = /-?\d[\d,]*(?:\.\d+)?/;

  // 実測オートフィットが途中経過（「0%」のような短い文字列）を測ってしまうと、
  // 完成形が箱からはみ出す。測る直前に完成形へ戻せるよう控えておく。
  const countUpTexts = [];

  function restoreCountUpText() {
    countUpTexts.forEach((item) => { item.el.textContent = item.text; });
  }

  function countUp(el, start, duration) {
    const raw = el.textContent.trim();
    const match = raw.match(NUMBER_RE);
    if (!match) return;                       // 数字が無ければ持ち上げ（y）だけが効く
    const target = parseFloat(match[0].replace(/,/g, ""));
    if (!isFinite(target)) return;

    const prefix = raw.slice(0, match.index);
    const suffix = raw.slice(match.index + match[0].length);
    // 小数桁と桁区切りは元の表記に合わせる。「3.2 倍」が途中で「3 倍」に見えたり、
    // 「1,200」が「1200」に変わったりすると、別の値に読めてしまうため。
    const decimals = (match[0].split(".")[1] || "").length;
    const grouped = match[0].includes(",");
    const format = (value) => {
      const fixed = value.toFixed(decimals);
      return grouped
        ? Number(fixed).toLocaleString("ja-JP", {
            minimumFractionDigits: decimals, maximumFractionDigits: decimals,
          })
        : fixed;
    };

    countUpTexts.push({ el: el, text: raw });

    // 尺の長いシーンでも数え続けない。持ち時間の 35% を目安に 0.6〜1.6 秒へ収める。
    const spin = Math.min(1.6, Math.max(0.6, duration * 0.35));
    const proxy = { value: 0 };
    tl.to(proxy, {
      value: target,
      duration: spin,
      ease: "power2.out",
      onUpdate: () => { el.textContent = prefix + format(proxy.value) + suffix; },
    }, start);
  }

  const clips = document.querySelectorAll(".clip");

  // Keep track of slide start/duration for navigation and stats
  const slides = [];

  clips.forEach((el) => {
    const start = parseFloat(el.getAttribute("data-start"));
    const duration = parseFloat(el.getAttribute("data-duration"));

    if (isNaN(start) || isNaN(duration)) return;

    if (el.classList.contains("slide")) {
      // 1. Slide containers: display management + シーン切替トランジション
      registerSlideVisibility(el, start, duration);

      // Record slide details for preview controls
      const indexAttr = el.getAttribute("id") || `slide-${slides.length + 1}`;
      const title = el.querySelector(".slide-title")?.textContent ||
                    el.querySelector(".section-title")?.textContent ||
                    "Untitled Slide";
      const badge = el.querySelector(".slide-eyebrow")?.textContent || "Section";

      slides.push({
        id: indexAttr,
        index: slides.length + 1,
        title: title,
        category: badge,
        start: start,
        duration: duration,
        element: el
      });
    } else {
      // 2. スライド内の要素。data-anim の語彙で登場のしかたを決める。
      const animName = el.getAttribute("data-anim");
      // 辞書に無い語彙は既定へ落とすが、黙って落とすと気づけない。
      // 実際 count-up は辞書に無いまま rise で描かれ続けており、
      // 「数字が主役のレイアウトなのに数字が動かない」原因になっていた。
      if (animName && !(animName in ANIMS)) {
        console.warn(`[anim] 未定義の data-anim="${animName}" を既定 (${DEFAULT_ANIM}) で描画します`);
      }
      const spec = ANIMS[animName] || ANIMS[DEFAULT_ANIM];
      const fromVars = Object.assign({ opacity: 0 }, spec.from);
      const toVars = Object.assign({ opacity: 1, ease: "power2.out", duration: 0.7 }, spec.to);

      gsap.set(el, { opacity: 0 });
      tl.fromTo(el, fromVars, toVars, start);
      // CSS プロパティの補間では表せない動き（数字のカウントなど）を足す。
      if (spec.extra) spec.extra(el, start, duration);

      const exitAt = Math.max(start, start + duration - EXIT_DURATION);
      tl.to(el, { opacity: 0, duration: EXIT_DURATION, ease: "power2.in" }, exitAt);
    }
  });

  // --- 5. 実測オートフィット（自動適応の第 3 層） ---
  //
  // 件数ごとの CSS 密度段階で大半は収まるが、「3 項目だが各 80 文字」のような
  // 文字数の振れまでは予測できない。描画後に実測し、はみ出していれば縮小する。
  //
  // 縮めるのは data-fit を付けた「箱」であって .clip ではない。
  // .clip の transform は GSAP が握っているため、そこへ scale を書くと
  // 登場アニメーションに上書きされて効かない（または動きが壊れる）。
  const MIN_FIT_SCALE = 0.62;

  function fitBox(box) {
    box.style.transform = "";
    const availH = box.clientHeight;
    const availW = box.clientWidth;
    if (!availH || !availW) return;
    // +1px は小数の丸め差で毎回わずかに縮むのを防ぐための遊び
    const ratioH = availH / Math.max(availH, box.scrollHeight - 1);
    const ratioW = availW / Math.max(availW, box.scrollWidth - 1);
    const scale = Math.max(MIN_FIT_SCALE, Math.min(ratioH, ratioW, 1));
    if (scale < 0.995) box.style.transform = `scale(${scale.toFixed(3)})`;
  }

  function autoFitAll() {
    // count-up は文字列を書き換えるため、測る前に必ず完成形へ戻す。
    // 「0%」を測って縮小率を決めると、数え終わった「42%」がはみ出す。
    restoreCountUpText();
    // スライドは display:none で待機しているため、そのままでは寸法が 0 になる。
    // 1 枚ずつ「見えない状態で表示」して測り、元に戻す。
    document.querySelectorAll(".slide").forEach((slide) => {
      const prevDisplay = slide.style.display;
      const prevVisibility = slide.style.visibility;
      const prevOpacity = slide.style.opacity;
      slide.style.display = "flex";
      slide.style.visibility = "hidden";
      slide.style.opacity = "1";
      slide.querySelectorAll("[data-fit]").forEach(fitBox);
      slide.style.display = prevDisplay;
      slide.style.visibility = prevVisibility;
      slide.style.opacity = prevOpacity;
    });
  }

  tl.seek(0);

  // フォントの読み込み完了を待ってから実測する。
  // 待たずに測ると代替フォントの寸法で判定してしまい、
  // 「たまに文字が小さすぎる動画ができる」という再現しにくい不具合になる。
  // ただしフォント読込が詰まったときにレンダリングが永久に始まらないのは困るので、
  // 3 秒で打ち切る。
  const fontsReady = (document.fonts && document.fonts.ready) ? document.fonts.ready : Promise.resolve();
  Promise.race([fontsReady, new Promise((resolve) => setTimeout(resolve, 3000))])
    .catch(() => {})
    .then(() => {
      autoFitAll();
      tl.seek(0);
      // hyperframes はこのフラグを見てフレームの取得を始める。
      // オートフィット後に立てることで、調整済みの絵だけが撮られる。
      window.__playerReady = true;
      window.__renderReady = true;
    });

  // Keep a playhead updater that triggers UI rendering
  let activeSlide = null;

  // --- 6. Viewport Responsive Scaling (16:9 ratio) ---
  // #stage はダッシュボードの外（body 直下）にあるため、プレビュー時は
  // 中央セル (.dashboard-preview) の矩形を測って、その上に重ねて表示する。
  const dashboardPreview = document.querySelector(".dashboard-preview");

  function layoutStage() {
    if (!isPreviewMode || !dashboardPreview) return;

    const rect = dashboardPreview.getBoundingClientRect();
    // .dashboard-preview の padding (40px) の分だけ内側に収める
    const availableWidth = rect.width - 80;
    const availableHeight = rect.height - 80;
    if (availableWidth <= 0 || availableHeight <= 0) {
      // 幅0・負の値では縮小しない（直前の倍率を維持する）
      return;
    }

    const targetWidth = parseInt(stage.dataset.width || "1920", 10);
    const targetHeight = parseInt(stage.dataset.height || "1080", 10);
    const scale = Math.min(availableWidth / targetWidth, availableHeight / targetHeight);

    const rootStyle = document.documentElement.style;
    rootStyle.setProperty("--stage-scale", scale);
    rootStyle.setProperty("--stage-left", `${rect.left + (rect.width - targetWidth * scale) / 2}px`);
    rootStyle.setProperty("--stage-top", `${rect.top + (rect.height - targetHeight * scale) / 2}px`);
  }

  window.addEventListener("resize", layoutStage);

  // Run scaling on DOM load and immediately
  window.addEventListener("load", layoutStage);
  layoutStage();

  // --- 7. Interactive Studio Controls (Only initialized in preview mode) ---
  if (isPreviewMode) {
    initPreviewDashboard();
  }

  function initPreviewDashboard() {
    const playPauseBtn = document.getElementById("btn-play-pause");
    const playPauseIcon = document.getElementById("icon-play-pause");
    const timeDisplay = document.getElementById("time-display");
    const timelineOuter = document.getElementById("timeline-outer");
    const timelineFill = document.getElementById("timeline-fill");
    const speedSelect = document.getElementById("speed-select");
    const slideListContainer = document.getElementById("dashboard-slide-list");

    // Populate Slide Navigation checklist
    slides.forEach((slide) => {
      const item = document.createElement("div");
      item.className = "slide-item";
      item.dataset.start = slide.start;
      
      const num = document.createElement("div");
      num.className = "slide-item-num";
      num.textContent = slide.index;
      
      const details = document.createElement("div");
      details.className = "slide-item-title";
      details.textContent = `${slide.category ? slide.category + ': ' : ''}${slide.title}`;

      const time = document.createElement("div");
      time.className = "slide-item-time";
      time.textContent = formatTime(slide.start);

      item.appendChild(num);
      item.appendChild(details);
      item.appendChild(time);

      item.addEventListener("click", () => {
        tl.time(slide.start);
        updateUI();
      });

      slideListContainer.appendChild(item);
    });

    // Play/Pause Action
    playPauseBtn.addEventListener("click", () => {
      if (tl.paused()) {
        tl.play();
        playPauseIcon.className = "fa-solid fa-pause";
      } else {
        tl.pause();
        playPauseIcon.className = "fa-solid fa-play";
      }
    });

    // Speed Control Action
    speedSelect.addEventListener("change", () => {
      tl.timeScale(parseFloat(speedSelect.value));
    });

    // Scrubbing (Drag/Click Timeline)
    let isDragging = false;

    function scrub(e) {
      const rect = timelineOuter.getBoundingClientRect();
      const clickX = e.clientX - rect.left;
      const width = rect.width;
      let pct = clickX / width;
      pct = Math.max(0, Math.min(1, pct));
      tl.progress(pct);
      updateUI();
    }

    timelineOuter.addEventListener("mousedown", (e) => {
      isDragging = true;
      scrub(e);
    });

    document.addEventListener("mousemove", (e) => {
      if (isDragging) scrub(e);
    });

    document.addEventListener("mouseup", () => {
      isDragging = false;
    });

    // Synchronize Timeline ticks
    gsap.ticker.add(() => {
      if (!isDragging) {
        updateUI();
      }
    });

    function updateUI() {
      const progress = tl.progress();
      const time = tl.time();
      
      // Update scrubbing progress bar
      timelineFill.style.width = (progress * 100) + "%";
      
      // Time text indicator
      timeDisplay.textContent = `${formatTime(time)} / ${formatTime(totalDuration)}`;

      // Synchronize Active Slide status
      let currentSlide = null;
      for (let i = 0; i < slides.length; i++) {
        const slide = slides[i];
        if (time >= slide.start && time < (slide.start + slide.duration)) {
          currentSlide = slide;
          break;
        }
      }

      if (currentSlide && currentSlide !== activeSlide) {
        activeSlide = currentSlide;
        
        // Update Sidebar List Items highlights
        const items = slideListContainer.querySelectorAll(".slide-item");
        items.forEach((item, idx) => {
          if (idx === currentSlide.index - 1) {
            item.classList.add("active");
            item.scrollIntoView({ behavior: "smooth", block: "nearest" });
          } else {
            item.classList.remove("active");
          }
        });
        
        // Re-render Track visualizer panel
        renderTrackVisualizer(currentSlide);
      }

      // Update active state in HTML slides
      slides.forEach((slide) => {
        if (time >= slide.start && time < (slide.start + slide.duration)) {
          slide.element.classList.add("active");
        } else {
          slide.element.classList.remove("active");
        }
      });

      // Synchronize Playback icon state
      if (tl.paused()) {
        playPauseIcon.className = "fa-solid fa-play";
      } else {
        playPauseIcon.className = "fa-solid fa-pause";
      }
    }

    // Right Sidebar visual track listing
    const trackPanel = document.createElement("div");
    trackPanel.className = "dashboard-panel";
    
    const panelHeader = document.createElement("div");
    panelHeader.className = "panel-header";
    panelHeader.innerHTML = `<h2><i class="fa-solid fa-sliders"></i> タイムラインレイヤー</h2>`;
    
    const trackTimeline = document.createElement("div");
    trackTimeline.className = "track-timeline";
    trackTimeline.id = "track-timeline-container";

    const panelFooter = document.createElement("div");
    panelFooter.className = "panel-footer";
    panelFooter.innerHTML = `
      <div style="font-size: 0.75rem; font-weight:600; margin-bottom:8px; color:var(--text-secondary);"><i class="fa-solid fa-terminal"></i> HyperFrames CLI レンダリング</div>
      <div class="render-cmd-box">npx hyperframes render index.html --output output.mp4</div>
    `;

    trackPanel.appendChild(panelHeader);
    trackPanel.appendChild(trackTimeline);
    trackPanel.appendChild(panelFooter);
    
    // Add track panel to dashboard
    document.getElementById("preview-dashboard").appendChild(trackPanel);

    function renderTrackVisualizer(slide) {
      trackTimeline.innerHTML = "";
      
      // Get all child elements under this slide with clip class
      const childClips = slide.element.querySelectorAll(".clip");
      
      childClips.forEach((clip) => {
        const cStart = parseFloat(clip.getAttribute("data-start"));
        const cDur = parseFloat(clip.getAttribute("data-duration"));
        
        const row = document.createElement("div");
        row.className = "track-row";
        
        // Element identifier name
        let name = clip.tagName.toLowerCase();
        if (clip.id) name += `#${clip.id}`;
        if (clip.className) {
          const firstClass = clip.className.split(" ").find(c => c !== "clip");
          if (firstClass) name += `.${firstClass}`;
        }
        
        const textSnippet = clip.textContent.trim().substring(0, 18);
        const label = textSnippet ? `"${textSnippet}..."` : name;

        // Calculate progress percentage inside the active slide duration
        const relStart = cStart - slide.start;
        const startPct = (relStart / slide.duration) * 100;
        const durPct = (cDur / slide.duration) * 100;

        row.innerHTML = `
          <div class="track-name" title="${name}">${label}</div>
          <div style="font-size: 0.6rem; color: var(--text-muted);">Start: ${cStart}s | Dur: ${cDur}s</div>
          <div class="track-bar-container">
            <div class="track-bar-fill" style="left: ${startPct}%; width: ${durPct}%;"></div>
          </div>
        `;
        trackTimeline.appendChild(row);
      });
    }
  }

  // --- 8. Helper Formatting Functions ---
  function formatTime(seconds) {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  }
