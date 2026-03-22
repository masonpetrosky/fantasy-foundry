import { useEffect, useRef } from "react";
import type { Dispatch, MutableRefObject, RefObject, SetStateAction } from "react";
import {
  CALC_LINK_QUERY_PARAM,
  encodeCalculatorSettings,
  mergeKnownCalculatorSettings,
  type CalculatorPreset,
} from "../app_state_storage";
import type { CalculatorSettings } from "../dynasty_calculator_config";

interface UseDynastyCalculatorControlsInput {
  settings: CalculatorSettings;
  setSettings: Dispatch<SetStateAction<CalculatorSettings>>;
  presets: Record<string, CalculatorPreset>;
  setPresets: Dispatch<SetStateAction<Record<string, CalculatorPreset>>>;
  presetName: string;
  setPresetName: Dispatch<SetStateAction<string>>;
  setSelectedPresetName: Dispatch<SetStateAction<string>>;
  setPresetStatus: Dispatch<SetStateAction<string>>;
  setStatus: Dispatch<SetStateAction<string>>;
  presetNameInputRef: RefObject<HTMLInputElement | null>;
  quickStartRunRef: MutableRefObject<((mode: string) => void) | null>;
  onRegisterQuickStartRunner?: (runner: ((mode: string) => void) | null) => void;
  onRegisterActionBridge?: (bridge: {
    copyShareLink: () => Promise<void>;
    focusPresetNameInput: () => void;
  } | null) => void;
}

interface UseDynastyCalculatorControlsReturn {
  savePreset: () => void;
  selectPreset: (name: string) => void;
  deletePreset: (name: string) => void;
  copyShareLink: () => Promise<void>;
}

export function useDynastyCalculatorControls({
  settings,
  setSettings,
  presets,
  setPresets,
  presetName,
  setPresetName,
  setSelectedPresetName,
  setPresetStatus,
  setStatus,
  presetNameInputRef,
  quickStartRunRef,
  onRegisterQuickStartRunner,
  onRegisterActionBridge,
}: UseDynastyCalculatorControlsInput): UseDynastyCalculatorControlsReturn {
  const actionBridgeCopyShareLinkRef = useRef<() => Promise<void>>(async () => undefined);
  const actionBridgeFocusPresetNameInputRef = useRef<() => void>(() => undefined);

  function loadPreset(name: string): void {
    const preset = presets[name];
    if (!preset || typeof preset !== "object") {
      setPresetStatus(`Error: Preset '${name}' was not found.`);
      return;
    }
    setSettings(current => mergeKnownCalculatorSettings(current, preset as Record<string, unknown>) as CalculatorSettings);
    setPresetName(name);
    setSelectedPresetName(name);
    setPresetStatus(`Loaded preset '${name}'.`);
  }

  function savePreset(): void {
    const name = String(presetName || "").trim();
    if (!name) {
      setPresetStatus("Error: Enter a preset name before saving.");
      return;
    }
    const existingPreset = presets[name];
    const isUpdate = Boolean(existingPreset && typeof existingPreset === "object");
    setPresets(current => ({ ...current, [name]: settings }));
    setPresetName(name);
    setSelectedPresetName(name);
    setPresetStatus(`${isUpdate ? "Updated" : "Saved new"} preset '${name}'.`);
  }

  function selectPreset(name: string): void {
    const normalizedName = String(name || "").trim();
    setSelectedPresetName(normalizedName);
    if (!normalizedName) {
      setPresetStatus("");
      return;
    }
    loadPreset(normalizedName);
  }

  function deletePreset(name: string): void {
    const normalizedName = String(name || "").trim();
    if (!normalizedName) return;
    if (!window.confirm(`Delete preset '${normalizedName}'?`)) {
      return;
    }
    setPresets(current => {
      const next = { ...current };
      delete next[normalizedName];
      return next;
    });
    setPresetName(current => (current === normalizedName ? "" : current));
    setSelectedPresetName(current => (current === normalizedName ? "" : current));
    setPresetStatus(`Deleted preset '${normalizedName}'.`);
  }

  async function copyShareLink(): Promise<void> {
    const encoded = encodeCalculatorSettings(settings);
    if (!encoded) {
      setStatus("Error: Unable to encode settings for sharing.");
      return;
    }
    const url = new URL(window.location.href);
    url.searchParams.set(CALC_LINK_QUERY_PARAM, encoded);
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(url.toString());
      } else {
        throw new Error("Clipboard API unavailable");
      }
      setStatus("Copied share link to clipboard.");
      window.history.replaceState({}, "", url.toString());
    } catch {
      window.prompt("Copy calculator link:", url.toString());
      setStatus("Share link is ready.");
    }
  }

  function focusPresetNameInput(): void {
    presetNameInputRef.current?.focus();
    presetNameInputRef.current?.select();
  }

  actionBridgeCopyShareLinkRef.current = copyShareLink;
  actionBridgeFocusPresetNameInputRef.current = focusPresetNameInput;

  useEffect(() => {
    if (typeof onRegisterQuickStartRunner !== "function") return undefined;
    onRegisterQuickStartRunner((mode: string) => {
      if (typeof quickStartRunRef.current === "function") {
        quickStartRunRef.current(mode);
      }
    });
    return () => {
      onRegisterQuickStartRunner(null);
    };
  }, [onRegisterQuickStartRunner, quickStartRunRef]);

  useEffect(() => {
    if (typeof onRegisterActionBridge !== "function") return undefined;
    onRegisterActionBridge({
      copyShareLink: () => actionBridgeCopyShareLinkRef.current(),
      focusPresetNameInput: () => actionBridgeFocusPresetNameInputRef.current(),
    });
    return () => {
      onRegisterActionBridge(null);
    };
  }, [onRegisterActionBridge]);

  return {
    savePreset,
    selectPreset,
    deletePreset,
    copyShareLink,
  };
}
