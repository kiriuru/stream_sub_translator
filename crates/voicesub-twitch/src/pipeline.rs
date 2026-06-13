use crate::emotes::EmoteRegistry;
use crate::lang::{language_allowed, resolve_message_language};
use crate::replacements::resolve_spoken_nick;
use crate::settings::TwitchTtsSettings;
use crate::source_text_replacement::{
    apply_builtin_profanity, profanity_settings_for_twitch, SourceTextReplacementSettings,
};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ProcessedChatMessage {
    pub clean_text: String,
    pub spoken_nick: String,
    pub speak_text: String,
    pub language: String,
    pub speakable: bool,
    pub skip_reason: Option<&'static str>,
}

pub fn process_chat_message(
    settings: &TwitchTtsSettings,
    _source_replacement: &SourceTextReplacementSettings,
    emotes: &EmoteRegistry,
    login: &str,
    display_name: &str,
    raw_text: &str,
    irc_emotes_tag: Option<&str>,
) -> ProcessedChatMessage {
    if let Some(reason) = crate::filter::filter_skip_reason(settings, login, raw_text) {
        return empty_result(settings, login, display_name, raw_text, false, Some(reason));
    }

    let mut clean_text = if settings.strip_emotes {
        emotes.clean_message_text(
            raw_text,
            irc_emotes_tag,
            &settings.emote_sources,
            settings.strip_emoji,
        )
    } else if settings.strip_emoji {
        crate::emoji::normalize_whitespace(&crate::emoji::strip_unicode_emoji(raw_text))
    } else {
        raw_text.trim().to_string()
    };

    if settings.strip_links {
        clean_text = crate::links::strip_links_from_text(&clean_text);
        clean_text = crate::emoji::normalize_whitespace(&clean_text);
    }

    clean_text = crate::lang::strip_leading_speaker_label(&clean_text);
    clean_text = crate::emoji::normalize_whitespace(&clean_text);

    clean_text = crate::lang::strip_twitch_mentions(&clean_text);

    clean_text = crate::symbols::strip_configured_symbols(&clean_text, &settings.strip_symbols);

    if settings.strip_links {
        clean_text = crate::links::strip_links_from_text(&clean_text);
        clean_text = crate::emoji::normalize_whitespace(&clean_text);
    }

    clean_text = apply_builtin_profanity(&clean_text, &profanity_settings_for_twitch(settings));

    if !crate::lang::has_meaningful_linguistic_content(&clean_text) {
        return empty_result(
            settings,
            login,
            display_name,
            raw_text,
            false,
            Some("min_chars"),
        );
    }

    if clean_text.chars().count() < settings.min_chars as usize {
        return empty_result(
            settings,
            login,
            display_name,
            raw_text,
            false,
            Some("min_chars"),
        );
    }

    let max = settings.max_chars.max(1) as usize;
    if clean_text.chars().count() > max {
        return empty_result(
            settings,
            login,
            display_name,
            raw_text,
            false,
            Some("max_chars"),
        );
    }

    let spoken_nick = strip_symbols_for_speech(
        &resolve_spoken_nick(settings, login, display_name),
        settings,
    );

    let fallback_lang = settings.language.trim().to_lowercase();
    let language = if settings.detect_language {
        resolve_message_language(&clean_text, settings.lang_min_chars as usize, &fallback_lang)
    } else {
        fallback_lang.clone()
    };

    if settings.detect_language && !language_allowed(&language, &settings.enabled_languages) {
        return ProcessedChatMessage {
            clean_text,
            spoken_nick,
            speak_text: String::new(),
            language,
            speakable: false,
            skip_reason: Some("language_filter"),
        };
    }

    let speak_text = build_speak_text(settings, &spoken_nick, &clean_text);
    ProcessedChatMessage {
        clean_text,
        spoken_nick,
        speak_text,
        language,
        speakable: true,
        skip_reason: None,
    }
}

fn strip_symbols_for_speech(text: &str, settings: &TwitchTtsSettings) -> String {
    crate::symbols::strip_configured_symbols(text, &settings.strip_symbols)
}

fn build_speak_text(settings: &TwitchTtsSettings, spoken_nick: &str, clean_text: &str) -> String {
    if !settings.include_username {
        return clean_text.to_string();
    }
    let pause = crate::settings::pause_separator(settings.pause_style);
    let template = crate::settings::normalize_speak_template(settings.speak_template.trim());
    if template.contains("{nick}") || template.contains("{text}") || template.contains("{pause}") {
        return template
            .replace("{pause}", pause)
            .replace("{nick}", spoken_nick)
            .replace("{text}", clean_text);
    }
    format!("{spoken_nick}{pause}{clean_text}")
}

fn empty_result(
    settings: &TwitchTtsSettings,
    login: &str,
    display_name: &str,
    raw_text: &str,
    speakable: bool,
    skip_reason: Option<&'static str>,
) -> ProcessedChatMessage {
    let spoken_nick = strip_symbols_for_speech(
        &resolve_spoken_nick(settings, login, display_name),
        settings,
    );
    ProcessedChatMessage {
        clean_text: raw_text.trim().to_string(),
        spoken_nick: spoken_nick.clone(),
        speak_text: if speakable {
            build_speak_text(settings, &spoken_nick, raw_text.trim())
        } else {
            String::new()
        },
        language: settings.language.trim().to_lowercase(),
        speakable,
        skip_reason,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::emotes::EmoteRegistry;
    use crate::settings::TwitchTtsSettings;
    use crate::source_text_replacement::{SourceTextReplacementPair, SourceTextReplacementSettings};

    fn no_replacement() -> SourceTextReplacementSettings {
        SourceTextReplacementSettings::default()
    }

    #[test]
    fn builds_period_pause_by_default() {
        let settings = TwitchTtsSettings::default();
        let registry = EmoteRegistry::new();
        let out = process_chat_message(
            &settings,
            &no_replacement(),
            &registry,
            "alice",
            "Alice",
            "hello there",
            None,
        );
        assert!(out.speakable);
        assert_eq!(out.speak_text, "Alice. hello there");
    }

    #[test]
    fn respects_custom_template() {
        let settings = TwitchTtsSettings {
            speak_template: "{nick} says: {text}".into(),
            ..Default::default()
        };
        let registry = EmoteRegistry::new();
        let out = process_chat_message(
            &settings,
            &no_replacement(),
            &registry,
            "bob",
            "Bob",
            "ping",
            None,
        );
        assert_eq!(out.speak_text, "Bob says: ping");
    }

    #[test]
    fn pause_style_controls_default_template_separator() {
        let registry = EmoteRegistry::new();
        let period = TwitchTtsSettings::default();
        let comma = TwitchTtsSettings {
            pause_style: crate::settings::TwitchPauseStyle::Comma,
            ..Default::default()
        };
        let period_out = process_chat_message(
            &period,
            &no_replacement(),
            &registry,
            "bob",
            "Bob",
            "hello",
            None,
        );
        let comma_out = process_chat_message(
            &comma,
            &no_replacement(),
            &registry,
            "bob",
            "Bob",
            "hello",
            None,
        );
        assert_eq!(period_out.speak_text, "Bob. hello");
        assert_eq!(comma_out.speak_text, "Bob, hello");
    }

    #[test]
    fn legacy_template_uses_pause_style_not_hardcoded_punctuation() {
        let settings = TwitchTtsSettings {
            speak_template: "{nick}. {text}".into(),
            pause_style: crate::settings::TwitchPauseStyle::Dash,
            ..Default::default()
        };
        let registry = EmoteRegistry::new();
        let out = process_chat_message(
            &settings,
            &no_replacement(),
            &registry,
            "bob",
            "Bob",
            "hello",
            None,
        );
        assert_eq!(out.speak_text, "Bob — hello");
    }

    #[test]
    fn language_filter_blocks_message() {
        let settings = TwitchTtsSettings {
            enabled_languages: vec!["en".into()],
            language: "en".into(),
            ..Default::default()
        };
        let registry = EmoteRegistry::new();
        let out = process_chat_message(
            &settings,
            &no_replacement(),
            &registry,
            "u",
            "U",
            "привет всем друзья",
            None,
        );
        assert!(!out.speakable);
        assert_eq!(out.skip_reason, Some("language_filter"));
    }

    #[test]
    fn max_chars_blocks_long_message() {
        let settings = TwitchTtsSettings {
            max_chars: 10,
            ..Default::default()
        };
        let registry = EmoteRegistry::new();
        let out = process_chat_message(
            &settings,
            &no_replacement(),
            &registry,
            "u",
            "User",
            "this message is definitely too long",
            None,
        );
        assert!(!out.speakable);
        assert_eq!(out.skip_reason, Some("max_chars"));
    }

    #[test]
    fn hello_is_english_not_und() {
        let settings = TwitchTtsSettings::default();
        let registry = EmoteRegistry::new();
        let out = process_chat_message(
            &settings,
            &no_replacement(),
            &registry,
            "kiriuru",
            "Kiriuru",
            "hello",
            None,
        );
        assert!(out.speakable);
        assert_eq!(out.language, "en");
    }

    #[test]
    fn builtin_profanity_uses_twitch_flag_only() {
        let settings = TwitchTtsSettings {
            include_builtin_profanity: true,
            ..Default::default()
        };
        let profanity = SourceTextReplacementSettings {
            enabled: false,
            include_builtin: true,
            case_insensitive: true,
            whole_words: true,
            pairs: vec![SourceTextReplacementPair {
                source: "hello".into(),
                target: "bye".into(),
            }],
        };
        let registry = EmoteRegistry::new();
        let out = process_chat_message(
            &settings,
            &profanity,
            &registry,
            "u",
            "User",
            "what the fuck",
            None,
        );
        assert_eq!(out.clean_text, "what the ***");
    }

    #[test]
    fn irc_emote_tag_removes_emote_only_message() {
        let settings = TwitchTtsSettings::default();
        let registry = EmoteRegistry::new();
        let out = process_chat_message(
            &settings,
            &no_replacement(),
            &registry,
            "u",
            "User",
            "baleGIGA",
            Some("25:0-7"),
        );
        assert!(!out.speakable);
        assert_eq!(out.skip_reason, Some("min_chars"));
    }

    #[test]
    fn strip_links_removes_urls_from_speech() {
        let settings = TwitchTtsSettings::default();
        let registry = EmoteRegistry::new();
        let out = process_chat_message(
            &settings,
            &no_replacement(),
            &registry,
            "u",
            "User",
            "look https://twitch.tv/foo please",
            None,
        );
        assert!(out.speakable);
        assert_eq!(out.clean_text, "look please");
        assert_eq!(out.speak_text, "User. look please");
    }

    #[test]
    fn strip_links_disabled_keeps_urls() {
        let settings = TwitchTtsSettings {
            strip_links: false,
            ..Default::default()
        };
        let registry = EmoteRegistry::new();
        let out = process_chat_message(
            &settings,
            &no_replacement(),
            &registry,
            "u",
            "User",
            "go https://twitch.tv/foo",
            None,
        );
        assert!(out.speakable);
        assert_eq!(out.clean_text, "go https://twitch.tv/foo");
    }

    #[test]
    fn mention_reply_detects_russian_not_portuguese() {
        let settings = TwitchTtsSettings::default();
        let registry = EmoteRegistry::new();
        let out = process_chat_message(
            &settings,
            &no_replacement(),
            &registry,
            "sasha_12041998",
            "sasha_12041998",
            "@KamakiriMeido Привет",
            None,
        );
        assert!(out.speakable);
        assert_eq!(out.language, "ru");
        assert_eq!(out.clean_text, "Привет");
        assert_eq!(out.spoken_nick, "sasha12041998");
        assert_eq!(out.speak_text, "sasha12041998. Привет");
    }

    #[test]
    fn link_only_speaker_label_is_not_speakable() {
        let settings = TwitchTtsSettings::default();
        let registry = EmoteRegistry::new();
        let out = process_chat_message(
            &settings,
            &no_replacement(),
            &registry,
            "wallenber",
            "Wallenber",
            "Wallenber: https://www.youtube.com/watch?v=zqBnOfSmKQo",
            None,
        );
        assert!(!out.speakable);
        assert_eq!(out.skip_reason, Some("min_chars"));
    }

    #[test]
    fn youtube_playlist_link_line_is_not_speakable() {
        let settings = TwitchTtsSettings::default();
        let registry = EmoteRegistry::new();
        let sample =
            "Wallenber: https://www.youtube.com/watch?v=3VTkBuxU4yk&list=RDMM&index=5";
        let out = process_chat_message(
            &settings,
            &no_replacement(),
            &registry,
            "wallenber",
            "Wallenber",
            sample,
            None,
        );
        assert!(!out.speakable);
        assert_eq!(out.skip_reason, Some("min_chars"));
    }

    #[test]
    fn bare_youtube_url_is_not_speakable_even_when_strip_links_disabled() {
        let settings = TwitchTtsSettings {
            strip_links: false,
            ..Default::default()
        };
        let registry = EmoteRegistry::new();
        let sample =
            "https://www.youtube.com/watch?v=3VTkBuxU4yk&list=RDMM&index=5";
        let out = process_chat_message(
            &settings,
            &no_replacement(),
            &registry,
            "wallenber",
            "Wallenber",
            sample,
            None,
        );
        assert!(!out.speakable);
        assert_eq!(out.skip_reason, Some("min_chars"));
    }

    #[test]
    fn broken_url_after_symbol_strip_does_not_detect_dutch() {
        let settings = TwitchTtsSettings {
            strip_links: false,
            ..Default::default()
        };
        let registry = EmoteRegistry::new();
        let sample =
            "https://www.youtube.com/watch?v=3VTkBuxU4yk&list=RDMM&index=5";
        let out = process_chat_message(
            &settings,
            &no_replacement(),
            &registry,
            "wallenber",
            "Wallenber",
            sample,
            None,
        );
        assert!(!out.speakable);
        assert_ne!(out.language, "nl");
    }

    #[test]
    fn strip_symbols_removes_configured_tokens_from_speech() {
        let settings = TwitchTtsSettings {
            strip_symbols: vec!["@".into(), "&".into(), "$".into()],
            ..Default::default()
        };
        let registry = EmoteRegistry::new();
        let out = process_chat_message(
            &settings,
            &no_replacement(),
            &registry,
            "u",
            "User",
            "pay & go @all",
            None,
        );
        assert!(out.speakable);
        assert_eq!(out.clean_text, "pay go");
    }

    #[test]
    fn strip_symbols_removes_underscore_from_message_and_nick() {
        let settings = TwitchTtsSettings {
            strip_symbols: vec!["@".into(), "&".into(), "$".into(), "_".into()],
            ..Default::default()
        };
        let registry = EmoteRegistry::new();
        let out = process_chat_message(
            &settings,
            &no_replacement(),
            &registry,
            "cool_guy",
            "Cool_Guy",
            "see you_later",
            None,
        );
        assert!(out.speakable);
        assert_eq!(out.clean_text, "see youlater");
        assert_eq!(out.spoken_nick, "CoolGuy");
        assert_eq!(out.speak_text, "CoolGuy. see youlater");
    }

    #[test]
    fn empty_strip_symbols_keeps_special_chars() {
        let settings = TwitchTtsSettings {
            strip_symbols: vec![],
            ..Default::default()
        };
        let registry = EmoteRegistry::new();
        let out = process_chat_message(
            &settings,
            &no_replacement(),
            &registry,
            "u",
            "User",
            "a & b",
            None,
        );
        assert!(out.speakable);
        assert_eq!(out.clean_text, "a & b");
    }

    #[test]
    fn preserves_digits_in_russian_chat_line() {
        let settings = TwitchTtsSettings::default();
        let registry = EmoteRegistry::new();
        let sample = "я ограничился 5ю каналами, но по идее можно до 100 сделать";
        let out = process_chat_message(
            &settings,
            &no_replacement(),
            &registry,
            "kiriuru",
            "Kiriuru",
            sample,
            None,
        );
        assert!(out.speakable, "expected speakable: {:?}", out.skip_reason);
        assert!(
            out.clean_text.contains('5') && out.clean_text.contains("100"),
            "digits must remain in clean_text, got: {}",
            out.clean_text
        );
    }

    #[test]
    fn pipeline_strips_emotes_but_preserves_digits() {
        let settings = TwitchTtsSettings::default();
        let registry = EmoteRegistry::new();
        registry.seed_test_emotes(&["kappa"], &["OMEGALUL"]);
        let out = process_chat_message(
            &settings,
            &no_replacement(),
            &registry,
            "u",
            "User",
            "Kappa OMEGALUL нужно 100 и 5ю каналов",
            None,
        );
        assert!(out.speakable);
        assert_eq!(
            out.clean_text,
            "нужно 100 и 5ю каналов"
        );
        assert!(out.speak_text.contains("100"));
        assert!(out.speak_text.contains('5'));
    }
}
