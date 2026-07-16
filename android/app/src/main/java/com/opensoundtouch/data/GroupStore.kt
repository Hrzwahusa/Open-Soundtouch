package com.opensoundtouch.data

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

/**
 * Local persistence for multi-room group definitions (SharedPreferences JSON).
 * Mirrors the desktop app's group_config.json — only the definitions are stored,
 * never an "active" state, so nothing auto-rejoins on boot.
 */
class GroupStore(context: Context) {

    private val prefs = context.getSharedPreferences("open_soundtouch_groups", Context.MODE_PRIVATE)

    fun load(): List<SavedGroup> {
        val raw = prefs.getString(KEY, null) ?: return emptyList()
        return try {
            val arr = JSONArray(raw)
            (0 until arr.length()).mapNotNull { i ->
                val o = arr.optJSONObject(i) ?: return@mapNotNull null
                val slavesArr = o.optJSONArray("slaves") ?: JSONArray()
                val slaves = (0 until slavesArr.length()).mapNotNull { j ->
                    val so = slavesArr.optJSONObject(j) ?: return@mapNotNull null
                    ZoneMember(so.optString("ip"), so.optString("mac"))
                }
                SavedGroup(
                    name = o.optString("name"),
                    masterIp = o.optString("masterIp"),
                    masterMac = o.optString("masterMac"),
                    slaves = slaves,
                )
            }
        } catch (e: Exception) {
            emptyList()
        }
    }

    fun save(list: List<SavedGroup>) {
        val arr = JSONArray()
        list.forEach { g ->
            val slaves = JSONArray()
            g.slaves.forEach { m ->
                slaves.put(JSONObject().put("ip", m.ip).put("mac", m.mac))
            }
            arr.put(
                JSONObject()
                    .put("name", g.name)
                    .put("masterIp", g.masterIp)
                    .put("masterMac", g.masterMac)
                    .put("slaves", slaves)
            )
        }
        prefs.edit().putString(KEY, arr.toString()).apply()
    }

    companion object {
        private const val KEY = "list"
    }
}