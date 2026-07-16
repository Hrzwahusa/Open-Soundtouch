package com.opensoundtouch.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.net.URLEncoder
import java.util.concurrent.TimeUnit

/**
 * Kotlin port of tunein_helper.py (the parts that matter for the DLNA path):
 *  - search()           → TuneIn OPML search (opml.radiotime.com/Search.ashx)
 *  - resolveStreamUrl() → guide id / playback path → direct stream URL (Tune.ashx)
 *
 * Native LOCAL_INTERNET_RADIO / TUNEIN sources are dead without the Bose cloud,
 * so playback always goes through DLNA with the resolved URL.
 */
class TuneInClient(private val http: OkHttpClient = default) {

    companion object {
        private val default: OkHttpClient = OkHttpClient.Builder()
            .connectTimeout(6, TimeUnit.SECONDS)
            .readTimeout(8, TimeUnit.SECONDS)
            .build()

        private const val SEARCH = "http://opml.radiotime.com/Search.ashx"
        private const val TUNE = "http://opml.radiotime.com/Tune.ashx"
    }

    suspend fun search(query: String, max: Int = 30): List<Station> = withContext(Dispatchers.IO) {
        val q = URLEncoder.encode(query.trim(), "UTF-8")
        val body = fetch("$SEARCH?query=$q&render=json") ?: return@withContext emptyList()
        val out = ArrayList<Station>()
        try {
            val arr = JSONObject(body).optJSONArray("body") ?: return@withContext emptyList()
            for (i in 0 until arr.length()) {
                val o = arr.optJSONObject(i) ?: continue
                if (o.optString("type") != "audio") continue
                val guide = o.optString("guide_id")
                val name = o.optString("text")
                if (guide.isBlank() || name.isBlank()) continue
                out.add(
                    Station(
                        name = name,
                        guideId = guide,
                        image = o.optString("image").ifBlank { null },
                        subtitle = o.optString("subtext").ifBlank { null },
                    )
                )
                if (out.size >= max) break
            }
        } catch (_: Exception) {
        }
        out
    }

    /**
     * Resolve a TuneIn guide id (e.g. "s25111"), a Bose playback path
     * ("/v1/playback/station/s25111"), or an already-direct URL to a playable
     * stream URL. Prefers plain http over https (matches the Python helper).
     */
    suspend fun resolveStreamUrl(idOrUrl: String): String? = withContext(Dispatchers.IO) {
        // Already a direct (non-TuneIn) URL → use as-is.
        if (idOrUrl.startsWith("http://") || idOrUrl.startsWith("https://")) {
            if (!idOrUrl.contains("opml.radiotime.com") && !idOrUrl.contains("tunein.com")) {
                return@withContext idOrUrl
            }
        }

        val guide =
            if (idOrUrl.contains("/playback/station/")) idOrUrl.substringAfterLast("/") else idOrUrl
        val body = fetch("$TUNE?id=$guide")?.trim() ?: return@withContext null

        // Plaintext URL list (one per line).
        if (body.startsWith("http://") || body.startsWith("https://")) {
            val lines = body.split("\n").map { it.trim() }.filter { it.isNotEmpty() }
            val chosen = lines.firstOrNull { it.startsWith("http://") }
                ?: lines.firstOrNull { it.startsWith("https://") }
            return@withContext chosen?.substringBefore("?")
        }

        // OPML / XML → first <outline type="audio" URL="...">.
        if (body.startsWith("<?xml") || body.startsWith("<opml")) {
            val audioTag = Regex("<outline\\b[^>]*>").findAll(body)
                .map { it.value }
                .firstOrNull { it.contains("type=\"audio\"") && it.contains("URL=\"") }
            if (audioTag != null) {
                Regex("URL=\"([^\"]+)\"").find(audioTag)?.groupValues?.get(1)
                    ?.let { return@withContext it }
            }
        }

        null
    }

    private fun fetch(url: String): String? = try {
        http.newCall(Request.Builder().url(url).build()).execute().use { r ->
            if (r.isSuccessful) r.body?.string() else null
        }
    } catch (e: Exception) {
        null
    }
}