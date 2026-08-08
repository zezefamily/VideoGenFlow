export type TTSProvider = "dubbingx" | "volcengine";

const STORAGE_KEY = "videogenflow:tts-provider";

export function getTTSProvider(): TTSProvider {
  if (typeof window === "undefined") return "volcengine";
  return window.localStorage.getItem(STORAGE_KEY) === "dubbingx"
    ? "dubbingx"
    : "volcengine";
}

export function setTTSProvider(provider: TTSProvider) {
  window.localStorage.setItem(STORAGE_KEY, provider);
  window.dispatchEvent(new CustomEvent("tts-provider-changed", { detail: provider }));
}

export const VOLC_DEFAULT_TTS = {
  voiceId: "zh_female_shuangkuaisisi_emo_v2_mars_bigtts",
  emotion: "coldness",
  emotionLabel: "冷淡",
  // 官方体验页“语速 20”表示相对正常语速 +20%，HTTP API 使用倍率。
  speed: 1.2,
  speedLabel: 20,
  pitch: -1,
  volume: 0,
} as const;
