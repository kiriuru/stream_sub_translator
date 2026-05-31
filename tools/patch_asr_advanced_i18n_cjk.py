"""Patch ASR advanced note/help strings for ja, ko, zh."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCALES_DIR = ROOT / "frontend" / "js" / "i18n" / "locales"

PATCHES: dict[str, dict[str, str]] = {
    "ja": {
        "tools.advanced.latency_preset.note": "推奨: バランスの取れた",
        "tools.advanced.latency_preset.help": "Parakeetのタイミング設定プリセット（超低遅延、バランスの取れた、品質）を一括適用します。「チューニング」タブと同じです。特別な理由がなければ「バランスの取れた」を選んでください。",
        "tools.advanced.streaming_decode.help": "有効にすると、Parakeetは前回のステップ以降の新しい音声部分だけをデコードします。CPU/GPU負荷が軽く、レイテンシも下がります。無効にすると、partial更新のたびにフレーズ全体を最初から再認識するため負荷が高く、長い発話では遅く感じることがあります。",
        "tools.advanced.partial_emit_mode.note": "推奨: word_growth",
        "tools.advanced.partial_emit_mode.help": "画面上でpartial（ライブ）テキストがどう伸びるかを決めます。word_growth は Web Speech のように認識された単語を追加します。char_delta は文字ごとの変化に反応し、チラつきやすくなります。",
        "tools.advanced.partial_min_new_words.note": "推奨: 1",
        "tools.advanced.partial_min_new_words.help": "word_growth モードでは、少なくともこの数の新しい単語が現れるまで partial を更新しません。1 が最も速い「タイプ入力」感です。大きいほど書き換えが減ります。",
        "tools.advanced.field_help.aria": "設定の説明を表示",
        "tools.advanced.vad_mode.note": "推奨: 2",
        "tools.advanced.vad_mode.help": "VAD（音声検出）は、マイク入力をいつ音声とみなすかを決めます。数値が小さいほど反応が速く、背景ノイズにも反応しやすくなります。大きいほどはっきりした音声を待ちます。モード 2 は多くの環境でバランスが良いです。",
        "tools.advanced.partial_emit.note": "推奨: 380-450",
        "tools.advanced.partial_emit.help": "partial 字幕の更新間隔（ミリ秒）の最小値です。小さいほど更新が早く（速く感じる）なりますがチラつくことがあります。大きいほど落ち着いた表示になります。",
        "tools.advanced.min_speech.note": "推奨: 180-220",
        "tools.advanced.min_speech.help": "partial テキストが表示されるまでに必要な発話時間（ミリ秒）です。小さすぎると短いノイズでも反応しやすく、大きいほど確実な発話の開始を待ちます。",
        "tools.advanced.silence_hold.note": "推奨: 160-220",
        "tools.advanced.silence_hold.help": "短い無音のあとも、すぐに終了せずこの時間（ミリ秒）だけ現在のフレーズを開いたままにします。一文の中の短い息継ぎで区切られないのに役立ちます。",
        "tools.advanced.pause_finalize.note": "推奨: 350-450",
        "tools.advanced.pause_finalize.help": "無音がこの時間（ミリ秒）続くと、発話フレーズが完成した字幕ブロックになります。短いほど早く確定し、長いほど長めの間を許容します。",
        "tools.advanced.max_phrase.note": "推奨: 6000",
        "tools.advanced.max_phrase.help": "連続発話がこの長さ（ミリ秒）を超えると、強制的にフレーズを分割します。非常に長い発話が partial のまま伸び続けるのを防ぎます。",
        "tools.advanced.min_delta.note": "推奨: 10",
        "tools.advanced.min_delta.help": "テキストが少なくともこの文字数だけ変わったときだけ partial を更新します。大きいほど細かい行ったり来たりの書き換えが減り、小さいほど微小な変化にも反応します。",
        "tools.advanced.coalescing.note": "推奨: 140-180",
        "tools.advanced.coalescing.help": "この時間窓内の非常に速い partial の書き換えをまとめます。単語の素早い修正を滑らかにしますが、更新は少し遅れることがあります。",
        "tools.advanced.chunk_window.note": "推奨: 0",
        "tools.advanced.chunk_window.help": "バックエンド chunking 用の高度な音声ウィンドウサイズです。通常は 0 のままにし、特定の互換性テスト時だけ変更してください。",
        "tools.advanced.chunk_overlap.note": "推奨: 0",
        "tools.advanced.chunk_overlap.help": "隣接する音声ウィンドウ間のオーバーラップです。通常の使用では 0 のままにしてください。",
        "tools.advanced.ignore_quiet.help": "有効にすると、認識開始前に非常に静かな入力を破棄します。背景ノイズによる誤起動に有効ですが、閾値が厳しすぎると小声を逃すことがあります。",
        "tools.advanced.min_rms.note": "推奨: オフ",
        "tools.advanced.min_rms.help": "音声とみなす最小音量（RMS）です。静かな部屋のノイズで誤起動が続く場合だけ上げてください。高すぎると本当の発話も無視されることがあります。",
        "tools.advanced.min_voiced_ratio.note": "推奨: 0.25",
        "tools.advanced.min_voiced_ratio.help": "音声らしいフレームが占める最小比率です。非音声ノイズの除外に役立ちます。誤起動が多いときは上げ、小声が消えるときは下げてください。",
        "tools.advanced.first_partial.note": "推奨: 180-250",
        "tools.advanced.first_partial.help": "最初の partial が表示されるまでに必要な発話量です。「テキスト開始までの発話」と別値にすれば、最初だけ慎重に、以降は速く更新する調整もできます。",
    },
    "ko": {
        "tools.advanced.latency_preset.note": "권장: 균형 잡힌",
        "tools.advanced.latency_preset.help": "Parakeet 타이밍 프리셋(매우 낮은 대기 시간, 균형 잡힌, 품질)을 한 번에 적용합니다. '튜닝' 탭과 동일합니다. 특별한 이유가 없으면 '균형 잡힌'을 선택하세요.",
        "tools.advanced.streaming_decode.help": "사용하면 Parakeet이 이전 단계 이후 새로 들어온 오디오만 디코딩합니다. CPU/GPU 부하가 줄고 지연도 낮아집니다. 끄면 partial 업데이트마다 전체 구문을 처음부터 다시 인식해 부하가 크고, 긴 발화에서는 더 느리게 느껴질 수 있습니다.",
        "tools.advanced.partial_emit_mode.note": "권장: word_growth",
        "tools.advanced.partial_emit_mode.help": "화면에서 partial(실시간) 텍스트가 어떻게 늘어나는지 정합니다. word_growth는 Web Speech처럼 인식된 단어를 추가합니다. char_delta는 글자 변화마다 반응해 깜빡임이 더 클 수 있습니다.",
        "tools.advanced.partial_min_new_words.note": "권장: 1",
        "tools.advanced.partial_min_new_words.help": "word_growth 모드에서는 최소 이 수만큼 새 단어가 나타난 뒤에 partial이 갱신됩니다. 1이 가장 빠른 '타자' 효과이고, 값이 클수록 잦은 다시 쓰기가 줄어듭니다.",
        "tools.advanced.field_help.aria": "설정 도움말 표시",
        "tools.advanced.vad_mode.note": "권장: 2",
        "tools.advanced.vad_mode.help": "VAD(음성 활동 감지)는 마이크 입력을 언제 음성으로 볼지 결정합니다. 숫자가 작을수록 빠르게 반응하지만 배경 소음에도 민감하고, 클수록 더 분명한 음성을 기다립니다. 모드 2는 대부분 환경에서 균형이 좋습니다.",
        "tools.advanced.partial_emit.note": "권장: 380-450",
        "tools.advanced.partial_emit.help": "partial 자막 갱신 사이의 최소 간격(밀리초)입니다. 값이 작을수록 더 자주 갱신되어 빠르게 느껴지지만 깜빡일 수 있고, 클수록 더 안정적입니다.",
        "tools.advanced.min_speech.note": "권장: 180-220",
        "tools.advanced.min_speech.help": "partial 텍스트가 나타나기 전에 필요한 발화 시간(밀리초)입니다. 너무 작으면 짧은 소음에도 반응하고, 크면 더 확실한 발화 시작을 기다립니다.",
        "tools.advanced.silence_hold.note": "권장: 160-220",
        "tools.advanced.silence_hold.help": "짧은 무음 뒤에도 바로 끝내지 않고 이 시간(밀리초) 동안 현재 구문을 열어 둡니다. 한 문장 안의 짧은 숨 고르기에서 끊기지 않게 도와줍니다.",
        "tools.advanced.pause_finalize.note": "권장: 350-450",
        "tools.advanced.pause_finalize.help": "무음이 이 시간(밀리초) 지속되면 발화 구문이 완료된 자막 블록이 됩니다. 짧을수록 빨리 확정되고, 길수록 더 긴 쉼을 허용합니다.",
        "tools.advanced.max_phrase.note": "권장: 6000",
        "tools.advanced.max_phrase.help": "연속 발화가 이 길이(밀리초)를 넘으면 엔진이 구문을 강제로 나눕니다. 아주 긴 발화가 partial로 끝없이 커지는 것을 막습니다.",
        "tools.advanced.min_delta.note": "권장: 10",
        "tools.advanced.min_delta.help": "텍스트가 최소 이 문자 수만큼 바뀔 때만 partial을 갱신합니다. 값이 클수록 작은 왔다 갔다 수정이 줄고, 작을수록 미세한 변화에도 반응합니다.",
        "tools.advanced.coalescing.note": "권장: 140-180",
        "tools.advanced.coalescing.help": "이 시간 창 안의 매우 빠른 partial 다시 쓰기를 합칩니다. 빠른 단어 수정을 부드럽게 하지만 갱신은 약간 늦어질 수 있습니다.",
        "tools.advanced.chunk_window.note": "권장: 0",
        "tools.advanced.chunk_window.help": "백엔드 chunking용 고급 오디오 창 크기입니다. 특정 호환성 테스트가 아니면 0으로 두세요.",
        "tools.advanced.chunk_overlap.note": "권장: 0",
        "tools.advanced.chunk_overlap.help": "인접 오디오 창 사이의 겹침입니다. 일반 사용에서는 0으로 두세요.",
        "tools.advanced.ignore_quiet.help": "사용하면 인식 시작 전에 매우 조용한 입력을 버립니다. 배경 소음으로 잘못 시작할 때 유용하지만, 너무 강하면 작은 목소리를 놓칠 수 있습니다.",
        "tools.advanced.min_rms.note": "권장: 끔",
        "tools.advanced.min_rms.help": "음성으로 인정하는 최소 음량(RMS)입니다. 조용한 방 소음이 계속 트리거할 때만 올리세요. 너무 높으면 실제 발화도 무시될 수 있습니다.",
        "tools.advanced.min_voiced_ratio.note": "권장: 0.25",
        "tools.advanced.min_voiced_ratio.help": "음성처럼 보이는 프레임의 최소 비율입니다. 비음성 소음을 걸러줍니다. 잘못된 시작이 많으면 올리고, 작은 목소리가 사라지면 내리세요.",
        "tools.advanced.first_partial.note": "권장: 180-250",
        "tools.advanced.first_partial.help": "첫 partial이 나타나기 전에 필요한 발화량입니다. '텍스트 시작 전 발화'와 다르게 두면 처음만 신중하게, 이후는 더 빠르게 갱신하도록 조정할 수 있습니다.",
    },
    "zh": {
        "tools.advanced.latency_preset.note": "推荐: 均衡",
        "tools.advanced.latency_preset.help": "一次性应用 Parakeet 时序预设（超低延迟、均衡、质量）。与“调整”选项卡相同。除非有特别理由追求速度或质量，否则选“均衡”。",
        "tools.advanced.streaming_decode.help": "开启后，Parakeet 只解码自上次步骤以来新增的那部分音频，CPU/GPU 负载更低、延迟更小。关闭后，每次 partial 更新都会从头重新识别整句话，负载更大，长句时可能感觉更慢。",
        "tools.advanced.partial_emit_mode.note": "推荐: word_growth",
        "tools.advanced.partial_emit_mode.help": "控制 partial（实时）文本在屏幕上如何增长。word_growth 像 Web Speech 一样逐词追加；char_delta 对任意字符变化都反应，更容易闪烁。",
        "tools.advanced.partial_min_new_words.note": "推荐: 1",
        "tools.advanced.partial_min_new_words.help": "在 word_growth 模式下，至少出现这么多新词后才更新 partial。1 打字效果最快；数值越大，频繁重写越少。",
        "tools.advanced.field_help.aria": "显示设置说明",
        "tools.advanced.vad_mode.note": "推荐: 2",
        "tools.advanced.vad_mode.help": "VAD（语音活动检测）决定何时把麦克风输入当作语音。数值越小反应越快，但也更容易被背景噪声触发；越大则等待更清晰的语音。模式 2 在大多数环境下较均衡。",
        "tools.advanced.partial_emit.note": "推荐: 380-450",
        "tools.advanced.partial_emit.help": "partial 字幕更新的最小间隔（毫秒）。值越小更新越频繁、感觉越快，但可能闪烁；越大越平稳。",
        "tools.advanced.min_speech.note": "推荐: 180-220",
        "tools.advanced.min_speech.help": "partial 文本出现前需要的说话时长（毫秒）。太小可能对短噪声也反应；更大则等待更明确的语音开始。",
        "tools.advanced.silence_hold.note": "推荐: 160-220",
        "tools.advanced.silence_hold.help": "短暂停顿后，引擎仍在此时间（毫秒）内保持当前短语打开，而不是立刻结束。有助于句内短呼吸不被切断。",
        "tools.advanced.pause_finalize.note": "推荐: 350-450",
        "tools.advanced.pause_finalize.help": "静音持续这么久（毫秒）后，口语短语才会成为完成的字幕块。更短则更快定稿；更长则更能容忍停顿。",
        "tools.advanced.max_phrase.note": "推荐: 6000",
        "tools.advanced.max_phrase.help": "连续说话超过此长度（毫秒）时，引擎会强制分割短语。防止很长的一句话一直以 growing partial 形式延伸。",
        "tools.advanced.min_delta.note": "推荐: 10",
        "tools.advanced.min_delta.help": "只有文本至少变化这么多字符时才更新 partial。值越大，小幅来回改写越少；越小则对微小编辑也更敏感。",
        "tools.advanced.coalescing.note": "推荐: 140-180",
        "tools.advanced.coalescing.help": "在此时间窗口内合并非常快速的 partial 重写。让词级修正更平滑，但更新可能稍晚。",
        "tools.advanced.chunk_window.note": "推荐: 0",
        "tools.advanced.chunk_window.help": "后端分块用的高级音频窗口大小。除非在测试特定兼容性场景，否则保持 0。",
        "tools.advanced.chunk_overlap.note": "推荐: 0",
        "tools.advanced.chunk_overlap.help": "相邻音频窗口之间的重叠。正常使用请保持 0。",
        "tools.advanced.ignore_quiet.help": "开启后，识别开始前会丢弃过静的输入。背景噪声误触发时有帮助，但阈值过高可能漏掉轻声说话。",
        "tools.advanced.min_rms.note": "推荐: 关",
        "tools.advanced.min_rms.help": "视为语音所需的最小响度（RMS）。仅在房间底噪不断触发识别时再提高；过高可能忽略真实语音。",
        "tools.advanced.min_voiced_ratio.note": "推荐: 0.25",
        "tools.advanced.min_voiced_ratio.help": "必须像语音的帧所占的最小比例。帮助过滤非语音噪声；误触发多就提高，轻声丢失就降低。",
        "tools.advanced.first_partial.note": "推荐: 180-250",
        "tools.advanced.first_partial.help": "第一个 partial 出现前需要的说话量。可与“文本出现前的语音”设不同值：首次显示更谨慎，后续更新更快。",
    },
}


def load_locale(locale: str) -> dict[str, str]:
    path = LOCALES_DIR / f"{locale}.js"
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"window\.__SST_I18N_LOCALES\.{locale}\s*=\s*(\{{.*\}});", text, re.S)
    if not match:
        raise SystemExit(f"Could not parse {path}")
    return json.loads(match.group(1))


def write_locale(locale: str, obj: dict[str, str]) -> None:
    path = LOCALES_DIR / f"{locale}.js"
    serialized = json.dumps(obj, ensure_ascii=False, indent=2)
    path.write_text(f"window.__SST_I18N_LOCALES.{locale} = {serialized};\n", encoding="utf-8")


def main() -> None:
    for locale, patch in PATCHES.items():
        obj = load_locale(locale)
        obj.update(patch)
        write_locale(locale, obj)
        print(f"patched {locale}: {len(patch)} keys")


if __name__ == "__main__":
    main()
