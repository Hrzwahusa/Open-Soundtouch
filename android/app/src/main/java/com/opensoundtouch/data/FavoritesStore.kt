package com.opensoundtouch.data

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

/**
 * Local persistence for radio favorites, backed by SharedPreferences (JSON).
 * Mirrors the desktop app's radio_favorites.json — favorites are independent of
 * device presets.
 */
class FavoritesStore(context: Context) {

    private val prefs = context.getSharedPreferences("open_soundtouch_favorites", Context.MODE_PRIVATE)

    fun load(): List<Favorite> {
        val raw = prefs.getString(KEY, null) ?: return emptyList()
        return try {
            val arr = JSONArray(raw)
            (0 until arr.length()).mapNotNull { i ->
                val o = arr.optJSONObject(i) ?: return@mapNotNull null
                Favorite(
                    name = o.optString("name"),
                    url = o.optString("url"),
                    guideId = o.optString("guideId"),
                    image = o.optString("image"),
                )
            }
        } catch (e: Exception) {
            emptyList()
        }
    }

    fun save(list: List<Favorite>) {
        val arr = JSONArray()
        list.forEach {
            arr.put(
                JSONObject()
                    .put("name", it.name)
                    .put("url", it.url)
                    .put("guideId", it.guideId)
                    .put("image", it.image)
            )
        }
        prefs.edit().putString(KEY, arr.toString()).apply()
    }

    companion object {
        private const val KEY = "list"
    }
}