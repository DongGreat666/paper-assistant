import type { IHighlight, ScaledPosition } from "react-pdf-highlighter";

export type AnnotationType = "highlight" | "underline" | "strikethrough" | "translation" | "comment";
export type TranslateDisplayMode = "float" | "sidebar";

export interface TranslationEntry {
  id: string;
  text: string;
  result?: string;
  loading: boolean;
  rects?: { x1: number; y1: number; x2: number; y2: number; pageNumber: number; placement?: boolean }[];
  page?: number;
  pinned?: boolean;
}

// React → Reflex
export type OutMessage =
  | { source: "pdf-reader"; type: "READER_READY" }
  | {
      source: "pdf-reader";
      type: "SELECT";
      text: string;
      position: ScaledPosition;
    }
  | {
      source: "pdf-reader";
      type: "HIGHLIGHT_ADDED";
      id: string;
      highlight: IHighlight;
      color: string;
      annotationType: AnnotationType;
    }
  | {
      source: "pdf-reader";
      type: "HIGHLIGHT_DELETED";
      id: string;
    }
  | {
      source: "pdf-reader";
      type: "TRANSLATE_REQUEST";
      id: string;
      text: string;
      rects: { x1: number; y1: number; x2: number; y2: number; pageNumber: number; placement?: boolean }[];
      page: number;
      mode: "floating" | "sidebar";
    }
  | {
      source: "pdf-reader";
      type: "SAVE_TRANSLATION";
      id: string;
      text: string;
      translation: string;
      rects: { x1: number; y1: number; x2: number; y2: number; pageNumber: number; placement?: boolean }[];
      page: number;
    }
  | {
      source: "pdf-reader";
      type: "MOVE_FREETEXT";
      id: string;
      text: string;
      rects: { x1: number; y1: number; x2: number; y2: number; pageNumber: number; placement?: boolean }[];
      page: number;
    }
  | {
      source: "pdf-reader";
      type: "ANNOTATION_ADDED";
      id: string;
      text: string;
      comment: string;
      rects: { x1: number; y1: number; x2: number; y2: number; pageNumber: number }[];
      page: number;
    }
  | { source: "pdf-reader"; type: "HIGHLIGHT_CLICKED"; id: string }
  | { source: "pdf-reader"; type: "PAGE_CHANGED"; page: number }
  | { source: "pdf-reader"; type: "UNDO" }
  | { source: "pdf-reader"; type: "ASK_AI"; action: string }
  | {
      source: "pdf-reader";
      type: "PIN_TRANSLATION";
      id: string;
      text: string;
      result: string;
      rects: { x1: number; y1: number; x2: number; y2: number; pageNumber: number }[];
      page: number;
    };

// Reflex → React
export type InMessage =
  | { type: "LOAD_HIGHLIGHTS"; highlights: IHighlight[] }
  | { type: "SCROLL_TO"; id: string }
  | { type: "ADD_HIGHLIGHT"; highlight: IHighlight }
  | { type: "REMOVE_HIGHLIGHT"; id: string }
  | { type: "TRANSLATE_RESULT"; id: string; translation: string }
  | { type: "SET_TRANSLATE_MODE"; mode: TranslateDisplayMode }
  | { type: "UNPIN_TRANSLATION"; id: string; text: string; result: string; rects: any[]; page: number }
  | { type: "START_TRANSLATION_PLACEMENT"; id: string; text: string; translation: string; rects: any[]; page: number }
  | { type: "AUTO_TRANSLATE"; enabled: boolean };

export interface HighlightColor {
  name: string;
  hex: string;
  alpha: number;
}

export const HIGHLIGHT_COLORS: HighlightColor[] = [
  { name: "黄", hex: "#FFD700", alpha: 0.4 },
  { name: "绿", hex: "#90EE90", alpha: 0.4 },
  { name: "蓝", hex: "#87CEFA", alpha: 0.4 },
  { name: "粉", hex: "#FFB6C1", alpha: 0.4 },
  { name: "橙", hex: "#FFA07A", alpha: 0.4 },
  { name: "无色", hex: "transparent", alpha: 0 },
];
