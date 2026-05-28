import { useCallback, useEffect, useRef, useState } from "react";
import {
  PdfLoader,
  PdfHighlighter,
  Highlight,
  Popup,
  AreaHighlight,
} from "react-pdf-highlighter";
import type { IHighlight, ScaledPosition, Content } from "react-pdf-highlighter";
import { sendMessage, onMessage, sendPageChanged } from "./bridge";
import { HIGHLIGHT_COLORS } from "./types";
import type { HighlightColor, AnnotationType, TranslationEntry } from "./types";

import "react-pdf-highlighter/dist/style.css";
import "./style.css";

const params = new URLSearchParams(window.location.search);
const fileUrl = params.get("file") || "";

// In Reflex dev mode, frontend (3000) and backend (8000) run on different ports.
// The parent page can pass ?backend=<origin> to specify the API origin.
// Otherwise, default dev port mapping: 3000 -> 8000; production: same origin.
function resolveBackendOrigin(): string {
  const explicit = params.get("backend");
  if (explicit) return explicit;
  const { protocol, hostname, port } = window.location;
  if (port === "3000") return `${protocol}//${hostname}:8000`;
  return window.location.origin;
}
const backendOrigin = resolveBackendOrigin();

function getBackendUrl(url: string): string {
  if (url.startsWith("/api/")) {
    return backendOrigin + url;
  }
  return url;
}

const PRIMARY_PDF_URL = getBackendUrl(fileUrl);
let idCounter = 0;
const genId = () => `hl-${Date.now()}-${++idCounter}`;
const FLOAT_TRANS_POS_KEY = "paper-assistant.translationFloatPosition";
const FLOAT_TRANS_MARGIN = 12;
const FLOAT_TRANS_DEFAULT_SIZE = { width: 360, height: 180 };

type FloatPosition = { x: number; y: number };

function clampFloatPosition(pos: FloatPosition, size = FLOAT_TRANS_DEFAULT_SIZE): FloatPosition {
  const maxX = Math.max(FLOAT_TRANS_MARGIN, window.innerWidth - size.width - FLOAT_TRANS_MARGIN);
  const maxY = Math.max(FLOAT_TRANS_MARGIN, window.innerHeight - size.height - FLOAT_TRANS_MARGIN);
  return {
    x: Math.min(Math.max(FLOAT_TRANS_MARGIN, pos.x), maxX),
    y: Math.min(Math.max(FLOAT_TRANS_MARGIN, pos.y), maxY),
  };
}

function readFloatPosition(): FloatPosition {
  const fallback = {
    x: window.innerWidth / 2 - FLOAT_TRANS_DEFAULT_SIZE.width / 2,
    y: 200,
  };
  try {
    const saved = window.localStorage.getItem(FLOAT_TRANS_POS_KEY);
    if (!saved) return clampFloatPosition(fallback);
    const parsed = JSON.parse(saved) as Partial<FloatPosition>;
    if (typeof parsed.x !== "number" || typeof parsed.y !== "number") {
      return clampFloatPosition(fallback);
    }
    return clampFloatPosition({ x: parsed.x, y: parsed.y });
  } catch {
    return clampFloatPosition(fallback);
  }
}

function writeFloatPosition(pos: FloatPosition) {
  try {
    window.localStorage.setItem(FLOAT_TRANS_POS_KEY, JSON.stringify(pos));
  } catch {
    // The position memory is a convenience; private storage failures should not block dragging.
  }
}

function hexToRgb(hex: string): string {
  if (hex === "transparent") return "0,0,0";
  const h = hex.replace("#", "");
  return `${parseInt(h.substring(0, 2), 16)},${parseInt(h.substring(2, 4), 16)},${parseInt(h.substring(4, 6), 16)}`;
}

function mergeSelectionRects(position: ScaledPosition): ScaledPosition {
  const rects = ((position as any).rects || []) as any[];
  if (rects.length <= 1) return position;

  const normalized = rects
    .map((rect) => ({
      ...rect,
      x1: Math.min(Number(rect.x1), Number(rect.x2)),
      y1: Math.min(Number(rect.y1), Number(rect.y2)),
      x2: Math.max(Number(rect.x1), Number(rect.x2)),
      y2: Math.max(Number(rect.y1), Number(rect.y2)),
      pageNumber: Number(rect.pageNumber || (position as any).pageNumber || 1),
    }))
    .filter((rect) =>
      Number.isFinite(rect.x1) &&
      Number.isFinite(rect.y1) &&
      Number.isFinite(rect.x2) &&
      Number.isFinite(rect.y2)
    )
    .sort((a, b) =>
      a.pageNumber - b.pageNumber ||
      (a.y1 + a.y2) / 2 - (b.y1 + b.y2) / 2 ||
      a.x1 - b.x1
    );

  const groups: any[][] = [];
  for (const rect of normalized) {
    const centerY = (rect.y1 + rect.y2) / 2;
    const height = Math.max(rect.y2 - rect.y1, 0.0001);
    const verticalOverlap = (a: any, b: any) => Math.min(a.y2, b.y2) - Math.max(a.y1, b.y1);
    const group = groups.find((items) => {
      if (items[0].pageNumber !== rect.pageNumber) return false;
      const groupCenter = items.reduce((sum, item) => sum + (item.y1 + item.y2) / 2, 0) / items.length;
      const groupHeight = Math.max(...items.map((item) => item.y2 - item.y1), 0.0001);
      const groupBox = {
        y1: Math.min(...items.map((item) => item.y1)),
        y2: Math.max(...items.map((item) => item.y2)),
      };
      const overlap = verticalOverlap(rect, groupBox);
      return (
        Math.abs(centerY - groupCenter) <= Math.max(height, groupHeight) * 0.85 ||
        overlap >= Math.min(height, groupHeight) * 0.35
      );
    });
    if (group) group.push(rect);
    else groups.push([rect]);
  }

  const mergedRects: any[] = [];
  for (const group of groups) {
    group.sort((a, b) => a.x1 - b.x1);
    const lineHeight = Math.max(...group.map((rect) => rect.y2 - rect.y1), 0.0001);
    const pageWidth = Math.max(...group.map((rect) => Number(rect.width) || 0), 0);
    const maxGap = Math.max(lineHeight * 2.5, pageWidth ? pageWidth * 0.018 : 0);
    let current = { ...group[0] };

    for (const rect of group.slice(1)) {
      const gap = rect.x1 - current.x2;
      const rectWidth = Math.max(rect.x2 - rect.x1, 0);
      const currentWidth = Math.max(current.x2 - current.x1, 0);
      const looksLikeDetachedPunctuation =
        rectWidth <= lineHeight * 0.95 ||
        currentWidth <= lineHeight * 0.95;
      const punctuationGap = Math.max(maxGap, lineHeight * 4, pageWidth ? pageWidth * 0.035 : 0);
      if (gap <= maxGap || (looksLikeDetachedPunctuation && gap <= punctuationGap)) {
        current = {
          ...current,
          x1: Math.min(current.x1, rect.x1),
          y1: Math.min(current.y1, rect.y1),
          x2: Math.max(current.x2, rect.x2),
          y2: Math.max(current.y2, rect.y2),
          width: current.width || rect.width,
          height: current.height || rect.height,
        };
      } else {
        mergedRects.push(current);
        current = { ...rect };
      }
    }
    mergedRects.push(current);
  }

  const boundingSource = mergedRects.filter((rect) => rect.pageNumber === (position as any).pageNumber);
  const boundingRects = boundingSource.length ? boundingSource : mergedRects;
  const boundingRect = {
    ...(position as any).boundingRect,
    x1: Math.min(...boundingRects.map((rect) => rect.x1)),
    y1: Math.min(...boundingRects.map((rect) => rect.y1)),
    x2: Math.max(...boundingRects.map((rect) => rect.x2)),
    y2: Math.max(...boundingRects.map((rect) => rect.y2)),
    width: boundingRects[0]?.width || (position as any).boundingRect?.width,
    height: boundingRects[0]?.height || (position as any).boundingRect?.height,
    pageNumber: (position as any).pageNumber || boundingRects[0]?.pageNumber,
  };

  return {
    ...(position as any),
    rects: mergedRects,
    boundingRect,
  } as ScaledPosition;
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function renderInlineMarkdown(value: string): string {
  let html = escapeHtml(value);
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/\$([^$\n]+)\$/g, '<span class="math-inline">$1</span>');
  return html;
}

function markdownToHtml(markdown: string): string {
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  const blocks: string[] = [];
  let paragraph: string[] = [];
  let listItems: string[] = [];
  let ordered = false;

  const flushParagraph = () => {
    if (!paragraph.length) return;
    blocks.push(`<p>${renderInlineMarkdown(paragraph.join(" "))}</p>`);
    paragraph = [];
  };

  const flushList = () => {
    if (!listItems.length) return;
    const tag = ordered ? "ol" : "ul";
    blocks.push(`<${tag}>${listItems.join("")}</${tag}>`);
    listItems = [];
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      flushParagraph();
      flushList();
      continue;
    }
    if (/^[-*_]{3,}$/.test(line)) {
      flushParagraph();
      flushList();
      blocks.push("<hr />");
      continue;
    }
    const heading = /^(#{1,4})\s+(.+)$/.exec(line);
    if (heading) {
      flushParagraph();
      flushList();
      const level = Math.min(heading[1].length, 4);
      blocks.push(`<h${level}>${renderInlineMarkdown(heading[2])}</h${level}>`);
      continue;
    }
    const unorderedItem = /^[-*]\s+(.+)$/.exec(line);
    const orderedItem = /^\d+[.)]\s+(.+)$/.exec(line);
    if (unorderedItem || orderedItem) {
      flushParagraph();
      const isOrdered = Boolean(orderedItem);
      if (listItems.length && ordered !== isOrdered) flushList();
      ordered = isOrdered;
      const text = unorderedItem ? unorderedItem[1] : orderedItem![1];
      listItems.push(`<li>${renderInlineMarkdown(text)}</li>`);
      continue;
    }
    flushList();
    paragraph.push(line);
  }

  flushParagraph();
  flushList();
  return blocks.join("");
}

function MarkdownResult({ text }: { text: string }) {
  return (
    <div
      className="translation-float-result markdown-result"
      dangerouslySetInnerHTML={{ __html: markdownToHtml(text) }}
    />
  );
}

// ─── Floating Selection Toolbar (WPS-style) ────────────────────────

function SelectionToolbar({
  position,
  onClose,
  onHighlight,
  onUnderline,
  onStrikethrough,
  onTranslate,
  onAnnotate,
  onCopy,
  onExplain,
}: {
  position: { x: number; y: number; above: boolean };
  onClose: () => void;
  onHighlight: (color: HighlightColor) => void;
  onUnderline: (color: HighlightColor) => void;
  onStrikethrough: () => void;
  onTranslate: () => void;
  onAnnotate: () => void;
  onCopy: () => void;
  onExplain: () => void;
}) {
  const [expandColor, setExpandColor] = useState<"highlight" | "underline" | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click (use ref to avoid stale closure)
  const onCloseRef = useRef(onClose);
  useEffect(() => { onCloseRef.current = onClose; });
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onCloseRef.current();
      }
    };
    const timer = setTimeout(() => document.addEventListener("mousedown", handler), 50);
    return () => { clearTimeout(timer); document.removeEventListener("mousedown", handler); };
  }, []);

  const positionStyle: React.CSSProperties = position.above
    ? { left: position.x, bottom: window.innerHeight - position.y, transform: "translateX(-50%)" }
    : { left: position.x, top: position.y, transform: "translateX(-50%)" };

  return (
    <div ref={ref} className="selection-toolbar" style={positionStyle}>
      {/* Section A: Basic Annotation */}
      <button className="stb-btn" title="复制" onClick={() => { onCopy(); onClose(); }}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
        </svg>
      </button>

      <div className="stb-sep" />

      {/* Highlight: click = yellow, ▾ = pick color */}
      <div className="stb-split">
        <button className="stb-btn stb-highlight-btn" title="高亮（黄色）"
          onClick={() => { onHighlight(HIGHLIGHT_COLORS[0]); onClose(); }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#eab308" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>
          </svg>
        </button>
        <button className="stb-arrow"
          onClick={(e) => { e.stopPropagation(); setExpandColor(expandColor === "highlight" ? null : "highlight"); }}>
          ▾
        </button>
        {expandColor === "highlight" && (
          <div className="stb-color-row" onMouseDown={(e) => e.stopPropagation()}>
            {HIGHLIGHT_COLORS.map((c) => (
              <button
                key={c.name}
                className="stb-color-dot"
                title={c.name}
                style={{
                  background: c.hex === "transparent" ? "#fff" : c.hex,
                  border: c.hex === "transparent" ? "2px dashed #999" : "2px solid transparent",
                }}
                onClick={(e) => { e.stopPropagation(); onHighlight(c); onClose(); }}
              />
            ))}
          </div>
        )}
      </div>

      {/* Underline: click = yellow underline, ▾ = pick color */}
      <div className="stb-split">
        <button className="stb-btn stb-underline-btn" title="下划线"
          onClick={() => { onUnderline(HIGHLIGHT_COLORS[0]); onClose(); }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M6 4v6a6 6 0 0 0 12 0V4"/><line x1="4" y1="20" x2="20" y2="20"/>
          </svg>
        </button>
        <button className="stb-arrow"
          onClick={(e) => { e.stopPropagation(); setExpandColor(expandColor === "underline" ? null : "underline"); }}>
          ▾
        </button>
        {expandColor === "underline" && (
          <div className="stb-color-row" onMouseDown={(e) => e.stopPropagation()}>
            {HIGHLIGHT_COLORS.map((c) => (
              <button
                key={c.name}
                className="stb-color-dot"
                title={c.name}
                style={{
                  background: c.hex === "transparent" ? "#fff" : c.hex,
                  border: c.hex === "transparent" ? "2px dashed #999" : "2px solid transparent",
                }}
                onClick={(e) => { e.stopPropagation(); onUnderline(c); onClose(); }}
              />
            ))}
          </div>
        )}
      </div>

      {/* Strikethrough */}
      <button className="stb-btn" title="删除线" onClick={() => { onStrikethrough(); onClose(); }}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M16 4H9a3 3 0 0 0 0 6h6"/><line x1="4" y1="12" x2="20" y2="12"/><path d="M15 12a3 3 0 0 1 0 6H8"/>
        </svg>
      </button>

      <div className="stb-sep" />

      {/* Section B: Text Processing */}
      <button className="stb-btn stb-translate-btn" title="翻译" onClick={() => { onTranslate(); onClose(); }}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="m5 8 6 6"/><path d="m4 14 6-6 2-3"/><path d="M2 5h12"/><path d="M7 2h1"/><path d="m22 22-5-10-5 10"/><path d="M14 18h6"/>
        </svg>
      </button>

      <button className="stb-btn" title="批注" onClick={() => { onAnnotate(); onClose(); }}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        </svg>
      </button>

      <div className="stb-sep" />

      {/* Section C: AI */}
      <button className="stb-btn stb-ai-btn" title="解释" onClick={() => { onExplain(); onClose(); }}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/>
        </svg>
      </button>

      <button className="stb-btn stb-ai-btn" title="总结" onClick={() => { sendMessage({ type: "ASK_AI", action: "summarize" }); onClose(); }}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="17" y1="10" x2="3" y2="10"/><line x1="21" y1="6" x2="3" y2="6"/><line x1="21" y1="14" x2="3" y2="14"/><line x1="17" y1="18" x2="3" y2="18"/>
        </svg>
      </button>
    </div>
  );
}

// ─── Draggable floating translation popup ──────────────────────────

function FloatTrans({ entry, onClose, onSave, onPin }: {
  entry: TranslationEntry;
  onClose: () => void;
  onSave: () => void;
  onPin: () => void;
}) {
  const floatRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState(readFloatPosition);
  const dragRef = useRef({
    dragging: false,
    startX: 0,
    startY: 0,
    startPosX: 0,
    startPosY: 0,
    currentX: pos.x,
    currentY: pos.y,
  });

  useEffect(() => {
    const onResize = () => {
      const rect = floatRef.current?.getBoundingClientRect();
      setPos((current) => {
        const next = clampFloatPosition(
          current,
          rect ? { width: rect.width, height: rect.height } : undefined
        );
        writeFloatPosition(next);
        return next;
      });
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragRef.current = {
      dragging: true,
      startX: e.clientX,
      startY: e.clientY,
      startPosX: pos.x,
      startPosY: pos.y,
      currentX: pos.x,
      currentY: pos.y,
    };
    const onMouseMove = (ev: MouseEvent) => {
      if (!dragRef.current.dragging) return;
      const rect = floatRef.current?.getBoundingClientRect();
      const next = clampFloatPosition({
        x: dragRef.current.startPosX + (ev.clientX - dragRef.current.startX),
        y: dragRef.current.startPosY + (ev.clientY - dragRef.current.startY),
      }, rect ? { width: rect.width, height: rect.height } : undefined);
      dragRef.current.currentX = next.x;
      dragRef.current.currentY = next.y;
      setPos(next);
    };
    const onMouseUp = () => {
      dragRef.current.dragging = false;
      writeFloatPosition({ x: dragRef.current.currentX, y: dragRef.current.currentY });
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
    };
    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
  }, [pos]);

  return (
    <div
      ref={floatRef}
      className="translation-float"
      style={{ left: pos.x, top: pos.y }}
    >
      <div className="translation-float-header" onMouseDown={onMouseDown}>
        <span className="translation-float-title">{entry.kind === "explanation" ? "解释" : "翻译"}</span>
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          {entry.kind !== "explanation" && (
            <button className="translation-float-pin" onClick={onPin} title="固定到右侧翻译栏">固定</button>
          )}
          <button className="translation-float-close" onClick={onClose}>&times;</button>
        </div>
      </div>
      {entry.loading ? (
        <div className="translation-float-loading">{entry.kind === "explanation" ? "解释中..." : "翻译中..."}</div>
      ) : (
        <MarkdownResult text={entry.result || (entry.kind === "explanation" ? "解释失败" : "翻译失败")} />
      )}
      {entry.kind !== "explanation" && !entry.loading && entry.result && (
        <button className="translation-float-save" onClick={onSave}>
          保存到 PDF
        </button>
      )}
    </div>
  );
}

// ─── Main App ──────────────────────────────────────────────────────

function TranslationPlacement({
  entry,
  onCancel,
  onConfirm,
}: {
  entry: TranslationEntry;
  onCancel: () => void;
  onConfirm: (box: DOMRect) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState(() => {
    const rect = entry.rects?.[entry.rects.length - 1];
    const page = entry.page || rect?.pageNumber || 1;
    const pageEl = document.querySelector(`[data-page-number="${page}"]`) as HTMLElement | null;
    if (!rect || !pageEl) {
      return { x: Math.max(80, window.innerWidth / 2 - 150), y: 160 };
    }
    const pageRect = pageEl.getBoundingClientRect();
    const relative = Math.max(rect.x1 || 0, rect.y1 || 0, rect.x2 || 0, rect.y2 || 0) <= 1;
    return {
      x: pageRect.left + (relative ? rect.x1 * pageRect.width : rect.x1),
      y: pageRect.top + (relative ? rect.y2 * pageRect.height : rect.y2) + 8,
    };
  });
  const dragRef = useRef({ dragging: false, startX: 0, startY: 0, startPosX: 0, startPosY: 0 });

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragRef.current = {
      dragging: true,
      startX: e.clientX,
      startY: e.clientY,
      startPosX: pos.x,
      startPosY: pos.y,
    };
    const onMouseMove = (ev: MouseEvent) => {
      if (!dragRef.current.dragging) return;
      setPos({
        x: dragRef.current.startPosX + (ev.clientX - dragRef.current.startX),
        y: dragRef.current.startPosY + (ev.clientY - dragRef.current.startY),
      });
    };
    const onMouseUp = () => {
      dragRef.current.dragging = false;
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
    };
    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
  }, [pos]);

  return (
    <div ref={ref} className="translation-placement" style={{ left: pos.x, top: pos.y }}>
      <div className="translation-placement-header" onMouseDown={onMouseDown}>
        <span>拖动译文框到写入位置</span>
        <button onClick={onCancel}>×</button>
      </div>
      <div className="translation-placement-body">{entry.result}</div>
      <div className="translation-placement-actions">
        <button onClick={onCancel}>取消</button>
        <button className="primary" onClick={() => ref.current && onConfirm(ref.current.getBoundingClientRect())}>
          写入 PDF
        </button>
      </div>
    </div>
  );
}

function App() {
  const [highlights, setHighlights] = useState<IHighlight[]>([]);
  const [colorMap, setColorMap] = useState<Map<string, string>>(new Map());
  const [typeMap, setTypeMap] = useState<Map<string, AnnotationType>>(new Map());
  const [pendingSelection, setPendingSelection] = useState<{
    position: ScaledPosition;
    content: Content;
  } | null>(null);
  const [toolbarPos, setToolbarPos] = useState<{ x: number; y: number; above: boolean } | null>(null);
  const [showAnnotationInput, setShowAnnotationInput] = useState(false);
  const [annotationText, setAnnotationText] = useState("");
  const [autoTranslate, setAutoTranslate] = useState(false);
  const [floatingAutoTranslate, setFloatingAutoTranslate] = useState(false);
  const [scaleValue, setScaleValue] = useState(1.0);
  const [fitWidth, setFitWidth] = useState(true); // true = fit-width mode, false = manual scale
  const [areaSelectMode, setAreaSelectMode] = useState(false);
  // Translation entries (shared by both modes)
  const [translations, setTranslations] = useState<TranslationEntry[]>([]);
  const [placement, setPlacement] = useState<TranslationEntry | null>(null);
  const [placementMode, setPlacementMode] = useState<"create" | "move">("create");
  const scrollRef = useRef<((highlight: IHighlight) => void) | null>(null);
  const pdfHighlighterRef = useRef<any>(null);
  const autoTranslateRef = useRef(false);
  autoTranslateRef.current = autoTranslate;
  const floatingAutoTranslateRef = useRef(false);
  floatingAutoTranslateRef.current = floatingAutoTranslate;
  const highlightsRef = useRef<IHighlight[]>([]);
  highlightsRef.current = highlights;
  const colorMapRef = useRef<Map<string, string>>(new Map());
  colorMapRef.current = colorMap;
  const typeMapRef = useRef<Map<string, AnnotationType>>(new Map());
  typeMapRef.current = typeMap;

  // Listen for messages from Reflex parent
  useEffect(() => {
    return onMessage((msg) => {
      switch (msg.type) {
        case "LOAD_HIGHLIGHTS": {
          const hls = msg.highlights as any[];
          setHighlights(hls);
          const newColorMap = new Map<string, string>();
          const newTypeMap = new Map<string, AnnotationType>();
          for (const h of hls) {
            if (h._color) newColorMap.set(h.id, h._color);
            if (h._type) newTypeMap.set(h.id, h._type as AnnotationType);
          }
          setColorMap(newColorMap);
          setTypeMap(newTypeMap);
          break;
        }
        case "SCROLL_TO": {
          const hl = highlightsRef.current.find((h) => h.id === msg.id);
          if (hl && scrollRef.current) scrollRef.current(hl);
          break;
        }
        case "ADD_HIGHLIGHT":
          setHighlights((prev) => [...prev, msg.highlight]);
          break;
        case "REMOVE_HIGHLIGHT":
          setHighlights((prev) => prev.filter((h) => h.id !== msg.id));
          setColorMap((prev) => {
            const next = new Map(prev);
            next.delete(msg.id);
            return next;
          });
          setTypeMap((prev) => {
            const next = new Map(prev);
            next.delete(msg.id);
            return next;
          });
          break;
        case "TRANSLATE_RESULT": {
          const { id, translation } = msg;
          setTranslations((prev) =>
            prev.map((t) => t.id === id ? { ...t, loading: false, result: translation } : t)
          );
          break;
        }
        case "EXPLAIN_RESULT": {
          const { id, explanation } = msg;
          setTranslations((prev) =>
            prev.map((t) => t.id === id ? { ...t, loading: false, result: explanation } : t)
          );
          break;
        }
        case "UNPIN_TRANSLATION": {
          const entry: TranslationEntry = {
            id: msg.id,
            text: msg.text,
            result: msg.result,
            loading: false,
            rects: msg.rects,
            page: msg.page,
            pinned: false,
          };
          setTranslations((prev) => {
            const pinned = prev.filter((t) => t.pinned);
            return [entry, ...pinned];
          });
          break;
        }
        case "AUTO_TRANSLATE": {
          setAutoTranslate(msg.enabled);
          if (msg.enabled) {
            setFloatingAutoTranslate(false);
          }
          break;
        }
        case "START_TRANSLATION_PLACEMENT": {
          setPlacementMode("create");
          setPlacement({
            id: msg.id,
            text: msg.text,
            result: msg.translation,
            loading: false,
            rects: msg.rects,
            page: msg.page,
          });
          break;
        }
      }
    });
  }, [placementMode]);

  const undoLast = useCallback(() => {
    const current = highlightsRef.current;
    if (current.length === 0) return;
    const last = current[current.length - 1];
    setHighlights(current.slice(0, -1));
    sendMessage({ type: "HIGHLIGHT_DELETED", id: last.id });
  }, []);

  // Ctrl+Z undo
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "z") {
        e.preventDefault();
        undoLast();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [undoLast]);

  // Toolbar: highlight with specific color
  const toolbarHighlight = useCallback(
    (color: HighlightColor) => {
      if (!pendingSelection) return;
      const { content } = pendingSelection;
      const position = mergeSelectionRects(pendingSelection.position);
      const id = genId();
      const highlight: IHighlight = {
        id,
        position,
        content: { text: content.text },
        comment: { text: "", emoji: "" },
      };
      setHighlights((prev) => [...prev, highlight]);
      setColorMap((prev) => new Map(prev).set(id, color.hex));
      setTypeMap((prev) => new Map(prev).set(id, "highlight"));
      sendMessage({
        type: "HIGHLIGHT_ADDED",
        id,
        highlight,
        color: color.hex,
        annotationType: "highlight",
      });
      setPendingSelection(null);
      setToolbarPos(null);
    },
    [pendingSelection]
  );

  // Toolbar: underline with specific color
  const toolbarUnderline = useCallback(
    (color: HighlightColor) => {
      if (!pendingSelection) return;
      const { content } = pendingSelection;
      const position = mergeSelectionRects(pendingSelection.position);
      const id = genId();
      const highlight: IHighlight = {
        id,
        position,
        content: { text: content.text },
        comment: { text: "", emoji: "" },
      };
      setHighlights((prev) => [...prev, highlight]);
      setColorMap((prev) => new Map(prev).set(id, color.hex));
      setTypeMap((prev) => new Map(prev).set(id, "underline"));
      sendMessage({
        type: "HIGHLIGHT_ADDED",
        id,
        highlight,
        color: color.hex,
        annotationType: "underline",
      });
      setPendingSelection(null);
      setToolbarPos(null);
    },
    [pendingSelection]
  );

  // Toolbar: strikethrough
  const toolbarStrikethrough = useCallback(
    () => {
      if (!pendingSelection) return;
      const { content } = pendingSelection;
      const position = mergeSelectionRects(pendingSelection.position);
      const id = genId();
      const highlight: IHighlight = {
        id,
        position,
        content: { text: content.text },
        comment: { text: "", emoji: "" },
      };
      setHighlights((prev) => [...prev, highlight]);
      setColorMap((prev) => new Map(prev).set(id, "#EF4444"));
      setTypeMap((prev) => new Map(prev).set(id, "strikethrough"));
      sendMessage({
        type: "HIGHLIGHT_ADDED",
        id,
        highlight,
        color: "#EF4444",
        annotationType: "strikethrough",
      });
      setPendingSelection(null);
      setToolbarPos(null);
    },
    [pendingSelection]
  );

  // Copy selected text
  const copyText = useCallback(() => {
    if (!pendingSelection) return;
    const text = pendingSelection.content.text || "";
    navigator.clipboard.writeText(text).catch(() => {});
    setPendingSelection(null);
    setToolbarPos(null);
  }, [pendingSelection]);

  // Translation: send request, add entry
  const requestTranslationForSelection = useCallback((
    position: ScaledPosition,
    content: Content,
    mode: "floating" | "sidebar"
  ) => {
    const id = genId();
    const text = (content.text || "").trim();
    if (!text) return;
    const normalizedPosition = mergeSelectionRects(position);

    const rects = (normalizedPosition.rects || []).map((r: any) => ({
      x1: r.x1, y1: r.y1, x2: r.x2, y2: r.y2, pageNumber: r.pageNumber,
    }));
    const page = normalizedPosition.pageNumber || (rects[0]?.pageNumber) || 0;

    if (mode === "floating") {
      const entry: TranslationEntry = {
        id,
        text,
        loading: true,
        rects,
        page,
      };
      setTranslations((prev) => {
        const pinned = prev.filter((t) => t.pinned);
        return [entry, ...pinned];
      });
    }

    sendMessage({
      type: "TRANSLATE_REQUEST",
      id,
      text,
      rects,
      page,
      mode,
    });
  }, []);

  const requestExplanationForSelection = useCallback((
    position: ScaledPosition,
    content: Content,
    image?: string
  ) => {
    const id = genId();
    const text = (content.text || "").trim();
    const normalizedPosition = mergeSelectionRects(position);
    const rects = (normalizedPosition.rects || []).map((r: any) => ({
      x1: r.x1, y1: r.y1, x2: r.x2, y2: r.y2, pageNumber: r.pageNumber,
    }));
    const page = normalizedPosition.pageNumber || (rects[0]?.pageNumber) || 0;
    const entry: TranslationEntry = {
      id,
      text: text || "框选区域",
      loading: true,
      rects,
      page,
      kind: "explanation",
    };
    setTranslations((prev) => {
      const pinned = prev.filter((t) => t.pinned);
      return [entry, ...pinned];
    });
    sendMessage({
      type: "EXPLAIN_REQUEST",
      id,
      text,
      image,
      rects,
      page,
      mode: "floating",
    });
  }, []);

  const requestTranslation = useCallback(() => {
    if (!pendingSelection) return;
    requestTranslationForSelection(mergeSelectionRects(pendingSelection.position), pendingSelection.content, "floating");
    setFloatingAutoTranslate(true);
    setAutoTranslate(false);
    setPendingSelection(null);
    setToolbarPos(null);
  }, [pendingSelection, requestTranslationForSelection]);

  const requestExplanation = useCallback(() => {
    if (!pendingSelection) return;
    requestExplanationForSelection(
      mergeSelectionRects(pendingSelection.position),
      pendingSelection.content,
      (pendingSelection.content as any).image
    );
    setPendingSelection(null);
    setToolbarPos(null);
  }, [pendingSelection, requestExplanationForSelection]);

  const toggleAreaSelectMode = useCallback(() => {
    setAreaSelectMode((enabled) => !enabled);
    setPendingSelection(null);
    setToolbarPos(null);
  }, []);

  // Save translation to PDF (float mode)
  const saveTranslationToPdf = useCallback((entry: TranslationEntry) => {
    if (!entry.result || !entry.rects || !entry.page) return;
    setPlacementMode("create");
    setPlacement(entry);
  }, []);

  const moveWrittenFreetext = useCallback((highlight: any) => {
    const text = (highlight.comment as any)?.translation || (highlight.comment as any)?.text || "";
    const rects = (highlight.position?.rects || []).map((r: any) => ({
      x1: r.x1, y1: r.y1, x2: r.x2, y2: r.y2, pageNumber: r.pageNumber,
    }));
    const page = highlight.position?.pageNumber || rects[0]?.pageNumber || 0;
    if (!text || !rects.length || !page) return;
    setPlacementMode("move");
    setPlacement({
      id: highlight.id,
      text,
      result: text,
      loading: false,
      rects,
      page,
    });
  }, []);

  const confirmTranslationPlacement = useCallback((entry: TranslationEntry, box: DOMRect) => {
    if (!entry.result) return;
    const centerX = box.left + box.width / 2;
    const centerY = box.top + box.height / 2;
    const pageEl = document
      .elementsFromPoint(centerX, centerY)
      .map((el) => el instanceof HTMLElement ? el.closest("[data-page-number]") : null)
      .find((el): el is HTMLElement => el instanceof HTMLElement);
    if (!pageEl) return;
    const pageRect = pageEl.getBoundingClientRect();
    const page = Number(pageEl.dataset.pageNumber || entry.page || 1);
    const placedRect = {
      x1: Math.max(0, (box.left - pageRect.left) / pageRect.width),
      y1: Math.max(0, (box.top - pageRect.top) / pageRect.height),
      x2: Math.min(1, (box.right - pageRect.left) / pageRect.width),
      y2: Math.min(1, (box.bottom - pageRect.top) / pageRect.height),
      pageNumber: page,
      placement: true,
    };
    if (placementMode === "move") {
      sendMessage({
        type: "MOVE_FREETEXT",
        id: entry.id,
        text: entry.result,
        rects: [placedRect],
        page,
      });
    } else {
      sendMessage({
        type: "SAVE_TRANSLATION",
        id: entry.id,
        text: entry.text,
        translation: entry.result,
        rects: [...(entry.rects || []), placedRect],
        page,
      });
    }
    setTranslations((prev) => prev.filter((t) => t.id !== entry.id));
    setPlacement(null);
  }, [placementMode]);

  // Close translation entry (sidebar mode)
  const closeTranslation = useCallback((id: string) => {
    setTranslations((prev) => prev.filter((t) => t.id !== id));
    setFloatingAutoTranslate(false);
  }, []);

  // Pin translation to right panel
  const pinTranslation = useCallback((entry: TranslationEntry) => {
    if (!entry.result) return;
    sendMessage({
      type: "PIN_TRANSLATION",
      id: entry.id,
      text: entry.text,
      result: entry.result,
      rects: entry.rects || [],
      page: entry.page || 0,
    });
    // Remove from floating list
    setTranslations((prev) => prev.filter((t) => t.id !== entry.id));
    setFloatingAutoTranslate(false);
  }, []);

  // Compute the pdfScaleValue prop: "page-width" for fit mode, numeric string for manual zoom
  // PdfHighlighter's ResizeObserver re-applies this prop on every resize,
  // so we MUST pass the desired scale through the prop, not just set viewer.currentScale.
  const pdfScaleProp = fitWidth ? "page-width" : String(scaleValue);

  const syncHorizontalScrollRange = useCallback(() => {
    const container = document.querySelector("._container_12oj9_1") as HTMLElement | null;
    const viewer = document.querySelector(".pdfViewer") as HTMLElement | null;
    if (!container || !viewer) return;

    if (fitWidth) {
      viewer.style.width = "";
      viewer.style.minWidth = "";
      return;
    }

    const pages = Array.from(viewer.querySelectorAll<HTMLElement>(".page:not(.dummyPage)"));
    const maxPageWidth = Math.ceil(
      Math.max(0, ...pages.map((page) => page.getBoundingClientRect().width))
    );
    if (!maxPageWidth) return;

    const stableWidth = Math.max(container.clientWidth, maxPageWidth);
    const stableWidthPx = `${stableWidth}px`;
    if (viewer.style.width !== stableWidthPx) viewer.style.width = stableWidthPx;
    if (viewer.style.minWidth !== stableWidthPx) viewer.style.minWidth = stableWidthPx;

    if (container.scrollLeft > container.scrollWidth - container.clientWidth) {
      container.scrollLeft = Math.max(0, container.scrollWidth - container.clientWidth);
    }
  }, [fitWidth]);

  useEffect(() => {
    let raf = 0;
    const run = () => {
      if (raf) window.cancelAnimationFrame(raf);
      raf = window.requestAnimationFrame(() => {
        raf = 0;
        syncHorizontalScrollRange();
      });
    };
    const timers = [
      window.setTimeout(run, 0),
      window.setTimeout(run, 120),
      window.setTimeout(run, 450),
      window.setTimeout(run, 1200),
      window.setTimeout(run, 2500),
    ];

    const container = document.querySelector("._container_12oj9_1");
    const viewer = document.querySelector(".pdfViewer");
    const resizeObserver = new ResizeObserver(run);
    if (container) resizeObserver.observe(container);
    if (viewer) resizeObserver.observe(viewer);
    const mutationObserver = new MutationObserver(run);
    mutationObserver.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["class", "style"],
    });
    window.addEventListener("resize", run);

    return () => {
      if (raf) window.cancelAnimationFrame(raf);
      timers.forEach((timer) => window.clearTimeout(timer));
      resizeObserver.disconnect();
      mutationObserver.disconnect();
      window.removeEventListener("resize", run);
    };
  }, [scaleValue, fitWidth, syncHorizontalScrollRange]);

  const zoomIn = useCallback(() => {
    setFitWidth(false);
    setScaleValue((s) => Math.min(s + 0.25, 5));
  }, []);

  const zoomOut = useCallback(() => {
    setFitWidth(false);
    setScaleValue((s) => Math.max(s - 0.25, 0.5));
  }, []);

  const zoomFitWidth = useCallback(() => {
    setFitWidth(true);
    // Read back actual scale after fit-width renders
    requestAnimationFrame(() => {
      const viewer = pdfHighlighterRef.current?.viewer;
      if (viewer?.currentScale) setScaleValue(viewer.currentScale);
    });
  }, []);

  const zoomReset = useCallback(() => {
    setFitWidth(true);
    requestAnimationFrame(() => {
      const viewer = pdfHighlighterRef.current?.viewer;
      if (viewer?.currentScale) setScaleValue(viewer.currentScale);
    });
  }, []);

  // Apply scale after render: PdfHighlighter doesn't handle pdfScaleValue prop changes,
  // so we must set viewer.currentScale directly after the prop change causes re-render.
  // The ResizeObserver will then see our scale and keep it (since pdfScaleProp matches).
  useEffect(() => {
    if (fitWidth) return; // "page-width" is handled by PdfHighlighter's init/ResizeObserver
    requestAnimationFrame(() => {
      const viewer = pdfHighlighterRef.current?.viewer;
      if (viewer) {
        viewer.currentScale = scaleValue;
        requestAnimationFrame(syncHorizontalScrollRange);
      }
    });
  }, [scaleValue, fitWidth, syncHorizontalScrollRange]);

  // Ctrl+Wheel zoom → pdf.js viewport scale
  useEffect(() => {
    const handler = (e: WheelEvent) => {
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        setFitWidth(false);
        setScaleValue((s) => {
          const factor = e.deltaY > 0 ? 0.9 : 1.1;
          return Math.min(Math.max(s * factor, 0.5), 5);
        });
      }
    };
    window.addEventListener("wheel", handler, { passive: false });
    return () => window.removeEventListener("wheel", handler);
  }, []);

  // Drag-to-pan: hold Space or middle mouse button
  useEffect(() => {
    const container = () => document.querySelector("._container_12oj9_1") as HTMLElement | null;
    let isPanning = false;
    let startX = 0, startY = 0, startScrollLeft = 0, startScrollTop = 0;
    let spaceDown = false;

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.code === "Space" && !e.repeat) {
        e.preventDefault();
        spaceDown = true;
        const c = container();
        if (c) c.style.cursor = "grab";
      }
    };
    const onKeyUp = (e: KeyboardEvent) => {
      if (e.code === "Space") {
        spaceDown = false;
        const c = container();
        if (c) c.style.cursor = "";
      }
    };
    const onMouseDown = (e: MouseEvent) => {
      const c = container();
      if (!c) return;
      // Space + left click OR middle mouse
      if ((spaceDown && e.button === 0) || e.button === 1) {
        e.preventDefault();
        isPanning = true;
        startX = e.clientX;
        startY = e.clientY;
        startScrollLeft = c.scrollLeft;
        startScrollTop = c.scrollTop;
        c.style.cursor = "grabbing";
      }
    };
    const onMouseMove = (e: MouseEvent) => {
      if (!isPanning) return;
      const c = container();
      if (!c) return;
      c.scrollLeft = startScrollLeft - (e.clientX - startX);
      c.scrollTop = startScrollTop - (e.clientY - startY);
    };
    const onMouseUp = () => {
      if (isPanning) {
        isPanning = false;
        const c = container();
        if (c) c.style.cursor = spaceDown ? "grab" : "";
      }
    };

    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("keyup", onKeyUp);
    document.addEventListener("mousedown", onMouseDown);
    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("keyup", onKeyUp);
      document.removeEventListener("mousedown", onMouseDown);
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
    };
  }, []);

  // Annotation: show input overlay
  const startAnnotation = useCallback(() => {
    if (!pendingSelection) return;
    setShowAnnotationInput(true);
    setAnnotationText("");
  }, [pendingSelection]);

  // Submit annotation
  const submitAnnotation = useCallback(() => {
    if (!pendingSelection || !annotationText.trim()) return;
    const { content } = pendingSelection;
    const position = mergeSelectionRects(pendingSelection.position);
    const id = genId();
    const highlight: IHighlight = {
      id,
      position,
      content: { text: content.text },
      comment: { text: annotationText.trim(), emoji: "" },
    };
    const annotColor = "#FFD700";
    setHighlights((prev) => [...prev, highlight]);
    setColorMap((prev) => new Map(prev).set(id, annotColor));
    setTypeMap((prev) => new Map(prev).set(id, "highlight"));

    const rects = (position.rects || []).map((r: any) => ({
      x1: r.x1, y1: r.y1, x2: r.x2, y2: r.y2, pageNumber: r.pageNumber,
    }));
    const page = position.pageNumber || (rects[0]?.pageNumber) || 0;

    sendMessage({
      type: "ANNOTATION_ADDED",
      id,
      text: content.text,
      comment: annotationText.trim(),
      rects,
      page,
    });
    setShowAnnotationInput(false);
    setAnnotationText("");
    setPendingSelection(null);
    setToolbarPos(null);
  }, [pendingSelection, annotationText]);

  const deleteHighlight = useCallback((id: string) => {
    setHighlights((prev) => prev.filter((h) => h.id !== id));
    setColorMap((prev) => { const next = new Map(prev); next.delete(id); return next; });
    setTypeMap((prev) => { const next = new Map(prev); next.delete(id); return next; });
    sendMessage({ type: "HIGHLIGHT_DELETED", id });
  }, []);

  // Compute toolbar position from ScaledPosition.boundingRect
  // boundingRect coords are CSS pixels relative to the page element (.page)
  // Need to add page element's viewport offset to get screen coordinates
  const updateToolbarPos = useCallback((boundingRect: { x1?: number; y1?: number; x2?: number; y2?: number; left?: number; top?: number; width?: number; height?: number; pageNumber?: number }) => {
    const pn = boundingRect.pageNumber;
    const pageEl = pn
      ? document.querySelector(`[data-page-number="${pn}"]`)
      : document.querySelector("[data-page-number]");
    if (!pageEl) return;
    const pRect = pageEl.getBoundingClientRect();
    // Support both {x1,y1,x2,y2} and {left,top,width,height} formats
    const bLeft = boundingRect.left ?? boundingRect.x1 ?? 0;
    const bTop = boundingRect.top ?? boundingRect.y1 ?? 0;
    const bRight = (boundingRect.left != null && boundingRect.width != null)
      ? boundingRect.left + boundingRect.width
      : (boundingRect.x2 ?? bLeft);
    const bBottom = (boundingRect.top != null && boundingRect.height != null)
      ? boundingRect.top + boundingRect.height
      : (boundingRect.y2 ?? bTop);
    // Convert to viewport coordinates
    const centerX = pRect.left + (bLeft + bRight) / 2;
    const bottomY = pRect.top + bBottom;
    const topY = pRect.top + bTop;
    const spaceBelow = window.innerHeight - bottomY;
    const above = spaceBelow < 50;
    setToolbarPos({
      x: centerX,
      y: above ? topY - 8 : bottomY + 8,
      above,
    });
  }, []);

  const highlightTransform = useCallback(
    (
      highlight: any,
      _index: number,
      setTip: (
        highlight: any,
        callback: (highlight: any) => React.ReactNode
      ) => void,
      hideTip: () => void,
      _viewportToScaled: (rect: any) => any,
      _screenshot: (position: any) => string,
      isScrolledTo: boolean
    ) => {
      const isTextHighlight = !highlight.content?.image;
      const hlColor = colorMapRef.current.get(highlight.id) || "#FFD700";
      const annType = typeMapRef.current.get(highlight.id) || "highlight";
      const commentText = (highlight.comment as any)?.text || "";
      const freetextText = (highlight.comment as any)?.translation || commentText;
      const isTransparent = hlColor === "transparent";
      const rgb = hexToRgb(hlColor);
      const bgColor = isTransparent ? "transparent" : `rgba(${rgb}, 0.3)`;
      const borderColor = isTransparent ? "transparent" : `rgba(${rgb}, 0.7)`;
      const wrapperClass = annType === "underline" ? "highlight-wrapper underline-wrapper"
        : annType === "strikethrough" ? "highlight-wrapper strikethrough-wrapper"
        : annType === "translation" || annType === "comment" ? "highlight-wrapper freetext-wrapper"
        : "highlight-wrapper";
      const shouldRenderTextHighlight = isTextHighlight;

      return (
        <Popup
          popupContent={
            <div className="highlight-popup">
              {commentText && (
                <div className="popup-comment">{commentText}</div>
              )}
              <button
                className="highlight-delete-btn"
                onClick={() => deleteHighlight(highlight.id)}
              >
                删除
              </button>
              {(annType === "translation" || annType === "comment") && freetextText && (
                <button
                  className="highlight-delete-btn"
                  onClick={() => moveWrittenFreetext(highlight)}
                >
                  移动
                </button>
              )}
            </div>
          }
          onMouseOver={(popupContent) =>
            setTip(highlight, () => popupContent)
          }
          onMouseOut={hideTip}
          key={highlight.id}
        >
          {shouldRenderTextHighlight ? (
            <div
              className={wrapperClass}
              style={{ "--hl-bg": bgColor, "--hl-border": borderColor } as React.CSSProperties}
            >
              <Highlight
                isScrolledTo={isScrolledTo}
                position={highlight.position}
                comment={highlight.comment}
              />
            </div>
          ) : isTextHighlight ? (
            <span className={wrapperClass} />
          ) : (
            <AreaHighlight
              isScrolledTo={isScrolledTo}
              highlight={highlight}
              onChange={() => {}}
            />
          )}
        </Popup>
      );
    },
    [deleteHighlight, moveWrittenFreetext]
  );

  if (!fileUrl) {
    return (
      <div className="error-msg">
        No PDF file specified. Add ?file=/api/pdf/... to the URL.
      </div>
    );
  }

  return (
    <div className={`app ${fitWidth ? "fit-width" : "manual-zoom"} ${areaSelectMode ? "area-select-mode" : ""}`}>
      {/* WPS-style floating selection toolbar */}
      {pendingSelection && toolbarPos && !showAnnotationInput && (
        <SelectionToolbar
          position={toolbarPos}
          onClose={() => { setPendingSelection(null); setToolbarPos(null); }}
          onHighlight={toolbarHighlight}
          onUnderline={toolbarUnderline}
          onStrikethrough={toolbarStrikethrough}
          onTranslate={requestTranslation}
          onAnnotate={startAnnotation}
          onCopy={copyText}
          onExplain={requestExplanation}
        />
      )}

      {/* Floating translation popups (unpinned only) */}
      {translations.filter((t) => !t.pinned).map((entry) => (
        <FloatTrans
          key={entry.id}
          entry={entry}
          onClose={() => closeTranslation(entry.id)}
          onSave={() => saveTranslationToPdf(entry)}
          onPin={() => pinTranslation(entry)}
        />
      ))}

      {placement && (
        <TranslationPlacement
          entry={placement}
          onCancel={() => setPlacement(null)}
          onConfirm={(box) => confirmTranslationPlacement(placement, box)}
        />
      )}

      {/* Annotation input overlay */}
      {showAnnotationInput && (
        <div className="color-picker-overlay" onClick={() => { setShowAnnotationInput(false); setPendingSelection(null); setToolbarPos(null); }}>
          <div className="annotation-input-box" onClick={(e) => e.stopPropagation()}>
            <div className="annotation-input-header">添加批注</div>
            <div className="annotation-selected-text">
              {(pendingSelection?.content.text || "").slice(0, 100)}
              {(pendingSelection?.content.text || "").length > 100 ? "..." : ""}
            </div>
            <textarea
              className="annotation-textarea"
              placeholder="输入批注内容..."
              value={annotationText}
              onChange={(e) => setAnnotationText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  submitAnnotation();
                }
              }}
              autoFocus
            />
            <div className="annotation-input-actions">
              <button className="action-btn" onClick={() => { setShowAnnotationInput(false); setPendingSelection(null); setToolbarPos(null); }}>取消</button>
              <button className="action-btn translate-btn" onClick={submitAnnotation}>保存</button>
            </div>
          </div>
        </div>
      )}

      {/* Undo button */}
      {highlights.length > 0 && (
        <button className="undo-btn" onClick={undoLast} title="撤销 (Ctrl+Z)">
          ↩
        </button>
      )}

      {/* Zoom controls */}
      <div className="zoom-controls">
        <button
          className={`zoom-btn area-select-btn ${areaSelectMode ? "active" : ""}`}
          onClick={toggleAreaSelectMode}
          title={areaSelectMode ? "退出框选" : "框选图、公式或区域"}
        >
          框选
        </button>
        <button className="zoom-btn" onClick={zoomOut} title="缩小">−</button>
        <button className="zoom-btn zoom-label" onClick={fitWidth ? zoomReset : zoomFitWidth} title={fitWidth ? "重置" : "适应宽度"}>
          {fitWidth ? "适应" : `${Math.round(scaleValue * 100)}%`}
        </button>
        <button className="zoom-btn" onClick={zoomIn} title="放大">+</button>
      </div>

      <PdfLoader
        url={PRIMARY_PDF_URL}
        workerSrc="./pdf.worker.mjs"
        beforeLoad={<div className="loading">Loading PDF...</div>}
      >
        {(pdfDocument) => (
          <PdfHighlighter
            ref={pdfHighlighterRef}
            pdfDocument={pdfDocument}
            pdfScaleValue={pdfScaleProp}
            enableAreaSelection={(event) => areaSelectMode || event.altKey}
            onScrollChange={((...args: unknown[]) => {
              const page = Number(args[1] || 0);
              sendPageChanged(page);
            }) as () => void}
            scrollRef={(scrollTo) => {
              scrollRef.current = scrollTo;
            }}
            onSelectionFinished={(
              position: ScaledPosition,
              content: Content,
              hideTipAndSelection: () => void,
              _transformSelection: () => void,
              screenshot?: (position: ScaledPosition) => string
            ) => {
              const text = content.text || "";
              const isAreaSelection = areaSelectMode || !text.trim();
              const image = isAreaSelection
                ? ((content as any).image || (screenshot ? screenshot(position) : ""))
                : "";
              const hasSelection = Boolean(text.trim() || image || position.boundingRect);
              if (hasSelection) {
                if (areaSelectMode) {
                  setAreaSelectMode(false);
                }
                // Always send SELECT for chat reference
                if (text.trim()) {
                  sendMessage({ type: "SELECT", text, position });
                }

                if (text.trim() && autoTranslateRef.current) {
                  requestTranslationForSelection(position, content, "sidebar");
                } else if (text.trim() && floatingAutoTranslateRef.current) {
                  requestTranslationForSelection(position, content, "floating");
                }
                // Always show toolbar for highlight / AI / translate actions
                setPendingSelection({
                  position,
                  content: image ? ({ ...content, image } as Content) : content,
                });
                if (position.boundingRect) {
                  updateToolbarPos(position.boundingRect);
                }
              }
              hideTipAndSelection();
              return null;
            }}
            highlightTransform={highlightTransform}
            highlights={highlights}
          />
        )}
      </PdfLoader>
    </div>
  );
}

export default App;
