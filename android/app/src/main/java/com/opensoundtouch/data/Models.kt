package com.opensoundtouch.data

/** A discovered SoundTouch device. */
data class Device(
    val name: String,
    val type: String,
    val ip: String,
    val mac: String,
    val deviceId: String,
)

data class Volume(
    val actual: Int,
    val target: Int,
    val muted: Boolean,
)

data class NowPlaying(
    val source: String,
    val track: String? = null,
    val artist: String? = null,
    val album: String? = null,
    val location: String? = null,
    val playStatus: String? = null,
)

data class ZoneMember(
    val ip: String,
    val mac: String,
)

data class Zone(
    val masterMac: String,
    val members: List<ZoneMember>,
)

/**
 * A saved multi-room group definition. Only the definition is persisted — a
 * device that is powered on boots standalone; groups are activated on demand
 * from the app (no auto-rejoin).
 */
data class SavedGroup(
    val name: String,
    val masterIp: String,
    val masterMac: String,
    val slaves: List<ZoneMember>,
) {
    val memberIps: List<String> get() = listOf(masterIp) + slaves.map { it.ip }
}

/** An on-device preset (physical button 1..6), stored in preset_proxies.conf. */
data class Preset(
    val slot: Int,
    val url: String,
    val name: String,
)

/** A TuneIn search result (a station). */
data class Station(
    val name: String,
    val guideId: String,
    val image: String? = null,
    val subtitle: String? = null,
)

/**
 * A saved internet-radio favorite (independent of presets).
 * Either a direct stream [url] or a TuneIn [guideId] (resolved to a URL on play).
 */
data class Favorite(
    val name: String,
    val url: String = "",
    val guideId: String = "",
    val image: String = "",
)