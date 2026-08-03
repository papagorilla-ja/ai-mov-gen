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

  // --- 2. シーン切替トランジション ---
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

  // --- 3. Dynamic Animation Builder from HTML data-attributes ---
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
      const badge = el.querySelector(".slide-badge")?.textContent || `Section`;
      const title = el.querySelector(".slide-title")?.textContent || 
                    el.querySelector(".section-huge-title")?.textContent || 
                    "Untitled Slide";
      
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
      // 2. Child elements within slides: Fade + Slide Up / Left transitions
      let fromVars = { opacity: 0, y: 30 };
      let toVars = { opacity: 1, y: 0, duration: 0.8, ease: "power2.out" };

      // Specialized animations based on element types
      if (el.classList.contains("slide-title") || el.classList.contains("section-title")) {
        fromVars = { opacity: 0, x: -50 };
        toVars = { opacity: 1, x: 0, duration: 1.0, ease: "power3.out" };
      } else if (el.classList.contains("slide-eyebrow")) {
        fromVars = { opacity: 0, x: -30 };
        toVars = { opacity: 1, x: 0, duration: 0.6, ease: "power2.out" };
      } else if (el.classList.contains("section-rule")) {
        fromVars = { opacity: 0, scaleX: 0 };
        toVars = { opacity: 1, scaleX: 1, duration: 0.7, ease: "power2.out", transformOrigin: "left center" };
      } else if (el.classList.contains("info-card")) {
        fromVars = { opacity: 0, y: 50, scale: 0.94 };
        toVars = { opacity: 1, y: 0, scale: 1, duration: 0.75, ease: "back.out(1.4)" };
      } else if (el.classList.contains("bullet-item")) {
        fromVars = { opacity: 0, x: -40 };
        toVars = { opacity: 1, x: 0, duration: 0.65, ease: "power3.out" };
      } else if (el.classList.contains("body-card")) {
        fromVars = { opacity: 0, y: 24, scale: 0.98 };
        toVars = { opacity: 1, y: 0, scale: 1, duration: 0.9, ease: "power2.out" };
      } else if (el.classList.contains("comparison-vs")) {
        fromVars = { opacity: 0, scale: 0.4 };
        toVars = { opacity: 1, scale: 1, duration: 0.6, ease: "back.out(2)" };
      } else if (el.classList.contains("dialog-line")) {
        const isB = el.classList.contains("speaker-b");
        fromVars = { opacity: 0, x: isB ? 40 : -40, scale: 0.96 };
        toVars = { opacity: 1, x: 0, scale: 1, duration: 0.5, ease: "power2.out" };
      }

      // Hide elements initially
      gsap.set(el, { opacity: 0 });

      // Animate In
      tl.fromTo(el, fromVars, toVars, start);
      
      // Animate Out slightly before slide ends
      tl.to(el, { 
        opacity: 0, 
        y: (el.classList.contains("slide-title") || el.classList.contains("section-title")) ? 0 : -20,
        x: (el.classList.contains("slide-title") || el.classList.contains("section-title")) ? -20 : 0,
        duration: 0.4, 
        ease: "power2.in" 
      }, start + duration - 0.4);
    }
  });

  // Force rendering of the first frame to apply initial states
  tl.seek(0);

  // Signal readiness for HyperFrames capture engine
  window.__playerReady = true;
  window.__renderReady = true;

  // Keep a playhead updater that triggers UI rendering
  let activeSlide = null;

  // --- 3. Viewport Responsive Scaling (16:9 ratio) ---
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

  // --- 4. Interactive Studio Controls (Only initialized in preview mode) ---
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

  // --- 5. Helper Formatting Functions ---
  function formatTime(seconds) {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  }
