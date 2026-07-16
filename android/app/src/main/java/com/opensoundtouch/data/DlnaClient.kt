package com.opensoundtouch.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

/**
 * Kotlin port of dlna_helper.py: plays a stream URL on the speaker's DLNA/UPnP
 * AVTransport renderer (port 8091). This is how internet radio is played, since
 * the native LOCAL_INTERNET_RADIO source is dead without the Bose cloud.
 *
 * Currently only http streams work (the renderer does not play https directly).
 */
class DlnaClient(private val http: OkHttpClient = defaultClient) {

    companion object {
        val defaultClient: OkHttpClient = OkHttpClient.Builder()
            .connectTimeout(4, TimeUnit.SECONDS)
            .readTimeout(6, TimeUnit.SECONDS)
            .build()

        private fun esc(s: String): String = s
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace("\"", "&quot;")
    }

    private val xml = "text/xml; charset=utf-8".toMediaType()

    suspend fun playUrl(
        deviceIp: String,
        url: String,
        title: String = "Radio",
        artist: String = "Internet Radio",
        album: String = "Favorit",
    ): Boolean = withContext(Dispatchers.IO) {
        val control = "http://$deviceIp:8091/AVTransport/Control"
        val ok1 = soap(control, "SetAVTransportURI", setUriBody(url, title, artist, album))
        val ok2 = soap(control, "Play", playBody())
        ok1 && ok2
    }

    private fun soap(url: String, action: String, body: String): Boolean = try {
        val req = Request.Builder().url(url)
            .addHeader("SOAPACTION", "\"urn:schemas-upnp-org:service:AVTransport:1#$action\"")
            .post(body.toRequestBody(xml))
            .build()
        http.newCall(req).execute().use { it.isSuccessful }
    } catch (e: Exception) {
        false
    }

    private fun setUriBody(url: String, title: String, artist: String, album: String): String {
        val didl = "&lt;DIDL-Lite xmlns=&quot;urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/&quot; " +
            "xmlns:dc=&quot;http://purl.org/dc/elements/1.1/&quot; " +
            "xmlns:upnp=&quot;urn:schemas-upnp-org:metadata-1-0/upnp/&quot;&gt;" +
            "&lt;item id=&quot;0&quot; parentID=&quot;-1&quot; restricted=&quot;1&quot;&gt;" +
            "&lt;dc:title&gt;${esc(title)}&lt;/dc:title&gt;" +
            "&lt;dc:creator&gt;${esc(artist)}&lt;/dc:creator&gt;" +
            "&lt;upnp:album&gt;${esc(album)}&lt;/upnp:album&gt;" +
            "&lt;upnp:class&gt;object.item.audioItem.musicTrack&lt;/upnp:class&gt;" +
            "&lt;res protocolInfo=&quot;http-get:*:audio/mpeg:*&quot;&gt;${esc(url)}&lt;/res&gt;" +
            "&lt;/item&gt;&lt;/DIDL-Lite&gt;"
        return """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:SetAVTransportURI xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
      <InstanceID>0</InstanceID>
      <CurrentURI>${esc(url)}</CurrentURI>
      <CurrentURIMetaData>$didl</CurrentURIMetaData>
    </u:SetAVTransportURI>
  </s:Body>
</s:Envelope>"""
    }

    private fun playBody(): String = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:Play xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
      <InstanceID>0</InstanceID>
      <Speed>1</Speed>
    </u:Play>
  </s:Body>
</s:Envelope>"""
}