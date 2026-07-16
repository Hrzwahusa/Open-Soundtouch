package com.opensoundtouch.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

/**
 * Kotlin port of the Python `SoundTouchController` (soundtouch_lib.py):
 * talks to the local SoundTouch Web API on port 8090.
 *
 * Notes carried over from the proven Python implementation:
 *  - Volume is SET as the text content of <volume>N</volume> (NOT <targetvolume>).
 *  - setZone must include the master itself as the FIRST <member>.
 *  - Keys are sent as press + release with sender="Gabbo".
 */
class SoundTouchClient(
    private val ip: String,
    private val http: OkHttpClient = defaultClient,
) {
    private val base = "http://$ip:8090"
    private val xml = "application/xml".toMediaType()

    companion object {
        val defaultClient: OkHttpClient = OkHttpClient.Builder()
            .connectTimeout(4, TimeUnit.SECONDS)
            .readTimeout(6, TimeUnit.SECONDS)
            .build()

        /** Last transport-level error (exception or non-2xx), for on-screen diagnostics. */
        @Volatile
        var lastError: String? = null

        // Known device keys (mirrors soundtouch_lib KEYS)
        const val KEY_PLAY_PAUSE = "PLAY_PAUSE"
        const val KEY_STOP = "STOP"
        const val KEY_NEXT = "NEXT_TRACK"
        const val KEY_PREV = "PREV_TRACK"
        const val KEY_POWER = "POWER"
        fun presetKey(n: Int) = "PRESET_$n"

        private fun esc(s: String): String = s
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace("\"", "&quot;")
    }

    // ---- low-level helpers ------------------------------------------------

    private suspend fun get(path: String): String? = withContext(Dispatchers.IO) {
        repeat(4) { attempt ->
            try {
                http.newCall(Request.Builder().url("$base$path").build()).execute().use { r ->
                    if (r.isSuccessful) return@withContext r.body?.string()
                    lastError = "GET $path -> HTTP ${r.code}"
                    return@withContext null
                }
            } catch (e: Exception) {
                lastError = "GET $path -> ${e.javaClass.simpleName}: ${e.message}"
                if (attempt < 3) Thread.sleep(150)
            }
        }
        null
    }

    private suspend fun post(path: String, body: String): Boolean = withContext(Dispatchers.IO) {
        // The on-device proxy (8090->8089, single connection) briefly refuses
        // connections between requests, so retry a few times on failure.
        repeat(4) { attempt ->
            try {
                val req = Request.Builder().url("$base$path")
                    .post(body.toRequestBody(xml)).build()
                http.newCall(req).execute().use { r ->
                    if (r.isSuccessful) return@withContext true
                    lastError = "POST $path -> HTTP ${r.code}"
                    return@withContext false
                }
            } catch (e: Exception) {
                lastError = "POST $path -> ${e.javaClass.simpleName}: ${e.message}"
                if (attempt < 3) Thread.sleep(150)
            }
        }
        false
    }

    // ---- API --------------------------------------------------------------

    suspend fun getInfo(): Device? {
        val body = get("/info") ?: return null
        val deviceId = Regex("deviceID=\"([^\"]*)\"").find(body)?.groupValues?.get(1) ?: ""
        val name = tag(body, "name") ?: "Unknown"
        val type = tag(body, "type") ?: "Unknown"
        val mac = tag(body, "macAddress") ?: deviceId  // networkInfo/macAddress, fallback deviceID
        return Device(name = name, type = type, ip = ip, mac = mac, deviceId = deviceId)
    }

    suspend fun getVolume(): Volume? {
        val body = get("/volume") ?: return null
        val actual = tag(body, "actualvolume")?.toIntOrNull() ?: return null
        val target = tag(body, "targetvolume")?.toIntOrNull() ?: actual
        val muted = tag(body, "muteenabled")?.equals("true", true) ?: false
        return Volume(actual, target, muted)
    }

    /** SET volume: value is the text content of <volume> (the important fix from Python). */
    suspend fun setVolume(v: Int): Boolean {
        val clamped = v.coerceIn(0, 100)
        return post("/volume", "<volume>$clamped</volume>")
    }

    suspend fun sendKey(key: String, sender: String = "Gabbo"): Boolean {
        val press = post("/key", "<key state=\"press\" sender=\"${esc(sender)}\">${esc(key)}</key>")
        kotlinx.coroutines.delay(120) // let the single-connection proxy recycle
        val release = post("/key", "<key state=\"release\" sender=\"${esc(sender)}\">${esc(key)}</key>")
        return press && release
    }

    suspend fun powerToggle() = sendKey(KEY_POWER)
    suspend fun playPause() = sendKey(KEY_PLAY_PAUSE)
    suspend fun selectPreset(n: Int) = sendKey(presetKey(n))

    suspend fun getNowPlaying(): NowPlaying? {
        val body = get("/now_playing") ?: return null
        val source = Regex("source=\"([^\"]*)\"").find(body)?.groupValues?.get(1) ?: ""
        return NowPlaying(
            source = source,
            track = tag(body, "track"),
            artist = tag(body, "artist"),
            album = tag(body, "album"),
            location = Regex("location=\"([^\"]*)\"").find(body)?.groupValues?.get(1),
            playStatus = tag(body, "playStatus"),
        )
    }

    suspend fun getSources(): List<String> {
        val body = get("/sources") ?: return emptyList()
        return Regex("source=\"([^\"]*)\"").findAll(body).map { it.groupValues[1] }.distinct().toList()
    }

    suspend fun setName(name: String): Boolean = post("/name", "<name>${esc(name)}</name>")

    // ---- Multi-room zones -------------------------------------------------

    suspend fun getZone(): Zone? {
        val body = get("/getZone") ?: return null
        val master = Regex("master=\"([^\"]*)\"").find(body)?.groupValues?.get(1) ?: ""
        if (master.isBlank()) return Zone("", emptyList())
        val members = Regex("<member ipaddress=\"([^\"]*)\">([^<]*)</member>")
            .findAll(body).map { ZoneMember(it.groupValues[1], it.groupValues[2]) }.toList()
        return Zone(master, members)
    }

    /** Create a zone. `slaves` are the slave (ip,mac) pairs; the master is added first automatically. */
    suspend fun setZone(masterMac: String, masterIp: String, slaves: List<ZoneMember>): Boolean {
        val all = buildList {
            add(ZoneMember(masterIp, masterMac))
            slaves.filter { it.mac.uppercase() != masterMac.uppercase() }.forEach { add(it) }
        }
        val membersXml = all.joinToString("") {
            "<member ipaddress=\"${it.ip}\">${it.mac}</member>"
        }
        val xmlBody = "<zone master=\"$masterMac\" senderIPAddress=\"$ip\">$membersXml</zone>"
        return post("/setZone", xmlBody)
    }

    suspend fun addZoneSlave(masterMac: String, slave: ZoneMember): Boolean =
        post("/addZoneSlave", "<zone master=\"$masterMac\"><member ipaddress=\"${slave.ip}\">${slave.mac}</member></zone>")

    suspend fun removeZoneSlave(masterMac: String, slaveMac: String): Boolean =
        post("/removeZoneSlave", "<zone master=\"$masterMac\"><member>$slaveMac</member></zone>")

    // ---- helpers ----------------------------------------------------------

    private fun tag(xml: String, name: String): String? =
        Regex("<$name>([^<]*)</$name>").find(xml)?.groupValues?.get(1)?.trim()
}