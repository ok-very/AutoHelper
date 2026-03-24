import{a as Z,j as e,r as a,c as Pe}from"./settings-DF93i-N1.js";import{B as z}from"./Badge-BioY5juV.js";import"./Button-Bucfe1W1.js";import"./Card-Xw5P1Lnw.js";import"./TextInput-DcYM_KGE.js";import"./Stack-DsMaUa8S.js";import{S as Ue,M as Te}from"./ModuleLayout-2hQmROsN.js";import{F as Be}from"./FeedbackMessage-CMePmpOh.js";import{u as ke,a as _e}from"./registry-Bmf5CZDU.js";import{C as ze,W as Fe,d as Ie}from"./WiringManifest-BRmXMo6Z.js";import{a as y}from"./api-C4sMNGFc.js";import{c as ee}from"./clsx-B-dksMZM.js";import{X as te}from"./x-BPJAHzF4.js";import{C as oe}from"./chevron-right-BfnBcDjX.js";import{P as Re}from"./pencil-DFGyCS6a.js";import{P as Le}from"./play-ge2fyybe.js";import{S as He}from"./send-D-f2ZK5I.js";/* empty css               */import"./moduleRegistry-DjpHALCo.js";const Me=[["path",{d:"M15.2 3a2 2 0 0 1 1.4.6l3.8 3.8a2 2 0 0 1 .6 1.4V19a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z",key:"1c8476"}],["path",{d:"M17 21v-7a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v7",key:"1ydtos"}],["path",{d:"M7 3v4a1 1 0 0 0 1 1h7",key:"t51u73"}]],ae=Z("save",Me);const Ae=[["path",{d:"m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3",key:"wmoenq"}],["path",{d:"M12 9v4",key:"juzpu7"}],["path",{d:"M12 17h.01",key:"p32p05"}]],Oe=Z("triangle-alert",Ae);function $e(o,i){if(!o||Object.keys(i).length===0)return o;const m=o.split("/").map(E=>i[E.trim()]).filter(Boolean);if(m.length===0)return o;const N=m.map(E=>E.split(" ")[0]);return`${o} — ${N.join(", ")}`}function We(o){return o.filter(i=>!(!i||i==="TBC"||i==="TBD"||/[$|_]{2,}|TOTAL|PENDING|Budget/i.test(i)||/\d{4}/.test(i)||/[,(]$/.test(i.trim())||/\(\$/.test(i)))}const R={bar:{display:"flex",flexWrap:"wrap",alignItems:"center",gap:"8px",fontFamily:"var(--font-sans)",fontSize:"12px"},searchWrap:{position:"relative",flex:"1 1 200px",maxWidth:"320px"},searchIcon:{position:"absolute",left:"8px",top:"50%",transform:"translateY(-50%)",color:"var(--fg-disabled)",pointerEvents:"none"},toggle:{display:"flex",alignItems:"center",gap:"4px",cursor:"pointer",userSelect:"none",fontFamily:"var(--font-sans)",fontSize:"12px"},separator:{width:"1px",height:"16px",background:"var(--border)",flexShrink:0}};function Ge({searchQuery:o,onSearchChange:i,filterPhase:r,onPhaseChange:m,filterLead:N,onLeadChange:E,filterCity:k,onCityChange:d,showOnHold:j,onShowOnHoldChange:p,showIssuesOnly:V,onShowIssuesOnlyChange:u,phases:v,leads:f,cities:x,onHoldCount:D,issueCount:S,memberMap:T}){const P=We(x);return e.jsxDEV("div",{style:R.bar,children:[e.jsxDEV("div",{style:R.searchWrap,children:[e.jsxDEV(Ue,{size:13,style:R.searchIcon},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/FilterBar.tsx",lineNumber:103,columnNumber:9},this),e.jsxDEV("input",{type:"text",className:"search-input",value:o,onChange:l=>i(l.target.value),placeholder:"Search projects...",style:{width:"100%"}},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/FilterBar.tsx",lineNumber:104,columnNumber:9},this)]},void 0,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/FilterBar.tsx",lineNumber:102,columnNumber:7},this),e.jsxDEV("select",{className:"filter-select",value:r,onChange:l=>m(l.target.value),children:[e.jsxDEV("option",{value:"",children:"All phases"},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/FilterBar.tsx",lineNumber:115,columnNumber:9},this),v.map(l=>e.jsxDEV("option",{value:l,children:l},l,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/FilterBar.tsx",lineNumber:116,columnNumber:26},this))]},void 0,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/FilterBar.tsx",lineNumber:114,columnNumber:7},this),e.jsxDEV("select",{className:"filter-select",value:N,onChange:l=>E(l.target.value),children:[e.jsxDEV("option",{value:"",children:"All leads"},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/FilterBar.tsx",lineNumber:120,columnNumber:9},this),f.map(l=>e.jsxDEV("option",{value:l,children:$e(l,T)},l,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/FilterBar.tsx",lineNumber:122,columnNumber:11},this))]},void 0,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/FilterBar.tsx",lineNumber:119,columnNumber:7},this),e.jsxDEV("select",{className:"filter-select",value:k,onChange:l=>d(l.target.value),children:[e.jsxDEV("option",{value:"",children:"All cities"},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/FilterBar.tsx",lineNumber:127,columnNumber:9},this),P.map(l=>e.jsxDEV("option",{value:l,children:l},l,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/FilterBar.tsx",lineNumber:128,columnNumber:33},this))]},void 0,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/FilterBar.tsx",lineNumber:126,columnNumber:7},this),e.jsxDEV("span",{style:R.separator},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/FilterBar.tsx",lineNumber:131,columnNumber:7},this),D>0&&e.jsxDEV("label",{style:{...R.toggle,color:j?"var(--fg)":"var(--fg-secondary)"},children:[e.jsxDEV("input",{type:"checkbox",checked:j,onChange:l=>p(l.target.checked),style:{accentColor:"var(--accent)"}},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/FilterBar.tsx",lineNumber:135,columnNumber:11},this),"On hold (",D,")"]},void 0,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/FilterBar.tsx",lineNumber:134,columnNumber:9},this),S>0&&e.jsxDEV("label",{style:{...R.toggle,color:V?"var(--color-warning, #B89B5E)":"var(--fg-secondary)"},children:[e.jsxDEV("input",{type:"checkbox",checked:V,onChange:l=>u(l.target.checked),style:{accentColor:"var(--color-warning, #B89B5E)"}},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/FilterBar.tsx",lineNumber:147,columnNumber:11},this),S," issues"]},void 0,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/FilterBar.tsx",lineNumber:146,columnNumber:9},this)]},void 0,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/FilterBar.tsx",lineNumber:101,columnNumber:5},this)}const qe=`
  [data-section] { position: relative; transition: outline 0.12s; }
  [data-section]:hover { outline: 1px dashed rgba(63, 92, 110, 0.3); outline-offset: 2px; cursor: pointer; }
  [data-section].editing { outline: 2px solid #3F5C6E; outline-offset: 2px; cursor: text; }
  [data-section].editing:hover { outline: 2px solid #3F5C6E; }

  .bfa-toolbar {
    position: absolute;
    left: 0;
    display: flex;
    align-items: center;
    gap: 2px;
    padding: 3px 6px;
    background: #fff;
    border: 1px solid #D6D2CB;
    border-radius: 4px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    z-index: 9999;
    font-family: "Source Sans 3", "Segoe UI", sans-serif;
    font-size: 11px;
    user-select: none;
  }
  .bfa-toolbar button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 24px;
    border: none;
    border-radius: 3px;
    background: transparent;
    color: #5A5A57;
    cursor: pointer;
    font-size: 12px;
    font-family: inherit;
    padding: 0;
    line-height: 1;
  }
  .bfa-toolbar button:hover { background: rgba(63, 92, 110, 0.08); }
  .bfa-toolbar button.active { background: rgba(63, 92, 110, 0.12); color: #2E2E2C; }
  .bfa-toolbar .sep {
    width: 1px;
    height: 16px;
    background: #D6D2CB;
    margin: 0 2px;
    flex-shrink: 0;
  }
  .bfa-toolbar select {
    height: 22px;
    border: 1px solid #D6D2CB;
    border-radius: 3px;
    background: transparent;
    color: #5A5A57;
    font-size: 10px;
    font-family: inherit;
    cursor: pointer;
    padding: 0 2px;
    outline: none;
  }
  .bfa-toolbar .hl-swatch {
    width: 16px;
    height: 16px;
    border-radius: 2px;
    border: 1px solid #D6D2CB;
    cursor: pointer;
    padding: 0;
    display: inline-block;
  }
  .bfa-toolbar .hl-swatch.active { border: 2px solid #3F5C6E; }
  .bfa-toolbar .hl-group {
    display: none;
    align-items: center;
    gap: 3px;
    padding: 3px;
    position: absolute;
    top: 100%;
    left: 0;
    margin-top: 2px;
    background: #fff;
    border: 1px solid #D6D2CB;
    border-radius: 4px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.08);
  }
  .bfa-toolbar .hl-group.open { display: flex; }
`,Ye=`
(function() {
  var toolbar = null;
  var activeSection = null;
  var hlOpen = false;

  var HIGHLIGHT_COLORS = [
    { label: 'Yellow', hex: '#FFF3B0' },
    { label: 'Green', hex: '#D4EDBC' },
    { label: 'Cyan', hex: '#B5E8EC' },
  ];

  function createToolbar() {
    if (toolbar) return toolbar;
    toolbar = document.createElement('div');
    toolbar.className = 'bfa-toolbar';
    toolbar.innerHTML =
      '<button data-cmd="bold" title="Bold"><b>B</b></button>' +
      '<button data-cmd="italic" title="Italic"><i>I</i></button>' +
      '<button data-cmd="strikeThrough" title="Strikethrough"><s>S</s></button>' +
      '<span class="sep"></span>' +
      '<button data-cmd="highlight" title="Highlight">H</button>' +
      '<div class="hl-group" id="bfa-hl-group"></div>' +
      '<span class="sep"></span>' +
      '<select data-cmd="fontSize" title="Font size">' +
      '  <option value="">Size</option>' +
      '  <option value="1">8pt</option>' +
      '  <option value="3">11pt</option>' +
      '</select>' +
      '<span class="sep"></span>' +
      '<button data-cmd="insertUnorderedList" title="Bullet list">&#8226;</button>';

    // Build highlight swatches
    var hlGroup = toolbar.querySelector('#bfa-hl-group');
    HIGHLIGHT_COLORS.forEach(function(c) {
      var btn = document.createElement('button');
      btn.className = 'hl-swatch';
      btn.style.background = c.hex;
      btn.title = c.label;
      btn.setAttribute('data-hl-color', c.hex);
      btn.addEventListener('mousedown', function(e) {
        e.preventDefault();
        applyHighlight(c.hex);
        closeHlGroup();
      });
      hlGroup.appendChild(btn);
    });
    // Remove highlight button
    var rmBtn = document.createElement('button');
    rmBtn.className = 'hl-swatch';
    rmBtn.style.background = '#fff';
    rmBtn.title = 'Remove';
    rmBtn.textContent = '×';
    rmBtn.style.fontSize = '12px';
    rmBtn.style.lineHeight = '14px';
    rmBtn.addEventListener('mousedown', function(e) {
      e.preventDefault();
      removeHighlight();
      closeHlGroup();
    });
    hlGroup.appendChild(rmBtn);

    // Wire toolbar buttons
    toolbar.addEventListener('mousedown', function(e) {
      e.preventDefault(); // keep focus in contentEditable
      var btn = e.target.closest('button[data-cmd]');
      if (!btn) return;
      var cmd = btn.getAttribute('data-cmd');
      if (cmd === 'highlight') {
        hlOpen = !hlOpen;
        hlGroup.classList.toggle('open', hlOpen);
        return;
      }
      document.execCommand(cmd, false, null);
      updateToolbarState();
    });

    // Wire font size select
    var sizeSelect = toolbar.querySelector('select[data-cmd="fontSize"]');
    sizeSelect.addEventListener('change', function(e) {
      e.preventDefault();
      var val = e.target.value;
      if (val) {
        document.execCommand('fontSize', false, val);
        // execCommand fontSize uses <font size="N"> — convert to inline style
        var fonts = activeSection ? activeSection.querySelectorAll('font[size]') : [];
        for (var i = 0; i < fonts.length; i++) {
          var f = fonts[i];
          var span = document.createElement('span');
          span.style.fontSize = f.getAttribute('size') === '1' ? '8pt' : '11pt';
          span.innerHTML = f.innerHTML;
          f.parentNode.replaceChild(span, f);
        }
      }
      updateToolbarState();
      sizeSelect.value = '';
    });

    document.body.appendChild(toolbar);
    return toolbar;
  }

  function applyHighlight(color) {
    // Use hiliteColor (non-IE) or backColor
    document.execCommand('hiliteColor', false, color);
    updateToolbarState();
  }

  function removeHighlight() {
    document.execCommand('hiliteColor', false, 'transparent');
    updateToolbarState();
  }

  function closeHlGroup() {
    hlOpen = false;
    var g = document.getElementById('bfa-hl-group');
    if (g) g.classList.remove('open');
  }

  function positionToolbar(sectionEl) {
    if (!toolbar) return;
    var rect = sectionEl.getBoundingClientRect();
    toolbar.style.top = (rect.top + window.scrollY - toolbar.offsetHeight - 6) + 'px';
    toolbar.style.left = rect.left + 'px';
  }

  function updateToolbarState() {
    if (!toolbar) return;
    var cmds = ['bold', 'italic', 'strikeThrough', 'insertUnorderedList'];
    cmds.forEach(function(cmd) {
      var btn = toolbar.querySelector('button[data-cmd="' + cmd + '"]');
      if (btn) {
        btn.classList.toggle('active', document.queryCommandState(cmd));
      }
    });
  }

  function showToolbar(sectionEl) {
    activeSection = sectionEl;
    createToolbar();
    toolbar.style.display = 'flex';
    // Position after a frame so the element dimensions are settled
    requestAnimationFrame(function() { positionToolbar(sectionEl); });
  }

  function hideToolbar() {
    if (toolbar) {
      toolbar.style.display = 'none';
      closeHlGroup();
    }
    activeSection = null;
  }

  // Selection change → update button states
  document.addEventListener('selectionchange', function() {
    if (activeSection) updateToolbarState();
  });

  // Expose to parent
  window.__bfaEditor = {
    showToolbar: showToolbar,
    hideToolbar: hideToolbar,
    positionToolbar: positionToolbar,
  };
})();
`;function se({uid:o,fetchUrl:i,onSaveSection:r,title:m}){const N=a.useRef(null),[E,k]=a.useState(80),[d,j]=a.useState(!0),[p,V]=a.useState(!1),[u,v]=a.useState(null),[f,x]=a.useState(null),[D,S]=a.useState(!1),T=a.useRef(""),P=a.useCallback(()=>{j(!0),V(!1),fetch(i).then(n=>{if(!n.ok)throw new Error(`${n.status}`);return n.text()}).then(n=>{v(n),j(!1)}).catch(()=>{V(!0),j(!1)})},[i]);a.useEffect(()=>{P()},[P]);const l=a.useCallback(()=>{const n=N.current;if(n)try{const h=n.contentDocument;h?.body&&requestAnimationFrame(()=>{const c=h.body.scrollHeight;c>0&&k(c+8)})}catch{}},[]),s=a.useCallback(()=>{l();const n=N.current?.contentDocument;if(!n)return;const h=n.createElement("style");h.textContent=qe,n.head.appendChild(h);const c=n.createElement("script");c.textContent=Ye,n.body.appendChild(c),n.body.addEventListener("click",U=>{const w=U.target.closest("[data-section]");if(!w)return;const M=w.dataset.section;M&&window.postMessage({type:"bfa-edit-section",uid:o,section:M},"*")})},[o,l]);a.useEffect(()=>{const n=h=>{if(h.data?.type==="bfa-edit-section"&&h.data.uid===o){const c=h.data.section;if(f===c)return;g(c)}};return window.addEventListener("message",n),()=>window.removeEventListener("message",n)});const g=a.useCallback(n=>{const h=N.current?.contentDocument;if(!h)return;const c=N.current?.contentWindow;if(f){const w=h.querySelector(`[data-section="${f}"]`);w&&(w.contentEditable="false",w.classList.remove("editing"),w.innerHTML=T.current),c?.__bfaEditor?.hideToolbar()}const U=h.querySelector(`[data-section="${n}"]`);U&&(T.current=U.innerHTML,U.contentEditable="true",U.classList.add("editing"),U.focus(),x(n),c?.__bfaEditor?.showToolbar(U),requestAnimationFrame(l))},[f,l]),F=a.useCallback(()=>{const n=N.current?.contentDocument,h=N.current?.contentWindow;if(!n||!f)return;const c=n.querySelector(`[data-section="${f}"]`);c&&(c.contentEditable="false",c.classList.remove("editing"),c.innerHTML=T.current),h?.__bfaEditor?.hideToolbar(),x(null)},[f]),H=a.useCallback(async()=>{const n=N.current?.contentDocument,h=N.current?.contentWindow;if(!n||!f)return;const c=n.querySelector(`[data-section="${f}"]`);if(c){S(!0);try{await r(f,c.innerHTML),c.contentEditable="false",c.classList.remove("editing"),h?.__bfaEditor?.hideToolbar(),x(null),P()}catch{}finally{S(!1)}}},[f,r,P]);return d?e.jsxDEV("div",{style:{padding:"4px 40px 12px",fontSize:"12px",color:"var(--fg-secondary)",fontFamily:"var(--font-sans)"},children:"Loading..."},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/IframeCompositionView.tsx",lineNumber:429,columnNumber:7},this):p||!u?e.jsxDEV("div",{style:{padding:"4px 40px 12px",fontSize:"12px",color:"var(--color-error)",fontFamily:"var(--font-sans)"},children:"Failed to load HTML"},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/IframeCompositionView.tsx",lineNumber:437,columnNumber:7},this):e.jsxDEV("div",{style:{padding:"2px 12px 8px 40px"},children:[f&&e.jsxDEV("div",{style:{display:"flex",alignItems:"center",gap:6,marginBottom:4,fontFamily:"var(--font-sans)"},children:[e.jsxDEV("span",{style:{fontSize:"11px",color:"var(--fg-secondary)"},children:["Editing: ",e.jsxDEV("b",{children:f},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/IframeCompositionView.tsx",lineNumber:448,columnNumber:22},this)]},void 0,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/IframeCompositionView.tsx",lineNumber:447,columnNumber:11},this),e.jsxDEV("button",{className:"btn btn-sm btn-primary",onClick:H,disabled:D,style:{fontSize:"11px",padding:"2px 8px",gap:3,display:"flex",alignItems:"center"},children:[e.jsxDEV(ae,{size:11},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/IframeCompositionView.tsx",lineNumber:456,columnNumber:13},this)," ",D?"Saving...":"Save"]},void 0,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/IframeCompositionView.tsx",lineNumber:450,columnNumber:11},this),e.jsxDEV("button",{className:"btn btn-sm",onClick:F,disabled:D,style:{fontSize:"11px",padding:"2px 8px",gap:3,display:"flex",alignItems:"center"},children:[e.jsxDEV(te,{size:11},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/IframeCompositionView.tsx",lineNumber:464,columnNumber:13},this)," Cancel"]},void 0,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/IframeCompositionView.tsx",lineNumber:458,columnNumber:11},this)]},void 0,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/IframeCompositionView.tsx",lineNumber:446,columnNumber:9},this),e.jsxDEV("iframe",{ref:N,srcDoc:u,onLoad:s,style:{width:"100%",height:`${E}px`,border:"none",display:"block",background:"#fff"},title:m||o},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/IframeCompositionView.tsx",lineNumber:468,columnNumber:7},this)]},void 0,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/IframeCompositionView.tsx",lineNumber:444,columnNumber:5},this)}function Ke({uid:o}){return e.jsxDEV(se,{uid:o,fetchUrl:`/api/bfa-todo/preambles/${o}/html`,onSaveSection:(i,r)=>y.bfaTodo.updatePreambleSection(o,i,r),title:`Preamble ${o}`},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/PreambleSection.tsx",lineNumber:16,columnNumber:5},this)}function Qe({preambles:o,preambleExpanded:i,onTogglePreambleExpanded:r}){return o.length===0?null:e.jsxDEV("div",{style:{border:"1px solid var(--border)"},children:[e.jsxDEV("div",{className:"flex items-center gap-2 px-3 py-1.5",style:{borderBottom:"1px solid var(--border)",background:"var(--bg-surface)",fontFamily:"var(--font-sans)",fontSize:"11px",color:"var(--fg-secondary)"},children:e.jsxDEV("span",{style:{fontWeight:600,textTransform:"uppercase",letterSpacing:"0.04em"},children:"Preamble"},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/PreambleSection.tsx",lineNumber:31,columnNumber:9},this)},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/PreambleSection.tsx",lineNumber:30,columnNumber:7},this),o.map(m=>e.jsxDEV("div",{style:{borderBottom:"1px solid var(--border)"},children:[e.jsxDEV("div",{className:"flex items-center gap-2",style:{padding:"6px 12px",cursor:"pointer",fontFamily:"var(--font-sans)"},onClick:()=>r(m.uid),children:[e.jsxDEV(oe,{size:14,className:ee("transition-transform shrink-0",i.has(m.uid)&&"rotate-90"),style:{color:"var(--fg-secondary)"}},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/PreambleSection.tsx",lineNumber:42,columnNumber:13},this),e.jsxDEV("span",{style:{fontSize:"13px",fontWeight:600,color:"var(--fg)"},children:m.title},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/PreambleSection.tsx",lineNumber:47,columnNumber:13},this),e.jsxDEV(z,{variant:"neutral",size:"xs",children:m.type==="preamble"?"overview":"lists"},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/PreambleSection.tsx",lineNumber:50,columnNumber:13},this)]},void 0,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/PreambleSection.tsx",lineNumber:37,columnNumber:11},this),i.has(m.uid)&&e.jsxDEV(Ke,{uid:m.uid},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/PreambleSection.tsx",lineNumber:53,columnNumber:13},this)]},m.uid,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/PreambleSection.tsx",lineNumber:36,columnNumber:9},this))]},void 0,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/PreambleSection.tsx",lineNumber:29,columnNumber:5},this)}function Je({uid:o,onProjectUpdated:i}){return e.jsxDEV(se,{uid:o,fetchUrl:`/api/bfa-todo/projects/${o}/html`,onSaveSection:async(r,m)=>{await y.bfaTodo.updateSection(o,r,m),i()},title:`Project ${o}`},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/ProjectRow.tsx",lineNumber:21,columnNumber:5},this)}function Xe({project:o,isExpanded:i,isSelected:r,memberMap:m,onToggleExpand:N,onToggleSelect:E,onProjectUpdated:k}){m[o.owner_team]||o.owner_team;const[d,j]=a.useState(!1),[p,V]=a.useState(!1),[u,v]=a.useState({client:o.client,project_name:o.project_name,city:o.city,phase:o.phase,owner_team:o.owner_team}),f=o.validation&&(o.validation.error_count>0||o.validation.warning_count>0),x=o.validation&&o.validation.error_count>0,D=o.validation?.items.filter(s=>s.suggestion)??[],S=s=>{s.stopPropagation(),v({client:o.client,project_name:o.project_name,city:o.city,phase:o.phase,owner_team:o.owner_team}),j(!0)},T=()=>j(!1),P=async()=>{V(!0);try{const s={};u.client!==o.client&&(s.client=u.client),u.project_name!==o.project_name&&(s.project_name=u.project_name),u.city!==o.city&&(s.city=u.city),u.phase!==o.phase&&(s.phase=u.phase),u.owner_team!==o.owner_team&&(s.owner_team=u.owner_team),Object.keys(s).length>0&&(await y.bfaTodo.updateProject(o.uid,s),k()),j(!1)}catch{}finally{V(!1)}},l=(s,g)=>{v(F=>({...F,[s]:g}))};return d?e.jsxDEV("div",{style:{borderBottom:"1px solid var(--border)",background:"rgba(63, 92, 110, 0.06)",fontFamily:"var(--font-sans)"},children:e.jsxDEV("div",{style:{padding:"8px 12px",display:"flex",flexDirection:"column",gap:6},children:[e.jsxDEV("div",{className:"flex items-center gap-2",children:[e.jsxDEV("input",{type:"text",className:"setting-input",value:u.client,onChange:s=>v(g=>({...g,client:s.target.value})),placeholder:"Client",style:{fontSize:"12px",width:"180px",fontWeight:600}},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/ProjectRow.tsx",lineNumber:95,columnNumber:13},this),e.jsxDEV("span",{style:{color:"var(--fg-secondary)",fontSize:"13px"},children:"—"},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/ProjectRow.tsx",lineNumber:103,columnNumber:13},this),e.jsxDEV("input",{type:"text",className:"setting-input",value:u.project_name,onChange:s=>v(g=>({...g,project_name:s.target.value})),placeholder:"Project name",style:{fontSize:"12px",flex:1,fontWeight:600}},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/ProjectRow.tsx",lineNumber:104,columnNumber:13},this)]},void 0,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/ProjectRow.tsx",lineNumber:94,columnNumber:11},this),e.jsxDEV("div",{className:"flex items-center gap-2",children:[e.jsxDEV("input",{type:"text",className:"setting-input",value:u.city,onChange:s=>v(g=>({...g,city:s.target.value})),placeholder:"City",style:{fontSize:"12px",width:"140px"}},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/ProjectRow.tsx",lineNumber:114,columnNumber:13},this),e.jsxDEV("input",{type:"text",className:"setting-input",value:u.phase,onChange:s=>v(g=>({...g,phase:s.target.value})),placeholder:"Phase",style:{fontSize:"12px",width:"140px"}},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/ProjectRow.tsx",lineNumber:122,columnNumber:13},this),e.jsxDEV("input",{type:"text",className:"setting-input",value:u.owner_team,onChange:s=>v(g=>({...g,owner_team:s.target.value})),placeholder:"Team",style:{fontSize:"12px",width:"80px"}},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/ProjectRow.tsx",lineNumber:130,columnNumber:13},this),e.jsxDEV("div",{style:{flex:1}},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/ProjectRow.tsx",lineNumber:138,columnNumber:13},this),e.jsxDEV("button",{className:"btn btn-sm btn-primary",onClick:P,disabled:p,style:{fontSize:"11px",padding:"2px 8px",gap:3,display:"flex",alignItems:"center"},children:[e.jsxDEV(ae,{size:11},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/ProjectRow.tsx",lineNumber:140,columnNumber:15},this)," ",p?"Saving...":"Save"]},void 0,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/ProjectRow.tsx",lineNumber:139,columnNumber:13},this),e.jsxDEV("button",{className:"btn btn-sm",onClick:T,disabled:p,style:{fontSize:"11px",padding:"2px 8px",gap:3,display:"flex",alignItems:"center"},children:[e.jsxDEV(te,{size:11},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/ProjectRow.tsx",lineNumber:143,columnNumber:15},this)," Cancel"]},void 0,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/ProjectRow.tsx",lineNumber:142,columnNumber:13},this)]},void 0,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/ProjectRow.tsx",lineNumber:113,columnNumber:11},this),D.length>0&&e.jsxDEV("div",{className:"flex flex-wrap items-center gap-2",style:{fontSize:"11px"},children:D.map((s,g)=>e.jsxDEV("button",{className:"btn btn-sm",onClick:()=>l(s.field,s.suggestion),style:{fontSize:"11px",padding:"1px 6px",gap:3,display:"flex",alignItems:"center",color:"var(--color-warning, #b45309)"},children:[e.jsxDEV(ze,{size:10},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/ProjectRow.tsx",lineNumber:155,columnNumber:19},this)," ",s.message]},g,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/ProjectRow.tsx",lineNumber:149,columnNumber:17},this))},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/ProjectRow.tsx",lineNumber:147,columnNumber:13},this)]},void 0,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/ProjectRow.tsx",lineNumber:93,columnNumber:9},this)},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/ProjectRow.tsx",lineNumber:92,columnNumber:7},this):e.jsxDEV("div",{style:{borderBottom:"1px solid var(--border)",background:i?"rgba(63, 92, 110, 0.04)":void 0},children:[e.jsxDEV("div",{className:"flex items-center gap-2",style:{padding:"6px 12px",cursor:"pointer",fontFamily:"var(--font-sans)",opacity:o.status==="on_hold"?.55:1},onClick:N,children:[e.jsxDEV("input",{type:"checkbox",checked:r,onChange:s=>{s.stopPropagation(),E()},onClick:s=>s.stopPropagation(),style:{accentColor:"var(--accent)"}},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/ProjectRow.tsx",lineNumber:172,columnNumber:9},this),e.jsxDEV(oe,{size:14,className:ee("transition-transform shrink-0",i&&"rotate-90"),style:{color:"var(--fg-secondary)"}},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/ProjectRow.tsx",lineNumber:179,columnNumber:9},this),e.jsxDEV("span",{style:{fontSize:"13px",fontWeight:600,color:"var(--fg)",flex:1,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"},children:[o.client," — ",o.project_name]},void 0,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/ProjectRow.tsx",lineNumber:184,columnNumber:9},this),e.jsxDEV("div",{style:{display:"flex",alignItems:"center",gap:6,flexShrink:0},children:[e.jsxDEV("span",{style:{fontSize:"11px",color:"var(--fg-secondary)",minWidth:80,textAlign:"right"},children:o.city},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/ProjectRow.tsx",lineNumber:188,columnNumber:11},this),e.jsxDEV("span",{style:{width:1,height:12,background:"var(--border)"}},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/ProjectRow.tsx",lineNumber:189,columnNumber:11},this),e.jsxDEV(z,{variant:"phase",size:"xs",children:o.phase},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/ProjectRow.tsx",lineNumber:190,columnNumber:11},this),e.jsxDEV(z,{variant:"neutral",size:"xs",children:o.owner_team},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/ProjectRow.tsx",lineNumber:191,columnNumber:11},this),o.status==="on_hold"&&e.jsxDEV(z,{variant:"neutral",size:"xs",children:"ON HOLD"},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/ProjectRow.tsx",lineNumber:192,columnNumber:44},this),f?e.jsxDEV("button",{onClick:S,title:o.validation.items.map(s=>s.message).join(`
`),style:{background:"none",border:"none",cursor:"pointer",padding:0,display:"flex"},children:e.jsxDEV(Oe,{size:14,style:{color:x?"var(--color-error, #dc2626)":"var(--color-warning, #b45309)"}},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/ProjectRow.tsx",lineNumber:199,columnNumber:15},this)},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/ProjectRow.tsx",lineNumber:194,columnNumber:13},this):e.jsxDEV("button",{onClick:S,title:"Edit fields",style:{background:"none",border:"none",cursor:"pointer",padding:0,display:"flex",opacity:.3},children:e.jsxDEV(Re,{size:12,style:{color:"var(--fg-secondary)"}},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/ProjectRow.tsx",lineNumber:207,columnNumber:15},this)},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/ProjectRow.tsx",lineNumber:202,columnNumber:13},this)]},void 0,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/ProjectRow.tsx",lineNumber:187,columnNumber:9},this)]},void 0,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/ProjectRow.tsx",lineNumber:167,columnNumber:7},this),i&&e.jsxDEV(Je,{uid:o.uid,onProjectUpdated:k},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/ProjectRow.tsx",lineNumber:212,columnNumber:22},this)]},void 0,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/components/ProjectRow.tsx",lineNumber:166,columnNumber:5},this)}function Ze(o,i){const r=i.toLowerCase();return o.client.toLowerCase().includes(r)||o.project_name.toLowerCase().includes(r)||o.city.toLowerCase().includes(r)||o.phase.toLowerCase().includes(r)||o.owner_team.toLowerCase().includes(r)}function Y(o){return Array.from(new Set(o)).sort()}function et(){const[o,i]=a.useState(null),[r,m]=a.useState([]),[N,E]=a.useState(!0),[k,d]=a.useState(""),[j,p]=a.useState(!1),[V,u]=a.useState(!1),[v,f]=a.useState(!1),[x,D]=a.useState(""),[S,T]=a.useState("bfa-html"),[P,l]=a.useState("none"),[s,g]=a.useState(""),[F,H]=a.useState(!1),[n,h]=a.useState("C:/Users/Neal/dev/BFA-todo/data"),[c,U]=a.useState(!1),[w,M]=a.useState(""),[A,re]=a.useState(""),[O,le]=a.useState(""),[$,ne]=a.useState(""),[W,ie]=a.useState(!1),[G,ce]=a.useState(!1),[B,q]=a.useState(new Set),[ue,de]=a.useState(new Set),[me,pe]=a.useState([]),[fe,be]=a.useState(new Set),{status:L,refresh:he}=ke(),Ne=_e(he),[K,ge]=a.useState({}),I=a.useCallback(()=>{E(!0),Promise.all([y.bfaTodo.status().catch(()=>null),y.bfaTodo.projects().catch(()=>[]),y.bfaTodo.preambles().catch(()=>[])]).then(([t,C,b])=>{t&&i(t),m(C),pe(b),E(!1)})},[]);a.useEffect(I,[I]),a.useEffect(()=>{y.config.get().then(t=>{t.bfa_todo_doc_id&&D(String(t.bfa_todo_doc_id))}).catch(()=>{})},[]),a.useEffect(()=>{L?.clickup.configured&&y.clickup.members().then(t=>{const C={};for(const b of t)b.initials&&(C[b.initials]=b.username);ge(C)}).catch(()=>{})},[L?.clickup.configured]);const ve=a.useMemo(()=>Y(r.map(t=>t.phase).filter(Boolean)),[r]),xe=a.useMemo(()=>Y(r.map(t=>t.owner_team).filter(Boolean)),[r]),Ce=a.useMemo(()=>Y(r.map(t=>t.city).filter(Boolean)),[r]),ye=a.useMemo(()=>r.filter(t=>t.status==="on_hold").length,[r]),Ee=a.useMemo(()=>r.filter(t=>t.validation&&(t.validation.error_count>0||t.validation.warning_count>0)).length,[r]),_=a.useMemo(()=>r.filter(t=>!(!W&&t.status==="on_hold"||G&&t.validation&&t.validation.error_count===0&&t.validation.warning_count===0||w&&!Ze(t,w)||A&&t.phase!==A||O&&t.owner_team!==O||$&&t.city!==$)),[r,w,A,O,$,W,G]),je=t=>{de(C=>{const b=new Set(C);return b.has(t)?b.delete(t):b.add(t),b})},De=t=>{q(C=>{const b=new Set(C);return b.has(t)?b.delete(t):b.add(t),b})},Se=t=>{be(C=>{const b=new Set(C);return b.has(t)?b.delete(t):b.add(t),b})},we=()=>{B.size===_.length?q(new Set):q(new Set(_.map(t=>t.uid)))},Ve=async()=>{u(!0),d("");try{const t=await y.bfaTodo.render();t.error?(d(t.error),p(!0)):(d(`Rendered ${t.project_count} projects`),p(!1),I())}catch(t){d(t.message??"Render failed"),p(!0)}u(!1)},Q=async()=>{if(!(!x.trim()||B.size===0)){f(!0),d(""),y.config.save({bfa_todo_doc_id:x.trim()}).catch(()=>{});try{const t=await y.bfaTodo.deploySelected(x.trim(),Array.from(B));t.error?(d(t.error),p(!0)):(d(`Deployed ${t.deployed} projects (${t.errors} errors)`),p(t.errors>0))}catch(t){d(t.message??"Deploy failed"),p(!0)}f(!1)}},J=async()=>{if(s.trim()){H(!0),d("");try{const t=await y.bfaTodo.importExcel(s.trim());t.error?(d(t.error),p(!0)):(d(`Imported ${t.project_count??""} projects from Excel`),p(!1),I())}catch(t){d(t.message??"Excel import failed"),p(!0)}H(!1)}},X=async()=>{if(n.trim()){U(!0),d("");try{const t=await y.bfaTodo.importHtml(n.trim());t.error?(d(t.error),p(!0)):(d(`Imported ${t.project_count} projects from HTML source`),p(!1),I())}catch(t){d(t.message??"HTML import failed"),p(!0)}U(!1)}};return e.jsxDEV(Te,{module:"bfa-todo",activePage:"overview",children:e.jsxDEV("div",{className:"flex flex-col gap-3",style:{height:"calc(100vh - 48px)"},children:N?e.jsxDEV("p",{className:"text-sm text-ws-text-secondary py-8 text-center",children:"Loading..."},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:196,columnNumber:11},this):e.jsxDEV(e.Fragment,{children:[e.jsxDEV(Fe,{module:"bfa-todo",status:L},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:199,columnNumber:13},this),e.jsxDEV("div",{className:"endpoint-bar",children:[e.jsxDEV("span",{className:"endpoint-label",children:"Source"},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:203,columnNumber:15},this),e.jsxDEV("select",{className:"endpoint-select",value:S,onChange:t=>T(t.target.value),children:[e.jsxDEV("option",{value:"bfa-html",children:"BFA HTML"},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:205,columnNumber:17},this),e.jsxDEV("option",{value:"monday-excel",children:"Monday Excel"},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:206,columnNumber:17},this),e.jsxDEV("option",{value:"clickup",disabled:!0,children:"ClickUp (coming soon)"},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:207,columnNumber:17},this)]},void 0,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:204,columnNumber:15},this),S==="bfa-html"&&e.jsxDEV(e.Fragment,{children:[e.jsxDEV("input",{type:"text",className:"endpoint-input",value:n,onChange:t=>h(t.target.value),placeholder:"Path to BFA HTML data directory...",onKeyDown:t=>{t.key==="Enter"&&X()}},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:211,columnNumber:19},this),e.jsxDEV("button",{className:"btn btn-sm btn-primary",onClick:X,disabled:c||!n.trim(),children:c?"Importing...":"Re-import"},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:212,columnNumber:19},this)]},void 0,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:210,columnNumber:17},this),S==="monday-excel"&&e.jsxDEV(e.Fragment,{children:[e.jsxDEV("input",{type:"text",className:"endpoint-input",value:s,onChange:t=>g(t.target.value),placeholder:"Path to Monday .xlsx export...",onKeyDown:t=>{t.key==="Enter"&&J()}},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:219,columnNumber:19},this),e.jsxDEV("button",{className:"btn btn-sm btn-primary",onClick:J,disabled:F||!s.trim(),children:F?"Importing...":"Import"},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:220,columnNumber:19},this)]},void 0,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:218,columnNumber:17},this)]},void 0,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:202,columnNumber:13},this),e.jsxDEV(Ge,{searchQuery:w,onSearchChange:M,filterPhase:A,onPhaseChange:re,filterLead:O,onLeadChange:le,filterCity:$,onCityChange:ne,showOnHold:W,onShowOnHoldChange:ie,showIssuesOnly:G,onShowIssuesOnlyChange:ce,phases:ve,leads:xe,cities:Ce,onHoldCount:ye,issueCount:Ee,memberMap:K},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:227,columnNumber:13},this),o&&e.jsxDEV("div",{className:"flex items-center gap-4 text-xs",style:{color:"var(--fg-secondary)",fontFamily:"var(--font-sans)"},children:[e.jsxDEV("span",{children:[o.project_count," projects total"]},void 0,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:242,columnNumber:17},this),o.last_render&&e.jsxDEV("span",{children:["Last render: ",new Date(o.last_render).toLocaleString()]},void 0,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:243,columnNumber:40},this),e.jsxDEV("div",{className:"flex gap-1.5",children:[o.has_html&&e.jsxDEV(z,{variant:"success",size:"xs",children:"HTML"},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:245,columnNumber:39},this),o.has_json&&e.jsxDEV(z,{variant:"success",size:"xs",children:"JSON"},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:246,columnNumber:39},this),o.has_gdocs&&e.jsxDEV(z,{variant:"success",size:"xs",children:"GDocs"},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:247,columnNumber:40},this)]},void 0,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:244,columnNumber:17},this)]},void 0,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:241,columnNumber:15},this),e.jsxDEV(Qe,{preambles:me,preambleExpanded:fe,onTogglePreambleExpanded:Se},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:252,columnNumber:13},this),e.jsxDEV("div",{className:"flex-1 overflow-y-auto",style:{border:"1px solid var(--border)"},children:[e.jsxDEV("div",{className:"flex items-center gap-2 px-3 py-1.5",style:{borderBottom:"1px solid var(--border)",background:"var(--bg-surface)",fontFamily:"var(--font-sans)",fontSize:"11px",color:"var(--fg-secondary)"},children:[e.jsxDEV("input",{type:"checkbox",checked:_.length>0&&B.size===_.length,onChange:we,style:{accentColor:"var(--accent)"}},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:261,columnNumber:17},this),e.jsxDEV("span",{style:{fontWeight:600,textTransform:"uppercase",letterSpacing:"0.04em"},children:[_.length," projects",B.size>0&&` · ${B.size} selected`]},void 0,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:262,columnNumber:17},this)]},void 0,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:260,columnNumber:15},this),_.length===0?e.jsxDEV("p",{className:"not-configured",style:{padding:"24px",textAlign:"center"},children:"No projects match filters"},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:268,columnNumber:17},this):_.map(t=>e.jsxDEV(Xe,{project:t,isExpanded:ue.has(t.uid),isSelected:B.has(t.uid),memberMap:K,onToggleExpand:()=>je(t.uid),onToggleSelect:()=>De(t.uid),onProjectUpdated:I},t.uid,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:271,columnNumber:19},this))]},void 0,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:259,columnNumber:13},this),e.jsxDEV("div",{className:"endpoint-bar",children:[e.jsxDEV("button",{className:"btn btn-sm",onClick:Ve,disabled:V,children:[e.jsxDEV(Le,{size:12},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:288,columnNumber:17},this),V?"Rendering...":"Render All"]},void 0,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:287,columnNumber:15},this),e.jsxDEV("span",{className:"endpoint-divider"},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:292,columnNumber:15},this),e.jsxDEV("span",{className:"endpoint-label",children:"Target"},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:294,columnNumber:15},this),e.jsxDEV("select",{className:"endpoint-select",value:P,onChange:t=>l(t.target.value),children:[e.jsxDEV("option",{value:"none",children:"None (local only)"},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:296,columnNumber:17},this),e.jsxDEV("option",{value:"google-docs",children:"Google Docs"},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:297,columnNumber:17},this),e.jsxDEV("option",{value:"clickup",disabled:!0,children:"ClickUp (coming soon)"},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:298,columnNumber:17},this)]},void 0,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:295,columnNumber:15},this),P==="google-docs"&&(()=>{const t=Ie("google",L);return e.jsxDEV(e.Fragment,{children:[e.jsxDEV("span",{className:"endpoint-status",children:t.summary},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:305,columnNumber:21},this),!t.healthy&&L?.google.oauth_available&&e.jsxDEV("button",{className:"btn btn-sm btn-primary",onClick:()=>Ne.connect("Google",y.google.auth,"google-oauth"),children:"Connect"},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:307,columnNumber:23},this),t.healthy&&e.jsxDEV(e.Fragment,{children:[e.jsxDEV("input",{type:"text",className:"endpoint-input",value:x,onChange:C=>D(C.target.value),placeholder:"Doc ID",style:{width:"200px",borderColor:x.trim()?void 0:"var(--color-warning)"},onKeyDown:C=>{C.key==="Enter"&&Q()}},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:313,columnNumber:25},this),e.jsxDEV("button",{className:"btn btn-sm btn-primary",onClick:Q,disabled:v||!x.trim()||B.size===0,children:[e.jsxDEV(He,{size:12},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:315,columnNumber:27},this),v?"Deploying...":`Deploy (${B.size})`]},void 0,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:314,columnNumber:25},this)]},void 0,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:312,columnNumber:23},this)]},void 0,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:304,columnNumber:19},this)})(),e.jsxDEV(Be,{message:k,isError:j},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:324,columnNumber:15},this)]},void 0,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:286,columnNumber:13},this)]},void 0,!0,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:198,columnNumber:11},this)},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:194,columnNumber:7},this)},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/pages/bfa-todo/BfaTodoPage.tsx",lineNumber:193,columnNumber:5},this)}Pe.createRoot(document.getElementById("app")).render(e.jsxDEV(et,{},void 0,!1,{fileName:"C:/Users/Neal/dev/autohelper/ui/src/entries/bfa-todo.tsx",lineNumber:5,columnNumber:52},void 0));
