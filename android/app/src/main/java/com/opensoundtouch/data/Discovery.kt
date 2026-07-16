package com.opensoundtouch.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import java.net.Inet4Address
import java.net.NetworkInterface
import java.util.concurrent.TimeUnit

/**
 * Discovers SoundTouch devices by scanning the local /24 for a device that
 * answers GET /info on port 8090. Mirrors SoundTouchDiscovery in soundtouch_lib.py.
 */
object Discovery {

    // Short per-host timeout so a full /24 sweep stays fast.
    private val scanClient: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(1200, TimeUnit.MILLISECONDS)
        .readTimeout(1500, TimeUnit.MILLISECONDS)
        .build()

    /** Returns e.g. "192.168.0" for the active (site-local) IPv4 interface, or null. */
    fun localSubnetBase(): String? {
        try {
            for (iface in NetworkInterface.getNetworkInterfaces()) {
                if (!iface.isUp || iface.isLoopback) continue
                for (addr in iface.inetAddresses) {
                    if (addr is Inet4Address && addr.isSiteLocalAddress) {
                        val parts = addr.hostAddress?.split(".") ?: continue
                        if (parts.size == 4) return "${parts[0]}.${parts[1]}.${parts[2]}"
                    }
                }
            }
        } catch (_: Exception) {
        }
        return null
    }

    /** Full site-local IPv4 address of this device, e.g. "192.168.0.42", or null. */
    fun localIp(): String? {
        try {
            for (iface in NetworkInterface.getNetworkInterfaces()) {
                if (!iface.isUp || iface.isLoopback) continue
                for (addr in iface.inetAddresses) {
                    if (addr is Inet4Address && addr.isSiteLocalAddress) {
                        return addr.hostAddress
                    }
                }
            }
        } catch (_: Exception) {
        }
        return null
    }

    suspend fun scan(): List<Device> = withContext(Dispatchers.IO) {
        val base = localSubnetBase() ?: return@withContext emptyList()
        coroutineScope {
            (1..254).map { host ->
                async {
                    val ip = "$base.$host"
                    SoundTouchClient(ip, scanClient).getInfo()
                }
            }.awaitAll().filterNotNull()
        }.sortedBy { it.name.lowercase() }
    }
}