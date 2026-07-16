package com.opensoundtouch.data

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

/**
 * Persists devices once discovered, so they stay selectable across app restarts
 * and even when a speaker is in standby (where discovery can't find it). The
 * user can then select it and power it on from the app.
 */
class DeviceStore(context: Context) {

    private val prefs = context.getSharedPreferences("open_soundtouch_devices", Context.MODE_PRIVATE)

    fun load(): List<Device> {
        val raw = prefs.getString(KEY, null) ?: return emptyList()
        return try {
            val arr = JSONArray(raw)
            (0 until arr.length()).mapNotNull { i ->
                val o = arr.optJSONObject(i) ?: return@mapNotNull null
                Device(
                    name = o.optString("name"),
                    type = o.optString("type"),
                    ip = o.optString("ip"),
                    mac = o.optString("mac"),
                    deviceId = o.optString("deviceId"),
                )
            }
        } catch (e: Exception) {
            emptyList()
        }
    }

    fun save(list: List<Device>) {
        val arr = JSONArray()
        list.forEach { d ->
            arr.put(
                JSONObject()
                    .put("name", d.name)
                    .put("type", d.type)
                    .put("ip", d.ip)
                    .put("mac", d.mac)
                    .put("deviceId", d.deviceId)
            )
        }
        prefs.edit().putString(KEY, arr.toString()).apply()
    }

    companion object {
        private const val KEY = "list"
    }
}
