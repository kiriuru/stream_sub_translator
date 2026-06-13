use serde::{Deserialize, Serialize};

pub const TWITCH_MAX_CHANNELS: usize = 5;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct TwitchReplacement {
    pub from: String,
    pub to: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(default)]
pub struct TwitchEmoteSources {
    pub twitch: bool,
    pub bttv: bool,
    pub seventv: bool,
}

impl Default for TwitchEmoteSources {
    fn default() -> Self {
        Self {
            twitch: true,
            bttv: true,
            seventv: true,
        }
    }
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TwitchPauseStyle {
    Comma,
    #[default]
    Period,
    Dash,
    Ellipsis,
}

pub fn pause_separator(style: TwitchPauseStyle) -> &'static str {
    match style {
        TwitchPauseStyle::Comma => ", ",
        TwitchPauseStyle::Period => ". ",
        TwitchPauseStyle::Dash => " — ",
        TwitchPauseStyle::Ellipsis => "… ",
    }
}

/// Map legacy hard-coded templates to `{nick}{pause}{text}` so pause style stays authoritative.
pub fn normalize_speak_template(template: &str) -> String {
    match template.trim() {
        "{nick}. {text}" | "{nick}, {text}" | "{nick} — {text}" | "{nick} - {text}"
        | "{nick}… {text}" | "{nick}... {text}" => "{nick}{pause}{text}".to_string(),
        other => other.to_string(),
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct TwitchTtsSettings {
    #[serde(default)]
    pub enabled: bool,
    /// Legacy single-channel field; kept in sync with the first entry in [`Self::channels`].
    #[serde(default)]
    pub channel: String,
    /// Up to [`TWITCH_MAX_CHANNELS`] channel logins (without `#`).
    #[serde(default)]
    pub channels: Vec<String>,
    #[serde(default)]
    pub nick: String,
    #[serde(default)]
    pub oauth_token: String,
    /// Twitch Developer Console Client ID for implicit OAuth (localhost redirect).
    #[serde(default)]
    pub oauth_client_id: String,
    #[serde(default = "default_speak_chat")]
    pub speak_chat: bool,
    #[serde(default = "default_include_username")]
    pub include_username: bool,
    /// Fallback TTS language when auto-detect is off or inconclusive.
    #[serde(default = "default_language")]
    pub language: String,
    #[serde(default = "default_min_chars")]
    pub min_chars: u32,
    #[serde(default = "default_max_chars")]
    pub max_chars: u32,
    #[serde(default = "default_block_commands")]
    pub block_commands: bool,
    #[serde(default)]
    pub ignore_users: Vec<String>,
    /// Symbol tokens removed from spoken chat text (`@`, `&`, `$`, …). Empty = read all symbols.
    #[serde(default = "default_strip_symbols")]
    pub strip_symbols: Vec<String>,
    /// Remove Twitch / BTTV / 7TV emote codes from message text.
    #[serde(default = "default_true")]
    pub strip_emotes: bool,
    /// Remove Unicode emoji from message text.
    #[serde(default = "default_true")]
    pub strip_emoji: bool,
    /// Remove URL-like tokens so TTS does not read hyperlinks aloud.
    #[serde(default = "default_true")]
    pub strip_links: bool,
    #[serde(default)]
    pub emote_sources: TwitchEmoteSources,
    /// Detect message language (Unicode heuristics + Lingua + whatlang fallback) for TTS voice selection and filtering.
    #[serde(default = "default_true")]
    pub detect_language: bool,
    /// Minimum cleaned message length for language detection (chars).
    #[serde(default = "default_lang_min_chars")]
    pub lang_min_chars: u32,
    /// Allowed ISO 639-1 codes (`ru`, `en`, `ja`, …). Empty = allow all.
    #[serde(default)]
    pub enabled_languages: Vec<String>,
    #[serde(default)]
    pub nick_replacements: Vec<TwitchReplacement>,
    /// Builtin profanity list for Twitch chat (independent from main-app ASR replacement).
    #[serde(default = "default_true")]
    pub include_builtin_profanity: bool,
    #[serde(default)]
    pub pause_style: TwitchPauseStyle,
    /// TTS template when `include_username` is true. Placeholders: `{nick}`, `{text}`, `{pause}`.
    #[serde(default = "default_speak_template")]
    pub speak_template: String,
    /// WASAPI / cpal output label for Twitch chat TTS (empty = system default).
    #[serde(default)]
    pub audio_output_device_id: String,
    #[serde(default)]
    pub audio_output_device_label: String,
    /// Override root `speech_rate` when set (> 0).
    #[serde(default)]
    pub speech_rate: f32,
    /// Override root `speech_volume` when >= 0; `-1` = inherit module default.
    #[serde(default = "default_inherit_volume")]
    pub speech_volume: f32,
    /// Twitch chat queue cap; 0 = use module default (6).
    #[serde(default)]
    pub max_queue_items: u32,
}

fn default_speak_chat() -> bool {
    true
}

fn default_include_username() -> bool {
    true
}

fn default_language() -> String {
    "en".to_string()
}

fn default_min_chars() -> u32 {
    2
}

fn default_max_chars() -> u32 {
    200
}

fn default_block_commands() -> bool {
    true
}

fn default_strip_symbols() -> Vec<String> {
    vec!["@".into(), "&".into(), "$".into(), "_".into()]
}

fn default_true() -> bool {
    true
}

fn default_lang_min_chars() -> u32 {
    2
}

fn default_speak_template() -> String {
    "{nick}{pause}{text}".to_string()
}

fn default_inherit_volume() -> f32 {
    -1.0
}

impl Default for TwitchTtsSettings {
    fn default() -> Self {
        Self {
            enabled: false,
            channel: String::new(),
            channels: Vec::new(),
            nick: String::new(),
            oauth_token: String::new(),
            oauth_client_id: String::new(),
            speak_chat: default_speak_chat(),
            include_username: default_include_username(),
            language: default_language(),
            min_chars: default_min_chars(),
            max_chars: default_max_chars(),
            block_commands: default_block_commands(),
            ignore_users: Vec::new(),
            strip_symbols: default_strip_symbols(),
            strip_emotes: true,
            strip_emoji: true,
            strip_links: true,
            emote_sources: TwitchEmoteSources::default(),
            detect_language: true,
            lang_min_chars: default_lang_min_chars(),
            enabled_languages: Vec::new(),
            nick_replacements: Vec::new(),
            include_builtin_profanity: true,
            pause_style: TwitchPauseStyle::default(),
            speak_template: default_speak_template(),
            audio_output_device_id: String::new(),
            audio_output_device_label: String::new(),
            speech_rate: 0.0,
            speech_volume: -1.0,
            max_queue_items: 0,
        }
    }
}

impl TwitchTtsSettings {
    pub fn effective_speech_rate(&self, root: f32) -> f32 {
        if self.speech_rate > 0.0 {
            self.speech_rate
        } else {
            root
        }
    }

    pub fn effective_speech_volume(&self, root: f32) -> f32 {
        if self.speech_volume >= 0.0 {
            self.speech_volume
        } else {
            root
        }
    }

    pub fn effective_max_queue_items(&self) -> u32 {
        if self.max_queue_items > 0 {
            self.max_queue_items
        } else {
            6
        }
    }

    pub fn resolved_channel_logins(&self) -> Vec<String> {
        let mut out = Vec::new();
        for raw in &self.channels {
            let login = normalize_channel_login(raw);
            if login.is_empty() || out.contains(&login) {
                continue;
            }
            out.push(login);
            if out.len() >= TWITCH_MAX_CHANNELS {
                break;
            }
        }
        if out.is_empty() {
            let legacy = normalize_channel_login(&self.channel);
            if !legacy.is_empty() {
                out.push(legacy);
            }
        }
        out
    }

    pub fn normalized_channels(&self) -> Vec<String> {
        self.resolved_channel_logins()
            .into_iter()
            .map(|login| format!("#{login}"))
            .collect()
    }

    pub fn normalized_channels_label(&self) -> String {
        self.normalized_channels().join(", ")
    }

    pub fn normalized_channel(&self) -> String {
        self.normalized_channels()
            .into_iter()
            .next()
            .unwrap_or_default()
    }

    pub fn channel_login(&self) -> String {
        self.resolved_channel_logins()
            .into_iter()
            .next()
            .unwrap_or_default()
    }

    pub fn channel_logins(&self) -> Vec<String> {
        self.resolved_channel_logins()
    }

    pub fn resolve_client_id(&self) -> String {
        let from_settings = self.oauth_client_id.trim();
        if !from_settings.is_empty() {
            return from_settings.to_string();
        }
        crate::emotes::DEFAULT_TWITCH_CLIENT_ID.to_string()
    }

    pub fn validate_for_connect(&self) -> Result<(), String> {
        let logins = self.resolved_channel_logins();
        if logins.is_empty() {
            return Err("at least one channel is required".into());
        }
        if logins.len() > TWITCH_MAX_CHANNELS {
            return Err(format!(
                "at most {TWITCH_MAX_CHANNELS} channels are allowed"
            ));
        }
        if self.nick.trim().is_empty() {
            return Err("nick is required".into());
        }
        if self.oauth_token.trim().is_empty() {
            return Err(
                "oauth token is required — use Twitch CLI (chat:read) or Device Code Flow; see TTS Twitch tab help"
                    .into(),
            );
        }
        Ok(())
    }
}

fn normalize_channel_login(raw: &str) -> String {
    raw.trim().trim_start_matches('#').to_lowercase()
}

#[cfg(test)]
mod speak_template_tests {
    use super::*;

    #[test]
    fn resolves_channels_from_list_and_legacy_field() {
        let mut settings = TwitchTtsSettings::default();
        settings.channel = "LegacyChan".into();
        assert_eq!(
            settings.resolved_channel_logins(),
            vec!["legacychan".to_string()]
        );

        settings.channels = vec![
            "#Alpha".into(),
            "beta".into(),
            "ALPHA".into(),
            "  ".into(),
        ];
        assert_eq!(
            settings.resolved_channel_logins(),
            vec!["alpha".to_string(), "beta".to_string()]
        );
    }

    #[test]
    fn caps_channel_list_at_five() {
        let mut settings = TwitchTtsSettings::default();
        settings.channels = (1..=7)
            .map(|index| format!("chan{index}"))
            .collect();
        assert_eq!(settings.resolved_channel_logins().len(), TWITCH_MAX_CHANNELS);
    }

    #[test]
    fn normalized_channels_label_joins_hash_prefixed_names() {
        let mut settings = TwitchTtsSettings::default();
        settings.channels = vec!["foo".into(), "bar".into()];
        assert_eq!(
            settings.normalized_channels_label(),
            "#foo, #bar"
        );
    }

    #[test]
    fn pause_separator_maps_styles() {
        assert_eq!(pause_separator(TwitchPauseStyle::Period), ". ");
        assert_eq!(pause_separator(TwitchPauseStyle::Comma), ", ");
    }

    #[test]
    fn normalize_legacy_templates_to_pause_token() {
        assert_eq!(
            normalize_speak_template("{nick}. {text}"),
            "{nick}{pause}{text}"
        );
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct TwitchChatMessage {
    pub id: String,
    pub user: String,
    pub display_name: String,
    pub text: String,
    pub speak_text: String,
    /// Message body after emote/emoji cleanup (before nick prefix).
    #[serde(default)]
    pub clean_text: String,
    /// Nick string sent to TTS (after replacements).
    #[serde(default)]
    pub spoken_nick: String,
    pub channel: String,
    pub language: String,
    pub is_mod: bool,
    pub is_subscriber: bool,
    /// `true` when message passed TTS filters in the IRC layer.
    #[serde(default)]
    pub speakable: bool,
}
